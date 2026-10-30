"""OpenTelemetry/OTLP projection backend for UAG observability."""

from __future__ import annotations

import atexit
import json
import os
import threading
import time
from contextlib import contextmanager
from typing import Any, Callable, Iterator, Mapping, MutableMapping

from .api import ObservabilitySpan, TraceIds
from .delivery_status import update_delivery_status
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


class _FailStopExporter:
    """Stop submitting telemetry after the first exporter failure.

    OpenTelemetry's batch processors keep invoking exporters periodically. If
    the configured collector is unavailable, forwarding those calls produces
    repeated connection attempts and repeated error logs. This adapter lets the
    first failure be observed, then drops later batches without contacting the
    exporter again. Paired Admin traces instead probe with a new batch after
    a cooldown, allowing import or receiver recovery without restarting UAG.
    Failed and cooldown batches are dropped, not buffered or replayed.
    """

    def __init__(
        self,
        exporter: Any,
        *,
        success_result: Any,
        failure_result: Any,
        retry_interval: float | None = None,
        status_callback: Callable[[str], None] | None = None,
    ):
        self._exporter = exporter
        self._success_result = success_result
        self._failure_result = failure_result
        self._lock = threading.Lock()
        self._disabled = False
        self._retry_interval = retry_interval
        self._retry_at = 0.0
        self._shutdown = False
        self._status_callback = status_callback

    def _note(self, state: str) -> None:
        if self._status_callback is not None:
            try:
                self._status_callback(state)
            except Exception:
                pass

    def export(self, batch: Any) -> Any:
        with self._lock:
            if self._shutdown:
                return self._success_result
            if self._disabled:
                if self._retry_interval is None:
                    # SDK success here means a dropped batch, not remote delivery.
                    return self._success_result
                if time.monotonic() < self._retry_at:
                    self._note("retry_cooldown")
                    return self._success_result
                self._disabled = False
            try:
                result = self._exporter.export(batch)
            except Exception:
                self._disabled = True
                self._retry_at = time.monotonic() + (self._retry_interval or 0)
                self._note("failed")
                return self._failure_result
            if result == self._failure_result:
                self._disabled = True
                self._retry_at = time.monotonic() + (self._retry_interval or 0)
                self._note("failed")
            elif result == self._success_result:
                self._note("sent")
            return result

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        with self._lock:
            if self._disabled or self._shutdown:
                return True
            force_flush = getattr(self._exporter, "force_flush", None)
            if not callable(force_flush):
                return True
            try:
                result = force_flush(timeout_millis)
            except Exception:
                self._disabled = True
                self._note("failed")
                return False
            if result is False:
                self._disabled = True
                self._note("failed")
            return result is not False

    def shutdown(self) -> None:
        with self._lock:
            if self._shutdown:
                return
            self._shutdown = True
            self._disabled = True
            shutdown = getattr(self._exporter, "shutdown", None)
            if callable(shutdown):
                try:
                    shutdown()
                except Exception:
                    pass


