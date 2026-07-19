from __future__ import annotations

import subprocess
import platform

from .i18n import _


def check_git_installation() -> None:
    """Check if git is installed; raise RuntimeError with install hints if not."""
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        os_type = platform.system().lower()
        install_msg = {
            "windows": _("Please install Git. See: %(url)s")
            % {"url": "https://git-scm.com/download/"},
            "linux": _(
                "Please install Git. Example: sudo apt install git (Ubuntu/Debian) or sudo yum install git (CentOS/RHEL)"
            ),
            "darwin": _(
                "Please install Git. If using Homebrew: brew install git, or install Xcode Command Line Tools: xcode-select --install"
            ),
        }.get(
            os_type,
            _("Please install Git. See: %(url)s")
            % {"url": "https://git-scm.com/download/"},
        )
        raise RuntimeError(
            f"{_('[ERROR] Git is not installed.')} {install_msg}"
        ) from None
