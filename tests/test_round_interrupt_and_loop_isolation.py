"""Round-loop regressions: interrupt boundary and loop-guard isolation.

1. An interrupt that arrives while the provider call is in flight must be
   honoured before tool execution on every dispatch path (registry and
   OpenAI-compatible).
2. Loop-guard state belongs to one conversation. A2A with
   UAGENT_A2A_CONCURRENCY>1 runs Tasks as threads in one process, so one Task
   must neither trip nor reset another Task's guard.
"""

from __future__ import annotations

import json
import threading
from types import SimpleNamespace

# ---------------------------------------------------------------------------
# 1. Interrupt during the provider call
# ---------------------------------------------------------------------------

_TOOL_CALL = {
    "id": "call_1",
    "type": "function",
    "function": {"name": "cmd_exec_json", "arguments": json.dumps({"cmd": "x"})},
}


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
    monkeypatch.setattr(
        llm,
        "_append_assistant_message",
        lambda *, messages, assistant_text, tool_calls_list, **_: messages.append(
            {
                "role": "assistant",
                "content": assistant_text,
                "tool_calls": tool_calls_list,
            }
        ),
    )


def _run_round_with_interrupt_during_call(monkeypatch, *, source: str, raw_result):
    import uagent.uagent_llm as llm
    import uagent.runtime.provider_round_dispatcher as dispatcher

    _patch_round_preamble(monkeypatch, llm)

    def fake_dispatch(**_kwargs):
        # The user presses Ctrl+C while the provider request is in flight.
        llm._core_module.interrupt_requested = True
        return SimpleNamespace(
            source=source,
            result=raw_result,
            outcome=SimpleNamespace(raw_result=raw_result),
            handles_collected_result=(source == "registry"),
            owns_tool_execution=False,
            supports_tool_continuation=True,
            host_rendered=False,
        )

    monkeypatch.setattr(dispatcher, "dispatch_provider_round", fake_dispatch)
    monkeypatch.setattr(
        dispatcher,
        "resolve_registry_round_route",
        lambda **_: dispatcher.RegistryRoundRoute(source == "registry", "test"),
    )

    executed: list[list[dict]] = []

    def fake_execute(*, tool_calls_list, **_):
        executed.append(tool_calls_list)
        return True, list(tool_calls_list)

    monkeypatch.setattr(llm, "execute_tool_continuation", fake_execute)
    stop_prompts: list[bool] = []
    monkeypatch.setattr(
        llm, "_inject_stop_prompt", lambda *_: stop_prompts.append(True)
    )

    core = SimpleNamespace(
        responses_state={},
        memory_projection_snapshot=None,
        set_status=lambda *a, **k: None,
        log_message=lambda *_: None,
    )
    result = llm._run_one_round(
        "openai",
        None,
        "test-model",
        [],
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
    )
    return llm, result, executed, stop_prompts


def test_openai_path_honours_interrupt_before_tool_execution(monkeypatch) -> None:
    """Control case: the OpenAI-compatible path already behaves correctly."""
    llm, result, executed, stop_prompts = _run_round_with_interrupt_during_call(
        monkeypatch,
        source="openai_compatible",
        raw_result=(True, None, "", "", [dict(_TOOL_CALL)], False),
    )
    assert result[0] == llm._RS_BREAK
    assert executed == []
    assert stop_prompts == [True]


def test_registry_path_honours_interrupt_before_tool_execution(monkeypatch) -> None:
    """Issue 1: the registry path runs the tool despite the pending interrupt."""
    llm, result, executed, stop_prompts = _run_round_with_interrupt_during_call(
        monkeypatch,
        source="registry",
        raw_result=(True, "", "", [dict(_TOOL_CALL)]),
    )
    assert executed == [], "tool executed although interrupt was requested"
    assert result[0] == llm._RS_BREAK
    assert stop_prompts == [True]


# ---------------------------------------------------------------------------
# 2. Loop-guard state isolated per concurrent session
# ---------------------------------------------------------------------------


def _tool_load(target: str) -> list[dict]:
    return [
        {
            "id": f"call_{target}",
            "type": "function",
            "function": {
                "name": "tool_load",
                "arguments": json.dumps({"name": target}),
            },
        }
    ]


