from __future__ import annotations

import json
import logging
from contextlib import contextmanager

from uagent.runtime.identity_context import (
    IdentityContext,
    TurnContext,
    bind_turn_context,
)
from uagent.runtime.logging_setup import log_event
from uagent.runtime.observability.api import TraceIds
from uagent.runtime.observability import runtime as observability_runtime
from uagent.runtime.execution import lifecycle_execution, mark_tool_waiting


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


def test_web_agent_execution_forces_fresh_root(monkeypatch) -> None:
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

    with bind_turn_context(turn, identity_context=identity):
        with lifecycle_execution():
            pass

    assert backend.spans[0]["operation"] == "invoke_agent"
    assert backend.spans[0]["root"] is True
    assert backend.spans[0]["attributes"]["uag.entry_point"] == "web"
    assert "principal_id" not in backend.spans[0]["attributes"]


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
