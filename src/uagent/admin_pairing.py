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
import socket
import stat
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .env_utils import env_get
from .runtime.instance_identity import get_instance_id, get_instance_name
from .utils.paths import get_state_dir

_SECRET_FILE = "admin_pairing_credentials.json"
_HOST_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
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


def _verify_windows_descriptor(descriptor, current_sid) -> None:
    """Validate owner, exactly one own ACE, and protected inheritance."""
    import win32security

    if descriptor.GetSecurityDescriptorOwner() != current_sid:
        raise PermissionError("pairing credentials must be owned by current user")
    control, _ = descriptor.GetSecurityDescriptorControl()
    if not control & win32security.SE_DACL_PROTECTED:
        raise PermissionError("pairing credentials must block inherited Windows ACLs")
    dacl = descriptor.GetSecurityDescriptorDacl()
    if dacl is None or dacl.GetAceCount() != 1:
        raise PermissionError("pairing credentials require a private Windows ACL")
    ace = dacl.GetAce(0)
    if (
        ace[0][0] != win32security.ACCESS_ALLOWED_ACE_TYPE
        or ace[0][1] != 0
        or ace[2] != current_sid
    ):
        raise PermissionError("pairing credentials must only allow current user")


def _windows_private_acl(path: Path) -> None:
    """Validate the current-user-only, inheritance-protected Windows file ACL."""
    if os.name != "nt":
        return
    try:
        import win32api
        import win32con
        import win32security
    except ImportError as exc:
        raise PermissionError("pywin32 is required for secure Windows pairing") from exc

    token = win32security.OpenProcessToken(
        win32api.GetCurrentProcess(), win32con.TOKEN_QUERY
    )
    current_sid = win32security.GetTokenInformation(token, win32security.TokenUser)[0]
    descriptor = win32security.GetFileSecurity(
        str(path),
        win32security.OWNER_SECURITY_INFORMATION
        | win32security.DACL_SECURITY_INFORMATION,
    )
    _verify_windows_descriptor(descriptor, current_sid)


def _secure_create_windows(path: Path, payload: bytes) -> None:
    """Atomically create a new Windows file with an owner-only protected DACL.

    Pass the descriptor to CreateFile itself: never publish the file using
    inherited permissions and then try to repair its ACL afterward.
    """
    try:
        import pywintypes
        import win32api
        import win32con
        import win32file
        import win32security
    except ImportError as exc:
        raise PermissionError("pywin32 is required for secure Windows pairing") from exc

    token = win32security.OpenProcessToken(
        win32api.GetCurrentProcess(), win32con.TOKEN_QUERY
    )
    current_sid = win32security.GetTokenInformation(token, win32security.TokenUser)[0]
    dacl = win32security.ACL()
    dacl.AddAccessAllowedAce(
        win32security.ACL_REVISION, win32con.GENERIC_ALL, current_sid
    )
    descriptor = win32security.SECURITY_DESCRIPTOR()
    descriptor.SetSecurityDescriptorOwner(current_sid, False)
    descriptor.SetSecurityDescriptorDacl(True, dacl, False)
    descriptor.SetSecurityDescriptorControl(
        win32security.SE_DACL_PROTECTED, win32security.SE_DACL_PROTECTED
    )
    attributes = pywintypes.SECURITY_ATTRIBUTES()
    attributes.SECURITY_DESCRIPTOR = descriptor
    attributes.bInheritHandle = False

    # CREATE_NEW prevents accidental overwrite even if another process races
    # to populate the same output path.
    try:
        handle = win32file.CreateFile(
            str(path),
            win32con.GENERIC_WRITE,
            0,
            attributes,
            win32con.CREATE_NEW,
            win32con.FILE_ATTRIBUTE_NORMAL,
            None,
        )
    except pywintypes.error as exc:
        if getattr(exc, "winerror", exc.args[0]) in (80, 183):
            raise FileExistsError("pairing output already exists") from exc
        raise OSError("could not create a private Windows pairing file") from exc
    try:
        # Query using the already-open handle: a second path-based open
        # would conflict with CreateFile's exclusive sharing mode.
        actual_descriptor = win32security.GetSecurityInfo(
            handle,
            win32security.SE_FILE_OBJECT,
            win32security.OWNER_SECURITY_INFORMATION
            | win32security.DACL_SECURITY_INFORMATION,
        )
        _verify_windows_descriptor(actual_descriptor, current_sid)
        _, written = win32file.WriteFile(handle, payload)
        if written != len(payload):
            raise OSError("incomplete write of pairing secrets")
        win32file.FlushFileBuffers(handle)
    except BaseException:
        handle.Close()
        path.unlink(missing_ok=True)
        raise
    else:
        handle.Close()


