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
_MANAGEMENT_TOOL_NAMES = frozenset({"tool_catalog", "tool_load", "unload_tool"})
_CATALOG_FALLBACK_TOOL_NAMES = frozenset({"search_web", "fetch_url"})
_LIVE_WEB_QUERY_HINTS = (
    "天気",
    "予報",
    "ニュース",
    "最新",
    "株価",
    "為替",
    "相場",
    "運行",
    "遅延",
    "営業時間",
    "空席",
    "予約",
    "検索",
    "調べて",
    "調べる",
    "weather",
    "forecast",
    "news",
    "latest",
    "current price",
    "stock price",
    "exchange rate",
    "traffic",
    "delay",
    "open now",
    "availability",
    "reservation",
    "search the web",
    "web search",
    "search online",
    "look up",
    "internet",
)

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


def _tool_name(spec: Any) -> str:
    if not isinstance(spec, Mapping):
        return ""
    name = spec.get("name")
    function = spec.get("function")
    if not name and isinstance(function, Mapping):
        name = function.get("name")
    return str(name or "").strip()


def _tool_names(tools: Any) -> list[str]:
    if not isinstance(tools, (list, tuple)):
        return []
    return [name for name in (_tool_name(spec) for spec in tools) if name]


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


def _render_tool_choice(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        function = value.get("function")
        if isinstance(function, Mapping):
            name = str(function.get("name") or "").strip()
            if name:
                return f"function:{name}"
        return str(value.get("type") or "object")
    return ""


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
                "message_count": (
                    len(messages) if isinstance(messages, (list, tuple)) else 0
                ),
                "tool_count": len(tools) if isinstance(tools, (list, tuple)) else 0,
                "tool_names": _tool_names(tools),
                "tool_choice": _render_tool_choice(payload.get("tool_choice")),
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
    """Map normalized runtime events to safe Foundry progress labels."""

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
        "tool_choice",
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
    """Report observable progress and hash visible streamed response text."""

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


def _forced_tool_choice(name: str) -> dict[str, Any]:
    return {"type": "function", "function": {"name": name}}


def _latest_tool_message_after_user(messages: Any) -> Mapping[str, Any] | None:
    if not isinstance(messages, (list, tuple)):
        return None
    for message in reversed(messages):
        if not isinstance(message, Mapping):
            continue
        role = str(message.get("role") or "").strip().lower()
        if role == "user":
            return None
        if role == "tool":
            return message
    return None


def _decode_tool_result(content: Any) -> dict[str, Any] | None:
    if isinstance(content, Mapping):
        return dict(content)
    if not isinstance(content, str):
        return None
    text = content.strip()
    begin = "---BEGIN_UAGENT_EXTERNAL_CONTENT---"
    end = "---END_UAGENT_EXTERNAL_CONTENT---"
    if text.startswith(begin) and text.endswith(end):
        text = text[len(begin) : -len(end)].strip()
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _catalog_selected_tool(result: Mapping[str, Any]) -> str:
    auto_loaded = result.get("auto_loaded")
    if isinstance(auto_loaded, str) and auto_loaded.strip():
        return auto_loaded.strip()
    rows = result.get("tools")
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            name = str(row.get("name") or "").strip()
            if name and name not in _MANAGEMENT_TOOL_NAMES:
                return name
    return ""


def _tool_load_selected_tool(result: Mapping[str, Any]) -> str:
    name = result.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    loaded = result.get("loaded")
    if isinstance(loaded, str) and loaded.strip():
        return loaded.strip()
    if isinstance(loaded, list):
        names = [str(item).strip() for item in loaded if str(item).strip()]
        if len(names) == 1:
            return names[0]
    return ""


def _query_needs_catalog_fallback(query: str) -> str:
    """Return the generic fallback tool justified by an explicit lookup intent."""

    text = (query or "").strip().lower()
    if not text:
        return ""
    if "://" in text:
        return "fetch_url"
    if any(hint in text for hint in _LIVE_WEB_QUERY_HINTS):
        return "search_web"
    return ""


def _relevant_foundry_local_tool_names(messages: Any) -> set[str] | None:
    """Return catalog-ranked concrete tools for the latest user request.

    ``None`` means the local catalog could not be consulted. An empty set means
    the catalog found no concrete tool related to the request, so forcing a
    management-tool round would only add latency and can change normal chat.

    ``get_tool_catalog`` always appends ``search_web`` and ``fetch_url`` as
    discovery fallbacks. Those rows are not evidence of tool intent by
    themselves, so they are only retained for explicit live/web/URL requests.
    """

    query = _content_text(_last_user_content(messages)).strip()
    if not query:
        return set()
    try:
        from .. import tools as tool_registry

        rows = tool_registry.get_tool_catalog(query=query, max_results=12)
    except Exception:
        return None

    names: set[str] = set()
    for row in rows or []:
        if not isinstance(row, Mapping):
            continue
        name = str(row.get("name") or "").strip()
        if name and name not in _MANAGEMENT_TOOL_NAMES:
            names.add(name)

    specific = names - _CATALOG_FALLBACK_TOOL_NAMES
    if specific:
        return specific

    fallback = _query_needs_catalog_fallback(query)
    if fallback and fallback in names:
        return {fallback}
    return set()


def resolve_foundry_local_tool_choice(messages: Any, tools: Any) -> Any:
    """Choose a deterministic tool policy for Foundry Local ChatCompletions.

    Some Foundry Local model/runtime combinations expose function calling but do
    not reliably implement ``tool_choice=auto``. UAG therefore uses a bounded
    deterministic sequence only when the local tool catalog finds a concrete
    capability related to the current user request:

    - relevant tool already exposed: force it when the match is unambiguous;
    - relevant tool not exposed yet: force ``tool_catalog`` to load/select it;
    - no relevant concrete tool: disable tools and let the model answer normally;
    - after a concrete tool result: disable tools for the final answer.

    If the local catalog cannot make a safe decision, ``auto`` is preserved as a
    best-effort fallback instead of guessing a tool.
    """

    available = _tool_names(tools)
    available_set = set(available)
    if not available:
        return None

    last_tool = _latest_tool_message_after_user(messages)
    if last_tool is None:
        relevant = _relevant_foundry_local_tool_names(messages)
        if relevant is None:
            return "auto"
        if not relevant:
            return "none"
        matching = [
            name
            for name in available
            if name in relevant and name not in _MANAGEMENT_TOOL_NAMES
        ]
        if len(matching) == 1:
            return _forced_tool_choice(matching[0])
        if "tool_catalog" in available_set:
            return _forced_tool_choice("tool_catalog")
        return "auto"

    tool_name = str(last_tool.get("name") or "").strip()
    result = _decode_tool_result(last_tool.get("content"))

    if tool_name == "tool_catalog":
        candidate = _catalog_selected_tool(result or {})
        if candidate and candidate in available_set:
            return _forced_tool_choice(candidate)
        return "none"

    if tool_name == "tool_load":
        candidate = _tool_load_selected_tool(result or {})
        if candidate and candidate in available_set:
            return _forced_tool_choice(candidate)
        return "none"

    if tool_name == "unload_tool":
        if "tool_catalog" in available_set:
            return _forced_tool_choice("tool_catalog")
        return "none"

    return "none"


def apply_foundry_local_chat_compat(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Return ChatCompletions kwargs with Foundry Local tool-choice workarounds."""

    out = dict(kwargs)
    tools = out.get("tools")
    if not isinstance(tools, (list, tuple)) or not tools:
        return out

    requested = out.get("tool_choice", "auto")
    if requested not in (None, "auto"):
        return out

    choice = resolve_foundry_local_tool_choice(out.get("messages"), tools)
    if choice is None:
        return out

    if choice == "none":
        out.pop("tools", None)
        out.pop("tool_choice", None)
        out.pop("parallel_tool_calls", None)
        return out

    out["tool_choice"] = choice
    if isinstance(choice, Mapping):
        function = choice.get("function")
        forced_name = (
            str(function.get("name") or "").strip()
            if isinstance(function, Mapping)
            else ""
        )
        if forced_name:
            matching = [spec for spec in tools if _tool_name(spec) == forced_name]
            if matching:
                out["tools"] = matching
    return out


def _suppress_duplicate_tool_call_text(response: Any) -> Any:
    """Blank Foundry's textual tool marker when structured tool_calls exist."""

    try:
        choices = getattr(response, "choices", None)
        if not choices:
            return response
        message = getattr(choices[0], "message", None)
        if message is None:
            return response
        tool_calls = getattr(message, "tool_calls", None) or []
        content = getattr(message, "content", None)
        if (
            tool_calls
            and isinstance(content, str)
            and "<|tool_call|>" in content
            and "<|/tool_call|>" in content
        ):
            message.content = ""
    except Exception:
        pass
    return response


def _exception_status_code(exception: Exception) -> int | None:
    status = getattr(exception, "status_code", None) or getattr(exception, "status", None)
    if status is None:
        response = getattr(exception, "response", None)
        status = getattr(response, "status_code", None) or getattr(response, "status", None)
    try:
        return int(status) if status is not None else None
    except (TypeError, ValueError):
        return None


def _is_foundry_local_server_error(exception: Exception) -> bool:
    status = _exception_status_code(exception)
    if status is not None:
        return 500 <= status <= 599
    text = f"{type(exception).__name__}: {exception}".lower()
    return any(
        marker in text
        for marker in (
            "internal server error",
            "http 500",
            "error code: 500",
            "bad gateway",
            "service unavailable",
            "gateway timeout",
        )
    )


def _required_followup_fallback(kwargs: Mapping[str, Any]) -> dict[str, Any] | None:
    """Use ``required`` for a single concrete tool after management-tool output."""

    last_tool = _latest_tool_message_after_user(kwargs.get("messages"))
    if last_tool is None:
        return None
    last_name = str(last_tool.get("name") or "").strip()
    if last_name not in {"tool_catalog", "tool_load"}:
        return None

    choice = kwargs.get("tool_choice")
    if not isinstance(choice, Mapping):
        return None
    function = choice.get("function")
    forced_name = (
        str(function.get("name") or "").strip()
        if isinstance(function, Mapping)
        else ""
    )
    if not forced_name or forced_name in _MANAGEMENT_TOOL_NAMES:
        return None

    tools = kwargs.get("tools")
    if not isinstance(tools, (list, tuple)) or len(tools) != 1:
        return None
    if _tool_name(tools[0]) != forced_name:
        return None

    out = dict(kwargs)
    out["tool_choice"] = "required"
    return out


class FoundryLocalServerError(RuntimeError):
    """Sanitized local-runtime 5xx error that must not enter generic 429 retry."""


def _raise_foundry_local_server_error(exception: Exception, *, phase: str) -> None:
    status = _exception_status_code(exception)
    print(
        f"[FOUNDRY_LOCAL_SERVER_ERROR] status={status!r} phase={phase}",
        file=sys.stderr,
        flush=True,
    )
    raise FoundryLocalServerError(
        f"Foundry Local request failed during {phase}"
    ) from exception


class _FoundryLocalCompletionsCompat:
    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def create(self, *args: Any, **kwargs: Any) -> Any:
        effective = apply_foundry_local_chat_compat(kwargs)
        try:
            response = self._inner.create(*args, **effective)
        except Exception as exception:
            if not _is_foundry_local_server_error(exception):
                raise
            fallback = _required_followup_fallback(effective)
            if fallback is None:
                _raise_foundry_local_server_error(exception, phase="chat completion")
            debug_foundry_local_runtime(
                "tool_followup_fallback",
                route="chat_completions",
                status_code=_exception_status_code(exception),
                error_class=type(exception).__name__,
                tool_choice="required",
            )
            try:
                response = self._inner.create(*args, **fallback)
            except Exception as fallback_exception:
                if _is_foundry_local_server_error(fallback_exception):
                    _raise_foundry_local_server_error(
                        fallback_exception,
                        phase="tool follow-up",
                    )
                raise
        if not effective.get("stream"):
            _suppress_duplicate_tool_call_text(response)
        return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class _FoundryLocalChatCompat:
    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.completions = _FoundryLocalCompletionsCompat(inner.completions)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def _install_foundry_local_chat_compat(client: Any) -> Any:
    """Install the compatibility wrapper without changing the OpenAI client type."""

    try:
        chat = getattr(client, "chat", None)
        if chat is None or getattr(chat, "completions", None) is None:
            return client
        if isinstance(chat, _FoundryLocalChatCompat):
            return client
        client.chat = _FoundryLocalChatCompat(chat)
    except Exception:
        pass
    return client


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

    return _install_foundry_local_chat_compat(client), model_name


__all__ = [
    "FoundryLocalProgressObserver",
    "FoundryLocalServerError",
    "apply_foundry_local_chat_compat",
    "debug_foundry_local_runtime",
    "foundry_local_debug_enabled",
    "foundry_local_progress_label",
    "make_foundry_local_client",
    "normalize_foundry_local_base_url",
    "resolve_foundry_local_tool_choice",
    "update_foundry_local_progress",
]
