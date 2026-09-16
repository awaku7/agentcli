from __future__ import annotations

from uagent.runtime import legacy_claude_round


def _kwargs() -> dict[str, object]:
    return {
        "client": "old-client",
        "depname": "claude-model",
        "call_messages": [],
        "messages": [],
        "gemini_cache_name": "cache-name",
        "core": object(),
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
        "append_assistant_message_fn": lambda **_kwargs: None,
        "handle_empty_no_tool_fn": lambda **_kwargs: ("none", 0),
        "emit_final_answer_fn": lambda **_kwargs: None,
    }


def test_claude_round_preserves_legacy_result_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        legacy_claude_round,
        "call_legacy_claude_round",
        lambda **_kwargs: (True, "new-client", "answer", []),
    )

    result = legacy_claude_round.run_legacy_claude_round(**_kwargs())

    assert result == ("break", "new-client", "cache-name", 0, "answer!")


def test_claude_round_failure_returns_without_postprocessing(monkeypatch) -> None:
    emitted = []
    kwargs = _kwargs()
    kwargs["emit_final_answer_fn"] = lambda **_kwargs: emitted.append(True)
    monkeypatch.setattr(
        legacy_claude_round,
        "call_legacy_claude_round",
        lambda **_kwargs: (False, "new-client", "error", []),
    )

    result = legacy_claude_round.run_legacy_claude_round(**kwargs)

    assert result == ("return", "new-client", "cache-name", 2, "error")
    assert emitted == []


__all__ = []
