"""Explicit reverse-proxy trust policy for inbound Web trace context.

The policy is intentionally independent from authentication and authorization.
Only the actual socket peer is considered for trust; forwarded client-address
headers never make an ingress trusted.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar, Token
from ipaddress import IPv4Network, IPv6Network, ip_address, ip_network
from typing import Any, TypeVar

from ...env_utils import env_get

_TRUSTED_PROXY_CIDRS_ENV = "UAGENT_OTEL_TRUSTED_PROXY_CIDRS"
_TRUSTED_INGRESS_CARRIER: ContextVar[tuple[tuple[str, str], ...]] = ContextVar(
    "uagent_trusted_ingress_carrier", default=()
)
_T = TypeVar("_T")


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


def trusted_ingress_carrier_for_request(request: object) -> dict[str, str]:
    """Return trusted W3C trace headers for an explicitly allowlisted peer.

    Trust is selected only by server-side ``UAGENT_OTEL_TRUSTED_PROXY_CIDRS``
    configuration and the request's actual socket peer. ``X-Forwarded-For`` and
    similar headers are deliberately ignored. Baggage is never accepted.
    """

    networks = _trusted_proxy_networks()
    if not networks:
        return {}

    client = getattr(request, "client", None)
    peer_host = str(getattr(client, "host", "") or "").strip()
    if not peer_host:
        return {}
    try:
        peer = ip_address(peer_host)
    except ValueError:
        return {}
    if not any(peer in network for network in networks):
        return {}

    headers = getattr(request, "headers", None)
    if headers is None:
        return {}
    try:
        carrier = {
            "traceparent": str(headers.get("traceparent", "") or "").strip(),
            "tracestate": str(headers.get("tracestate", "") or "").strip(),
        }
    except Exception:
        return {}
    return _normalize_carrier(carrier)


def set_trusted_ingress_carrier(
    carrier: Mapping[str, Any] | None,
) -> Token[tuple[tuple[str, str], ...]]:
    """Bind only the supported trusted trace-context fields in this context."""

    normalized = _normalize_carrier(carrier)
    compact = tuple((key, normalized[key]) for key in ("traceparent", "tracestate") if key in normalized)
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
    carrier: Mapping[str, Any] | None,
    func: Callable[..., _T],
    *args: Any,
    **kwargs: Any,
) -> _T:
    """Run one worker call with its server-approved ingress trace carrier."""

    with bind_trusted_ingress_carrier(carrier):
        return func(*args, **kwargs)
