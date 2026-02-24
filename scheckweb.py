import sys
import os

# src ディレクトリをパスに追加してパッケージとして認識可能にする
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from uagent.checks import check_git_installation

check_git_installation()

try:
    from uagent.web import main
except ImportError as e:
    print(f"Error: {e}")
    print(
        "Ensure you are in the project root directory and the 'src/scheck' directory exists."
    )
    sys.exit(1)

if __name__ == "__main__":
    main()
