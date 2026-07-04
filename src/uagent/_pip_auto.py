# src/uagent/_pip_auto.py
"""Auto-install optional Python packages on ImportError."""

from __future__ import annotations

import subprocess
import sys

from .i18n import _


def auto_install(package_name: str, module_name: str | None = None) -> bool:
    """Try to install a Python package via pip, then verify it's importable.

    Args:
        package_name: The pip package name (e.g. 'mermaid-cli').
        module_name: The module to import after install (defaults to package_name).

    Returns:
        True if the module is importable after the attempt, False otherwise.
    """
    target = module_name or package_name

    # Try importing first
    try:
        __import__(target)
        return True
    except ImportError:
        pass

    # Attempt pip install
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", package_name],
            stdout=sys.stderr,
            stderr=sys.stderr,
            timeout=120,
        )
    except Exception:
        return False

    # Verify after install
    try:
        __import__(target)
        return True
    except ImportError:
        return False


def install_with_status(
    package_name: str,
    module_name: str | None = None,
    display_name: str | None = None,
    verify_submodule: str | None = None,
) -> bool:
    """Auto-install a package with progress messages.

    Displays localized status messages during install.
    Falls back to auto_install if i18n messages are unavailable.

    Args:
        package_name: The pip package name.
        module_name: The module to import after install (defaults to package_name).
        display_name: Human-readable name for messages (defaults to package_name).
        verify_submodule: If set, additionally import this submodule (e.g. "\"PySide6.QtCore"\")
                          to verify C extension DLLs actually load. Default None.

    Returns:
        True if all imports succeed after the attempt, False otherwise.
    """
    label = display_name or package_name
    target = module_name or package_name

    def _install(force: bool = False) -> bool:
        cmd = [sys.executable, "-m", "pip", "install"]
        if force:
            cmd.append("--force-reinstall")
        cmd.append(package_name)
        try:
            result = subprocess.run(cmd, stdout=sys.stderr, stderr=sys.stderr, timeout=120)
            return result.returncode == 0
        except Exception:
            return False

    def _import_ok() -> bool:
        try:
            __import__(target)
            return True
        except ImportError:
            return False

    def _submodule_ok() -> bool:
        if not verify_submodule:
            return True
        try:
            __import__(verify_submodule, fromlist=[''])
            return True
        except Exception:
            return False

    # Check current state
    if _import_ok() and _submodule_ok():
        return True

    # If already importable but submodule (DLL) fails -> force-reinstall once
    if _import_ok() and not _submodule_ok():
        print(f"{label} is installed but broken (DLL load failed). Reinstalling...", file=sys.stderr)
        if _install(force=True) and _import_ok() and _submodule_ok():
            return True
        # If force-reinstall didn't help, caller may add DLL directories and retry
        return False

    # Not installed at all -> normal install
    print(f"Installing {label}...", file=sys.stderr)
    if not _install(force=False):
        print(f"Failed to install {label}.", file=sys.stderr)
        return False
    ok = _import_ok() and _submodule_ok()
    if not ok:
        # If install succeeded but DLL still broken, try force-reinstall
        print(f"{label} installed but verification failed. Attempting force-reinstall...", file=sys.stderr)
        ok = _install(force=True) and _import_ok() and _submodule_ok()
    print(f"{label} installed {'successfully' if ok else 'but verification failed'}.", file=sys.stderr)
    return ok
