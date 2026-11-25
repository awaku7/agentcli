"""Registry round path behaves like the legacy path (INT-05).

The registry path (provider runtime registry + RoundOrchestrator) was
unreachable in practice because of a context-decision conversion bug, so it
drifted from the legacy path. These tests pin the behaviour it must share
with the legacy path before it is enabled again.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from uagent.runtime.active_context import ContextDecision
from uagent.llm_registry_round import (
    _CoreInterruptCancellationToken,
    _registry_stream_event_observer,
    _try_registry_simple_chat_round,
)


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
    emit_skip_print: list[bool] = []
    monkeypatch.setattr(
        llm,
        "_emit_final_answer_if_any",
        lambda *, assistant_text, skip_print=False, **_: (
            emitted.append(assistant_text),
            emit_skip_print.append(skip_print),
        ),
    )
    monkeypatch.setattr(
        dispatcher,
        "resolve_registry_round_route",
        lambda **_: dispatcher.RegistryRoundRoute(True, "test"),
    )

    def run(*, answer: str, judgment_mode: bool = False, stream_rendered: bool = False):
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
            _registry_stream_output_rendered=stream_rendered,
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
        return llm, result, messages, emitted, logged, emit_skip_print

    return run


def test_registry_final_answer_is_stored_in_history(registry_round) -> None:
    llm, result, messages, emitted, logged, _skip_print = registry_round(
        answer="final answer"
    )

    assert result.status == llm._RS_BREAK
    assert messages[-1]["role"] == "assistant"
    assert messages[-1]["content"] == "final answer"
    assert any(m.get("role") == "assistant" for m in logged)
    assert emitted == ["final answer"]


def test_registry_final_answer_is_not_printed_in_judgment_mode(registry_round) -> None:
    _llm, _result, messages, emitted, _logged, _skip_print = registry_round(
        answer="COMPLETE", judgment_mode=True
    )

    assert messages[-1]["content"] == "COMPLETE"
    assert emitted == []


def test_registry_stream_events_render_deltas_incrementally() -> None:
    emitted: list[str] = []
    core = SimpleNamespace(print_stream_delta=emitted.append)
    observe = _registry_stream_event_observer(core, streaming=True)

    observe(SimpleNamespace(type="ResponseStarted", data={}))
    observe(SimpleNamespace(type="TextDelta", data={"text": "first "}))
    observe(SimpleNamespace(type="TextDelta", data={"text": "answer"}))

    assert emitted == ["first ", "answer"]
    assert core._registry_stream_output_rendered is True


def test_registry_stream_snapshots_render_only_new_suffixes() -> None:
    emitted: list[str] = []
    core = SimpleNamespace(print_stream_delta=emitted.append)
    observe = _registry_stream_event_observer(core, streaming=True)

    observe(SimpleNamespace(type="TextSnapshot", data={"text": "first"}))
    observe(SimpleNamespace(type="TextSnapshot", data={"text": "first answer"}))

    assert emitted == ["first", " answer"]
    assert core._registry_stream_output_rendered is True


def test_registry_streamed_answer_is_not_printed_again(registry_round) -> None:
    _llm, _result, _messages, _emitted, _logged, skip_print = registry_round(
        answer="already displayed", stream_rendered=True
    )

    assert skip_print == [True]


def test_registry_cancellation_token_tracks_interrupt_flag() -> None:
    core = SimpleNamespace(interrupt_lock=threading.Lock(), interrupt_requested=False)
    token = _CoreInterruptCancellationToken(core)

    assert token.is_cancelled() is False
    with core.interrupt_lock:
        core.interrupt_requested = True
    assert token.is_cancelled() is True


def test_registry_cancelled_round_does_not_fall_back_to_legacy(
    monkeypatch,
) -> None:
    import uagent.providers.openai_projection_policy as projection_policy
    from uagent.providers.openai_compatible_runtime import OpenAICompatibleRuntime
    import uagent.providers.runtime_registry as runtime_registry
    from uagent.runtime.round_contracts import ProviderRuntimeRegistry
    import uagent.llm_registry_round as registry_round

    emitted: list[str] = []
    core = SimpleNamespace(
        interrupt_lock=threading.Lock(),
        interrupt_requested=False,
        context_plan=None,
        context_tool_specs=(),
        context_tool_decisions=(
            ContextDecision(
                item_id="result-1",
                source="tool_result",
                section="tool_results",
                action="KEEP",
                reason="within budget",
            ),
        ),
        context_schema_revision="1",
        history_revision="",
        responses_state={},
        workdir=".",
        print_stream_delta=emitted.append,
        round_identity_factory=SimpleNamespace(
            projection_id=lambda *_: "projection",
            key_provider=SimpleNamespace(get_key=lambda *_: b"x" * 32),
        ),
    )
    discovery = SimpleNamespace(
        uses_legacy_catalog=False,
        uses_native_search=False,
        uses_management_bootstrap=lambda **_: False,
    )

    class InterruptingStream:
        closed = False
        sent = 0

        def __iter__(self):
            for index in range(20):
                self.sent += 1
                yield SimpleNamespace(
                    choices=[
                        SimpleNamespace(delta=SimpleNamespace(content=f"tok{index}"))
                    ]
                )
                if index == 1:
                    with core.interrupt_lock:
                        core.interrupt_requested = True

        def close(self):
            self.closed = True

    stream = InterruptingStream()
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_: stream))
    )

    monkeypatch.setattr(registry_round, "_get_shrink_max_tokens", lambda *_: 0)
    monkeypatch.setattr(
        projection_policy,
        "build_openai_projection",
        lambda **_: SimpleNamespace(
            options={}, reasoning="", auto_user_text="", effort_used=None
        ),
    )

    def build_runtime_registry(**kwargs):
        runtimes = ProviderRuntimeRegistry()
        runtimes.register(
            "openai",
            OpenAICompatibleRuntime(
                client=kwargs["client"],
                provider=kwargs["provider"],
                model=kwargs["model"],
                identifiers=kwargs["identifiers"],
                transport=kwargs["transport"],
                streaming=kwargs["streaming"],
                options=kwargs["options"],
            ),
        )
        return runtimes

    monkeypatch.setattr(
        runtime_registry, "build_provider_runtime_registry", build_runtime_registry
    )

    result = _try_registry_simple_chat_round(
        provider="openai",
        client=client,
        depname="test-model",
        call_messages=[{"role": "user", "content": "hello"}],
        core=core,
        use_responses_api=False,
        stream_responses=True,
        send_tools_this_round=False,
        round_count=1,
        registry_route=SimpleNamespace(allowed=True),
        tool_discovery=discovery,
    )

    assert result == (True, "", "", [])
    assert core._last_round_reason == "interrupted"
    assert emitted == ["tok0", "tok1", "\n"]
    assert core._registry_stream_output_rendered is True
    assert stream.sent < 20
    assert stream.closed is True
