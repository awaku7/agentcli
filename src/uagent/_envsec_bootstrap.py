"""Recover a missing envsec module after the standalone-package migration."""

from __future__ import annotations

import importlib
import subprocess
import sys

_REPAIR_SPEC = "uag-envsec>=0.1.1"
_REPAIR_HINT = "python -m pip install --force-reinstall --no-deps 'uag-envsec>=0.1.1'"


def ensure_envsec_available() -> None:
    """Repair only the missing top-level module, respecting auto-install policy.

    Older UAG wheels included the uag_envsec package. During an upgrade, pip
    may install the standalone distribution and then delete its files while
    uninstalling old UAG. Its metadata remains, so reinstalling UAG alone
    cannot restore the module.
    """
    try:
        importlib.import_module("uag_envsec")
        return
    except ModuleNotFoundError as exc:
        if exc.name != "uag_envsec":
            raise

    from ._pip_auto import _may_install

    if not _may_install("uag-envsec"):
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
