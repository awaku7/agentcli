from __future__ import annotations

from contextlib import contextmanager
from contextvars import copy_context
from types import SimpleNamespace

import pytest

from uagent.runtime.observability.noop import NOOP_SPAN
from uagent.runtime.observability.semantic_mapping import map_span
from uagent.runtime.observability.settings import ObservabilitySettings
from uagent.runtime.round_contracts import (
    ContextPlan,
    ProviderProjection,
    ProviderRuntimeRegistry,
    RoundIdentifiers,
    SerializedRequest,
    StreamEvent,
)
from uagent.runtime.round_orchestrator import RoundOrchestrator


class _Span:
    def __init__(self) -> None:
        self.attributes = {}
        self.statuses = []
        self.events = []
        self.exceptions = []

    def set_attribute(self, key, value) -> None:
        self.attributes[key] = value

    def add_event(self, name, attributes=None) -> None:
        self.events.append((name, dict(attributes or {})))

    def add_content_event(self, event) -> bool:
        return False

    def record_exception(self, exc) -> None:
        self.exceptions.append(type(exc).__name__)

    def set_status(self, status, description=None) -> None:
        self.statuses.append((status, description))


class _Backend:
    enabled = True

    def __init__(self) -> None:
        self.records = []
        self._stack = []

    @contextmanager
    def start_span(self, operation, *, attributes=None, root=False):
        span = _Span()
        record = {
            "operation": operation,
            "attributes": dict(attributes or {}),
            "parent": self._stack[-1]["operation"] if self._stack else None,
            "root": root,
            "span": span,
        }
        self.records.append(record)
        self._stack.append(record)
        try:
            yield span
        finally:
            assert self._stack[-1] is record
            self._stack.pop()

    def record_event(self, name, attributes=None):
        return None

    def current_trace_ids(self):
        return None


class _ChatFailureBackend(_Backend):
    @contextmanager
    def start_span(self, operation, *, attributes=None, root=False):
        if operation == "chat":
            self.records.append(
                {
                    "operation": operation,
                    "attributes": dict(attributes or {}),
                    "parent": self._stack[-1]["operation"] if self._stack else None,
                    "root": root,
                    "span": NOOP_SPAN,
                }
            )
            yield NOOP_SPAN
            return
        with super().start_span(
            operation,
            attributes=attributes,
            root=root,
        ) as span:
            yield span


class _Cancellation:
    def is_cancelled(self):
        return False


class _Runtime:
    def __init__(self, terminal_type="ResponseCompleted") -> None:
        self.terminal_type = terminal_type

    def project(self, plan, session):
        return ProviderProjection(
            plan.plan_id,
            "projection",
            "openai",
            "gpt-test",
            "chat",
            plan.messages,
        )

    def serialize(self, projection):
        return SerializedRequest(
            RoundIdentifiers("turn", "round", "attempt", "request", "stream", 0),
            projection.plan_id,
            projection.projection_id,
            "openai",
            "gpt-test",
            {},
        )

    def run(self, request, cancellation):
        yield StreamEvent(
            "ResponseStarted",
            request.identifiers,
            0,
            0.0,
            {"stream_mode": "delta"},
        )
        data = (
            {"response_id": "resp"} if self.terminal_type == "ResponseCompleted" else {}
        )
        yield StreamEvent(self.terminal_type, request.identifiers, 1, 0.0, data)


def _settings(*providers: str) -> ObservabilitySettings:
    return ObservabilitySettings(
        enabled=True,
        provider_instrumentation=frozenset(providers),
    )


def _install_runtime(
    monkeypatch,
    backend: _Backend,
    settings: ObservabilitySettings,
) -> None:
    monkeypatch.setattr(
        "uagent.runtime.observability.runtime.get_observability_backend",
        lambda: backend,
    )
    monkeypatch.setattr(
        "uagent.runtime.observability.settings.get_observability_settings",
        lambda: settings,
    )


