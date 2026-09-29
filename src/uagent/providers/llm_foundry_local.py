"""Microsoft Foundry Local OpenAI-compatible transport."""

from __future__ import annotations

import ipaddress
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from ..env_utils import env_get


def normalize_foundry_local_base_url(value: str) -> str:
    """Normalize a loopback Foundry Local endpoint to an OpenAI ``/v1`` URL."""
    raw = str(value or "").strip()
    if not raw:
        raise ValueError(
            "UAGENT_FOUNDRY_LOCAL_BASE_URL is required; "
            "use `foundry server status` to obtain the local URL"
        )
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Foundry Local base URL scheme must be http or https")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Foundry Local base URL must not contain credentials")
    host = parsed.hostname
    if not host:
        raise ValueError("Foundry Local base URL must include a host")
    if host.lower() != "localhost":
        try:
            address = ipaddress.ip_address(host)
        except ValueError as exc:
            raise ValueError("Foundry Local base URL host must be loopback") from exc
        if not address.is_loopback:
            raise ValueError("Foundry Local base URL host must be loopback")
    if parsed.query or parsed.fragment:
        raise ValueError("Foundry Local base URL must not contain query or fragment")
    path = parsed.path.rstrip("/")
    if path not in {"", "/v1"}:
        raise ValueError("Foundry Local base URL path must be empty or /v1")
    return urlunsplit((parsed.scheme, parsed.netloc, "/v1", "", ""))


def make_foundry_local_client(core: Any) -> Any:
    """Create an OpenAI client for an already-running Foundry Local server."""
    getter = getattr(core, "get_env", None)
    if callable(getter):
        try:
            configured = str(getter("UAGENT_FOUNDRY_LOCAL_BASE_URL") or "")
        except (KeyError, ValueError):
            configured = ""
    else:
        configured = str(env_get("UAGENT_FOUNDRY_LOCAL_BASE_URL", "") or "")

    base_url = normalize_foundry_local_base_url(configured)
    from openai import OpenAI

    try:
        from .util_providers import make_httpx_client

        return OpenAI(
            api_key="none",
            base_url=base_url,
            http_client=make_httpx_client(),
        )
    except TypeError:
        return OpenAI(api_key="none", base_url=base_url)


__all__ = ["make_foundry_local_client", "normalize_foundry_local_base_url"]
