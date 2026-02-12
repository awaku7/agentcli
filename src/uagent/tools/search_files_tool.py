# tools/search_files_tool.py
import os
import re
import fnmatch
from typing import Any, Dict, List, Optional, Tuple

# ツール実行中は Busy 表示にしたいので ON
BUSY_LABEL = True
STATUS_LABEL = "tool:search_files"

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "search_files",
        "description": "ディレクトリ内のファイルを検索します。ファイル名パターン(glob)での検索に加え、ファイル内容の正規表現検索(Grep)も可能です。",
        "system_prompt": """このツールは次の目的で使われます: ディレクトリ内のファイルを検索します。ファイル名パターン(glob)での検索に加え、ファイル内容の正規表現検索(Grep)も可能です。""",
        "parameters": {
            "type": "object",
            "properties": {
                "root_path": {
                    "type": "string",
                    "description": "検索を開始するディレクトリパス（省略時はカレントディレクトリ）。",
                },
                "name_pattern": {
                    "type": "string",
                    "description": "ファイル名のパターン（glob形式、例: '*.py', 'test_*'）。省略時は全ファイルを対象にします。",
                },
                "content_pattern": {
                    "type": "string",
                    "description": "ファイル内で検索したい文字列の正規表現パターン。指定した場合、マッチする行を含むファイルのみを返します。",
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "大文字小文字を区別するかどうか（デフォルト: False）。",
                },
                "max_results": {
                    "type": "integer",
                    "description": "検索結果の最大件数（デフォルト: 50）。これを超えると検索を打ち切ります。",
                },
                "exclude_binary": {
                    "type": "boolean",
                    "description": "content_pattern 指定時、バイナリと推定されるファイルを検索対象から除外します（デフォルト: True）。",
                    "default": True,
                },
                "binary_sniff_bytes": {
                    "type": "integer",
                    "description": "バイナリ判定のために先頭から読み込むバイト数（デフォルト: 8192）。",
                    "default": 8192,
                },
                "fast_read_threshold_bytes": {
                    "type": "integer",
                    "description": "このサイズ未満のファイルは全文 read() して高速に検索します（デフォルト: 8000000=約8MB）。これ以上は行単位でストリーミング検索します。",
                    "default": 8000000,
                },
            },
            # root_path は必須ではないが、明示的な引数なしでも動くようにしておく
            "required": [],
        },
    },
}


# 検索から除外するディレクトリ
IGNORE_DIRS = {
    '.git',
    '__pycache__',
    '.venv',
    'venv',
    'node_modules',
    '.idea',
    '.vscode',
    'coverage',
}

# 検索対象外にする拡張子（バイナリや巨大ファイルなど）
IGNORE_EXTS = {
    ".pyc",
    ".pyd",
    ".so",
    ".dll",
    ".exe",
    ".bin",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
}


def _looks_binary(head: bytes) -> bool:
    """バイナリっぽいかを軽量に推定する。

    方針:
    - NUL(\x00) が含まれたらほぼバイナリ。
    - それ以外でも、制御文字の比率が高い場合はバイナリ扱い。

    NOTE: 完璧な判定は不可能だが、「バイナリは見たくない」用途の除外としては十分。
    """

    if not head:
        return False

    if b"\x00" in head:
        return True

    # 許容する制御文字: \t, \n, \r
    bad = 0
    for b in head:
        if b in (9, 10, 13):
            continue
        if 0 <= b < 32:
            bad += 1

    # 先頭チャンクの 10% 以上が制御文字ならバイナリ寄りと判定
    return (bad / len(head)) > 0.10


def _grep_text_full_read(
    full_path: str,
    regex: re.Pattern[str],
    max_hits_per_file: int,
) -> List[str]:
    """小〜中サイズファイル向け: 全文 read() して高速に grep。

    - まず全文に対して regex.search() でヒット有無を確認
    - ヒットした場合のみ splitlines() して行番号を抽出
    """

    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    if not regex.search(text):
        return []

    matched_lines: List[str] = []
    for i, line in enumerate(text.splitlines(), start=1):
        if regex.search(line):
            matched_lines.append(f"L{i}: {line.strip()[:200]}")
            if len(matched_lines) >= max_hits_per_file:
                matched_lines.append("... (more matches in file)")
                break

    return matched_lines


