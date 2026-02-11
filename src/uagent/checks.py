import subprocess
import sys
import platform


def check_git_installation():
    """Check if git is installed, and exit with installation instructions if not."""
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        os_type = platform.system().lower()
        install_msg = {
            "windows": "Gitをインストールしてください。公式サイトからダウンロード: https://git-scm.com/download/win",
            "linux": "Gitをインストールしてください。例: sudo apt install git (Ubuntu/Debian) または sudo yum install git (CentOS/RHEL)",
            "darwin": "Gitをインストールしてください。Homebrewの場合: brew install git, またはXcode Command Line Tools: xcode-select --install",
        }.get(os_type, "Gitをインストールしてください。https://git-scm.com/ を参照")
        print("[ERROR] Gitがインストールされていません。", file=sys.stderr)
        print(install_msg, file=sys.stderr)
        sys.exit(1)
