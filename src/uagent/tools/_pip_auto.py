# src/uagent/tools/_pip_auto.py
"""Auto-install optional Python packages on ImportError."""

from __future__ import annotations

import subprocess
import sys


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
            capture_output=True,
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
