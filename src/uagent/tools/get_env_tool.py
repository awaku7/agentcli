# tools/get_env_tool.py
from typing import Any, Dict
import os

from .context import get_callbacks

BUSY_LABEL = False

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_env",
        "description": "指定した名前の環境変数値を取得し、要求された名前で返します。オプションで値をマスクできます。",
        "system_prompt": """このツールは次の目的で使われます: 指定した名前の環境変数値を取得し、要求された名前で返します。オプションで値をマスクできます。""",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "読み取る環境変数名。",
                },
                "missing_ok": {
                    "type": "boolean",
                    "description": "true の場合、欠落時にエラーではなく '(not set)' を返します。既定は false。",
                },
                "mask": {
                    "type": "boolean",
                    "description": "true の場合、値をマスクします（例: 秘密情報）。既定は true。",
                },
                "unmasked_chars": {
                    "type": "integer",
                    "description": "マスク時、先頭と末尾に残す文字数。既定は 2。",
                },
            },
            "required": ["name"],
        },
    },
}


def _mask_value(val: str, keep: int = 2) -> str:
    if val is None:
        return ""
    s = str(val)
    if keep < 0:
        keep = 0
    # Short values: fully mask
    if len(s) <= keep * 2 + 1:
        return "***"
    head = s[:keep] if keep else ""
    tail = s[-keep:] if keep else ""
    return f"{head}***{tail}"


def run_tool(args: Dict[str, Any]) -> str:
    # NOTE:
    # - ツール呼び出しの概要は tools/__init__.py 側で一律にトレース出力します。
    # - 個別ツールでのデバッグ print は二重出力になるため、原則置かない方針です。

    cb = get_callbacks()

    name = str(args.get("name", "") or "").strip()
    missing_ok = bool(args.get("missing_ok", False))

    # Security default: mask unless explicitly disabled.
    mask = True if args.get("mask") is None else bool(args.get("mask"))
    try:
        unmasked_chars = int(args.get("unmasked_chars", 2))
    except Exception:
        unmasked_chars = 2

    if not name:
        return "[get_env error] 'name' is required"

    try:
        # Prefer host-provided getter (it may enforce policies)
        if cb.get_env is not None:
            try:
                val = cb.get_env(name)
            except SystemExit:
                # Host get_env may sys.exit(1) when missing
                if missing_ok:
                    return f"{name}=(not set)"
                return f"[get_env error] {name} is not set"

            out_val = _mask_value(val, keep=unmasked_chars) if mask else str(val)
            return f"{name}={out_val}"

        # Fallback: direct os.environ
        val2 = os.environ.get(name)
        if val2 is None:
            if missing_ok:
                return f"{name}=(not set)"
            return f"[get_env error] {name} is not set"

        out_val2 = _mask_value(val2, keep=unmasked_chars) if mask else str(val2)
        return f"{name}={out_val2}"

    except Exception as e:
        return f"[get_env error] {type(e).__name__}: {e}"
