"""OpenTelemetry/OTLP projection backend for UAG observability."""

from __future__ import annotations

import atexit
import os
from contextlib import contextmanager
from typing import Any, Iterator, Mapping

from .api import ObservabilitySpan, TraceIds
from .noop import NOOP_SPAN
from .privacy import sanitize_attributes
from .semantic_mapping import map_span
from .settings import ObservabilitySettings


class OpenTelemetrySpan:
    """Small adapter around an OpenTelemetry SDK span."""

    def __init__(self, span: Any, *, capture_content: bool) -> None:
        self._span = span
        self._capture_content = capture_content

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
            self._span.record_exception(exc)
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
        except Exception:
            pass


class OpenTelemetryBackend:
    """Process-level OTel backend using a UAG-owned tracer provider."""

    def __init__(
        self,
        *,
        tracer: Any,
        provider: Any,
        settings: ObservabilitySettings,
    ) -> None:
        self._tracer = tracer
        self._provider = provider
        self._settings = settings
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


def create_otel_backend(settings: ObservabilitySettings) -> OpenTelemetryBackend:
    """Create the supported OTel tracer provider/exporter projection."""

    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    service_name = (os.getenv("OTEL_SERVICE_NAME") or "uagent").strip() or "uagent"
    provider = TracerProvider(
        resource=Resource.create({"service.name": service_name}),
        sampler=_sampler_from_environment(),
    )
    exporter = _build_trace_exporter()
    if exporter is not None:
        provider.add_span_processor(BatchSpanProcessor(exporter))
    tracer = provider.get_tracer("uagent.runtime.observability")
    backend = OpenTelemetryBackend(
        tracer=tracer,
        provider=provider,
        settings=settings,
    )
    atexit.register(backend.shutdown)
    return backend


__all__ = ["OpenTelemetryBackend", "OpenTelemetrySpan", "create_otel_backend"]
