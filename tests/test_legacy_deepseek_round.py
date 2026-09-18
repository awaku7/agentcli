from __future__ import annotations

from uagent.runtime import legacy_deepseek_round


class _Core:
    responses_state = {}
    _is_web = False

    def __init__(self) -> None:
        self.logged: list[dict[str, object]] = []

    def log_message(self, message: dict[str, object]) -> None:
        self.logged.append(message)


def _kwargs(core: _Core) -> dict[str, object]:
    return {
        "provider": "deepseek",
        "client": "old-client",
        "depname": "deepseek-model",
        "call_messages": [],
        "messages": [],
        "gemini_cache_name": "cache-name",
        "core": core,
        "make_client_fn": object(),
        "call_maybe_thread_fn": object(),
        "append_result_to_outfile_fn": object(),
        "try_open_images_from_text_fn": object(),
        "empty_no_tool_rounds": 2,
        "empty_no_tool_max": 3,
        "tr_cfg": None,
        "use_responses_api": False,
        "stream_responses": False,
        "send_tools_this_round": True,
        "max_retries_429": 2,
        "retry_base": 1.0,
        "retry_cap": 4.0,
        "judgment_mode": False,
        "inject_stop_prompt_fn": lambda *_args: None,
        "translate_assistant_fn": lambda **kwargs: f"{kwargs['assistant_text']}!",
        "should_keep_assistant_message_fn": lambda *_args: True,
        "handle_empty_no_tool_fn": lambda **_kwargs: ("none", 0),
        "emit_final_answer_fn": lambda **_kwargs: None,
    }


def test_deepseek_round_preserves_reasoning_message_and_result_contract(
    monkeypatch,
) -> None:
    core = _Core()
    kwargs = _kwargs(core)
    kwargs["messages"] = []
    monkeypatch.setattr(
        legacy_deepseek_round,
        "call_legacy_deepseek_round",
        lambda **_kwargs: (True, "new-client", "answer", "reasoning", []),
    )

    result = legacy_deepseek_round.run_legacy_deepseek_round(**kwargs)

    assert result == ("break", "new-client", "cache-name", 0, "answer!")
    assert kwargs["messages"]
    assert kwargs["messages"][0]["role"] == "assistant"
    assert core.logged == kwargs["messages"]


def test_deepseek_round_failure_returns_without_logging(monkeypatch) -> None:
    core = _Core()
    emitted = []
    kwargs = _kwargs(core)
    kwargs["emit_final_answer_fn"] = lambda **_kwargs: emitted.append(True)
    monkeypatch.setattr(
        legacy_deepseek_round,
        "call_legacy_deepseek_round",
        lambda **_kwargs: (False, "new-client", "error", "", []),
    )

    result = legacy_deepseek_round.run_legacy_deepseek_round(**kwargs)

    assert result == ("return", "new-client", "cache-name", 2, "error")
    assert core.logged == []
    assert emitted == []


def test_deepseek_round_executes_tool_calls_before_continuing(monkeypatch) -> None:
    core = _Core()
    kwargs = _kwargs(core)
    tool_call = {
        "id": "call-1",
        "type": "function",
        "function": {"name": "read_file", "arguments": "{}"},
    }
    executed = []
    monkeypatch.setattr(
        legacy_deepseek_round,
        "call_legacy_deepseek_round",
        lambda **_kwargs: (
            True,
            "new-client",
            "tool request",
            "reasoning",
            [tool_call],
        ),
    )
    monkeypatch.setattr(
        legacy_deepseek_round,
        "execute_legacy_tool_calls",
        lambda **payload: executed.append(payload) or (True, [tool_call]),
    )

    result = legacy_deepseek_round.run_legacy_deepseek_round(**kwargs)

    assert result == ("ok", "new-client", "cache-name", 0, "tool request!")
    assert len(executed) == 1
    assert executed[0]["tool_calls"] == [tool_call]
    assert executed[0]["messages"] is kwargs["messages"]


__all__ = []
