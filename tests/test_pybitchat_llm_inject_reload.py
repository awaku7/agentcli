"""pybitchat LLM injection が tools リロード後も生存することを検証する回帰テスト.

背景: cli.py は起動時に ``set_llm_event_queue(core.event_queue)`` を呼び、
``tools.start_tools_warmup()`` が ``_load_plugins()`` 経由で tools/ 配下の
全モジュールを ``importlib.reload()`` していた。reload はモジュール本体を
再実行するため ``pybitchat_shared._LLM_EVENT_QUEUE`` / ``_CHAT_MODE`` /
``_RUNNING`` 等のランタイム状態を破棄し、chat_mode="llm" の受信メッセージが
表示されるだけで LLM に注入されなくなる不具合があった。

修正: ``_load_plugins()`` は TOOL_SPEC + run_tool を持たないヘルパー
モジュール（pybitchat_shared 等）を reload しない。
"""

from __future__ import annotations

import queue
from typing import Any


def _reset_state(pbs: Any) -> None:
    pbs.set_llm_event_queue(None)
    pbs._CHAT_MODE = "off"


def test_reload_plugins_preserves_llm_event_queue_and_chat_mode() -> None:
    """reload_plugins() が LLM イベントキューと chat mode を保持する."""
    from uagent.tools import pybitchat_shared as pbs

    try:
        q: "queue.Queue[dict[str, Any]]" = queue.Queue()
        pbs.set_llm_event_queue(q)
        pbs._CHAT_MODE = "llm"

        # cli.py の warmup / :reload 相当のパス
        from uagent.tools import reload_plugins

        reload_plugins()

        assert pbs._LLM_EVENT_QUEUE is q, "reload 後にキュー参照が失われている"
        assert pbs.is_chat_mode() == "llm", "reload 後に chat mode がリセットされている"
    finally:
        _reset_state(pbs)


def test_inject_to_llm_enqueues_after_reload() -> None:
    """reload 後も受信メッセージが LLM イベントキューに到達する."""
    from uagent.tools import pybitchat_shared as pbs

    try:
        q: "queue.Queue[dict[str, Any]]" = queue.Queue()
        pbs.set_llm_event_queue(q)
        pbs._CHAT_MODE = "llm"

        from uagent.tools import reload_plugins

        reload_plugins()

        pbs._inject_to_llm("[bitchat] uka: konnichiwa")
        assert q.qsize() == 1, "reload 後に注入イベントがドロップされている"
        ev = q.get_nowait()
        assert ev["kind"] == "user"
        assert "konnichiwa" in ev["text"]
    finally:
        _reset_state(pbs)


def test_tool_modules_still_registered_after_reload() -> None:
    """reload 後も実ツールモジュールは再登録される."""
    from uagent.tools import reload_plugins

    reload_plugins()

    # 実ツール（TOOL_SPEC + run_tool あり）は reload 対象のまま。
    from uagent.tools import pybitchat_subscribe_tool as mod

    assert isinstance(mod.TOOL_SPEC, dict)
    assert callable(mod.run_tool)
