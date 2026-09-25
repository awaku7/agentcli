from __future__ import annotations

import asyncio
from contextlib import contextmanager

from uagent.runtime.execution import lifecycle_execution
from uagent.runtime.identity_context import TurnContext
from uagent.runtime.observability.api import TraceIds
from uagent.runtime.observability.trusted_ingress import (
    RawSocketPeerCaptureMiddleware,
    SingleUseTrustedIngressCarrier,
    bind_trusted_ingress_carrier,
    call_with_trusted_ingress,
    get_trusted_ingress_carrier,
    trusted_ingress_carrier_for_request,
)

_TRACEPARENT = "00-11111111111111111111111111111111-2222222222222222-01"
_TRACESTATE = "vendor=value"


class _Client:
    def __init__(self, host: str) -> None:
        self.host = host


class _Request:
    def __init__(
        self,
        host: str,
        headers: dict[str, str],
        *,
        raw_host: str | None = None,
    ) -> None:
        self.client = _Client(host)
        self.headers = headers
        peer = raw_host if raw_host is not None else host
        self.scope = {"uagent.raw_socket_peer": (peer, 12345)}


class _Span:
    def __init__(self) -> None:
        self.attributes: dict[str, object] = {}
        self.status: tuple[str, str | None] | None = None

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value

    def add_event(self, name: str, attributes=None) -> None:
        return None

    def record_exception(self, exc: BaseException) -> None:
        return None

    def set_status(self, status: str, description: str | None = None) -> None:
        self.status = (status, description)


class _Backend:
    enabled = True

    def __init__(self, *, fail_attach: bool = False) -> None:
        self.fail_attach = fail_attach
        self.attach_calls: list[dict[str, str]] = []
        self.start_calls: list[dict[str, object]] = []
        self.span = _Span()

    @contextmanager
    def attach_remote_context(self, carrier):
        self.attach_calls.append(dict(carrier))
        if self.fail_attach:
            raise RuntimeError("attach failed")
        yield None

    @contextmanager
    def start_span(self, operation: str, *, attributes=None, root: bool = False):
        self.start_calls.append(
            {
                "operation": operation,
                "attributes": dict(attributes or {}),
                "root": root,
            }
        )
        yield self.span

    def current_trace_ids(self) -> TraceIds:
        return TraceIds()

    def record_event(self, *args, **kwargs) -> None:
        return None

    def record_counter(self, *args, **kwargs) -> None:
        return None

    def record_histogram(self, *args, **kwargs) -> None:
        return None

    def inject_context(self, carrier) -> None:
        return None


def _web_turn() -> TurnContext:
    return TurnContext(
        principal_id="principal",
        room_id="room",
        project_id="project",
        session_id="session",
        entry_point="web",
        authenticated=True,
        authn_kind="oidc",
    )


def test_trusted_ingress_defaults_off(monkeypatch) -> None:
    monkeypatch.delenv("UAGENT_OTEL_TRUSTED_PROXY_CIDRS", raising=False)
    request = _Request("127.0.0.1", {"traceparent": _TRACEPARENT})

    assert trusted_ingress_carrier_for_request(request).take() == {}


def test_trusted_ingress_uses_raw_peer_not_forwarded_or_rewritten_client(
    monkeypatch,
) -> None:
    monkeypatch.setenv("UAGENT_OTEL_TRUSTED_PROXY_CIDRS", "127.0.0.1/32")
    request = _Request(
        "127.0.0.1",
        {
            "traceparent": _TRACEPARENT,
            "x-forwarded-for": "127.0.0.1",
        },
        raw_host="203.0.113.50",
    )

    assert trusted_ingress_carrier_for_request(request).take() == {}