def test_phase4c_registry_openai_emits_one_closed_child_span(monkeypatch) -> None:
    backend = _Backend()
    _install_runtime(monkeypatch, backend, _settings("openai"))
    monkeypatch.setattr(
        "uagent.runtime.round_orchestrator.get_observability_backend",
        lambda: backend,
    )

    registry = ProviderRuntimeRegistry()
    registry.register("openai", _Runtime())
    RoundOrchestrator(registry).run(
        ContextPlan("plan", ({"role": "user", "content": "hello"},)),
        provider="openai",
        session={},
        cancellation=_Cancellation(),
    )

    provider_records = [
        record for record in backend.records if record["operation"] == "provider_sdk"
    ]
    assert len(provider_records) == 1
    record = provider_records[0]
    assert record["parent"] == "chat"
    assert record["attributes"] == {"uag.provider.id": "openai"}
    assert record["span"].statuses == [("ok", None)]
    assert record["span"].events == []
    assert record["span"].exceptions == []


def test_phase4c_registry_failure_sets_error_without_exception_payload(
    monkeypatch,
) -> None:
    backend = _Backend()
    _install_runtime(monkeypatch, backend, _settings("openai"))
    monkeypatch.setattr(
        "uagent.runtime.round_orchestrator.get_observability_backend",
        lambda: backend,
    )

    registry = ProviderRuntimeRegistry()
    registry.register("openai", _Runtime("ResponseFailed"))
    RoundOrchestrator(registry).run(
        ContextPlan("plan", ({"role": "user", "content": "hello"},)),
        provider="openai",
        session={},
        cancellation=_Cancellation(),
    )

    record = next(
        record for record in backend.records if record["operation"] == "provider_sdk"
    )
    assert record["span"].statuses == [("error", None)]
    assert record["span"].events == []
    assert record["span"].exceptions == []


def test_phase4c_failed_canonical_chat_cannot_export_root_provider_child(
    monkeypatch,
) -> None:
    backend = _ChatFailureBackend()
    _install_runtime(monkeypatch, backend, _settings("openai"))
    monkeypatch.setattr(
        "uagent.runtime.round_orchestrator.get_observability_backend",
        lambda: backend,
    )

    registry = ProviderRuntimeRegistry()
    registry.register("openai", _Runtime())
    result = RoundOrchestrator(registry).run(
        ContextPlan("plan", ({"role": "user", "content": "hello"},)),
        provider="openai",
        session={},
        cancellation=_Cancellation(),
    )

    assert result.result.status == "completed"
    assert [record["operation"] for record in backend.records] == ["chat"]


def test_phase4c_selected_provider_without_canonical_scope_emits_no_child(
    monkeypatch,
) -> None:
    from uagent.runtime.observability.runtime import provider_sdk_diagnostic_span

    backend = _Backend()
    _install_runtime(monkeypatch, backend, _settings("openai"))

    with backend.start_span("chat"):
        with provider_sdk_diagnostic_span("openai"):
            pass

    assert [record["operation"] for record in backend.records] == ["chat"]


def test_phase4c_unselected_provider_emits_no_child(monkeypatch) -> None:
    from uagent.runtime.observability.runtime import (
        canonical_chat_diagnostic_scope,
        provider_sdk_diagnostic_span,
    )

    backend = _Backend()
    _install_runtime(monkeypatch, backend, _settings("claude"))

    with backend.start_span("chat") as chat_span:
        with canonical_chat_diagnostic_scope(chat_span, backend):
            with provider_sdk_diagnostic_span("openai"):
                pass

    assert [record["operation"] for record in backend.records] == ["chat"]


def test_phase4c_provider_exception_is_not_copied_to_child(monkeypatch) -> None:
    from uagent.runtime.observability.runtime import (
        canonical_chat_diagnostic_scope,
        provider_sdk_diagnostic_span,
    )

    backend = _Backend()
    _install_runtime(monkeypatch, backend, _settings("openai"))

    with pytest.raises(RuntimeError, match="secret provider failure"):
        with backend.start_span("chat") as chat_span:
            with canonical_chat_diagnostic_scope(chat_span, backend):
                with provider_sdk_diagnostic_span("openai"):
                    raise RuntimeError("secret provider failure")

    record = next(
        record for record in backend.records if record["operation"] == "provider_sdk"
    )
    assert record["span"].statuses == [("error", None)]
    assert record["span"].events == []
    assert record["span"].exceptions == []


