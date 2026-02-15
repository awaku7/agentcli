# tools/shared_memory.py
"""shared_memory.py

共有長期記憶（複数ユーザーで共有するメモ）を扱うユーティリティ。

目的:
- scheck_core.py から共有メモリ機能を分離し、tools 側で完結できるようにする。
- add_shared_memory_tool / get_shared_memory_tool などから直接利用する。

仕様:
- UAGENT_SHARED_MEMORY_FILE が設定されている場合のみ有効。
- ファイル形式は JSONL（1行1レコード）: {"ts": <epoch seconds>, "note": <str>}
- 出力トリミングは「文字数」ではなく「バイト数」上限で制御。

注意:
- ここでは core の Busy 表示などには触れない。
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_MAX_SHARED_MEMORY_BYTES = 200_000


def _get_base_log_dir() -> str:
    from uagent.utils.paths import get_log_dir

    return str(get_log_dir())


def _get_shared_memory_file() -> str:
    env = os.environ.get("UAGENT_SHARED_MEMORY_FILE")
    if env:
        return str(Path(env).expanduser().resolve())
    return os.path.join(_get_base_log_dir(), "scheck_shared_memory.jsonl")


def is_enabled() -> bool:
    # デフォルト値を導入したため、基本的には常に有効
    return True


def get_shared_memory_file() -> str:
    """共有メモリファイルの絶対パス。無効時は空文字。"""
    return _get_shared_memory_file()


def get_max_bytes() -> int:
    env = os.environ.get("UAGENT_MAX_SHARED_MEMORY_BYTES")
    if env:
        try:
            v = int(env)
            if v > 0:
                return v
        except Exception:
            pass
    return DEFAULT_MAX_SHARED_MEMORY_BYTES


def append_shared_memory(note: str) -> None:
    """共有長期記憶ファイルに1件追記。無効時は何もしない。"""
    path = _get_shared_memory_file()
    if not path:
        return

    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        record = {"ts": time.time(), "note": note}
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        # 共有メモリはベストエフォート（失敗しても落とさない）
        pass


def load_shared_memory_raw(max_bytes: Optional[int] = None) -> str:
    """共有長期記憶(JSONL)の生データを返す。

    - 無効時: その旨のメッセージを返す
    - 未作成: (no shared memory yet)
    - 長い場合: max_bytes を超えない範囲に切り詰め、末尾に注記を付ける
    """
    path = _get_shared_memory_file()
    if not path:
        return "(shared memory is disabled; set UAGENT_SHARED_MEMORY_FILE to enable it)"

    if max_bytes is None:
        max_bytes = get_max_bytes()

    try:
        with open(path, "rb") as f:
            data = f.read(max_bytes + 1)
    except FileNotFoundError:
        return "(no shared memory yet)"
    except Exception as e:
        return f"[shared_memory error] {type(e).__name__}: {e}"

    truncated_note = ""
    if len(data) > max_bytes:
        data = data[:max_bytes]
        truncated_note = f"\n[shared_memory truncated: limited to {max_bytes} bytes]"

    # UTF-8 としてデコード（不正バイトは置換）
    text = data.decode("utf-8", errors="replace")
    return text + truncated_note


def load_shared_memory_records() -> List[Dict[str, Any]]:
    """共有長期記憶(JSONL)を list[dict] として読み込む。壊れた行はスキップ。"""
    path = _get_shared_memory_file()
    if not path:
        return []

    records: List[Dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if isinstance(obj, dict) and "note" in obj:
                    records.append(obj)
    except FileNotFoundError:
        pass
    except Exception:
        pass

    return records