def _run_interleaved(session_a, session_b) -> None:
    """Run two session callables in separate threads, A then B then A.

    Each callable receives ``step(n)`` which blocks until it is that session's
    turn, mirroring two A2A Tasks running in worker threads concurrently.
    """
    turn = threading.Condition()
    state = {"step": 0}
    errors: list[BaseException] = []

    def make_step():
        def step(n: int) -> None:
            with turn:
                turn.wait_for(lambda: state["step"] == n, timeout=5)

        return step

    def advance() -> None:
        with turn:
            state["step"] += 1
            turn.notify_all()

    def wrap(fn):
        def runner() -> None:
            try:
                fn(make_step(), advance)
            except BaseException as exc:  # surface assertion errors
                errors.append(exc)
                advance()

        return runner

    threads = [
        threading.Thread(target=wrap(session_a)),
        threading.Thread(target=wrap(session_b)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    if errors:
        raise errors[0]


def test_other_session_does_not_trip_loop_guard() -> None:
    """Session B's first tool_load is not counted against A's history."""
    import uagent.uagent_llm as llm

    result: dict[str, tuple] = {}

    def session_a(step, advance) -> None:
        llm.begin_loop_guard_turn()
        step(0)
        for _ in range(3):  # below threshold 4
            blocked, *_ = llm.check_mgmt_tool_loop(_tool_load("file_grep"))
            assert not blocked
        advance()

    def session_b(step, advance) -> None:
        llm.begin_loop_guard_turn()
        step(1)
        result["b"] = llm.check_mgmt_tool_loop(_tool_load("file_grep"))
        advance()

    _run_interleaved(session_a, session_b)
    blocked_b, name, count = result["b"]
    assert not blocked_b, f"session B blocked on its first call ({name} x{count})"


def test_other_session_turn_start_does_not_reset_loop_guard() -> None:
    """B starting a new turn does not clear A's counters."""
    import uagent.uagent_llm as llm

    result: dict[str, bool] = {}

    def session_a(step, advance) -> None:
        llm.begin_loop_guard_turn()
        blocked_any = False
        step(0)
        for _ in range(3):
            blocked, *_ = llm.check_mgmt_tool_loop(_tool_load("file_grep"))
            blocked_any = blocked_any or blocked
        advance()
        step(2)
        for _ in range(3):
            blocked, *_ = llm.check_mgmt_tool_loop(_tool_load("file_grep"))
            blocked_any = blocked_any or blocked
        result["a_blocked"] = blocked_any
        advance()

    def session_b(step, advance) -> None:
        step(1)
        # What run_llm_rounds does for a new user turn.
        llm.begin_loop_guard_turn()
        advance()

    _run_interleaved(session_a, session_b)
    assert result["a_blocked"], "session A repeated tool_load 6 times unblocked"


def test_consecutive_streak_is_isolated_between_sessions() -> None:
    """The same-tool streak default no longer lives in module globals."""
    import uagent.uagent_llm as llm

    counts: dict[str, int] = {}

    def session_a(step, advance) -> None:
        llm.begin_loop_guard_turn()
        step(0)
        for _ in range(3):
            _, _, counts["a"] = llm.check_consecutive_tool_calls(
                [
                    _tool_load("x")[0]
                    | {"function": {"name": "read_file", "arguments": "{}"}}
                ]
            )
        advance()

    def session_b(step, advance) -> None:
        llm.begin_loop_guard_turn()
        step(1)
        _, _, counts["b"] = llm.check_consecutive_tool_calls(
            [{"id": "c", "function": {"name": "read_file", "arguments": "{}"}}]
        )
        advance()

    _run_interleaved(session_a, session_b)
    assert counts == {"a": 3, "b": 1}


def test_auto_pilot_preserve_keeps_counters_in_same_context() -> None:
    """preserve_tool_loop_state reuses the context's state (Auto-Pilot path)."""
    import uagent.uagent_llm as llm

    first = llm.begin_loop_guard_turn()
    llm.check_mgmt_tool_loop(_tool_load("file_grep"))
    assert llm._loop_guard_state() is first
    assert llm._TOOL_CALL_FINGERPRINTS["tool_load:file_grep"] == 1
    llm.begin_loop_guard_turn()
    assert "tool_load:file_grep" not in llm._TOOL_CALL_FINGERPRINTS
