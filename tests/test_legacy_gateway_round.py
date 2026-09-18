from __future__ import annotations

from uagent.runtime import legacy_gateway_round


class _Core:
    def __init__(self) -> None:
        self._is_web = False


def _kwargs(core: _Core) -> dict[str, object]:
    return {
        "provider": "vercel",
        "client": "old-client",
        "depname": "gateway-model",
        "call_messages": [],
        "messages": [],
        "gemini_cache_name": "cache-name",
        "core": core,
        "make_client_fn": object(),
        "call_maybe_thread_fn": object(),
        "append_result_to_outfile_fn": object(),
        "try_open_images_from_text_fn": object(),
        "empty_no_tool_rounds": 2,
        "tr_cfg": None,
        "send_tools_this_round": True,
        "max_retries_429": 2,
        "retry_base": 1.0,
        "retry_cap": 4.0,
        "judgment_mode": False,
        "inject_stop_prompt_fn": lambda *_args: None,
        "translate_assistant_fn": lambda **kwargs: f"{kwargs['assistant_text']}!",
        "should_keep_assistant_message_fn": lambda *_args: True,
        "emit_final_answer_fn": lambda **_kwargs: None,
    }


def test_gateway_round_preserves_result_contract(monkeypatch) -> None:
    core = _Core()
    kwargs = _kwargs(core)
    emitted: list[dict[str, object]] = []
    kwargs["emit_final_answer_fn"] = lambda **payload: emitted.append(payload)
    monkeypatch.setattr(
        legacy_gateway_round,
        "call_legacy_reasoning_round",
        lambda **_kwargs: (True, "new-client", "answer", "reasoning", []),
    )

    result = legacy_gateway_round.run_legacy_gateway_round(**kwargs)

    assert result == ("break", "new-client", "cache-name", 2, "answer!")
    assert kwargs["messages"]
    assert kwargs["messages"][0]["role"] == "assistant"
    assert emitted and emitted[0]["provider"] == "vercel"


def test_gateway_round_failure_returns_without_emitting(monkeypatch) -> None:
    core = _Core()
    emitted = []
    kwargs = _kwargs(core)
    kwargs["emit_final_answer_fn"] = lambda **_kwargs: emitted.append(True)
    monkeypatch.setattr(
        legacy_gateway_round,
        "call_legacy_reasoning_round",
        lambda **_kwargs: (False, "new-client", "error", "", []),
    )

    result = legacy_gateway_round.run_legacy_gateway_round(**kwargs)

    assert result == ("return", "new-client", "cache-name", 2, "error")
    assert emitted == []


def test_gateway_round_executes_tool_calls_instead_of_emitting_final(
    monkeypatch,
) -> None:
    core = _Core()
    kwargs = _kwargs(core)
    tool_call = {
        "id": "call-1",
        "type": "function",
        "function": {"name": "read_file", "arguments": "{}"},
    }
    executed = []
    emitted = []
    kwargs["emit_final_answer_fn"] = lambda **payload: emitted.append(payload)
    monkeypatch.setattr(
        legacy_gateway_round,
        "call_legacy_reasoning_round",
        lambda **_kwargs: (
            True,
            "new-client",
            "tool request",
            "reasoning",
            [tool_call],
        ),
    )
    monkeypatch.setattr(
        legacy_gateway_round,
        "execute_legacy_tool_calls",
        lambda **payload: executed.append(payload) or (True, [tool_call]),
    )

    result = legacy_gateway_round.run_legacy_gateway_round(**kwargs)

    assert result == ("ok", "new-client", "cache-name", 0, "tool request!")
    assert len(executed) == 1
    assert executed[0]["tool_calls"] == [tool_call]
    assert emitted == []


__all__ = []
