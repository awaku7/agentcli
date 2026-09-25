from __future__ import annotations

import json
import logging
from contextlib import contextmanager

import pytest

from uagent.runtime.identity_context import IdentityContext, TurnContext
from uagent.runtime.logging_setup import log_event
from uagent.runtime.observability.api import TraceIds
from uagent.runtime.observability import runtime as observability_runtime
from uagent.runtime.execution import (
    lifecycle_execution,
    mark_tool_running,
    mark_tool_waiting,
)


class _Span:
    def __init__(self) -> None:
        self.attributes = {}
        self.events = []
        self.status = []

    def set_attribute(self, key, value) -> None:
        self.attributes[key] = value

    def add_event(self, name, attributes=None) -> None:
        self.events.append((name, dict(attributes or {})))

    def record_exception(self, exc) -> None:
        self.events.append(("exception", {"type": type(exc).__name__}))

    def set_status(self, status, description=None) -> None:
        self.status.append((status, description))


class _Backend:
    enabled = True

    def __init__(self) -> None:
        self.spans = []
        self.active = []

    @contextmanager
    def start_span(self, operation, *, attributes=None, root=False):
        span = _Span()
        record = {
            "operation": operation,
            "attributes": dict(attributes or {}),
            "root": root,
            "span": span,
        }
        self.spans.append(record)
        self.active.append(span)
        try:
            yield span
        finally:
            self.active.pop()

    def record_event(self, name, attributes=None):
        return None

    def current_trace_ids(self):
        if not self.active:
            return TraceIds()
        return TraceIds("1" * 32, "2" * 16)


def test_web_agent_execution_forces_fresh_root_from_explicit_turn(monkeypatch) -> None:
    backend = _Backend()
    monkeypatch.setattr(
        "uagent.runtime.observability.bootstrap.get_observability_backend",
        lambda: backend,
    )
    identity = IdentityContext("user-A", True, "oidc")
    turn = TurnContext.from_identity(
        identity,
        room_id="shared",
        entry_point="web",
    )

    with lifecycle_execution(turn_context=turn):
        pass

    assert backend.spans[0]["operation"] == "invoke_agent"
    assert backend.spans[0]["root"] is True
    assert backend.spans[0]["attributes"]["uag.entry_point"] == "web"
    assert backend.spans[0]["attributes"]["uag.auth.kind"] == "oidc"
    assert "principal_id" not in backend.spans[0]["attributes"]


def test_non_web_agent_execution_projects_explicit_turn_metadata(monkeypatch) -> None:
    backend = _Backend()
    monkeypatch.setattr(
        "uagent.runtime.observability.bootstrap.get_observability_backend",
        lambda: backend,
    )
    identity = IdentityContext("local", True, "local")
    turn = TurnContext.from_identity(identity, entry_point="cli")

    with lifecycle_execution(turn_context=turn):
        pass

    assert backend.spans[0]["root"] is False
    assert backend.spans[0]["attributes"]["uag.entry_point"] == "cli"
    assert backend.spans[0]["attributes"]["uag.auth.kind"] == "local"
    assert "principal_id" not in backend.spans[0]["attributes"]


def test_agent_span_status_follows_terminal_lifecycle_state(monkeypatch) -> None:
    backend = _Backend()
    monkeypatch.setattr(
        "uagent.runtime.observability.bootstrap.get_observability_backend",
        lambda: backend,
    )

    with lifecycle_execution() as lifecycle:
        lifecycle.fail()

    failed_span = backend.spans[-1]["span"]
    assert failed_span.attributes["uag.agent.lifecycle_status"] == "failed"
    assert failed_span.status[-1] == ("error", "failed")

    with lifecycle_execution() as lifecycle:
        lifecycle.cancel()

    cancelled_span = backend.spans[-1]["span"]
    assert cancelled_span.attributes["uag.agent.lifecycle_status"] == "cancelled"
    assert cancelled_span.status[-1] == ("unset", "cancelled")


def test_tool_dispatch_starts_execute_tool_span_only_when_runner_starts(
    monkeypatch,
) -> None:
    backend = _Backend()
    monkeypatch.setattr(
        observability_runtime, "get_observability_backend", lambda: backend
    )
    observability_runtime._reset_runtime_observability_for_tests()

    observability_runtime.before_structured_event(
        "tool.dispatch", {"tool": "read_file", "side_effect": "read"}
    )
    assert backend.spans == []

    mark_tool_waiting()
    assert backend.spans[0]["operation"] == "execute_tool"
    assert backend.spans[0]["attributes"] == {
        "uag.tool.name": "read_file",
        "uag.tool.side_effect": "read",
    }

    observability_runtime.before_structured_event(
        "tool.completed", {"tool": "read_file"}
    )
    observability_runtime.after_structured_event("tool.completed")
    assert backend.spans[0]["span"].status[-1] == ("ok", None)


def test_nested_tool_spans_close_inner_before_outer(monkeypatch) -> None:
    backend = _Backend()
    monkeypatch.setattr(
        observability_runtime, "get_observability_backend", lambda: backend
    )
    observability_runtime._reset_runtime_observability_for_tests()

    observability_runtime.before_structured_event(
        "tool.dispatch", {"tool": "sub_agent", "side_effect": "write"}
    )
    mark_tool_waiting()
    observability_runtime.before_structured_event(
        "tool.dispatch", {"tool": "read_file", "side_effect": "read"}
    )
    mark_tool_waiting()

    assert [record["attributes"]["uag.tool.name"] for record in backend.spans] == [
        "sub_agent",
        "read_file",
    ]
    assert len(backend.active) == 2

    observability_runtime.before_structured_event(
        "tool.completed", {"tool": "read_file"}
    )
    observability_runtime.after_structured_event("tool.completed")
    assert len(backend.active) == 1
    assert backend.spans[1]["span"].status[-1] == ("ok", None)

    observability_runtime.before_structured_event(
        "tool.completed", {"tool": "sub_agent"}
    )
    observability_runtime.after_structured_event("tool.completed")
    assert backend.active == []
    assert backend.spans[0]["span"].status[-1] == ("ok", None)


def test_keyboard_interrupt_abandons_active_tool_span(monkeypatch) -> None:
    backend = _Backend()
    monkeypatch.setattr(
        observability_runtime, "get_observability_backend", lambda: backend
    )
    observability_runtime._reset_runtime_observability_for_tests()

    observability_runtime.before_structured_event(
        "tool.dispatch", {"tool": "cmd_exec", "side_effect": "write"}
    )
    mark_tool_waiting()
    assert len(backend.active) == 1

    def interrupt_runner_cleanup() -> None:
        try:
            raise KeyboardInterrupt()
        finally:
            mark_tool_running()

    with pytest.raises(KeyboardInterrupt):
        interrupt_runner_cleanup()

    assert backend.active == []
    assert backend.spans[0]["span"].attributes["uag.status"] == "abandoned"
    assert backend.spans[0]["span"].status[-1] == (
        "error",
        "tool span abandoned",
    )


def test_structured_event_includes_active_trace_ids(monkeypatch, caplog) -> None:
    backend = _Backend()
    monkeypatch.setattr(
        "uagent.runtime.observability.bootstrap.get_observability_backend",
        lambda: backend,
    )

    with caplog.at_level(logging.INFO, logger="uagent.events"):
        with backend.start_span("test"):
            log_event("llm.round.completed", provider="fake", model="fake-model")

    payload = json.loads(caplog.records[-1].message)
    assert payload["trace_id"] == "1" * 32
    assert payload["span_id"] == "2" * 16
