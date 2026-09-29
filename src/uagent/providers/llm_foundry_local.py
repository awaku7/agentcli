"""Microsoft Foundry Local OpenAI-compatible client for UAG.

UAG does not start, download, load, or probe Foundry Local models here.
The caller supplies the already-running loopback endpoint. Capability
routing remains offline and is resolved through llmcapa.
"""

from __future__ import annotations

import ipaddress
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from ..auth.provider_credentials import get_provider_api_key
from ..env_utils import env_get


class _FoundryLocalChatCompletionsProxy:
    """Enforce Foundry Local function-calling capability at the send boundary."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def create(self, *args: Any, **kwargs: Any) -> Any:
        model_name = str(kwargs.get("model") or "").strip()
        try:
            from ..llmcapa_util import supports_feature

            tools_allowed = (
                supports_feature(
                    "function_calling",
                    model_name or None,
                    "foundry_local",
                    default=None,
                )
                is True
            )
        except Exception:
            tools_allowed = False

        if not tools_allowed and ("tools" in kwargs or "tool_choice" in kwargs):
            kwargs = dict(kwargs)
            kwargs.pop("tools", None)
            kwargs.pop("tool_choice", None)
        return self._inner.create(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class _FoundryLocalChatProxy:
    def __init__(self, inner: Any) -> None:
        self._inner = inner

    @property
    def completions(self) -> _FoundryLocalChatCompletionsProxy:
        return _FoundryLocalChatCompletionsProxy(self._inner.completions)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class _FoundryLocalClientProxy:
    """Transparent OpenAI client proxy with Foundry-specific safety gates."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    @property
    def chat(self) -> _FoundryLocalChatProxy:
        return _FoundryLocalChatProxy(self._inner.chat)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def normalize_foundry_local_base_url(value: str) -> str:
    """Return a loopback-only OpenAI base URL ending in ``/v1``."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("UAGENT_FOUNDRY_LOCAL_BASE_URL is required")
    parsed = urlsplit(value.strip())
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


def make_foundry_local_client(core: Any, model_name: str) -> tuple[Any, str]:
    """Create an OpenAI-compatible client for an existing Foundry Local service."""
    getter = getattr(core, "get_env", None)

    def get(name: str, default: str = "") -> str:
        if callable(getter):
            try:
                return str(getter(name) or default)
            except (KeyError, ValueError):
                return default
        return str(env_get(name, default) or default)

    base_url = normalize_foundry_local_base_url(
        get("UAGENT_FOUNDRY_LOCAL_BASE_URL", "")
    )
    api_key = (
        get_provider_api_key(
            "foundry_local",
            store=getattr(core, "credential_store", None),
            env_getter=getter if callable(getter) else None,
        )
        or "dummy"
    )

    from openai import OpenAI

    try:
        from .util_providers import make_httpx_client

        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=make_httpx_client(),
        )
    except TypeError:
        client = OpenAI(api_key=api_key, base_url=base_url)

    return _FoundryLocalClientProxy(client), model_name


__all__ = ["make_foundry_local_client", "normalize_foundry_local_base_url"]
