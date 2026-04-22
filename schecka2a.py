import os
import sys

# src ディレクトリをパスに追加してパッケージとして認識可能にする
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from uagent.checks import check_git_installation

check_git_installation()

try:
    from uagent.a2a.server import main
except ImportError as e:
    print(f"Error: {e}")
    print(
        "Ensure you are in the project root directory and the 'src' directory exists."
    )
    sys.exit(1)


if __name__ == "__main__":
    if not (os.environ.get("UAGENT_A2A_TOKEN") or "").strip():
        print(
            "Warning: UAGENT_A2A_TOKEN is not set (A2A authenticated endpoints will reject requests)."
        )
    main(sys.argv[1:])
