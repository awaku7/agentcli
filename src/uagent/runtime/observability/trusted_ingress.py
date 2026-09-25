"""Explicit reverse-proxy trust policy for inbound Web trace context.

The policy is intentionally independent from authentication and authorization.
Only the raw socket peer captured before proxy-header rewriting is considered
for trust; forwarded client-address headers never make an ingress trusted.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar, Token
from ipaddress import IPv4Network, IPv6Network, ip_address, ip_network
from threading import Lock
from typing import Any, TypeVar

from ...env_utils import env_get

_TRUSTED_PROXY_CIDRS_ENV = "UAGENT_OTEL_TRUSTED_PROXY_CIDRS"
_RAW_SOCKET_PEER_SCOPE_KEY = "uagent.raw_socket_peer"
_TRUSTED_INGRESS_CARRIER: ContextVar[tuple[tuple[str, str], ...]] = ContextVar(
    "uagent_trusted_ingress_carrier", default=()
)
_T = TypeVar("_T")


class RawSocketPeerCaptureMiddleware:
    """Capture the raw ASGI socket peer before proxy-header rewriting."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(
        self, scope: dict[str, Any], receive: Any, send: Any
    ) -> None:
        if scope.get("type") in {"http", "websocket"}:
            scope[_RAW_SOCKET_PEER_SCOPE_KEY] = scope.get("client")
        await self.app(scope, receive, send)


class SingleUseTrustedIngressCarrier:
    """A handshake trace carrier that can be consumed by only one Agent turn."""

    def __init__(self, carrier: Mapping[str, Any] | None = None) -> None:
        self._carrier = _normalize_carrier(carrier)
        self._lock = Lock()

    def take(self) -> dict[str, str]:
        with self._lock:
            carrier = self._carrier
            self._carrier = {}
            return dict(carrier)


def _trusted_proxy_networks() -> tuple[IPv4Network | IPv6Network, ...]:
    """Return the configured peer allowlist, failing closed on bad config."""

    raw = str(env_get(_TRUSTED_PROXY_CIDRS_ENV) or "").strip()
    if not raw:
        return ()
    parts = [part.strip() for part in raw.replace(";", ",").split(",")]
    networks: list[IPv4Network | IPv6Network] = []
    for part in parts:
        if not part:
            continue
        try:
            networks.append(ip_network(part, strict=False))
        except ValueError:
            return ()
    return tuple(networks)


def _normalize_carrier(carrier: Mapping[str, Any] | None) -> dict[str, str]:
    normalized: dict[str, str] = {}
    if not carrier:
        return normalized
    for key in ("traceparent", "tracestate"):
        value = str(carrier.get(key) or "").strip()
        if value:
            normalized[key] = value
    return normalized


def trusted_ingress_carrier_for_request(
    request: object,
) -> SingleUseTrustedIngressCarrier:
    """Return a single-use W3C carrier for an explicitly allowlisted raw peer.

    Trust is selected only by server-side ``UAGENT_OTEL_TRUSTED_PROXY_CIDRS``
    configuration and the raw socket peer stored by
    :class:`RawSocketPeerCaptureMiddleware`. ``X-Forwarded-For`` and similar
    headers are deliberately ignored. Baggage is never accepted.
    """

    networks = _trusted_proxy_networks()
    if not networks:
        return SingleUseTrustedIngressCarrier()

    scope = getattr(request, "scope", None)
    if not isinstance(scope, Mapping):
        return SingleUseTrustedIngressCarrier()
    raw_peer = scope.get(_RAW_SOCKET_PEER_SCOPE_KEY)
    if not isinstance(raw_peer, (tuple, list)) or not raw_peer:
        return SingleUseTrustedIngressCarrier()
    peer_host = str(raw_peer[0] or "").strip()
    if not peer_host:
        return SingleUseTrustedIngressCarrier()
    try:
        peer = ip_address(peer_host)
    except ValueError:
        return SingleUseTrustedIngressCarrier()
    if not any(peer in network for network in networks):
        return SingleUseTrustedIngressCarrier()

    headers = getattr(request, "headers", None)
    if headers is None:
        return SingleUseTrustedIngressCarrier()
    try:
        carrier = {
            "traceparent": str(headers.get("traceparent", "") or "").strip(),
            "tracestate": str(headers.get("tracestate", "") or "").strip(),
        }
    except Exception:
        return SingleUseTrustedIngressCarrier()
    return SingleUseTrustedIngressCarrier(carrier)


def set_trusted_ingress_carrier(
    carrier: Mapping[str, Any] | None,
) -> Token[tuple[tuple[str, str], ...]]:
    """Bind only the supported trusted trace-context fields in this context."""

    normalized = _normalize_carrier(carrier)
    compact = tuple(
        (key, normalized[key])
        for key in ("traceparent", "tracestate")
        if key in normalized
    )
    return _TRUSTED_INGRESS_CARRIER.set(compact)


def reset_trusted_ingress_carrier(token: Token[tuple[tuple[str, str], ...]]) -> None:
    _TRUSTED_INGRESS_CARRIER.reset(token)


def get_trusted_ingress_carrier() -> dict[str, str]:
    return dict(_TRUSTED_INGRESS_CARRIER.get())


@contextmanager
def bind_trusted_ingress_carrier(
    carrier: Mapping[str, Any] | None,
) -> Iterator[None]:
    token = set_trusted_ingress_carrier(carrier)
    try:
        yield
    finally:
        reset_trusted_ingress_carrier(token)


def call_with_trusted_ingress(
    carrier: Mapping[str, Any] | SingleUseTrustedIngressCarrier | None,
    func: Callable[..., _T],
    *args: Any,
    **kwargs: Any,
) -> _T:
    """Run one worker call with its server-approved ingress trace carrier."""

    selected = carrier.take() if isinstance(carrier, SingleUseTrustedIngressCarrier) else carrier
    with bind_trusted_ingress_carrier(selected):
        return func(*args, **kwargs)