def test_phase4c_copied_contexts_share_one_terminal_child_claim(monkeypatch) -> None:
    from uagent.runtime.observability.runtime import (
        canonical_chat_diagnostic_scope,
        provider_sdk_diagnostic_span,
    )

    backend = _Backend()
    _install_runtime(monkeypatch, backend, _settings("openai"))

    def attach() -> None:
        with provider_sdk_diagnostic_span("openai"):
            pass

    with backend.start_span("chat") as chat_span:
        with canonical_chat_diagnostic_scope(chat_span, backend):
            first = copy_context()
            second = copy_context()
            first.run(attach)
            second.run(attach)

    provider_records = [
        record for record in backend.records if record["operation"] == "provider_sdk"
    ]
    assert len(provider_records) == 1
    assert provider_records[0]["parent"] == "chat"


def test_phase4c_copied_context_cannot_create_child_after_scope_exit(
    monkeypatch,
) -> None:
    from uagent.runtime.observability.runtime import (
        canonical_chat_diagnostic_scope,
        provider_sdk_diagnostic_span,
    )

    backend = _Backend()
    _install_runtime(monkeypatch, backend, _settings("openai"))

    def attach() -> None:
        with provider_sdk_diagnostic_span("openai"):
            pass

    with backend.start_span("chat") as chat_span:
        with canonical_chat_diagnostic_scope(chat_span, backend):
            late_context = copy_context()

    late_context.run(attach)

    assert [record["operation"] for record in backend.records] == ["chat"]


def test_phase4c_child_uses_backend_owned_by_canonical_chat_scope(monkeypatch) -> None:
    from uagent.runtime.observability.runtime import (
        canonical_chat_diagnostic_scope,
        provider_sdk_diagnostic_span,
    )

    parent_backend = _Backend()
    other_backend = _Backend()
    monkeypatch.setattr(
        "uagent.runtime.observability.settings.get_observability_settings",
        lambda: _settings("openai"),
    )
    monkeypatch.setattr(
        "uagent.runtime.observability.runtime.get_observability_backend",
        lambda: other_backend,
    )

    with parent_backend.start_span("chat") as chat_span:
        with canonical_chat_diagnostic_scope(chat_span, parent_backend):
            with provider_sdk_diagnostic_span("openai"):
                pass

    assert [record["operation"] for record in parent_backend.records] == [
        "chat",
        "provider_sdk",
    ]
    assert parent_backend.records[1]["parent"] == "chat"
    assert other_backend.records == []


def test_phase4c_legacy_claude_false_result_marks_child_error(monkeypatch) -> None:
    from uagent.runtime.legacy_provider_dispatch import _call_with_fallback_chat_span

    backend = _Backend()
    _install_runtime(monkeypatch, backend, _settings("claude"))

    result = _call_with_fallback_chat_span(
        provider="claude",
        caller=lambda **_kwargs: (False,),
        kwargs={
            "depname": "claude-test",
            "call_messages": [{"role": "user", "content": "hello"}],
            "core": SimpleNamespace(_last_responses_usage=None),
        },
    )

    assert result == (False,)
    provider_records = [
        record for record in backend.records if record["operation"] == "provider_sdk"
    ]
    assert len(provider_records) == 1
    assert provider_records[0]["parent"] == "chat"
    assert provider_records[0]["attributes"] == {"uag.provider.id": "claude"}
    assert provider_records[0]["span"].statuses == [("error", None)]


def test_phase4c_semantic_mapping_drops_non_allowlisted_provider_metadata() -> None:
    mapped = map_span(
        "provider_sdk",
        {
            "uag.provider.id": "openai",
            "gen_ai.request.model": "must-not-export",
            "server.address": "must-not-export",
        },
    )

    assert mapped.name == "provider_sdk"
    assert mapped.attributes == {"uag.provider.id": "openai"}


def test_phase4c_semantic_mapping_rejects_unknown_provider_id() -> None:
    mapped = map_span(
        "provider_sdk",
        {
            "uag.provider.id": "azure",
            "server.address": "must-not-export",
        },
    )

    assert mapped.name == "provider_sdk"
    assert mapped.attributes == {}