def _read_private(path: Path) -> dict | None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode) or info.st_size > _MAX_BYTES:
        raise PermissionError("invalid UAG pairing credential file")
    if os.name != "nt" and info.st_mode & 0o077:
        raise PermissionError("UAG pairing credentials are not private")
    _windows_private_acl(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if (
        type(data) is not dict
        or set(data) not in (_KEYS, _KEYS | {"supervisor_bearer"})
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
        or (
            "supervisor_bearer" in data
            and (
                type(data["supervisor_bearer"]) is not str
                or not _TOKEN_RE.fullmatch(data["supervisor_bearer"])
                or data["supervisor_bearer"]
                in (data["manifest_bearer"], data["otlp_bearer"])
            )
        )
    ):
        raise ValueError("invalid saved UAG pairing credentials")
    return data


def _secure_create(path: Path, payload: bytes) -> None:
    """Create a new secret file with private permissions from the first instant."""
    if len(payload) > _MAX_BYTES:
        raise ValueError("pairing file exceeds size limit")
    if path.is_symlink():
        raise PermissionError("will not overwrite a symlink")
    if os.name == "nt":
        _secure_create_windows(path, payload)
        return

    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        stream = os.fdopen(fd, "wb")
        fd = -1
        with stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        if fd >= 0:
            os.close(fd)
        path.unlink(missing_ok=True)
        raise


def get_supervisor_read_token() -> str | None:
    """Read the independent Supervisor token from the same private pairing state."""
    data = load_pairing()
    return data.get("supervisor_bearer") if data is not None else None


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
    *,
    uag_url: str,
    admin_url: str,
    output: Path,
    rotate: bool = False,
    supervisor_url: str | None = None,
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
    if any(
        os.environ.get(key)
        for key in (
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "OTEL_EXPORTER_OTLP_HEADERS",
            "OTEL_EXPORTER_OTLP_TRACES_HEADERS",
        )
    ):
        raise ValueError("unset explicitly configured OTLP exporter options first")

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
    # A single atomic runtime credential file is the source of truth.
    # --rotate must change every active bearer together, including Supervisor.
    had_supervisor = old is not None and "supervisor_bearer" in old
    if had_supervisor and rotate and supervisor_url is None:
        raise ValueError("--supervisor-url is required to rotate Supervisor pairing")
    if supervisor_url is not None:
        supervisor_url = _url(supervisor_url)
        host_id = os.environ.get("UAG_SUPERVISOR_HOST_ID") or socket.gethostname()
        if not _HOST_ID.fullmatch(host_id):
            raise ValueError("invalid Supervisor host ID")
    if supervisor_url is not None or had_supervisor:
        supervisor_token = (
            secrets.token_urlsafe(48)
            if rotate or not had_supervisor
            else old["supervisor_bearer"]
        )
        if supervisor_token in (manifest_token, otlp_token):
            raise ValueError("Supervisor bearer must be independent")
        record["supervisor_bearer"] = supervisor_token

    payload = _encode(record)
    transfer = {
        key: value for key, value in record.items() if key != "supervisor_bearer"
    }
    if supervisor_url is not None:
        transfer["supervisor"] = {
            "host_id": host_id,
            "base_url": supervisor_url,
            "read_bearer": record["supervisor_bearer"],
        }
    transfer_payload = _encode(transfer)
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
            # Create with owner-only permissions before any secret is written.
            pending = folder / (".pair-" + secrets.token_hex(16))
            _secure_create(pending, payload)
        else:
            pending = None
    else:
        pending = None

    transfer_created = False
    try:
        _secure_create(target, transfer_payload)
        transfer_created = True
        if old is None:
            _secure_create(source, payload)
        elif pending is not None:
            os.replace(pending, source)
    except BaseException:
        # Only roll back a transfer file THIS invocation successfully created.
        # A competing CREATE_NEW winner must never be deleted.
        if transfer_created:
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
        "--supervisor-url",
        default=None,
        help="optional remote Supervisor HTTPS URL for automatic Admin registration",
    )
    cmd.add_argument("--workdir", help="UAG workdir containing .env/.env.sec")
    cmd.add_argument(
        "--rotate",
        action="store_true",
        help="explicitly replace existing pairing credentials",
    )
    args = parser.parse_args(arguments)
    try:
        # The standard UAG workdir resolver honours --workdir and
        # UAGENT_WORKDIR, then the current working directory.
        from .runtime.runtime_init import (
            apply_workdir,
            decide_workdir,
            load_dotenv_custom,
        )

        decision = decide_workdir(
            cli_workdir=args.workdir,
            env_workdir=env_get("UAGENT_WORKDIR"),
        )
        apply_workdir(decision)
        # Use normal startup precedence first: .env may select the
        # UAGENT_ENVSEC_KEY_BACKEND used to decrypt .env.sec. The standard
        # loader reports errors as warnings, so validate the ciphertext again
        # afterward and abort export if existing secrets cannot be loaded.
        load_dotenv_custom()
        secured_env = Path.cwd() / ".env.sec"
        if secured_env.is_file():
            from uag_envsec import decrypt_text

            encrypted = secured_env.read_text(encoding="utf-8").strip()
            if encrypted:
                decrypt_text(encrypted)
        path = export_pairing(
            uag_url=args.uag_url,
            admin_url=args.admin_url,
            output=Path(args.output),
            rotate=args.rotate,
            supervisor_url=args.supervisor_url,
        )
    except (OSError, ValueError, PermissionError, json.JSONDecodeError) as exc:
        print(f"Pairing export failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(f"Private pairing file created: {path}")
    print("It contains secrets. Transfer securely and delete after Admin import.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
