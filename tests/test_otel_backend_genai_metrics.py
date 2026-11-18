from __future__ import annotations

import pytest

from uagent.runtime.observability.settings import ObservabilitySettings


class RawSpan:
    def __init__(self) -> None:
        self.attributes: dict = {}
        self.statuses: list = []
        self.events: list = []

    def set_attribute(self, name, value) -> None:
        self.attributes[name] = value

    def add_event(self, name, attributes=None) -> None:
        self.events.append((name, dict(attributes or {})))

    def set_status(self, status) -> None:
        self.statuses.append(status)


class Manager:
    def __init__(self, span: RawSpan) -> None:
        self.span = span

    def __enter__(self):
        return self.span

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


class Tracer:
    def __init__(self) -> None:
        self.spans: list[RawSpan] = []

    def start_as_current_span(self, *args, **kwargs):
        span = RawSpan()
        self.spans.append(span)
        return Manager(span)


class Provider:
    def shutdown(self) -> None:
        return None


class FakeCounter:
    def __init__(self) -> None:
        self.adds: list = []

    def add(self, value, attributes=None) -> None:
        self.adds.append((value, dict(attributes or {})))


class FakeHistogram:
    def __init__(self) -> None:
        self.records: list = []

    def record(self, value, attributes=None) -> None:
        self.records.append((value, dict(attributes or {})))


class FakeMeter:
    def __init__(self) -> None:
        self.counters: dict[str, FakeCounter] = {}
        self.histograms: dict[str, FakeHistogram] = {}
        self.counter_units: dict[str, str | None] = {}
        self.histogram_units: dict[str, str | None] = {}
        self.histogram_buckets: dict[str, list | None] = {}

    def create_counter(self, name, unit=None, **kwargs):
        self.counter_units[name] = unit
        return self.counters.setdefault(name, FakeCounter())

    def create_histogram(self, name, unit=None, **kwargs):
        self.histogram_units[name] = unit
        self.histogram_buckets[name] = kwargs.get("explicit_bucket_boundaries_advisory")
        return self.histograms.setdefault(name, FakeHistogram())


def _backend(meter=None):
    from uagent.runtime.observability.otel_backend import OpenTelemetryBackend

    return OpenTelemetryBackend(
        tracer=Tracer(),
        provider=Provider(),
        settings=ObservabilitySettings(enabled=True),
        meter=meter,
    )


def test_chat_span_end_records_genai_metrics() -> None:
    meter = FakeMeter()
    backend = _backend(meter)
    with backend.start_span(
        "chat",
        attributes={"uag.llm.provider": "openai", "uag.llm.model": "gpt-x"},
    ) as span:
        span.set_attribute("uag.tokens.reported.input", 120)
        span.set_attribute("uag.tokens.reported.output", 30)
        span.set_attribute("gen_ai.usage.cache_read.input_tokens", 40)
        span.set_attribute("gen_ai.usage.reasoning.output_tokens", 5)

    input_adds = meter.counters["gen_ai.client.inference.usage.input_tokens"].adds
    assert len(input_adds) == 1
    value, dims = input_adds[0]
    assert value == 120
    assert dims["gen_ai.operation.name"] == "chat"
    assert dims["gen_ai.provider.name"] == "openai"
    assert dims["gen_ai.request.model"] == "gpt-x"
    assert dims["gen_ai.token.modality"] == "unknown"

    output_adds = meter.counters["gen_ai.client.inference.usage.output_tokens"].adds
    assert [value for value, _ in output_adds] == [30]

    cache_adds = meter.counters[
        "gen_ai.client.inference.usage.cache_read.input_tokens"
    ].adds
    assert [value for value, _ in cache_adds] == [40]
    assert cache_adds[0][1]["gen_ai.token.modality"] == "unknown"

    reasoning_adds = meter.counters[
        "gen_ai.client.inference.usage.reasoning.output_tokens"
    ].adds
    assert [value for value, _ in reasoning_adds] == [5]
    # The reasoning counter is the one usage counter without a modality.
    assert "gen_ai.token.modality" not in reasoning_adds[0][1]

    duration = meter.histograms["gen_ai.client.inference.duration"].records
    assert len(duration) == 1
    assert duration[0][0] >= 0
    assert duration[0][1]["gen_ai.provider.name"] == "openai"
    assert meter.histogram_units["gen_ai.client.inference.duration"] == "s"
    assert meter.histogram_buckets["gen_ai.client.inference.duration"][0] == 0.01

    op_input = meter.histograms[
        "gen_ai.client.inference.operation.input_tokens"
    ].records
    assert [value for value, _ in op_input] == [120]
    op_output = meter.histograms[
        "gen_ai.client.inference.operation.output_tokens"
    ].records
    assert [value for value, _ in op_output] == [30]


def test_tool_span_records_execute_tool_duration() -> None:
    meter = FakeMeter()
    backend = _backend(meter)
    with backend.start_span("execute_tool", attributes={"uag.tool.name": "run_shell"}):
        pass

    records = meter.histograms["gen_ai.execute_tool.duration"].records
    assert len(records) == 1
    assert records[0][1]["gen_ai.tool.name"] == "run_shell"
    assert meter.counters == {}


