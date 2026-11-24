"""Per-turn context preparation isolation."""

from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.fixture
def llm(monkeypatch):
    import uagent.uagent_llm as module

    events: list[tuple[str, dict]] = []
    import uagent.runtime.logging_setup as logging_setup

    monkeypatch.setattr(
        logging_setup,
        "log_event",
        lambda event, **fields: events.append((event, fields)),
    )
    module._test_events = events
    yield module
    del module._test_events


def _patch_steps(monkeypatch, llm, calls: list[str], *, fail: set[str]) -> None:
    def step(name):
        def run(*_args, **_kwargs):
            calls.append(name)
            if name in fail:
                raise RuntimeError(name)
            return "snapshot" if name == "memory_projection" else None

        return run

    import uagent.runtime.memory_retrieval as memory_retrieval
    import uagent.runtime.sub_agent_receipt_context as receipt

    monkeypatch.setattr(
        memory_retrieval, "observe_memory_shadow_retrieval", step("shadow_retrieval")
    )
    monkeypatch.setattr(llm, "prepare_memory_projection", step("memory_projection"))
    monkeypatch.setattr(llm, "_inject_agent_state_context", step("agent_state_context"))
    monkeypatch.setattr(
        llm, "_inject_retrieved_tool_context", step("retrieved_tool_context")
    )
    monkeypatch.setattr(llm, "_update_agent_state_for_turn", step("agent_state_update"))
    monkeypatch.setattr(
        receipt, "inject_sub_agent_receipt_context", step("sub_agent_receipt_context")
    )
    monkeypatch.setattr(llm, "_apply_context_budget", step("context_budget"))
    monkeypatch.setattr(llm, "_record_context_telemetry", step("context_telemetry"))


def _core(calls: list[str], *, fail_build=False, fail_tools=False):
    def build_message_context(*_args, **_kwargs):
        calls.append("active_context")
        if fail_build:
            raise RuntimeError("active_context")
        return "fresh-context"

    def optimize_tool_definitions(*_args, **_kwargs):
        calls.append("tool_selection")
        if fail_tools:
            raise RuntimeError("tool_selection")
        return SimpleNamespace(
            specs=["fresh-spec"], decisions=[], raw_chars=10, active_chars=5
        )

    return SimpleNamespace(
        context_manager=SimpleNamespace(
            build_message_context=build_message_context,
            optimize_tool_definitions=optimize_tool_definitions,
        ),
        # Leftovers from a previous turn must never survive a failed step.
        memory_projection_snapshot="stale-snapshot",
        active_context="stale-context",
        context_tool_specs=["stale-spec"],
    )


ALL_STEPS = [
    "shadow_retrieval",
    "memory_projection",
    "agent_state_context",
    "retrieved_tool_context",
    "agent_state_update",
    "sub_agent_receipt_context",
    "context_budget",
    "active_context",
    "context_telemetry",
    "tool_selection",
]


def test_all_steps_run_in_order(monkeypatch, llm) -> None:
    calls: list[str] = []
    _patch_steps(monkeypatch, llm, calls, fail=set())
    core = _core(calls)

    llm._prepare_turn_context([{"role": "user", "content": "hi"}], core)

    assert calls == ALL_STEPS
    assert core.memory_projection_snapshot == "snapshot"
    assert core.active_context == "fresh-context"
    assert core.context_tool_specs == ["fresh-spec"]
    assert llm._test_events == []


def test_early_failure_does_not_skip_budget_or_tool_selection(monkeypatch, llm) -> None:
    calls: list[str] = []
    _patch_steps(monkeypatch, llm, calls, fail={"agent_state_context"})
    core = _core(calls)

    llm._prepare_turn_context([{"role": "user", "content": "hi"}], core)

    assert calls == ALL_STEPS
    assert core.context_tool_specs == ["fresh-spec"]
    assert llm._test_events == [
        (
            "llm.turn_prep.failed",
            {
                "step": "agent_state_context",
                "error_type": "RuntimeError",
                "status": "error",
            },
        )
    ]


def test_failed_steps_clear_previous_turn_state(monkeypatch, llm) -> None:
    calls: list[str] = []
    _patch_steps(monkeypatch, llm, calls, fail={"memory_projection"})
    core = _core(calls, fail_build=True, fail_tools=True)

    llm._prepare_turn_context([{"role": "user", "content": "hi"}], core)

    assert calls == ALL_STEPS
    assert core.memory_projection_snapshot is None
    assert core.active_context is None
    assert core.context_tool_specs is None
    assert [fields["step"] for _event, fields in llm._test_events] == [
        "memory_projection",
        "active_context",
        "tool_selection",
    ]
