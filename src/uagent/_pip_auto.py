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

    # Check if already importable
    try:
        __import__(target)
        return True
    except ImportError:
        pass

    # Show installing message
    try:
        msg = _("Installing {package}...").format(package=label)
    except Exception:
        msg = f"Installing {label}..."
    print(msg, file=sys.stderr)

    # Attempt pip install
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package_name],
            stdout=sys.stderr, stderr=sys.stderr, timeout=120,
        )
        success = result.returncode == 0
    except Exception:
        success = False

    # Verify after install
    try:
        __import__(target)
        success = True
    except ImportError:
        success = False

    # Verify submodule if specified (e.g. to test C extension DLL loading)
    if success and verify_submodule:
        try:
            __import__(verify_submodule, fromlist=[''])
        except Exception:
            success = False

    # Show result message
    try:
        if success:
            done_msg = _("{package} installed successfully.").format(package=label)
        else:
            done_msg = _("Failed to install {package}.").format(package=label)
    except Exception:
        done_msg = f"{label} installed." if success else f"Failed to install {label}."
    print(done_msg, file=sys.stderr)

    return success
