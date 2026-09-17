from __future__ import annotations

from uagent.runtime import legacy_gemini_round


class _Core:
    def __init__(self) -> None:
        self._is_web = False
        self.context_tool_specs = []


def _kwargs(core: _Core) -> dict[str, object]:
    return {
        "provider": "gemini",
        "client": "old-client",
        "depname": "gemini-model",
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
        "append_assistant_message_fn": lambda **_kwargs: None,
        "handle_empty_no_tool_fn": lambda **_kwargs: ("none", 0),
        "emit_final_answer_fn": lambda **_kwargs: None,
    }


def test_gemini_round_preserves_content_dump_and_result_contract(monkeypatch) -> None:
    core = _Core()
    kwargs = _kwargs(core)
    appended: list[dict[str, object]] = []
    kwargs["append_assistant_message_fn"] = lambda **payload: appended.append(payload)
    monkeypatch.setattr(
        legacy_gemini_round,
        "call_legacy_gemini_round",
        lambda **_kwargs: (True, "new-client", "answer", [], {"parts": []}),
    )

    result = legacy_gemini_round.run_legacy_gemini_round(**kwargs)

    assert result == ("break", "new-client", "cache-name", 0, "answer!")
    assert appended and appended[0]["gemini_content_dump"] == {"parts": []}


def test_gemini_round_failure_returns_without_appending(monkeypatch) -> None:
    core = _Core()
    appended = []
    kwargs = _kwargs(core)
    kwargs["append_assistant_message_fn"] = lambda **_kwargs: appended.append(True)
    monkeypatch.setattr(
        legacy_gemini_round,
        "call_legacy_gemini_round",
        lambda **_kwargs: (False, "new-client", "error", [], None),
    )

    result = legacy_gemini_round.run_legacy_gemini_round(**kwargs)

    assert result == ("return", "new-client", "cache-name", 2, "error")
    assert appended == []


def test_gemini_round_synthesizes_catalog_call_for_thought_only_response(
    monkeypatch,
) -> None:
    core = _Core()
    core.context_tool_specs = [{"function": {"name": "tool_catalog"}}]
    kwargs = _kwargs(core)
    appended: list[dict[str, object]] = []
    kwargs["append_assistant_message_fn"] = lambda **payload: appended.append(payload)
    monkeypatch.setattr(
        "uagent.runtime.legacy_gemini_round.call_legacy_gemini_round",
        lambda **_kwargs: (True, "client", "", [], {}),
    )
    monkeypatch.setattr(
        "uagent.llm_flow_helpers._execute_tool_calls",
        lambda **call_kwargs: (True, call_kwargs["tool_calls_list"]),
    )

    result = legacy_gemini_round.run_legacy_gemini_round(**kwargs)

    assert result[0] == "ok"
    assert core._gemini_tool_catalog_ready is True
    assert appended[0]["tool_calls_list"][0]["function"]["name"] == "tool_catalog"


__all__ = []
