from uagent.runtime.observability.api import TraceIds
from uagent.runtime.observability.bootstrap import (
    _reset_observability_state_for_tests,
    get_observability_backend,
    initialize_observability,
)
from uagent.runtime.observability.noop import NOOP_BACKEND
from uagent.runtime.observability.settings import ObservabilitySettings


def setup_function():
    _reset_observability_state_for_tests()


def teardown_function():
    _reset_observability_state_for_tests()


def test_noop_backend_is_safe_and_has_no_trace_ids():
    assert NOOP_BACKEND.enabled is False
    with NOOP_BACKEND.start_span("test", attributes={"value": 1}) as span:
        span.set_attribute("later", 2)
        span.add_event("event", {"ok": True})
        span.record_exception(RuntimeError("ignored"))
    assert NOOP_BACKEND.current_trace_ids() == TraceIds()


def test_disabled_bootstrap_returns_noop_without_dependency_check(monkeypatch):
    def fail_if_called(_settings):
        raise AssertionError("dependency readiness must not run while disabled")

    monkeypatch.setattr(
        "uagent.runtime.observability.bootstrap.ensure_otel_dependencies",
        fail_if_called,
    )

    result = initialize_observability(ObservabilitySettings(enabled=False))
    assert result.backend is NOOP_BACKEND
    assert result.dependencies_ready is False
    assert result.reason == "disabled"
    assert get_observability_backend() is NOOP_BACKEND


def test_enabled_bootstrap_degrades_to_noop_when_dependencies_fail(monkeypatch):
    monkeypatch.setattr(
        "uagent.runtime.observability.bootstrap.ensure_otel_dependencies",
        lambda _settings: False,
    )

    result = initialize_observability(ObservabilitySettings(enabled=True))
    assert result.backend is NOOP_BACKEND
    assert result.reason == "dependencies_unavailable"


def test_enabled_bootstrap_uses_factory_after_dependencies_are_ready(monkeypatch):
    class FakeBackend:
        enabled = True

        def start_span(self, operation, *, attributes=None):
            return NOOP_BACKEND.start_span(operation, attributes=attributes)

        def record_event(self, name, attributes=None):
            return None

        def current_trace_ids(self):
            return TraceIds("trace", "span")

    backend = FakeBackend()
    monkeypatch.setattr(
        "uagent.runtime.observability.bootstrap.ensure_otel_dependencies",
        lambda _settings: True,
    )

    result = initialize_observability(
        ObservabilitySettings(enabled=True), backend_factory=lambda _settings: backend
    )
    assert result.backend is backend
    assert result.dependencies_ready is True
    assert result.reason == "enabled"