def _grep_text_streaming(
    full_path: str,
    regex: re.Pattern[str],
    max_hits_per_file: int,
) -> List[str]:
    """巨大ファイル向け: 行単位でストリーミング grep（メモリ安全）。"""

    matched_lines: List[str] = []
    line_num = 0
    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line_num += 1
            if regex.search(line):
                matched_lines.append(f"L{line_num}: {line.strip()[:200]}")
                if len(matched_lines) >= max_hits_per_file:
                    matched_lines.append("... (more matches in file)")
                    break

    return matched_lines


def run_tool(args: Dict[str, Any]) -> str:
    """
    ファイル検索を実行する
    """
    root_path = args.get("root_path") or "."
    name_pattern = args.get("name_pattern") or "*"
    content_pattern = args.get("content_pattern", "")
    case_sensitive = args.get("case_sensitive", False)
    max_results = args.get("max_results", 50)
    exclude_binary = bool(args.get("exclude_binary", True))
    binary_sniff_bytes = int(args.get("binary_sniff_bytes", 8192))
    fast_read_threshold_bytes = int(args.get("fast_read_threshold_bytes", 8_000_000))

    # max_results の正規化
    try:
        max_results = int(max_results)
    except Exception:
        max_results = 50

    if not os.path.exists(root_path):
        return f"[search_files error] ディレクトリが存在しません: {root_path}"

    # コンテンツ検索用の正規表現コンパイル
    regex = None
    if content_pattern:
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            regex = re.compile(content_pattern, flags)
        except re.error as e:
            return f"[search_files error] 正規表現のコンパイルに失敗しました: {e}"

    results = []
    count = 0
    truncated = False

    import sys

    print(
        f"[search_files] root='{root_path}', name='{name_pattern}', grep='{content_pattern}'",
        file=sys.stderr,
    )

    for dirpath, dirnames, filenames in os.walk(root_path):
        # 除外ディレクトリのフィルタリング
        # os.walk の dirnames を書き換えることで再帰を抑制できる
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]

        for fname in filenames:
            if count >= max_results:
                truncated = True
                break

            # 拡張子チェック
            _, ext = os.path.splitext(fname)
            if ext.lower() in IGNORE_EXTS:
                continue

            # ファイル名マッチング
            # fnmatch はデフォルトで case-insensitive (Windows) かもしれないが、
            # 明示的にコントロールしたい場合もある。ここではシンプルに fnmatch を使う。
            if not fnmatch.fnmatch(fname, name_pattern):
                continue

            full_path = os.path.join(dirpath, fname)

            # コンテンツ検索 (Grep)
            if regex:
                try:
                    # バイナリ判定（grep時のみ）
                    if exclude_binary:
                        with open(full_path, "rb") as bf:
                            head = bf.read(binary_sniff_bytes)
                        if _looks_binary(head):
                            continue

                    max_hits_per_file = 5
                    try:
                        size = os.path.getsize(full_path)
                    except Exception:
                        size = None

                    if size is not None and size < fast_read_threshold_bytes:
                        matched_lines = _grep_text_full_read(
                            full_path, regex=regex, max_hits_per_file=max_hits_per_file
                        )
                    else:
                        matched_lines = _grep_text_streaming(
                            full_path, regex=regex, max_hits_per_file=max_hits_per_file
                        )

                    if matched_lines:
                        results.append(f"File: {full_path}")
                        for m in matched_lines:
                            results.append(f"  {m}")
                        count += 1

                except Exception:
                    # 読み込みエラーはスキップ
                    continue
            else:
                # ファイル名検索のみ
                results.append(f"File: {full_path}")
                count += 1

        if truncated:
            break

    if not results:
        return "[search_files] 条件に一致するファイルは見つかりませんでした。"

    header = f"[search_files] Found {count} results:\n"
    if truncated:
        header += f"(Results truncated to {max_results})\n"

    return header + "\n".join(results)
