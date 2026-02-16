# tools/read_file.py
from typing import Any, Dict
import os
import threading

from .context import get_callbacks

# セマンティック検索DB更新用のインポート
try:
    from .semantic_search_files_tool import sync_file
except ImportError:
    sync_file = None

BUSY_LABEL = True
STATUS_LABEL = "tool:read_file"


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "ファイル内容を読み取ります（最大 20000000 バイトまで）。開始行や行数を指定した部分的な読み取りも可能です。",
        "system_prompt": """ファイル内容を読み取ります。
- 大きなファイルは start_line や max_lines を使用して部分的に読み取ることが推奨されます。
- 改行コードは自動的に正規化されます。""",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "読み取るファイルのパス。",
                },
                "path": {
                    "type": "string",
                    "description": "(互換) 読み取るファイルのパス。filename の別名として受け付けます。",
                },
                "start_line": {
                    "type": "integer",
                    "description": "読み取りを開始する行番号（1始まり）。デフォルトは 1。",
                    "default": 1,
                },
                "max_lines": {
                    "type": ["integer", "null"],
                    "description": "読み取る最大行数。null の場合はファイル末尾まで読み取ります。",
                    "default": None,
                },
                "head_lines": {
                    "type": ["integer", "null"],
                    "description": "先頭から読む行数。tail_lines と同時指定不可。",
                    "default": None,
                },
                "tail_lines": {
                    "type": ["integer", "null"],
                    "description": "末尾から読む行数。head_lines と同時指定不可。",
                    "default": None,
                },
            },
            "required": ["filename"],
            "additionalProperties": False,
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()

    filename = args.get("filename") or args.get("path") or ""
    if not filename:
        return "[read_file error] filename/path が指定されていません"
    filename = os.path.expanduser(str(filename))

    head_lines = args.get("head_lines")
    tail_lines = args.get("tail_lines")

    if head_lines is not None and tail_lines is not None:
        return "[read_file error] head_lines and tail_lines cannot be specified together"

    if head_lines is not None:
        head_lines = int(head_lines)
        start_line = 1
        max_lines = head_lines
    elif tail_lines is not None:
        tail_lines = int(tail_lines)
        # エンコーディングを先に判定（tail のために）
        try:
            with open(filename, "rb") as f:
                head = f.read(8192)
                try:
                    head.decode("utf-8")
                    encoding = "utf-8"
                except UnicodeDecodeError:
                    encoding = cb.cmd_encoding
                    if encoding.lower() == "utf-8":
                        encoding = "cp932"
        except Exception:
            encoding = "utf-8"  # fallback

        # 総行数をカウント
        with open(filename, "r", encoding=encoding, errors="replace", newline=None) as f:
            total_lines = sum(1 for _ in f)

        if total_lines < tail_lines:
            start_line = 1
            max_lines = total_lines
        else:
            start_line = total_lines - tail_lines + 1
            max_lines = tail_lines
    else:
        start_line = max(1, int(args.get("start_line", 1)))
        max_lines = args.get("max_lines")
        if max_lines is not None:
            max_lines = int(max_lines)

    max_bytes = cb.read_file_max_bytes

    try:
        # まずはバイナリで一部読み込み、エンコーディングを判定
        with open(filename, "rb") as f:
            head = f.read(8192)
            try:
                head.decode("utf-8")
                encoding = "utf-8"
            except UnicodeDecodeError:
                # cb.cmd_encoding が 'utf-8' の場合、日本語Windowsなら 'cp932' を試す
                encoding = cb.cmd_encoding
                if encoding.lower() == "utf-8":
                    encoding = "cp932"

        # テキストモードで開き、行ごとに処理（CRLFを自動処理）
        lines = []
        total_bytes = 0
        with open(filename, "r", encoding=encoding, errors="replace", newline=None) as f:
            i = 0
            for i, line in enumerate(f, 1):
                if i < start_line:
                    continue
                lines.append(line)
                total_bytes += len(line.encode(encoding, errors="replace"))
                if max_lines is not None and len(lines) >= max_lines:
                    break
                # 安全のためのバイト制限
                if total_bytes > max_bytes:
                    lines.append(f"\n[read_file truncated: byte limit {max_bytes} reached]")
                    break

        if not lines and start_line > 1:
            return f"(file has only {i} lines, start_line {start_line} is out of range)"

        # 読み込み成功時、バックグラウンドでベクトルDBを更新
        if sync_file and os.path.isfile(filename):
            # カレントディレクトリをルートとして更新を試みる
            try:
                threading.Thread(target=sync_file, args=(filename, os.getcwd()), daemon=True).start()
            except Exception:
                pass

        return "".join(lines)
    except Exception as e:
        return f"[read_file error] {type(e).__name__}: {e}"