def _configured_otlp_endpoint(signal: str) -> str:
    """Return a configured signal-specific or common OTLP endpoint, if any."""

    for name in (
        f"OTEL_EXPORTER_OTLP_{signal.upper()}_ENDPOINT",
        "OTEL_EXPORTER_OTLP_ENDPOINT",
    ):
        endpoint = (os.getenv(name) or "").strip()
        if endpoint:
            return endpoint
    return ""


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

    def __init__(
        self, span: Any, *, capture_content: bool, operation: str = ""
    ) -> None:
        self._span = span
        self._capture_content = capture_content
        self._operation = operation
        self._captured_messages: dict[str, list[dict[str, Any]]] = {}
        self._content_ordinals: set[int] = set()
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

    def _content_attribute_fits_sdk(self, encoded: str) -> bool:
        """Avoid SDK truncation that would corrupt a serialized JSON value."""
        # SpanLimits is authoritative for this exact SDK span, including
        # OTEL_SPAN_ATTRIBUTE_VALUE_LENGTH_LIMIT and its global fallback.
        # Only the concrete OTel adapter inspects this private SDK contract.
        try:
            limits = getattr(self._span, "_limits", None)
            if limits is None:
                return True  # Non-SDK test spans; the real SDK exposes limits.
            value_limit = limits.max_span_attribute_length
            if value_limit is None:
                return True
            return type(value_limit) is int and len(encoded) <= value_limit
        except Exception:
            return False

    def add_content_event(self, event: object) -> bool:
        """Write trusted, sanitized content as GenAI semconv 1.44 span attributes.

        Python OTel attributes cannot represent arbitrary structured values.
        The conventions permit a JSON-encoded string for these span attributes.
        This is a breaking change: legacy `uag.content` events are not emitted.
        """
        if not self._capture_content:
            return False
        try:
            from .content_capture import PreparedContentEvent

            if type(event) is not PreparedContentEvent or not event.is_trusted():
                return False
            category, value, ordinal = event.category, event.value, event.ordinal
            if (
                type(category) is not str
                or type(value) is not str
                or type(ordinal) is not int
                or not 1 <= ordinal <= 32
                or ordinal in self._content_ordinals
            ):
                return False

            if self._operation == "invoke_agent":
                if category == "user_input":
                    key, role = "gen_ai.input.messages", "user"
                elif category == "assistant_output":
                    key, role = "gen_ai.output.messages", "assistant"
                else:
                    return False
                message = {
                    "role": role,
                    "parts": [{"type": "text", "content": value}],
                }
                # An invocation produces one output, not N model choices.
                # Intermediate assistant messages must not masquerade as
                # separate output choices; retain the latest eligible reply.
                if category == "assistant_output":
                    messages = [message]
                else:
                    messages = [
                        *self._captured_messages.get(key, []),
                        message,
                    ]
                encoded = json.dumps(
                    messages, ensure_ascii=False, separators=(",", ":")
                )
                if not self._content_attribute_fits_sdk(encoded):
                    return False
                self._span.set_attribute(key, encoded)
                self._captured_messages[key] = messages
            elif self._operation == "execute_tool":
                if category not in {"tool_arguments", "tool_result"}:
                    return False
                if category == "tool_arguments":
                    data = json.loads(value)
                    if type(data) is not dict:
                        return False
                    key = "gen_ai.tool.call.arguments"
                else:
                    # The reviewed tool result can be a scalar string. The
                    # standard tool-result shape is an object, so wrap it
                    # without exposing the original unsanitized value.
                    key = "gen_ai.tool.call.result"
                    try:
                        data = json.loads(value)
                    except (ValueError, TypeError):
                        data = value
                    if type(data) is not dict:
                        data = {"content": data}
                encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
                if not self._content_attribute_fits_sdk(encoded):
                    return False
                self._span.set_attribute(key, encoded)
            else:
                return False
            self._content_ordinals.add(ordinal)
            return True
        except Exception:
            return False

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
            raw_span,
            capture_content=self._settings.capture_content,
            operation=operation,
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
    def attach_remote_context(self, carrier: Mapping[str, str]) -> Iterator[bool]:
        """Attach a valid trusted W3C remote parent for the context duration."""

        traceparent = str(carrier.get("traceparent") or "").strip()
        if not traceparent:
            yield False
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

        attached = token is not None and detach_context is not None
        try:
            yield attached
        finally:
            if attached:
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
    # Do not silently fall back to the SDK's default localhost endpoint. An
    # absent collector is a normal configuration, not an exporter failure.
    from ...admin_pairing import get_otlp_pairing

    has_explicit_endpoint = bool(_configured_otlp_endpoint("traces"))
    paired = get_otlp_pairing() if protocol == "http/protobuf" else None
    pairing_is_usable = paired is not None and not any(
        os.getenv(key)
        for key in (
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "OTEL_EXPORTER_OTLP_HEADERS",
            "OTEL_EXPORTER_OTLP_TRACES_HEADERS",
        )
    )
    if not has_explicit_endpoint and not pairing_is_usable:
        return None

    if protocol == "grpc":
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        return OTLPSpanExporter()
    if protocol == "http/protobuf":
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        # Pairing never overrides explicit exporter headers. The credential is
        # only used for the exact saved Admin endpoint; do not send it to a
        # different destination supplied by the process environment.
        if pairing_is_usable:
            paired_endpoint, token = paired
            configured_endpoint = (
                os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") or ""
            ).strip()
            if not configured_endpoint or configured_endpoint == paired_endpoint:
                exporter = OTLPSpanExporter(
                    endpoint=paired_endpoint,
                    headers={"Authorization": "Bearer " + token},
                )
                # Import can activate Admin after UAG starts. Permit later
                # batches to probe again without retrying every failed batch.
                exporter._uag_admin_pairing = True
                return exporter
            # An explicit different collector takes precedence, without
            # inheriting the paired Admin credentials.
        return OTLPSpanExporter()
    raise ValueError(f"unsupported OTLP traces protocol: {protocol}")


