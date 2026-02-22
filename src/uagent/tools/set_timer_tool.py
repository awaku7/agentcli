# tools/set_timer.py
from .i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)

from typing import Any, Dict
import threading
import time

from .context import get_callbacks

BUSY_LABEL = False  # 非同期でタイマーを仕掛けるだけなので Busy は要らない

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "set_timer",
        "description": "指定した秒数後にメッセージを表示し、必要ならLLMへ自動メッセージを入力させることもできる。",
        "system_prompt": """このツールは次の目的で使われます: 指定した秒数後にメッセージを表示し、必要ならLLMへ自動メッセージを入力させることもできる。""",
        "parameters": {
            "type": "object",
            "properties": {
                "seconds": {"type": "integer", "description": "タイマーの秒数。"},
                "message": {
                    "type": "string",
                    "description": "完了時に表示するメッセージ。",
                },
                "on_timeout_prompt": {
                    "type": "string",
                    "description": "満了時にLLMへ自動入力する内容。",
                    "nullable": True,
                },
            },
            "required": ["seconds"],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()

    raw_seconds = args.get("seconds", 0)

    try:
        seconds = int(raw_seconds)
    except Exception:
        return (
            f"[set_timer error] seconds が整数として解釈できません: {repr(raw_seconds)}"
        )

    if seconds < 0:
        return f"[set_timer error] seconds は 0 以上で指定してください: {seconds}"

    message = args.get("message", "タイマー終了")
    on_timeout_prompt = args.get("on_timeout_prompt")

    if cb.event_queue is None:
        return "[set_timer error] event_queue コールバックが初期化されていません。"

    def timer_func():
        time.sleep(seconds)
        if cb.set_status:
            cb.set_status(True, "timer_pending")
        cb.event_queue.put({"kind": "timer", "text": on_timeout_prompt or message})

    threading.Thread(target=timer_func, daemon=True).start()
    return f"[set_timer] {seconds}秒でタイマーセット: {message} (on_timeout_prompt={repr(on_timeout_prompt)})"
