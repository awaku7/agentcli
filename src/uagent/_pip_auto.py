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

    def _run_pip(*args: str) -> bool:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", *args, package_name],
                stdout=sys.stderr, stderr=sys.stderr, timeout=120,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _verify() -> bool:
        try:
            __import__(target)
        except ImportError:
            return False
        if verify_submodule:
            try:
                __import__(verify_submodule, fromlist=[''])
            except Exception:
                return False
        return True

    # Already works
    if _verify():
        return True

    # Try installing
    print(f"Installing {label}...", file=sys.stderr)
    _run_pip()
    if _verify():
        print(f"{label} installed successfully.", file=sys.stderr)
        return True

    # One more try with --force-reinstall (e.g. stale/corrupted installation)
    print(f"Retrying with --force-reinstall...", file=sys.stderr)
    _run_pip("--force-reinstall")
    if _verify():
        print(f"{label} installed successfully.", file=sys.stderr)
        return True

    print(f"Failed to install {label}.", file=sys.stderr)
    return False