def _build_metric_exporter() -> Any | None:
    # The Admin pairing contract is traces-only. Do not attempt to push
    # metrics to an unsupported Admin endpoint unless explicitly configured.
    from ...admin_pairing import get_otlp_pairing

    if (
        "OTEL_METRICS_EXPORTER" not in os.environ
        and get_otlp_pairing()
        and not any(
            os.getenv(key)
            for key in (
                "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
                "OTEL_EXPORTER_OTLP_ENDPOINT",
            )
        )
    ):
        return None
    configured = (os.getenv("OTEL_METRICS_EXPORTER") or "otlp").strip().lower()
    exporters = {item.strip() for item in configured.split(",") if item.strip()}
    if exporters == {"none"}:
        return None
    if "otlp" not in exporters:
        raise ValueError("UAG metrics supports OTEL_METRICS_EXPORTER=otlp or none")

    # As with traces, never use the SDK's implicit localhost collector.
    if not _configured_otlp_endpoint("metrics"):
        return None

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
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExportResult

    service_name = (os.getenv("OTEL_SERVICE_NAME") or "uagent").strip() or "uagent"
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource, sampler=_sampler_from_environment())
    exporter = _build_trace_exporter()
    if exporter is not None:
        exporter = _FailStopExporter(
            exporter,
            success_result=SpanExportResult.SUCCESS,
            failure_result=SpanExportResult.FAILURE,
            retry_interval=(
                30.0 if getattr(exporter, "_uag_admin_pairing", False) else None
            ),
            status_callback=update_delivery_status,
        )
        from ...admin_pairing import get_otlp_pairing

        if get_otlp_pairing() and "OTEL_BSP_MAX_EXPORT_BATCH_SIZE" not in os.environ:
            provider.add_span_processor(
                BatchSpanProcessor(exporter, max_export_batch_size=256)
            )
        else:
            provider.add_span_processor(BatchSpanProcessor(exporter))
        update_delivery_status("awaiting_export")
    else:
        # OTel can be enabled for local spans with no configured collector.
        update_delivery_status("no_endpoint")
    tracer = provider.get_tracer("uagent.runtime.observability")

    meter = None
    meter_provider = None
    try:
        metric_exporter = _build_metric_exporter()
        if metric_exporter is not None:
            from opentelemetry.sdk.metrics import MeterProvider
            from opentelemetry.sdk.metrics.export import (
                MetricExportResult,
                PeriodicExportingMetricReader,
            )

            metric_exporter = _FailStopExporter(
                metric_exporter,
                success_result=MetricExportResult.SUCCESS,
                failure_result=MetricExportResult.FAILURE,
            )

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
