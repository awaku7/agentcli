"""Export a reusable, explicitly opted-in UAG-to-Admin pairing file.

Do not use this file as a public configuration export: it contains two bearer secrets.
The private runtime copy is kept under the UAG user-state directory.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import stat
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .runtime.instance_identity import get_instance_id, get_instance_name
from .utils.paths import get_state_dir

_SECRET_FILE = "admin_pairing_credentials.json"
_MAX_BYTES = 16_384
_TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{32,256}\Z")
_KEYS = frozenset(
    {
        "format",
        "version",
        "instance_id",
        "instance_name",
        "uag_base_url",
        "admin_base_url",
        "manifest_bearer",
        "otlp_bearer",
    }
)


def _url(raw: str) -> str:
    """Keep endpoint configuration explicit; HTTP must be loopback-only."""
    if type(raw) is not str or len(raw) > 2048:
        raise ValueError("URL is required and must be no longer than 2048 characters")
    try:
        u = urlsplit(raw)
        host = u.hostname
        _ = u.port
    except ValueError as exc:
        raise ValueError("invalid URL") from exc
    if not host or u.scheme not in ("http", "https") or u.username or u.password:
        raise ValueError("invalid URL scheme, hostname or credentials")
    if u.query or u.fragment or u.path not in ("", "/"):
        raise ValueError("use the service base URL without path/query/fragment")
    if u.scheme == "http":
        import ipaddress

        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = host.lower().rstrip(".") == "localhost"
        if not loopback:
            raise ValueError("remote pairing requires HTTPS")
    return urlunsplit((u.scheme, u.netloc, "", "", ""))


def _private_folder() -> Path:
    folder = get_state_dir()
    if folder.is_symlink():
        raise ValueError("UAG state directory must not be a symlink")
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name != "nt" and folder.stat().st_mode & 0o077:
        raise PermissionError("UAG state directory must not be group/world accessible")
    return folder


def _read_private(path: Path) -> dict | None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode) or info.st_size > _MAX_BYTES:
        raise PermissionError("invalid UAG pairing credential file")
    if os.name != "nt" and info.st_mode & 0o077:
        raise PermissionError("UAG pairing credentials are not private")
    data = json.loads(path.read_text(encoding="utf-8"))
    if (
        type(data) is not dict
        or set(data) != _KEYS
        or data.get("format") != "uag-admin-pairing"
        or type(data.get("version")) is not int
        or data["version"] != 1
        or any(
            type(data.get(k)) is not str
            for k in (
                "instance_id",
                "instance_name",
                "uag_base_url",
                "admin_base_url",
                "manifest_bearer",
                "otlp_bearer",
            )
        )
        or not _TOKEN_RE.fullmatch(data["manifest_bearer"])
        or not _TOKEN_RE.fullmatch(data["otlp_bearer"])
        or data["manifest_bearer"] == data["otlp_bearer"]
    ):
        raise ValueError("invalid saved UAG pairing credentials")
    return data


def _secure_create(path: Path, payload: bytes) -> None:
    """Create-only; do not silently overwrite user-authored secrets."""
    if len(payload) > _MAX_BYTES:
        raise ValueError("pairing file exceeds size limit")
    if path.is_symlink():
        raise PermissionError("will not overwrite a symlink")
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _encode(data: dict) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def load_pairing() -> dict | None:
    """For opt-in runtime integration only; fail closed on unsafe files."""
    return _read_private(get_state_dir() / _SECRET_FILE)


def get_manifest_pairing_token() -> str | None:
    data = load_pairing()
    return data["manifest_bearer"] if data is not None else None


def get_otlp_pairing() -> tuple[str, str] | None:
    data = load_pairing()
    if data is None:
        return None
    return data["admin_base_url"] + "/otlp/v1/traces", data["otlp_bearer"]


def export_pairing(
    *, uag_url: str, admin_url: str, output: Path, rotate: bool = False
) -> Path:
    """Write a secret-bearing transfer file and preserve runtime credentials."""
    uag_url = _url(uag_url)
    admin_url = _url(admin_url)
    folder = _private_folder()
    source = folder / _SECRET_FILE
    old = _read_private(source)
    instance_id = get_instance_id()
    if old is not None and old["instance_id"] != instance_id:
        raise ValueError("existing pairing is bound to a different UAG instance")
    if (
        old is not None
        and not rotate
        and (old["uag_base_url"] != uag_url or old["admin_base_url"] != admin_url)
    ):
        raise ValueError("pairing URLs changed; use --rotate explicitly")

    existing_manifest = os.environ.get("UAGENT_MANAGEMENT_API_TOKEN", "").strip()
    if existing_manifest and not _TOKEN_RE.fullmatch(existing_manifest):
        raise ValueError("existing manifest bearer is invalid")
    if (
        old is not None
        and existing_manifest
        and existing_manifest != old["manifest_bearer"]
    ):
        raise ValueError("manifest token conflicts with existing pairing")
    if rotate:
        if existing_manifest:
            raise ValueError("cannot rotate manifest token while environment fixes it")
        manifest_token = secrets.token_urlsafe(48)
        otlp_token = secrets.token_urlsafe(48)
    else:
        manifest_token = existing_manifest or (
            old["manifest_bearer"] if old is not None else secrets.token_urlsafe(48)
        )
        otlp_token = (
            old["otlp_bearer"] if old is not None else secrets.token_urlsafe(48)
        )

    # Respect explicit exporter configuration, rather than silently overriding it.
    explicit_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    if explicit_endpoint and explicit_endpoint != admin_url + "/otlp/v1/traces":
        raise ValueError("OTLP endpoint environment conflicts with pairing")
    if os.environ.get("OTEL_EXPORTER_OTLP_TRACES_HEADERS"):
        raise ValueError("unset explicit OTLP trace headers before pairing")

    record = {
        "format": "uag-admin-pairing",
        "version": 1,
        "instance_id": instance_id,
        "instance_name": get_instance_name(instance_id),
        "uag_base_url": uag_url,
        "admin_base_url": admin_url,
        "manifest_bearer": manifest_token,
        "otlp_bearer": otlp_token,
    }
    payload = _encode(record)
    target = output.expanduser().absolute()
    if target == source or target.is_symlink():
        raise ValueError("invalid transfer-file path")
    if target.parent.is_symlink():
        raise ValueError("output parent directory must not be a symlink")
    if target.exists():
        raise FileExistsError("output exists; delete previous transfer file first")

    if old != record:
        # Do not replace the active credential set until both output and state
        # serialization succeed. Rotation is only supported via explicit request.
        if old is not None:
            # Atomic replacement of private credentials on the same filesystem.
            with tempfile.NamedTemporaryFile(
                dir=folder, prefix=".pair-", delete=False
            ) as stream:
                pending = Path(stream.name)
                os.chmod(pending, 0o600)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        else:
            pending = None
    else:
        pending = None

    try:
        _secure_create(target, payload)
        if old is None:
            _secure_create(source, payload)
        elif pending is not None:
            os.replace(pending, source)
    except BaseException:
        # Failure to publish runtime state must not leave a usable transfer file.
        target.unlink(missing_ok=True)
        raise
    finally:
        if pending is not None:
            pending.unlink(missing_ok=True)
    return target


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="uag admin")
    sub = parser.add_subparsers(dest="action", required=True)
    cmd = sub.add_parser("export", help="export UAG Admin pairing file")
    cmd.add_argument("--uag-url", default="http://127.0.0.1:8000")
    cmd.add_argument("--admin-url", default="http://127.0.0.1:8088")
    cmd.add_argument("--output", default="uag-admin-link.json")
    cmd.add_argument(
        "--rotate",
        action="store_true",
        help="explicitly replace existing pairing credentials",
    )
    args = parser.parse_args(arguments)
    try:
        path = export_pairing(
            uag_url=args.uag_url,
            admin_url=args.admin_url,
            output=Path(args.output),
            rotate=args.rotate,
        )
    except (OSError, ValueError, PermissionError, json.JSONDecodeError) as exc:
        print(f"Pairing export failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(f"Private pairing file created: {path}")
    print("It contains secrets. Transfer securely and delete after Admin import.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
