from __future__ import annotations

import threading

from uagent import tools


def test_tool_warmup_is_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("UAGENT_TOOLS_WARMUP", raising=False)
    monkeypatch.setattr(tools, "_INITIALIZED", False)
    monkeypatch.setattr(tools, "_WARMUP_STARTED", False)

    def unexpected_load() -> None:
        raise AssertionError("default startup must not preload tool plugins")

    monkeypatch.setattr(tools, "_ensure_loaded", unexpected_load)

    tools.start_tools_warmup()


def test_opt_in_tool_warmup_runs_synchronously(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_TOOLS_WARMUP", "1")
    monkeypatch.setattr(tools, "_INITIALIZED", False)
    monkeypatch.setattr(tools, "_WARMUP_STARTED", False)
    load_thread_ids: list[int] = []
    command_map_thread_ids: list[int] = []
    monkeypatch.setattr(
        tools, "_ensure_loaded", lambda: load_thread_ids.append(threading.get_ident())
    )
    monkeypatch.setattr(
        tools,
        "get_dynamic_commands_map",
        lambda: command_map_thread_ids.append(threading.get_ident()),
    )

    caller_thread_id = threading.get_ident()
    tools.start_tools_warmup()

    assert load_thread_ids == [caller_thread_id]
    assert command_map_thread_ids == [caller_thread_id]
