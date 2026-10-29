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


def test_paired_backend_recovers_after_import_without_restart(monkeypatch):
    """Real OTLP/HTTP: pre-import 404 must not disable later trace batches."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    from types import SimpleNamespace

    import pytest

    # General test jobs need not install OTel. Check all optional imports
    # before starting the receiver, including incompatible installed packages.
    pytest.importorskip("opentelemetry.sdk", exc_type=ImportError)
    trace_service = pytest.importorskip(
        "opentelemetry.proto.collector.trace.v1.trace_service_pb2",
        exc_type=ImportError,
    )
    pytest.importorskip(
        "opentelemetry.exporter.otlp.proto.http.trace_exporter",
        exc_type=ImportError,
    )
    ExportTraceServiceRequest = trace_service.ExportTraceServiceRequest
    from uagent.runtime.observability.settings import ObservabilitySettings

    received = []
    active = False

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            received.append((self.path, self.headers["Authorization"], body))
            self.send_response(200 if active else 404)
            self.send_header("Content-Type", "application/x-protobuf")
            self.end_headers()

        def log_message(self, *args):
            pass

    _clear_otlp_endpoints(monkeypatch)
    for name in (
        "OTEL_EXPORTER_OTLP_HEADERS",
        "OTEL_EXPORTER_OTLP_TRACES_HEADERS",
        "OTEL_EXPORTER_OTLP_PROTOCOL",
        "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL",
        "OTEL_TRACES_EXPORTER",
        "OTEL_EXPORTER_OTLP_COMPRESSION",
        "OTEL_EXPORTER_OTLP_TRACES_COMPRESSION",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OTEL_TRACES_SAMPLER", "always_on")
    monkeypatch.setattr(otel_backend, "_build_metric_exporter", lambda: None)
    now = [0.0]
    monkeypatch.setattr(otel_backend, "time", SimpleNamespace(monotonic=lambda: now[0]))
    server = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    endpoint = f"http://127.0.0.1:{server.server_port}/otlp/v1/traces"
    monkeypatch.setattr(admin_pairing, "get_otlp_pairing", lambda: (endpoint, "T" * 48))
    backend = otel_backend.create_otel_backend(ObservabilitySettings(enabled=True))
    try:
        for instant in (0.0, 1.0, 30.0, 31.0):
            now[0] = instant
            active = instant >= 1.0
            with backend.start_span("chat", root=True):
                pass
            assert backend._provider.force_flush()
        # First batch fails; second is dropped during cooldown; next two arrive.
        assert len(received) == 3
        for path, authorization, body in received:
            assert path == "/otlp/v1/traces"
            assert authorization == "Bearer " + "T" * 48
            message = ExportTraceServiceRequest.FromString(body)
            assert len(message.resource_spans[0].scope_spans[0].spans) == 1
    finally:
        backend.shutdown()
        server.shutdown()
        server.server_close()
        worker.join()


def test_cooldown_recovers_from_exception_and_shutdown_stays_final(monkeypatch):
    from types import SimpleNamespace

    now = [0.0]
    monkeypatch.setattr(otel_backend, "time", SimpleNamespace(monotonic=lambda: now[0]))

    class Exporter:
        calls = 0

        def export(self, batch):
            self.calls += 1
            if self.calls == 1:
                raise OSError("Admin not started")
            return _ExportResult.SUCCESS

    inner = Exporter()
    exporter = otel_backend._FailStopExporter(
        inner,
        success_result=_ExportResult.SUCCESS,
        failure_result=_ExportResult.FAILURE,
        retry_interval=30.0,
    )
    assert exporter.export([1]) is _ExportResult.FAILURE
    now[0] = 29.0
    exporter.export([2])
    assert inner.calls == 1
    now[0] = 30.0
    assert exporter.export([3]) is _ExportResult.SUCCESS
    assert inner.calls == 2
    exporter.shutdown()
    now[0] = 60.0
    exporter.export([4])
    assert inner.calls == 2


def test_paired_credentials_and_otlp_env_do_not_activate_disabled_telemetry(
    monkeypatch,
):
    from uagent.runtime.observability import bootstrap
    from uagent.runtime.observability.noop import NOOP_BACKEND
    from uagent.runtime.observability.settings import ObservabilitySettings

    calls = []
    monkeypatch.setattr(
        admin_pairing, "get_otlp_pairing", lambda: calls.append("pairing")
    )
    monkeypatch.setattr(
        bootstrap, "ensure_otel_dependencies", lambda _: calls.append("install")
    )
    monkeypatch.setattr(
        otel_backend, "create_otel_backend", lambda _: calls.append("exporter")
    )
    bootstrap._reset_observability_state_for_tests()
    try:
        for explicit, env in (
            (None, {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://127.0.0.1:4318"}),
            (False, {"UAGENT_OTEL_ENABLED": "1"}),
        ):
            settings = ObservabilitySettings.resolve(
                explicit_enabled=explicit, environ=env
            )
            result = bootstrap.initialize_observability(settings)
            assert result.reason == "disabled"
            assert result.backend is NOOP_BACKEND
            with result.backend.start_span("chat", root=True):
                pass
        assert calls == []
    finally:
        bootstrap._reset_observability_state_for_tests()
