"""Microsoft Foundry Local OpenAI-compatible client for UAG.

UAG connects to an already-running loopback endpoint. It does not start the
service, download/load models, or use the Foundry Local SDK here.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import sys
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit

from ..auth.provider_credentials import get_provider_api_key
from ..env_utils import env_get

_TRUE_VALUES = {"1", "true", "yes", "on"}

_FOUNDRY_LOCAL_PROGRESS_LABELS = {
    "ResponseStarted": "LLM:Foundry:inference",
    "ReasoningDelta": "LLM:Foundry:reasoning",
    "TextDelta": "LLM:Foundry:streaming",
    "ToolCallDelta": "LLM:Foundry:tool-call",
}


def foundry_local_debug_enabled() -> bool:
    """Return whether Foundry Local diagnostics are enabled.

    ``UAGENT_DEBUG_FOUNDRY_LOCAL`` is the provider-specific opt-in switch.
    ``UAGENT_DEBUG_OPENAI_RUNTIME`` remains accepted for backward compatibility.
    """

    local = (env_get("UAGENT_DEBUG_FOUNDRY_LOCAL", "") or "").strip().lower()
    if local in _TRUE_VALUES:
        return True
    generic = (env_get("UAGENT_DEBUG_OPENAI_RUNTIME", "") or "").strip().lower()
    return generic in _TRUE_VALUES


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    except (TypeError, ValueError):
        text = str(value)
    return text.encode("utf-8", errors="replace")


def _content_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
                continue
            if not isinstance(item, Mapping):
                continue
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
                continue
            nested = item.get("content")
            if isinstance(nested, str):
                parts.append(nested)
        if parts:
            return "\n".join(parts)
    if value is None:
        return ""
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return str(value)


def _last_user_content(messages: Any) -> Any:
    if not isinstance(messages, (list, tuple)):
        return None
    for message in reversed(messages):
        if not isinstance(message, Mapping):
            continue
        if str(message.get("role") or "").strip().lower() == "user":
            return message.get("content")
    return None


def _tool_names(tools: Any) -> list[str]:
    names: list[str] = []
    if not isinstance(tools, (list, tuple)):
        return names
    for spec in tools:
        if not isinstance(spec, Mapping):
            continue
        name = spec.get("name")
        function = spec.get("function")
        if not name and isinstance(function, Mapping):
            name = function.get("name")
        if isinstance(name, str) and name:
            names.append(name)
    return names


def _request_payload(request: Any) -> tuple[bytes, dict[str, Any] | None]:
    try:
        raw = request.content
    except Exception:
        raw = b""
    if isinstance(raw, str):
        raw = raw.encode("utf-8", errors="replace")
    elif not isinstance(raw, (bytes, bytearray)):
        raw = bytes(raw or b"")
    raw_bytes = bytes(raw)
    try:
        parsed = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        parsed = None
    return raw_bytes, parsed if isinstance(parsed, dict) else None


def _foundry_local_request_diagnostics(request: Any) -> None:
    """Log privacy-preserving diagnostics for the actual wire request."""

    if not foundry_local_debug_enabled():
        return
    raw, payload = _request_payload(request)
    fields: dict[str, Any] = {
        "request_sha256": _sha256_bytes(raw),
    }
    if payload is not None:
        messages = payload.get("messages")
        transport = "chat_completions"
        if messages is None:
            messages = payload.get("input")
            transport = "responses"
        tools = payload.get("tools") or ()
        last_user = _last_user_content(messages)
        last_user_text = _content_text(last_user)
        fields.update(
            {
                "model": payload.get("model"),
                "transport": transport,
                "streaming": bool(payload.get("stream")),
                "message_count": len(messages)
                if isinstance(messages, (list, tuple))
                else 0,
                "tool_count": len(tools) if isinstance(tools, (list, tuple)) else 0,
                "tool_names": _tool_names(tools),
                "last_user_chars": len(last_user_text),
                "last_user_sha256": _sha256_bytes(
                    last_user_text.encode("utf-8", errors="replace")
                ),
                "messages_sha256": _sha256_bytes(_json_bytes(messages)),
                "option_keys": sorted(
                    key
                    for key in payload
                    if key not in {"model", "input", "messages", "tools"}
                ),
            }
        )
    debug_foundry_local_runtime("wire_request", **fields)


def _response_text_from_payload(payload: Any) -> str:
    if not isinstance(payload, Mapping):
        return ""
    direct = payload.get("output_text")
    if isinstance(direct, str):
        return direct
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, Mapping):
            message = first.get("message")
            if isinstance(message, Mapping):
                content = message.get("content")
                if isinstance(content, str):
                    return content
    return ""


def _foundry_local_response_diagnostics(response: Any) -> None:
    """Log response hashes for non-streaming diagnostics without exposing text."""

    if not foundry_local_debug_enabled():
        return
    request = getattr(response, "request", None)
    _, request_payload = (
        _request_payload(request) if request is not None else (b"", None)
    )
    streaming = bool(request_payload.get("stream")) if request_payload else False
    fields: dict[str, Any] = {
        "status_code": getattr(response, "status_code", None),
        "streaming": streaming,
    }
    if not streaming:
        try:
            raw = response.read()
        except Exception:
            raw = b""
        if isinstance(raw, str):
            raw = raw.encode("utf-8", errors="replace")
        raw_bytes = bytes(raw or b"")
        fields["wire_response_sha256"] = _sha256_bytes(raw_bytes)
        try:
            payload = json.loads(raw_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            payload = None
        text = _response_text_from_payload(payload)
        if text:
            fields["response_chars"] = len(text)
            fields["response_sha256"] = _sha256_bytes(
                text.encode("utf-8", errors="replace")
            )
    debug_foundry_local_runtime("wire_response", **fields)


def foundry_local_progress_label(event_type: str) -> str | None:
    """Map normalized runtime events to safe Foundry progress labels.

    The label describes observable request phases only. It deliberately does
    not expose model reasoning text or infer an effort level the server did not
    report.
    """
    return _FOUNDRY_LOCAL_PROGRESS_LABELS.get(str(event_type or ""))


def update_foundry_local_progress(core: Any, event_type: str) -> None:
    """Update the host status line for an observable Foundry stream event."""
    label = foundry_local_progress_label(event_type)
    set_status = getattr(core, "set_status", None)
    if label is None or not callable(set_status):
        return
    try:
        set_status(True, label)
    except Exception:
        # Status display is best-effort and must never fail the model request.
        pass


def debug_foundry_local_runtime(event: str, **fields: Any) -> None:
    """Log allowlisted, content-free diagnostics for Foundry Local."""

    if not foundry_local_debug_enabled():
        return
    allowed = {
        "model",
        "transport",
        "streaming",
        "message_count",
        "tool_count",
        "tool_names",
        "finish_reason",
        "tool_call_count",
        "assistant_chars",
        "response_chars",
        "last_user_chars",
        "last_user_sha256",
        "messages_sha256",
        "request_sha256",
        "response_sha256",
        "wire_response_sha256",
        "option_keys",
        "route",
        "status_code",
        "error_class",
    }
    safe_fields = {key: value for key, value in fields.items() if key in allowed}
    rendered = " ".join(f"{key}={value!r}" for key, value in safe_fields.items())
    print(
        f"[FOUNDRY_LOCAL_DEBUG] event={event!r} {rendered}".rstrip(),
        file=sys.stderr,
        flush=True,
    )


class FoundryLocalProgressObserver:
    """Report observable progress and hash visible streamed response text.

    The observer reads only tag boundaries to switch the status label. It does
    not render or store the reasoning text itself. When diagnostics are enabled,
    it also emits a SHA-256 digest of visible TextDelta content at completion.
    """

    _THINK_START = "<think>"
    _THINK_END = "</think>"

    def __init__(self, core: Any) -> None:
        self._core = core
        self._in_reasoning = False
        self._marker_tail = ""
        self._last_phase = ""
        self._response_hasher = hashlib.sha256()
        self._response_chars = 0

    def __call__(self, event: Any) -> None:
        event_type = str(getattr(event, "type", "") or "")
        if event_type == "ResponseStarted":
            self._in_reasoning = False
            self._marker_tail = ""
            self._last_phase = "inference"
            self._response_hasher = hashlib.sha256()
            self._response_chars = 0
            update_foundry_local_progress(self._core, event_type)
        elif event_type == "TextDelta":
            data = getattr(event, "data", {})
            text = data.get("text", "") if isinstance(data, Mapping) else ""
            if isinstance(text, str) and text:
                self._response_hasher.update(text.encode("utf-8", errors="replace"))
                self._response_chars += len(text)
                self._observe_text(text)
        elif event_type == "ReasoningDelta":
            self._set_phase("reasoning")
        elif event_type == "ToolCallDelta":
            if self._last_phase != "tool-call":
                self._last_phase = "tool-call"
                update_foundry_local_progress(self._core, event_type)
        elif event_type == "ResponseCompleted":
            debug_foundry_local_runtime(
                "registry_response",
                route="registry",
                response_chars=self._response_chars,
                response_sha256=self._response_hasher.hexdigest(),
            )
        else:
            update_foundry_local_progress(self._core, event_type)

    def _set_phase(self, phase: str) -> None:
        event_type = {
            "reasoning": "ReasoningDelta",
            "streaming": "TextDelta",
        }.get(phase)
        if event_type and phase != self._last_phase:
            self._last_phase = phase
            update_foundry_local_progress(self._core, event_type)

    @staticmethod
    def _partial_marker_suffix_length(text: str, marker: str) -> int:
        for size in range(min(len(text), len(marker) - 1), 0, -1):
            if text.endswith(marker[:size]):
                return size
        return 0

    def _observe_text(self, text: str) -> None:
        pending = self._marker_tail + text
        self._marker_tail = ""
        while pending:
            marker = self._THINK_END if self._in_reasoning else self._THINK_START
            marker_at = pending.find(marker)
            if marker_at >= 0:
                if marker_at:
                    self._set_phase("reasoning" if self._in_reasoning else "streaming")
                self._in_reasoning = not self._in_reasoning
                self._set_phase("reasoning" if self._in_reasoning else "streaming")
                pending = pending[marker_at + len(marker) :]
                continue

            partial_size = self._partial_marker_suffix_length(pending, marker)
            visible = pending[:-partial_size] if partial_size else pending
            if self._in_reasoning:
                self._set_phase("reasoning")
            elif visible:
                self._set_phase("streaming")
            if partial_size:
                self._marker_tail = pending[-partial_size:]
            return


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
    """Create a standard OpenAI client for an existing Foundry Local endpoint."""
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
            http_client=make_httpx_client(
                event_hooks={
                    "request": [_foundry_local_request_diagnostics],
                    "response": [_foundry_local_response_diagnostics],
                }
            ),
        )
    except TypeError:
        client = OpenAI(api_key=api_key, base_url=base_url)

    return client, model_name


__all__ = [
    "FoundryLocalProgressObserver",
    "debug_foundry_local_runtime",
    "foundry_local_debug_enabled",
    "foundry_local_progress_label",
    "make_foundry_local_client",
    "normalize_foundry_local_base_url",
    "update_foundry_local_progress",
]
