import sys
import os
import time

from src.uagent.checks import check_git_installation

check_git_installation()

# ログ出力先
LOG_FILE = "gui_worker_session.log"


class LogStream:
    """stdout/stderr をファイルへリダイレクトするためのストリーム。"""

    def __init__(self, filename: str):
        self.filename = filename

    def write(self, data: str):
        if data:
            try:
                with open(self.filename, "a", encoding="utf-8", errors="replace") as f:
                    f.write(data)
            except Exception:
                pass

    def flush(self):
        pass

    def reconfigure(self, *args, **kwargs):
        pass


# 起動時にログファイルを初期化
try:
    with open(LOG_FILE, "w", encoding="utf-8") as _f:
        _f.write(f"[INFO] GUI Session Started: {time.ctime()}\n")
except Exception:
    pass

# グローバルなリダイレクト（ImportError 等もキャプチャするため）
_log_stream = LogStream(LOG_FILE)
sys.stdout = _log_stream
sys.stderr = _log_stream

# GUIモードフラグを環境変数で設定
os.environ["UAGENT_GUI_MODE"] = "1"

# src ディレクトリをパスに追加してパッケージとして認識可能にする
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

try:
    from uagent.gui import main
except ImportError as e:
    # リダイレクトを一時的に解除してエラー表示（またはログに書くだけでも良い）
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__
    print(f"Error: {e}")
    print(
        "Ensure you are in the project root directory and the 'src/scheck' directory exists."
    )
    sys.exit(1)

if __name__ == "__main__":
    main()