def test_trusted_ingress_accepts_only_w3c_trace_context(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_OTEL_TRUSTED_PROXY_CIDRS", "127.0.0.0/8")
    request = _Request(
        "198.51.100.9",
        {
            "traceparent": _TRACEPARENT,
            "tracestate": _TRACESTATE,
            "baggage": "principal_id=secret",
            "authorization": "Bearer secret",
        },
        raw_host="127.0.0.1",
    )

    assert trusted_ingress_carrier_for_request(request).take() == {
        "traceparent": _TRACEPARENT,
        "tracestate": _TRACESTATE,
    }


def test_trusted_ingress_bad_allowlist_fails_closed(monkeypatch) -> None:
    monkeypatch.setenv(
        "UAGENT_OTEL_TRUSTED_PROXY_CIDRS", "127.0.0.1/32,not-a-network"
    )
    request = _Request("127.0.0.1", {"traceparent": _TRACEPARENT})

    assert trusted_ingress_carrier_for_request(request).take() == {}


def test_trusted_ingress_requires_raw_peer_capture(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_OTEL_TRUSTED_PROXY_CIDRS", "127.0.0.1/32")
    request = _Request("127.0.0.1", {"traceparent": _TRACEPARENT})
    request.scope = {}

    assert trusted_ingress_carrier_for_request(request).take() == {}


def test_raw_peer_capture_precedes_proxy_rewrite() -> None:
    seen: dict[str, object] = {}

    async def inner(scope, receive, send) -> None:
        seen["raw"] = scope.get("uagent.raw_socket_peer")
        scope["client"] = ("198.51.100.42", 0)
        seen["client"] = scope.get("client")

    middleware = RawSocketPeerCaptureMiddleware(inner)
    asyncio.run(
        middleware(
            {"type": "websocket", "client": ("127.0.0.1", 4321)},
            None,
            None,
        )
    )

    assert seen == {
        "raw": ("127.0.0.1", 4321),
        "client": ("198.51.100.42", 0),
    }


def test_handshake_carrier_is_consumed_once() -> None:
    carrier = SingleUseTrustedIngressCarrier(
        {"traceparent": _TRACEPARENT, "tracestate": _TRACESTATE}
    )

    assert carrier.take() == {
        "traceparent": _TRACEPARENT,
        "tracestate": _TRACESTATE,
    }
    assert carrier.take() == {}


def test_single_use_carrier_is_consumed_by_worker_binding() -> None:
    carrier = SingleUseTrustedIngressCarrier({"traceparent": _TRACEPARENT})

    first = call_with_trusted_ingress(carrier, get_trusted_ingress_carrier)
    second = call_with_trusted_ingress(carrier, get_trusted_ingress_carrier)

    assert first == {"traceparent": _TRACEPARENT}
    assert second == {}
    assert get_trusted_ingress_carrier() == {}


def test_trusted_ingress_binding_is_scoped() -> None:
    assert get_trusted_ingress_carrier() == {}

    seen = call_with_trusted_ingress(
        {"traceparent": _TRACEPARENT, "baggage": "secret=yes"},
        get_trusted_ingress_carrier,
    )

    assert seen == {"traceparent": _TRACEPARENT}
    assert get_trusted_ingress_carrier() == {}


def test_web_agent_span_continues_explicitly_trusted_parent(monkeypatch) -> None:
    from uagent.runtime.observability import bootstrap

    backend = _Backend()
    monkeypatch.setattr(bootstrap, "get_observability_backend", lambda: backend)

    with bind_trusted_ingress_carrier(
        {"traceparent": _TRACEPARENT, "tracestate": _TRACESTATE}
    ):
        with lifecycle_execution(turn_context=_web_turn()):
            pass

    assert backend.attach_calls == [
        {"traceparent": _TRACEPARENT, "tracestate": _TRACESTATE}
    ]
    assert backend.start_calls[0]["operation"] == "invoke_agent"
    assert backend.start_calls[0]["root"] is False


def test_web_agent_span_stays_fresh_root_without_trusted_parent(monkeypatch) -> None:
    from uagent.runtime.observability import bootstrap

    backend = _Backend()
    monkeypatch.setattr(bootstrap, "get_observability_backend", lambda: backend)

    with lifecycle_execution(turn_context=_web_turn()):
        pass

    assert backend.attach_calls == []
    assert backend.start_calls[0]["root"] is True


def test_trusted_parent_attach_failure_isolated_and_falls_back_to_root(
    monkeypatch,
) -> None:
    from uagent.runtime.observability import bootstrap

    backend = _Backend(fail_attach=True)
    monkeypatch.setattr(bootstrap, "get_observability_backend", lambda: backend)

    with bind_trusted_ingress_carrier({"traceparent": _TRACEPARENT}):
        with lifecycle_execution(turn_context=_web_turn()):
            pass

    assert backend.attach_calls == [{"traceparent": _TRACEPARENT}]
    assert backend.start_calls[0]["root"] is True
