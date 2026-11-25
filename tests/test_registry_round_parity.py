"""Registry round path behaves like the legacy path (INT-05).

The registry path (provider runtime registry + RoundOrchestrator) was
unreachable in practice because of a context-decision conversion bug, so it
drifted from the legacy path. These tests pin the behaviour it must share
with the legacy path before it is enabled again.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest


def _patch_round_preamble(monkeypatch, llm) -> None:
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
            lambda **_: SimpleNamespace(use_responses_api=False, stream_responses=False)
        ),
    )
    monkeypatch.setattr(
        llm, "build_auto_shrink_projection", lambda **_: SimpleNamespace(changed=False)
    )
    monkeypatch.setattr(llm, "_record_round_context_plan", lambda **_: None)
    monkeypatch.setattr(llm, "_reconcile_system_prompt_for_route", lambda *a, **k: None)
    monkeypatch.setattr(llm, "_apply_semantic_message_transforms", lambda msgs, _: msgs)
    monkeypatch.setattr(llm, "project_messages_for_provider", lambda msgs, **_: msgs)
    monkeypatch.setattr(llm, "_begin_responses_runtime", lambda **_: None)
    monkeypatch.setattr(
        llm, "plan_provider_cache", lambda **_: SimpleNamespace(to_dict=lambda: {})
    )
    monkeypatch.setattr(llm, "_sync_responses_runtime_completed", lambda **_: None)
    monkeypatch.setattr(llm, "_record_responses_runtime_response", lambda **_: None)
    monkeypatch.setattr(llm, "_spinner_stop_quietly", lambda: None)


@pytest.fixture
def registry_round(monkeypatch):
    """Run one round whose provider dispatch returns a registry final answer."""
    import uagent.runtime.provider_round_dispatcher as dispatcher
    import uagent.uagent_llm as llm

    _patch_round_preamble(monkeypatch, llm)
    emitted: list[str] = []
    monkeypatch.setattr(
        llm,
        "_emit_final_answer_if_any",
        lambda *, assistant_text, **_: emitted.append(assistant_text),
    )
    monkeypatch.setattr(
        dispatcher,
        "resolve_registry_round_route",
        lambda **_: dispatcher.RegistryRoundRoute(True, "test"),
    )

    def run(*, answer: str, judgment_mode: bool = False):
        raw_result = (True, answer, "", [])
        monkeypatch.setattr(
            dispatcher,
            "dispatch_provider_round",
            lambda **_: SimpleNamespace(
                source="registry",
                result=raw_result,
                outcome=SimpleNamespace(raw_result=raw_result),
                handles_collected_result=True,
                owns_tool_execution=False,
                supports_tool_continuation=False,
                host_rendered=False,
            ),
        )
        logged: list[dict] = []
        core = SimpleNamespace(
            responses_state={},
            memory_projection_snapshot=None,
            set_status=lambda *a, **k: None,
            log_message=logged.append,
        )
        messages: list[dict] = [{"role": "user", "content": "hello"}]
        result = llm._run_one_round(
            "openai",
            None,
            "test-model",
            messages,
            core=core,
            make_client_fn=lambda: None,
            append_result_to_outfile_fn=lambda *_: None,
            try_open_images_from_text_fn=lambda *_: None,
            round_count=1,
            max_tool_rounds=10,
            empty_no_tool_rounds=0,
            empty_no_tool_max=2,
            cache_mgr=None,
            gemini_cache_name=None,
            use_llm_thread=False,
            judgment_mode=judgment_mode,
        )
        return llm, result, messages, emitted, logged

    return run


def test_registry_final_answer_is_stored_in_history(registry_round) -> None:
    llm, result, messages, emitted, logged = registry_round(answer="final answer")

    assert result.status == llm._RS_BREAK
    assert messages[-1]["role"] == "assistant"
    assert messages[-1]["content"] == "final answer"
    assert any(m.get("role") == "assistant" for m in logged)
    assert emitted == ["final answer"]


def test_registry_final_answer_is_not_printed_in_judgment_mode(registry_round) -> None:
    _llm, _result, messages, emitted, _logged = registry_round(
        answer="COMPLETE", judgment_mode=True
    )

    assert messages[-1]["content"] == "COMPLETE"
    assert emitted == []
