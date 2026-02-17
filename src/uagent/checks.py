import subprocess
import sys
import platform

from .i18n import _


def check_git_installation():
    """Check if git is installed, and exit with installation instructions if not."""
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        os_type = platform.system().lower()
        install_msg = {
            "windows": _(
                "Please install Git. Download from: https://git-scm.com/download/win"
            ),
            "linux": _(
                "Please install Git. Example: sudo apt install git (Ubuntu/Debian) or sudo yum install git (CentOS/RHEL)"
            ),
            "darwin": _(
                "Please install Git. If using Homebrew: brew install git, or install Xcode Command Line Tools: xcode-select --install"
            ),
        }.get(os_type, _("Please install Git. See: https://git-scm.com/"))
        print(_("[ERROR] Git is not installed."), file=sys.stderr)
        print(install_msg, file=sys.stderr)
        sys.exit(1)
