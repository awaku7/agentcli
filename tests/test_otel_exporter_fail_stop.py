from __future__ import annotations

from enum import Enum

from uagent import admin_pairing
from uagent.runtime.observability import otel_backend


def _clear_otlp_endpoints(monkeypatch) -> None:
    for name in (
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
    ):
        monkeypatch.delenv(name, raising=False)


def test_no_trace_endpoint_means_no_exporter_or_implicit_localhost(monkeypatch):
    _clear_otlp_endpoints(monkeypatch)
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "otlp")
    monkeypatch.setattr(admin_pairing, "get_otlp_pairing", lambda: None)

    assert otel_backend._build_trace_exporter() is None


def test_no_metrics_endpoint_means_no_exporter_or_implicit_localhost(monkeypatch):
    _clear_otlp_endpoints(monkeypatch)
    monkeypatch.setenv("OTEL_METRICS_EXPORTER", "otlp")
    monkeypatch.setattr(admin_pairing, "get_otlp_pairing", lambda: None)

    assert otel_backend._build_metric_exporter() is None


class _ExportResult(Enum):
    SUCCESS = "success"
    FAILURE = "failure"


def test_fail_stop_exporter_disables_remote_calls_after_first_failure():
    class Exporter:
        def __init__(self):
            self.calls = 0

        def export(self, batch):
            self.calls += 1
            return _ExportResult.FAILURE

    inner = Exporter()
    exporter = otel_backend._FailStopExporter(
        inner,
        success_result=_ExportResult.SUCCESS,
        failure_result=_ExportResult.FAILURE,
    )

    assert exporter.export(["first"]) is _ExportResult.FAILURE
    assert exporter.export(["second"]) is _ExportResult.SUCCESS
    assert exporter.export(["third"]) is _ExportResult.SUCCESS
    assert inner.calls == 1


def test_fail_stop_exporter_disables_remote_calls_after_exception():
    class Exporter:
        def __init__(self):
            self.calls = 0

        def export(self, batch):
            self.calls += 1
            raise OSError("collector unavailable")

    inner = Exporter()
    exporter = otel_backend._FailStopExporter(
        inner,
        success_result=_ExportResult.SUCCESS,
        failure_result=_ExportResult.FAILURE,
    )

    assert exporter.export(["first"]) is _ExportResult.FAILURE
    assert exporter.export(["second"]) is _ExportResult.SUCCESS
    assert inner.calls == 1


def test_created_backend_uses_fail_stop_adapter_for_traces(monkeypatch):
    import pytest

    pytest.importorskip("opentelemetry.sdk")
    from opentelemetry.sdk.trace.export import SpanExportResult

    from uagent.runtime.observability.settings import ObservabilitySettings

    class Exporter:
        def __init__(self):
            self.calls = 0

        def export(self, spans):
            self.calls += 1
            return SpanExportResult.FAILURE

        def shutdown(self):
            return None

    inner = Exporter()
    monkeypatch.setattr(otel_backend, "_build_trace_exporter", lambda: inner)
    monkeypatch.setattr(otel_backend, "_build_metric_exporter", lambda: None)
    backend = otel_backend.create_otel_backend(ObservabilitySettings(enabled=True))
    try:
        for _ in range(2):
            with backend.start_span("invoke_agent"):
                pass
            backend._provider.force_flush()
    finally:
        backend.shutdown()

    assert inner.calls == 1
