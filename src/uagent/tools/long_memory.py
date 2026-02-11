# tools/long_memory.py
"""Long-term memory utilities.

This module was extracted from scheck_core.py so that the core can stay lean.
It is intentionally placed under tools/ so both:
- tool implementations (tools/*_tool.py)
- the main CLI runner (scheck.py)
can import and reuse the same logic.

The storage location is controlled by env vars:
- UAGENT_LOG_DIR
- UAGENT_MEMORY_FILE (optional)

Secret values must not be stored.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List


def _get_base_log_dir() -> str:
    return os.path.abspath(
        os.environ.get("UAGENT_LOG_DIR")
        or os.path.join(os.path.expanduser("~"), ".scheck", "logs")
    )


def get_memory_file_path() -> str:
    """Return the resolved path to the personal long-memory JSONL file."""
    base_log_dir = _get_base_log_dir()
    return os.environ.get("UAGENT_MEMORY_FILE") or os.path.join(
        base_log_dir, "scheck_memory.jsonl"
    )


def get_max_memory_bytes() -> int:
    # limit passed to LLM / displayed
    return 200_000


def append_long_memory(note: str) -> None:
    """Append one memory record to the JSONL file. Errors are ignored."""
    memory_file = get_memory_file_path()
    try:
        dirpath = os.path.dirname(memory_file)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        record = {"ts": time.time(), "note": note}
        with open(memory_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def load_long_memory_raw() -> str:
    """Load the JSONL content as raw text (truncated)."""
    memory_file = get_memory_file_path()
    max_bytes = get_max_memory_bytes()

    try:
        with open(memory_file, encoding="utf-8") as f:
            data = f.read(max_bytes + 1)
    except FileNotFoundError:
        return "(no long-term memory yet)"
    except Exception as e:
        return f"[long_memory error] {type(e).__name__}: {e}"

    truncated_note = ""
    if len(data) > max_bytes:
        data = data[:max_bytes]
        truncated_note = f"\n[long_memory truncated: limited to {max_bytes} chars]"

    return data + truncated_note


def load_long_memory_records() -> List[Dict[str, Any]]:
    """Parse JSONL and return list of dicts. Broken lines are skipped."""
    memory_file = get_memory_file_path()
    records: List[Dict[str, Any]] = []
    try:
        with open(memory_file, encoding="utf-8") as f:
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
        # printing is left to caller (CLI)
        pass
    return records


def delete_long_memory_entry(index: int) -> bool:
    """Delete one record by index. Returns True on success."""
    records = load_long_memory_records()
    if index < 0 or index >= len(records):
        return False

    memory_file = get_memory_file_path()

    try:
        records.pop(index)
        dirpath = os.path.dirname(memory_file)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        with open(memory_file, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        return False

    return True
