"""Shared Structured Output configuration and request adapters."""

from __future__ import annotations

import json
from typing import Any

from ..env_utils import env_get

_TRUE = {"1", "true", "yes", "on", "enable", "enabled"}
_FALSE = {"0", "false", "no", "off", "disable", "disabled"}


def structured_output_enabled() -> bool:
    """Return whether native structured output is enabled (default: enabled)."""
    raw = (env_get("UAGENT_STRUCTURED_OUTPUT", "true") or "true").strip().lower()
    return raw not in _FALSE


def _structured_request(messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Read the internal response-mode/schema markers from system messages."""
    if not structured_output_enabled():
        return None
    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "system":
            continue
        content = message.get("content", "")
        if not isinstance(content, str) or "response_mode: json" not in content:
            continue
        schema: Any = None
        marker = "\n\nresponse_schema:\n"
        if marker in content:
            raw = content.split(marker, 1)[1]
            for end_marker in (
                "\n\nrequired_fields:",
                "\n\nstrict_output:",
                "\n\nevidence_required:",
            ):
                raw = raw.split(end_marker, 1)[0]
            try:
                schema = json.JSONDecoder().raw_decode(raw.lstrip())[0]
            except (TypeError, ValueError, json.JSONDecodeError):
                schema = None
        if isinstance(schema, dict):
            return {
                "type": "json_schema",
                "json_schema": {
                    "name": "response",
                    "strict": True,
                    "schema": schema,
                },
            }
        return {"type": "json_object"}
    return None


def structured_output_request(messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the normalized requested JSON output format for a provider."""
    return _structured_request(messages)


def native_structured_output_request(
    messages: list[dict[str, Any]], *, model_id: str = "", provider: str = ""
) -> dict[str, Any] | None:
    """Select a native format only when llmcapa confirms the exact model."""
    requested = _structured_request(messages)
    if requested is None:
        return None
    try:
        from ..llmcapa_util import supports_json_mode, supports_json_schema

        schema_ok = supports_json_schema(model_id, provider)
        json_ok = supports_json_mode(model_id, provider)
    except Exception:
        schema_ok = json_ok = None
    if requested.get("type") == "json_schema" and schema_ok is True:
        return requested
    if json_ok is True:
        return {"type": "json_object"}
    return None


def apply_openai_chat_structured_output(
    chat_kwargs: dict[str, Any], *, provider: str, messages: list[dict[str, Any]], model_id: str = ""
) -> None:
    """Apply OpenAI Chat Completions Structured Output when requested."""
    if (
        provider not in {"openai", "azure", "openrouter", "deepseek"}
        or "response_format" in chat_kwargs
    ):
        return
    response_format = native_structured_output_request(
        messages, model_id=model_id or str(chat_kwargs.get("model", "")), provider=provider
    )
    if response_format is not None:
        chat_kwargs["response_format"] = response_format


def apply_openai_responses_structured_output(
    resp_kwargs: dict[str, Any], *, provider: str, messages: list[dict[str, Any]], model_id: str = ""
) -> None:
    """Apply OpenAI Responses API ``text.format`` when requested."""
    if provider not in {"openai", "azure", "openrouter", "deepseek"}:
        return
    response_format = native_structured_output_request(
        messages, model_id=model_id or str(resp_kwargs.get("model", "")), provider=provider
    )
    if response_format is None:
        return
    if response_format.get("type") == "json_schema":
        schema = response_format["json_schema"]
        fmt = {
            "type": "json_schema",
            "name": schema["name"],
            "strict": schema["strict"],
            "schema": schema["schema"],
        }
    else:
        fmt = {"type": "json_object"}
    text = resp_kwargs.get("text")
    if not isinstance(text, dict):
        text = {}
    text["format"] = fmt
    resp_kwargs["text"] = text
