"""Microsoft Foundry Local OpenAI-compatible client for UAG.

UAG connects to an already-running loopback endpoint. It does not start the
service, download/load models, or use the Foundry Local SDK here.
"""

from __future__ import annotations

import ipaddress
import sys
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit

from ..auth.provider_credentials import get_provider_api_key
from ..env_utils import env_get

_FOUNDRY_LOCAL_PROGRESS_LABELS = {
    "ResponseStarted": "LLM:Foundry:inference",
    "ReasoningDelta": "LLM:Foundry:reasoning",
    "TextDelta": "LLM:Foundry:streaming",
    "ToolCallDelta": "LLM:Foundry:tool-call",
}


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
    """Log allowlisted metadata for Foundry's legacy compatibility path.

    The OpenAI-compatible registry has its own debug hook. This covers the
    compatibility fallback while excluding prompts, outputs, and tool
    arguments from diagnostics.
    """
    enabled = (env_get("UAGENT_DEBUG_OPENAI_RUNTIME", "") or "").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
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
        "status_code",
        "error_class",
    }
    safe_fields = {key: value for key, value in fields.items() if key in allowed}
    rendered = " ".join(f"{key}={value!r}" for key, value in safe_fields.items())
    print(
        f"[OPENAI_RUNTIME] provider='foundry_local' event={event!r} {rendered}".rstrip(),
        file=sys.stderr,
        flush=True,
    )


class FoundryLocalProgressObserver:
    """Report observable progress, recognizing split inline ``<think>`` tags.

    The observer reads only tag boundaries to switch the status label. It does
    not render or store the reasoning text itself.
    """

    _THINK_START = "<think>"
    _THINK_END = "</think>"

    def __init__(self, core: Any) -> None:
        self._core = core
        self._in_reasoning = False
        self._marker_tail = ""
        self._last_phase = ""

    def __call__(self, event: Any) -> None:
        event_type = str(getattr(event, "type", "") or "")
        if event_type == "ResponseStarted":
            self._in_reasoning = False
            self._marker_tail = ""
            self._last_phase = "inference"
            update_foundry_local_progress(self._core, event_type)
        elif event_type == "TextDelta":
            data = getattr(event, "data", {})
            text = data.get("text", "") if isinstance(data, Mapping) else ""
            if isinstance(text, str) and text:
                self._observe_text(text)
        elif event_type == "ReasoningDelta":
            self._set_phase("reasoning")
        elif event_type == "ToolCallDelta":
            if self._last_phase != "tool-call":
                self._last_phase = "tool-call"
                update_foundry_local_progress(self._core, event_type)
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
            http_client=make_httpx_client(),
        )
    except TypeError:
        client = OpenAI(api_key=api_key, base_url=base_url)

    return client, model_name


__all__ = [
    "FoundryLocalProgressObserver",
    "debug_foundry_local_runtime",
    "foundry_local_progress_label",
    "make_foundry_local_client",
    "normalize_foundry_local_base_url",
    "update_foundry_local_progress",
]
