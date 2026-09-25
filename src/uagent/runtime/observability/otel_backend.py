"""OpenTelemetry/OTLP projection backend for UAG observability."""

from __future__ import annotations

import atexit
import os
from contextlib import contextmanager
from typing import Any, Iterator, Mapping, MutableMapping

from .api import ObservabilitySpan, TraceIds
from .noop import NOOP_SPAN
from .privacy import sanitize_attributes
from .semantic_mapping import map_span
from .settings import ObservabilitySettings

_METRIC_STRING_VALUES = {
    "uag.context.kind": {"messages", "candidates"},
    "uag.context.decision.action": {"KEEP", "COMPACT", "EXCLUDE", "RETRIEVE_MORE"},
    "uag.retrieval.kind": {"context", "memory"},
    "uag.memory.scope_mode": {"local", "scoped"},
    "uag.status": {"ok", "error", "disabled"},
}
_METRIC_BOOLEAN_KEYS = {
    "uag.memory.identity_bound",
    "uag.memory.profile_present",
    "uag.memory.guidance_present",
    "uag.memory.shared_enabled",
}


def _sanitize_metric_attributes(
    attributes: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return a deliberately tiny low-cardinality metric attribute set."""

    safe: dict[str, Any] = {}
    for key, value in dict(attributes or {}).items():
        name = str(key or "").strip()
        if name in _METRIC_STRING_VALUES:
            rendered = str(value or "").strip()
            if rendered in _METRIC_STRING_VALUES[name]:
                safe[name] = rendered
        elif name in _METRIC_BOOLEAN_KEYS and isinstance(value, bool):
            safe[name] = value
    return safe


class OpenTelemetrySpan:
    """Small adapter around an OpenTelemetry SDK span."""

    def __init__(self, span: Any, *, capture_content: bool) -> None:
        self._span = span
        self._capture_content = capture_content
        self._cancelled = False

    @property
    def cancelled(self) -> bool:
        """Whether the runtime explicitly finalized this span as cancelled."""

        return self._cancelled

    def set_attribute(self, key: str, value: Any) -> None:
        try:
            safe = sanitize_attributes(
                {key: value}, capture_content=self._capture_content
            )
            for name, item in safe.items():
                self._span.set_attribute(name, item)
        except Exception:
            pass

    def add_event(self, name: str, attributes: Mapping[str, Any] | None = None) -> None:
        try:
            self._span.add_event(
                str(name),
                sanitize_attributes(attributes, capture_content=self._capture_content),
            )
        except Exception:
            pass

    def record_exception(self, exc: BaseException) -> None:
        try:
            exception_type = f"{type(exc).__module__}.{type(exc).__name__}"
            self._span.add_event("exception", {"exception.type": exception_type})
        except Exception:
            pass

    def set_status(self, status: str, description: str | None = None) -> None:
        try:
            from opentelemetry.trace import Status, StatusCode

            normalized = str(status or "").strip().lower()
            if normalized in {"error", "failed", "failure"}:
                code = StatusCode.ERROR
            elif normalized in {"ok", "success", "completed"}:
                code = StatusCode.OK
            else:
                code = StatusCode.UNSET
            self._span.set_status(Status(code, description=description))
            self._cancelled = code == StatusCode.UNSET and str(
                description or ""
            ).strip().lower() in {"cancelled", "canceled"}
        except Exception:
            pass


class OpenTelemetryBackend:
    """Process-level OTel backend using UAG-owned trace and metric providers."""

    def __init__(
        self,
        *,
        tracer: Any,
        provider: Any,
        settings: ObservabilitySettings,
        meter: Any | None = None,
        meter_provider: Any | None = None,
    ) -> None:
        self._tracer = tracer
        self._provider = provider
        self._settings = settings
        self._meter = meter
        self._meter_provider = meter_provider
        self._counter_instruments: dict[str, Any] = {}
        self._histogram_instruments: dict[str, Any] = {}
        self._shutdown = False

    @property
    def enabled(self) -> bool:
        return True

    @contextmanager
    def start_span(
        self,
        operation: str,
        *,
        attributes: Mapping[str, Any] | None = None,
        root: bool = False,
    ) -> Iterator[ObservabilitySpan]:
        try:
            from opentelemetry.context import Context

            mapped = map_span(operation, attributes)
            safe_attributes = sanitize_attributes(
                mapped.attributes,
                capture_content=self._settings.capture_content,
            )
            manager = self._tracer.start_as_current_span(
                mapped.name,
                context=Context() if root else None,
                attributes=safe_attributes,
                record_exception=False,
                set_status_on_exception=False,
            )
            raw_span = manager.__enter__()
        except Exception:
            yield NOOP_SPAN
            return

        span = OpenTelemetrySpan(
            raw_span, capture_content=self._settings.capture_content
        )
        try:
            yield span
        except BaseException as exc:
            if not span.cancelled:
                span.record_exception(exc)
                span.set_status("error", type(exc).__name__)
            try:
                manager.__exit__(type(exc), exc, exc.__traceback__)
            except Exception:
                pass
            raise
        else:
            try:
                manager.__exit__(None, None, None)
            except Exception:
                pass

    def record_event(
        self, name: str, attributes: Mapping[str, Any] | None = None
    ) -> None:
        try:
            from opentelemetry import trace

            span = trace.get_current_span()
            if span is None or not span.is_recording():
                return
            span.add_event(
                str(name),
                sanitize_attributes(
                    attributes,
                    capture_content=self._settings.capture_content,
                ),
            )
        except Exception:
            pass

    def record_counter(
        self,
        name: str,
        value: int | float = 1,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        if self._meter is None or isinstance(value, bool):
            return
        try:
            instrument = self._counter_instruments.get(name)
            if instrument is None:
                instrument = self._meter.create_counter(str(name))
                self._counter_instruments[str(name)] = instrument
            instrument.add(value, _sanitize_metric_attributes(attributes))
        except Exception:
            pass

    def record_histogram(
        self,
        name: str,
        value: int | float,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        if self._meter is None or isinstance(value, bool):
            return
        try:
            instrument = self._histogram_instruments.get(name)
            if instrument is None:
                instrument = self._meter.create_histogram(str(name))
                self._histogram_instruments[str(name)] = instrument
            instrument.record(value, _sanitize_metric_attributes(attributes))
        except Exception:
            pass

    def inject_context(self, carrier: MutableMapping[str, str]) -> None:
        """Inject only W3C Trace Context into a trusted outbound carrier."""

        try:
            from opentelemetry.trace.propagation.tracecontext import (
                TraceContextTextMapPropagator,
            )

            TraceContextTextMapPropagator().inject(carrier)
        except Exception:
            pass

    @contextmanager
    def attach_remote_context(self, carrier: Mapping[str, str]) -> Iterator[None]:
        """Attach a valid trusted W3C remote parent for the context duration."""

        traceparent = str(carrier.get("traceparent") or "").strip()
        if not traceparent:
            yield None
            return

        token = None
        detach_context = None
        try:
            from opentelemetry import trace
            from opentelemetry.context import attach, detach
            from opentelemetry.trace.propagation.tracecontext import (
                TraceContextTextMapPropagator,
            )

            extracted = TraceContextTextMapPropagator().extract(dict(carrier))
            span_context = trace.get_current_span(extracted).get_span_context()
            if span_context.is_valid and span_context.is_remote:
                token = attach(extracted)
                detach_context = detach
        except Exception:
            token = None
            detach_context = None

        try:
            yield None
        finally:
            if token is not None and detach_context is not None:
                try:
                    detach_context(token)
                except Exception:
                    pass

    def current_trace_ids(self) -> TraceIds:
        try:
            from opentelemetry import trace

            span_context = trace.get_current_span().get_span_context()
            if not span_context.is_valid:
                return TraceIds()
            return TraceIds(
                trace_id=f"{span_context.trace_id:032x}",
                span_id=f"{span_context.span_id:016x}",
            )
        except Exception:
            return TraceIds()

    def shutdown(self) -> None:
        if self._shutdown:
            return
        self._shutdown = True
        try:
            if self._meter_provider is not None:
                self._meter_provider.shutdown()
        except Exception:
            pass
        try:
            self._provider.shutdown()
        except Exception:
            pass


def _sampler_from_environment() -> Any:
    from opentelemetry.sdk.trace.sampling import (
        ALWAYS_OFF,
        ALWAYS_ON,
        ParentBased,
        TraceIdRatioBased,
    )

    name = (os.getenv("OTEL_TRACES_SAMPLER") or "parentbased_always_on").strip().lower()
    raw_arg = (os.getenv("OTEL_TRACES_SAMPLER_ARG") or "1.0").strip()
    try:
        ratio = min(1.0, max(0.0, float(raw_arg)))
    except (TypeError, ValueError):
        ratio = 1.0

    if name == "always_on":
        return ALWAYS_ON
    if name == "always_off":
        return ALWAYS_OFF
    if name == "traceidratio":
        return TraceIdRatioBased(ratio)
    if name == "parentbased_always_off":
        return ParentBased(ALWAYS_OFF)
    if name == "parentbased_traceidratio":
        return ParentBased(TraceIdRatioBased(ratio))
    return ParentBased(ALWAYS_ON)


def _build_trace_exporter() -> Any | None:
    configured = (os.getenv("OTEL_TRACES_EXPORTER") or "otlp").strip().lower()
    exporters = {item.strip() for item in configured.split(",") if item.strip()}
    if exporters == {"none"}:
        return None
    if "otlp" not in exporters:
        raise ValueError(
            "UAG Phase-1 tracing supports OTEL_TRACES_EXPORTER=otlp or none"
        )

    protocol = (
        (
            os.getenv("OTEL_EXPORTER_OTLP_TRACES_PROTOCOL")
            or os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL")
            or "http/protobuf"
        )
        .strip()
        .lower()
    )
    if protocol == "grpc":
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        return OTLPSpanExporter()
    if protocol == "http/protobuf":
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        return OTLPSpanExporter()
    raise ValueError(f"unsupported OTLP traces protocol: {protocol}")


def _build_metric_exporter() -> Any | None:
    configured = (os.getenv("OTEL_METRICS_EXPORTER") or "otlp").strip().lower()
    exporters = {item.strip() for item in configured.split(",") if item.strip()}
    if exporters == {"none"}:
        return None
    if "otlp" not in exporters:
        raise ValueError("UAG metrics supports OTEL_METRICS_EXPORTER=otlp or none")

    protocol = (
        (
            os.getenv("OTEL_EXPORTER_OTLP_METRICS_PROTOCOL")
            or os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL")
            or "http/protobuf"
        )
        .strip()
        .lower()
    )
    if protocol == "grpc":
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
            OTLPMetricExporter,
        )

        return OTLPMetricExporter()
    if protocol == "http/protobuf":
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
            OTLPMetricExporter,
        )

        return OTLPMetricExporter()
    raise ValueError(f"unsupported OTLP metrics protocol: {protocol}")


def create_otel_backend(settings: ObservabilitySettings) -> OpenTelemetryBackend:
    """Create the supported OTel trace projection and best-effort metrics."""

    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    service_name = (os.getenv("OTEL_SERVICE_NAME") or "uagent").strip() or "uagent"
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource, sampler=_sampler_from_environment())
    exporter = _build_trace_exporter()
    if exporter is not None:
        provider.add_span_processor(BatchSpanProcessor(exporter))
    tracer = provider.get_tracer("uagent.runtime.observability")

    meter = None
    meter_provider = None
    try:
        metric_exporter = _build_metric_exporter()
        if metric_exporter is not None:
            from opentelemetry.sdk.metrics import MeterProvider
            from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

            metric_reader = PeriodicExportingMetricReader(metric_exporter)
            meter_provider = MeterProvider(
                resource=resource,
                metric_readers=[metric_reader],
            )
            meter = meter_provider.get_meter("uagent.runtime.observability")
    except Exception:
        meter = None
        meter_provider = None

    backend = OpenTelemetryBackend(
        tracer=tracer,
        provider=provider,
        settings=settings,
        meter=meter,
        meter_provider=meter_provider,
    )
    atexit.register(backend.shutdown)
    return backend


__all__ = ["OpenTelemetryBackend", "OpenTelemetrySpan", "create_otel_backend"]
