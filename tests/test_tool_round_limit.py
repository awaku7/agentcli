from __future__ import annotations

from types import SimpleNamespace


def test_round_limit_clears_responses_continuation_before_break(monkeypatch) -> None:
    import uagent.uagent_llm as llm

    clear_reasons: list[str] = []
    response_state = {
        "provider": "openai",
        "model": "test-model",
        "previous_response_id": "resp_incomplete",
        "active_response_id": "resp_incomplete",
    }
    core = SimpleNamespace(
        responses_state=response_state,
        responses_runtime=SimpleNamespace(
            clear_continuation=lambda reason: clear_reasons.append(reason)
        ),
        clear_responses_continuation=lambda: (
            response_state.pop("previous_response_id", None),
            response_state.pop("active_response_id", None),
        ),
        memory_projection_snapshot=None,
    )

    monkeypatch.setattr(llm._core_module, "interrupt_requested", False)
    monkeypatch.setattr(llm, "load_translate_config", lambda: None)
    monkeypatch.setattr(llm, "memory_projection_access_is_current", lambda *_: True)
    monkeypatch.setattr(llm, "_build_call_messages", lambda **_: [])
    monkeypatch.setattr(llm, "apply_memory_projection", lambda messages, *_: messages)
    monkeypatch.setattr(llm, "_resolve_round_runtime_flags", lambda **_: (False, False))
    monkeypatch.setattr(
        llm.RoundTransportSelection,
        "from_flags",
        staticmethod(
            lambda **_: SimpleNamespace(
                use_responses_api=False,
                stream_responses=False,
            )
        ),
    )
    monkeypatch.setattr(llm, "_apply_semantic_message_transforms", lambda msgs, _: msgs)
    monkeypatch.setattr(llm, "project_messages_for_provider", lambda msgs, **_: msgs)
    monkeypatch.setattr(llm, "_begin_responses_runtime", lambda **_: None)
    monkeypatch.setattr(
        llm,
        "plan_provider_cache",
        lambda **_: SimpleNamespace(to_dict=lambda: {}),
    )
    monkeypatch.setattr(llm, "_spinner_stop_quietly", lambda: None)

    result = llm._run_one_round(
        "openai",
        None,
        "test-model",
        [],
        core=core,
        make_client_fn=lambda: None,
        append_result_to_outfile_fn=lambda *_: None,
        try_open_images_from_text_fn=lambda *_: None,
        round_count=2,
        max_tool_rounds=1,
        empty_no_tool_rounds=0,
        empty_no_tool_max=2,
        cache_mgr=None,
        gemini_cache_name=None,
        use_llm_thread=False,
    )

    assert result[0] == llm._RS_BREAK
    assert core._last_round_reason == "max_tool_rounds"
    assert clear_reasons == ["tool_round_limit"]
    assert "previous_response_id" not in response_state
    assert "active_response_id" not in response_state
