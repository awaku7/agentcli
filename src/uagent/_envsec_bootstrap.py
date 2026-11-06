"""Recover a missing envsec module after the standalone-package migration."""

from __future__ import annotations

import importlib
import json
import os
import re
import subprocess
import stat
import sys
from pathlib import Path

_REPAIR_SPEC = "uag-envsec>=0.1.1"
_REPAIR_HINT = "python -m pip install --force-reinstall --no-deps 'uag-envsec>=0.1.1'"
_POLICY_LINE = re.compile(r"^\s*(?:export\s+)?UAGENT_AUTO_INSTALL\s*=\s*(.*)$")



def _scheduled_payload_workdir(payload_id: str, payload_dir: str | None) -> str:
    """Inspect an OS schedule's project without consuming its one-shot payload.

    The full scheduler cannot be imported here: its package initialization
    imports runtime modules which themselves require uag_envsec.
    """
    if not re.fullmatch(r"[0-9a-f]{32}", payload_id):
        raise ValueError("invalid scheduled payload ID")
    if payload_dir:
        directory = Path(payload_dir).absolute()
    else:
        from .utils.paths import get_state_dir

        directory = get_state_dir() / "scheduled_payloads"
    if directory.name != "scheduled_payloads":
        raise ValueError("invalid scheduled payload directory")
    directory = directory.resolve(strict=True)
    if not directory.is_dir() or directory.name != "scheduled_payloads":
        raise ValueError("invalid scheduled payload directory")
    if os.name != "nt" and stat.S_IMODE(directory.stat().st_mode) & 0o077:
        raise ValueError("scheduled payload directory permissions are too broad")

    source = directory / f"{payload_id}.json"
    if not hasattr(os, "O_NOFOLLOW") and source.is_symlink():
        raise ValueError("scheduled payload must not be a symlink")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(source, flags)
    with os.fdopen(fd, "rb") as stream:
        raw = stream.read(256_001)
    if len(raw) > 256_000:
        raise ValueError("scheduled payload exceeds size limit")
    document = json.loads(raw.decode("utf-8"))
    if not isinstance(document, dict) or document.get("version") != 1:
        raise ValueError("unsupported scheduled payload")
    workdir = document.get("workdir", "")
    if not isinstance(workdir, str) or len(workdir) > 4096:
        raise ValueError("invalid scheduled working directory")
    return workdir

def _startup_workdir() -> Path:
    """Resolve the selected workdir without importing the full runtime."""
    workdir = None
    args = sys.argv[1:]
    payload_id = None
    payload_dir = None
    for index, arg in enumerate(args):
        if arg == "--":
            break
        if arg in ("--workdir", "-C") and index + 1 < len(args):
            workdir = args[index + 1]
        elif arg.startswith("--workdir="):
            workdir = arg.partition("=")[2]
        elif arg.startswith("-C") and len(arg) > 2:
            workdir = arg[2:]
        elif arg == "--scheduled-payload-id":
            payload_id = args[index + 1] if index + 1 < len(args) else ""
        elif arg.startswith("--scheduled-payload-id="):
            payload_id = arg.partition("=")[2]
        elif arg == "--scheduled-payload-dir":
            payload_dir = args[index + 1] if index + 1 < len(args) else ""
        elif arg.startswith("--scheduled-payload-dir="):
            payload_dir = arg.partition("=")[2]
    if payload_id is not None:
        workdir = _scheduled_payload_workdir(payload_id, payload_dir) or workdir
    if not workdir:
        workdir = os.environ.get("UAGENT_WORKDIR") or os.getcwd()
    from .env_utils import strip_outer_quotes

    return Path(strip_outer_quotes(workdir)).expanduser()


def _project_auto_install_policy() -> str | None:
    """Read the unencrypted policy before early package-level repair.

    Pre-existing process values have priority over the project's .env. We
    cannot import the normal runtime configuration loader here because it
    imports uag_envsec, which may be missing.
    """
    if "UAGENT_AUTO_INSTALL" in os.environ:
        return None
    try:
        env_file = _startup_workdir() / ".env"
    except (OSError, ValueError, UnicodeError):
        # If the scheduled job cannot be inspected, do not authorize pip.
        return "off"
    try:
        with env_file.open(encoding="utf-8-sig") as handle:
            lines = handle.readlines()
    except FileNotFoundError:
        return None
    except OSError:
        # An unreadable policy must never implicitly authorize a pip call.
        return "off"

    # If available, use the same parser as the normal startup loader.
    try:
        from dotenv import dotenv_values
    except ImportError:
        # python-dotenv is optional during early startup. Basic assignments
        # remain supported; complex values fail closed rather than assuming allow.
        policy = None
        for line in lines:
            match = _POLICY_LINE.match(line)
            if match:
                raw = match.group(1).strip()
                if raw[:1] in ('"', "'"):
                    policy = raw[1:].split(raw[0], 1)[0]
                else:
                    policy = raw.split(" #", 1)[0].strip()
    else:
        try:
            policy = dotenv_values(env_file).get("UAGENT_AUTO_INSTALL")
        except (OSError, ValueError):
            return "off"
    if policy is None:
        return None
    normalized = str(policy).strip().lower()
    return normalized if normalized in {"allow", "prompt", "off"} else "off"


def ensure_envsec_available() -> None:
    """Repair only the missing top-level module, respecting auto-install policy.

    Older UAG wheels included uag_envsec. During an upgrade, pip may install
    the standalone distribution and delete its files while uninstalling old UAG.
    Its metadata remains, so reinstalling UAG alone does not restore the module.
    """
    try:
        importlib.import_module("uag_envsec")
        return
    except ModuleNotFoundError as exc:
        if exc.name != "uag_envsec":
            raise

    from ._pip_auto import _may_install

    policy = _project_auto_install_policy()
    if not _may_install("uag-envsec", policy_override=policy):
        raise ModuleNotFoundError(
            f"UAG requires the missing uag_envsec module. Repair with: {_REPAIR_HINT}"
        ) from None

    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--force-reinstall",
                "--no-deps",
                _REPAIR_SPEC,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=sys.stderr,
            timeout=120,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ModuleNotFoundError(
            f"Could not repair uag_envsec. Run: {_REPAIR_HINT}"
        ) from exc

    importlib.invalidate_caches()
    try:
        importlib.import_module("uag_envsec")
    except ModuleNotFoundError as exc:
        if exc.name != "uag_envsec":
            raise
        raise ModuleNotFoundError(
            f"uag_envsec is still missing after repair. Run: {_REPAIR_HINT}"
        ) from exc
