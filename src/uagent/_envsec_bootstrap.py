"""Recover a missing envsec module after the standalone-package migration."""

from __future__ import annotations

import importlib
import os
import re
import subprocess
import sys
from pathlib import Path

_REPAIR_SPEC = "uag-envsec>=0.1.1"
_REPAIR_HINT = "python -m pip install --force-reinstall --no-deps 'uag-envsec>=0.1.1'"
_POLICY_LINE = re.compile(r"^\s*(?:export\s+)?UAGENT_AUTO_INSTALL\s*=\s*(.*)$")


def _startup_workdir() -> Path:
    """Resolve the selected workdir without importing the full runtime."""
    workdir = None
    args = sys.argv[1:]
    for index, arg in enumerate(args):
        if arg == "--":
            break
        if arg in ("--workdir", "-C") and index + 1 < len(args):
            workdir = args[index + 1]
        elif arg.startswith("--workdir="):
            workdir = arg.partition("=")[2]
        elif arg.startswith("-C") and len(arg) > 2:
            workdir = arg[2:]
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
    env_file = _startup_workdir() / ".env"
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
