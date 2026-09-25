from __future__ import annotations

import importlib
import sys
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

import pytest

from uagent.runtime.observability import bootstrap
from uagent.tools import context as tool_context
from uagent.tools import sub_agent_tool


@dataclass
class _FakeSpan:
    statuses: list[tuple[str, str | None]]

    def set_status(self, status: str, description: str | None = None) -> None:
        self.statuses.append((status, description))


class _FakeSpanManager:
    def __init__(self, backend: "_FakeBackend", call: dict[str, Any]) -> None:
        self.backend = backend
        self.call = call
        self.span = _FakeSpan([])
        self.token = None

    def __enter__(self) -> _FakeSpan:
        parent = self.backend.active.get()
        self.call["parent"] = parent
        self.token = self.backend.active.set(self.call["attributes"]["uag.agent.name"])
        return self.span

    def __exit__(self, exc_type, exc, traceback) -> bool:
        self.call["exc_type"] = exc_type
        self.call["statuses"] = list(self.span.statuses)
        if self.token is not None:
            self.backend.active.reset(self.token)
        return False


class _FakeBackend:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.active: ContextVar[str | None] = ContextVar(
            "fake_observability_active_subagent", default="parent"
        )

    def start_span(
        self,
        operation: str,
        *,
        attributes: dict[str, Any] | None = None,
        root: bool = False,
    ) -> _FakeSpanManager:
        call = {
            "operation": operation,
            "attributes": dict(attributes or {}),
            "root": root,
        }
        self.calls.append(call)
        return _FakeSpanManager(self, call)


def test_sub_agent_binding_opens_canonical_child_agent_span(monkeypatch) -> None:
    backend = _FakeBackend()
    monkeypatch.setattr(bootstrap, "get_observability_backend", lambda: backend)

    token = tool_context.set_active_sub_agent("planner")
    try:
        assert tool_context.get_active_sub_agent() == "planner"
        assert backend.active.get() == "planner"
    finally:
        tool_context.reset_active_sub_agent(token)

    assert tool_context.get_active_sub_agent() is None
    assert backend.active.get() == "parent"
    assert backend.calls == [
        {
            "operation": "invoke_agent",
            "attributes": {"uag.agent.name": "planner"},
            "root": False,
            "parent": "parent",
            "exc_type": None,
            "statuses": [("ok", None)],
        }
    ]


def test_untrusted_sub_agent_name_is_collapsed_before_export(monkeypatch) -> None:
    backend = _FakeBackend()
    monkeypatch.setattr(bootstrap, "get_observability_backend", lambda: backend)
    raw_name = "secret-token-from-tool-argument"

    token = tool_context.set_active_sub_agent(raw_name)
    try:
        assert tool_context.get_active_sub_agent() == raw_name
    finally:
        tool_context.reset_active_sub_agent(token)

    assert backend.calls[0]["attributes"] == {"uag.agent.name": "custom"}
    assert raw_name not in str(backend.calls[0])


def test_nested_sub_agents_inherit_current_context(monkeypatch) -> None:
    backend = _FakeBackend()
    monkeypatch.setattr(bootstrap, "get_observability_backend", lambda: backend)

    planner = tool_context.set_active_sub_agent("planner")
    try:
        reviewer = tool_context.set_active_sub_agent("reviewer")
        try:
            assert backend.active.get() == "reviewer"
        finally:
            tool_context.reset_active_sub_agent(reviewer)
        assert backend.active.get() == "planner"
    finally:
        tool_context.reset_active_sub_agent(planner)

    assert [call["parent"] for call in backend.calls] == ["parent", "planner"]
    assert [call["attributes"] for call in backend.calls] == [
        {"uag.agent.name": "planner"},
        {"uag.agent.name": "reviewer"},
    ]


def test_sub_agent_exception_is_forwarded_to_span_without_being_swallowed(
    monkeypatch,
) -> None:
    backend = _FakeBackend()
    monkeypatch.setattr(bootstrap, "get_observability_backend", lambda: backend)

    with pytest.raises(ValueError, match="boom"):
        token = tool_context.set_active_sub_agent("reviewer")
        try:
            raise ValueError("boom")
        finally:
            tool_context.reset_active_sub_agent(token)

    assert backend.calls[0]["exc_type"] is ValueError
    assert backend.calls[0]["statuses"] == []


def test_sub_agent_status_failure_restores_context_and_closes_span(monkeypatch) -> None:
    backend = _FakeBackend()
    monkeypatch.setattr(bootstrap, "get_observability_backend", lambda: backend)

    class _Callbacks:
        def set_status(self, active: bool, message: str) -> None:
            if active:
                raise RuntimeError("status unavailable")

    monkeypatch.setattr(sub_agent_tool, "get_callbacks", lambda: _Callbacks())
    reasoning_token = sub_agent_tool._SUB_AGENT_REASONING_OVERRIDE.set("parent")
    try:
        with pytest.raises(RuntimeError, match="status unavailable"):
            sub_agent_tool.run_tool(
                {"agent_name": "planner", "task": "do not execute"}
            )

        assert tool_context.get_active_sub_agent() is None
        assert backend.active.get() == "parent"
        assert sub_agent_tool._SUB_AGENT_REASONING_OVERRIDE.get() == "parent"
    finally:
        sub_agent_tool._SUB_AGENT_REASONING_OVERRIDE.reset(reasoning_token)

    assert backend.calls[0]["exc_type"] is RuntimeError


def test_observability_failure_does_not_break_sub_agent_binding(monkeypatch) -> None:
    class _BrokenBackend:
        def start_span(self, *args, **kwargs):
            raise RuntimeError("otel unavailable")

    monkeypatch.setattr(
        bootstrap, "get_observability_backend", lambda: _BrokenBackend()
    )

    token = tool_context.set_active_sub_agent("planner")
    try:
        assert tool_context.get_active_sub_agent() == "planner"
    finally:
        tool_context.reset_active_sub_agent(token)

    assert tool_context.get_active_sub_agent() is None


def test_legacy_plain_contextvar_token_can_be_reset() -> None:
    legacy_context: ContextVar[str | None] = ContextVar(
        "legacy_active_sub_agent", default=None
    )
    token = legacy_context.set("planner")

    tool_context.reset_active_sub_agent(token)

    assert legacy_context.get() is None


def test_sub_agent_token_survives_real_tools_context_reimport(monkeypatch) -> None:
    backend = _FakeBackend()
    monkeypatch.setattr(bootstrap, "get_observability_backend", lambda: backend)

    module_name = tool_context.__name__
    package = sys.modules["uagent.tools"]
    original_module = sys.modules[module_name]
    original_package_context = getattr(package, "context", None)
    token = tool_context.set_active_sub_agent("planner")
    reset_done = False
    try:
        sys.modules.pop(module_name, None)
        reloaded = importlib.import_module(module_name)
        assert reloaded is not original_module
        assert reloaded.get_active_sub_agent() == "planner"
        reloaded.reset_active_sub_agent(token)
        reset_done = True
        assert reloaded.get_active_sub_agent() is None
    finally:
        if not reset_done:
            tool_context.reset_active_sub_agent(token)
        sys.modules[module_name] = original_module
        if original_package_context is not None:
            setattr(package, "context", original_package_context)

    assert backend.active.get() == "parent"