def test_invoke_agent_records_child_call_counts() -> None:
    meter = FakeMeter()
    backend = _backend(meter)
    with backend.start_span("invoke_agent", attributes={"uag.agent.name": "uag"}):
        with backend.start_span("invoke_agent", attributes={"uag.agent.name": "sub"}):
            with backend.start_span(
                "chat",
                attributes={
                    "uag.llm.provider": "openai",
                    "uag.llm.model": "gpt-x",
                },
            ):
                pass
        with backend.start_span(
            "execute_tool", attributes={"uag.tool.name": "run_shell"}
        ):
            pass
        with backend.start_span(
            "execute_tool", attributes={"uag.tool.name": "read_file"}
        ):
            pass

    inference = meter.histograms["gen_ai.invoke_agent.inference_calls"].records
    tools = meter.histograms["gen_ai.invoke_agent.tool_calls"].records
    # Innermost invocation finishes first: its chat counts only toward it,
    # while the outer invocation counts its two direct tool calls.
    assert [value for value, _ in inference] == [1, 0]
    assert [value for value, _ in tools] == [0, 2]
    durations = meter.histograms["gen_ai.invoke_agent.duration"].records
    assert len(durations) == 2
    assert durations[0][1]["gen_ai.agent.name"] == "sub"
    assert durations[1][1]["gen_ai.agent.name"] == "uag"


def test_failed_chat_span_records_error_type() -> None:
    meter = FakeMeter()
    backend = _backend(meter)
    with pytest.raises(ValueError):
        with backend.start_span(
            "chat",
            attributes={"uag.llm.provider": "openai", "uag.llm.model": "gpt-x"},
        ):
            raise ValueError("boom")

    duration = meter.histograms["gen_ai.client.inference.duration"].records
    assert len(duration) == 1
    assert duration[0][1]["error.type"] == "ValueError"
    assert meter.counters == {}


def test_sentence_failed_chat_span_uses_fallback_error_type() -> None:
    meter = FakeMeter()
    backend = _backend(meter)
    with backend.start_span(
        "chat",
        attributes={"uag.llm.provider": "openai", "uag.llm.model": "gpt-x"},
    ) as span:
        # Production paths such as the legacy provider dispatch fail spans
        # with a free-form sentence instead of an exception class.
        span.set_status("error", "provider round failed")

    duration = meter.histograms["gen_ai.client.inference.duration"].records
    assert len(duration) == 1
    assert duration[0][1]["error.type"] == "error"


def test_spans_without_meter_record_nothing() -> None:
    backend = _backend(None)
    with backend.start_span("invoke_agent", attributes={"uag.agent.name": "uag"}):
        with backend.start_span(
            "chat",
            attributes={"uag.llm.provider": "openai", "uag.llm.model": "gpt-x"},
        ) as span:
            span.set_attribute("uag.tokens.reported.input", 10)


_OTEL_ENV_KEYS = (
    "OTEL_METRICS_EXPORTER",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_EXPORTER_OTLP_HEADERS",
    "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
    "OTEL_EXPORTER_OTLP_METRICS_HEADERS",
    "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL",
    "OTEL_EXPORTER_OTLP_PROTOCOL",
)


def _clear_otel_env(monkeypatch) -> None:
    for key in _OTEL_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def _stub_metric_exporter_module(monkeypatch, fake_exporter) -> None:
    """Make the lazy exporter import resolve to a recording stand-in.

    The real exporter package is installed lazily and its version can skew
    against a preinstalled opentelemetry-api, so these tests never import
    it; they only verify which arguments the backend constructs it with.
    """

    import sys
    import types

    names = [
        "opentelemetry.exporter",
        "opentelemetry.exporter.otlp",
        "opentelemetry.exporter.otlp.proto",
        "opentelemetry.exporter.otlp.proto.http",
        "opentelemetry.exporter.otlp.proto.http.metric_exporter",
    ]
    for name in names[:-1]:
        if name not in sys.modules:
            monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    module = types.ModuleType(names[-1])
    module.OTLPMetricExporter = fake_exporter
    monkeypatch.setitem(sys.modules, names[-1], module)


def test_metrics_exporter_uses_pairing_endpoint(monkeypatch) -> None:
    from uagent import admin_pairing
    from uagent.runtime.observability import otel_backend

    _clear_otel_env(monkeypatch)
    monkeypatch.setattr(
        admin_pairing,
        "get_otlp_metrics_pairing",
        lambda: ("https://admin.example.net/otlp/v1/metrics", "S" * 48),
    )
    constructor_calls = []

    class FakeExporter:
        pass

    def fake_exporter(**kwargs):
        constructor_calls.append(kwargs)
        return FakeExporter()

    _stub_metric_exporter_module(monkeypatch, fake_exporter)
    exporter = otel_backend._build_metric_exporter()
    assert constructor_calls == [
        {
            "endpoint": "https://admin.example.net/otlp/v1/metrics",
            "headers": {"Authorization": "Bearer " + "S" * 48},
        }
    ]
    assert exporter is not None
    assert getattr(exporter, "_uag_admin_pairing", False) is True


def test_metrics_exporter_explicit_endpoint_wins_over_pairing(monkeypatch) -> None:
    from uagent import admin_pairing
    from uagent.runtime.observability import otel_backend

    _clear_otel_env(monkeypatch)
    monkeypatch.setenv(
        "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
        "https://metrics.example.net/v1/metrics",
    )
    monkeypatch.setattr(
        admin_pairing,
        "get_otlp_metrics_pairing",
        lambda: ("https://admin.example.net/otlp/v1/metrics", "S" * 48),
    )
    constructor_calls = []

    def fake_exporter(**kwargs):
        constructor_calls.append(kwargs)
        return object()

    _stub_metric_exporter_module(monkeypatch, fake_exporter)
    otel_backend._build_metric_exporter()
    assert constructor_calls == [{}]


def test_metrics_exporter_none_when_unpaired_without_endpoint(monkeypatch) -> None:
    from uagent import admin_pairing
    from uagent.runtime.observability import otel_backend

    _clear_otel_env(monkeypatch)
    monkeypatch.setattr(admin_pairing, "get_otlp_metrics_pairing", lambda: None)
    assert otel_backend._build_metric_exporter() is None
