"""Provider projection policy for OpenAI-compatible registry requests.

This module owns translation from UAGENT request policy to the native request
fields consumed by the OpenAI/Azure runtime adapter.  It deliberately does not
call an SDK or mutate messages; transport-specific serialization remains inside
the provider runtime.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any, Mapping

from .. import llmcapa_util
from ..env_utils import env_get
from ..llm_helpers import (
    _choose_auto_effort,
    _extract_latest_user_text,
    _is_thinking_task,
)
from ..runtime.capability_resolver import (
    native_structured_output_request_for_runtime,
)
from .provider_caps import temperature_env_name


@dataclass(frozen=True)
class OpenAIProjection:
    """Typed policy output used to build one OpenAI-compatible request."""

    options: dict[str, Any]
    reasoning: str
    auto_user_text: str
    effort_used: str | None


def _verified_vllm_reasoning_efforts(model: str) -> set[str]:
    """Only accept effort values explicitly verified for this vLLM model.

    llmcapa's provider defaults are not evidence that a particular vLLM
    deployment/model accepts the same levels. Never borrow another provider's
    model row or assume the generic low/medium/high fallback.
    """
    cap = llmcapa_util.get_capability(model, "vllm", scoped_only=True)
    if cap is None or getattr(cap, "supports_reasoning_effort", None) is not True:
        return set()
    values = getattr(cap, "reasoning_effort_values", None)
    if not isinstance(values, (list, tuple)):
        return set()
    return {
        value.strip().lower()
        for value in values
        if isinstance(value, str) and value.strip()
    }


def sanitize_sarashina_tool_specs(tool_specs: Any) -> list[dict[str, Any]]:
    """Strip tool-schema keywords outside Sarashina's documented subset."""

    def sanitize(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {
                key: sanitize(item)
                for key, item in value.items()
                if key
                not in {
                    "additionalProperties",
                    "default",
                    "description",
                    "maximum",
                    "minimum",
                }
                and not (key == "required" and item == [])
            }
        if isinstance(value, list):
            return [sanitize(item) for item in value]
        return value

    normalized: list[dict[str, Any]] = []
    for spec in tool_specs or ():
        if not isinstance(spec, Mapping):
            continue
        item = dict(spec)
        function = item.get("function")
        if isinstance(function, Mapping):
            function_item = dict(function)
            parameters = function_item.get("parameters")
            if isinstance(parameters, Mapping):
                projected_parameters = sanitize(parameters)
                if function_item.get("name") == "tool_load":
                    properties = projected_parameters.get("properties")
                    if isinstance(properties, dict):
                        properties.pop("names", None)
                    projected_parameters["required"] = ["name"]
                    function_item["description"] = (
                        "Load one or more tools by name after tool_catalog identifies "
                        "them. Put multiple comma- or whitespace-separated tool names "
                        "in the name string."
                    )
                function_item["parameters"] = projected_parameters
            item["function"] = function_item
        normalized.append(item)
    return normalized


def sanitize_sarashina_messages(messages: Any) -> list[dict[str, Any]]:
    """Project messages to the roles and keys documented by Sarashina."""
    normalized: list[dict[str, Any]] = []
    allowed_roles = {"system", "user", "assistant", "tool"}
    for message in messages or ():
        if not isinstance(message, Mapping):
            continue
        role = str(message.get("role") or "").strip().lower()
        if role == "developer":
            role = "system"
        if role not in allowed_roles:
            raise ValueError(
                f"Sarashina Chat Completions does not support role {role!r}"
            )
        item: dict[str, Any] = {"role": role}
        if "content" in message:
            content = message.get("content")
            if content is None or isinstance(content, str):
                item["content"] = content
            else:
                raise ValueError(
                    "Sarashina Chat Completions currently accepts text-only message content"
                )
        if role == "assistant":
            tool_calls = message.get("tool_calls")
            if isinstance(tool_calls, list):
                item["tool_calls"] = [
                    {
                        "id": str(call.get("id") or ""),
                        "type": "function",
                        "function": {
                            "name": str((call.get("function") or {}).get("name") or ""),
                            "arguments": str(
                                (call.get("function") or {}).get("arguments") or "{}"
                            ),
                        },
                    }
                    for call in tool_calls
                    if isinstance(call, Mapping)
                    and isinstance(call.get("function"), Mapping)
                ]
        elif role == "tool" and message.get("tool_call_id") is not None:
            item["tool_call_id"] = str(message.get("tool_call_id"))
        normalized.append(item)
    return normalized


def sarashina_message_shapes(messages: Any) -> list[dict[str, Any]]:
    """Describe Sarashina message roles/keys without logging message values."""
    shapes: list[dict[str, Any]] = []
    for message in messages or ():
        if not isinstance(message, Mapping):
            continue
        content = message.get("content")
        content_type = "null" if content is None else type(content).__name__
        shapes.append(
            {
                "role": str(message.get("role") or ""),
                "fields": sorted(str(key) for key in message),
                "content_type": content_type,
            }
        )
    return shapes


def sarashina_tool_schema_field_names(tool_specs: Any) -> list[str]:
    """Return schema keyword names only; never include tool values or arguments."""
    names: set[str] = set()

    def visit(schema: Any) -> None:
        if not isinstance(schema, Mapping):
            return
        for key, value in schema.items():
            names.add(str(key))
            if key == "properties" and isinstance(value, Mapping):
                for child_schema in value.values():
                    visit(child_schema)
            elif key == "items":
                visit(value)
            elif key in {"anyOf", "oneOf", "allOf"} and isinstance(value, list):
                for child_schema in value:
                    visit(child_schema)

    for spec in tool_specs or ():
        if not isinstance(spec, Mapping):
            continue
        function = spec.get("function")
        parameters = (
            function.get("parameters") if isinstance(function, Mapping) else None
        )
        visit(parameters)
    return sorted(names)


def sarashina_tool_schema_fields_by_tool(tool_specs: Any) -> dict[str, list[str]]:
    """Report schema keyword names per function, without exposing values."""
    fields: dict[str, list[str]] = {}
    for spec in tool_specs or ():
        if not isinstance(spec, Mapping):
            continue
        function = spec.get("function")
        if not isinstance(function, Mapping):
            continue
        name = str(function.get("name") or "")
        if name:
            fields[name] = sarashina_tool_schema_field_names([spec])
    return dict(sorted(fields.items()))


def build_openai_projection(
    *,
    provider: str,
    model: str,
    transport: str,
    messages: list[dict[str, Any]],
    send_tools: bool,
    compaction_threshold: int,
) -> OpenAIProjection:
    """Project environment and semantic request policy into native options.

    The returned mapping is provider-adapter input only.  This function has no
    network side effects and never changes ``messages``.
    """
    use_responses_api = (transport or "").strip().lower() == "responses"
    provider_key = (provider or "").strip().lower()
    options: dict[str, Any] = {}
    reasoning = (env_get("UAGENT_REASONING", "") or "").strip().lower()
    auto_user_text = ""
    effort_used: str | None = None
    if reasoning == "auto":
        auto_user_text = _extract_latest_user_text(messages)
        if _is_thinking_task(auto_user_text):
            effort_used = _choose_auto_effort(auto_user_text)
    elif reasoning and reasoning not in {"off", "false", "none"}:
        effort_used = reasoning

    if provider_key == "vllm":
        # "off" is only representable by reasoning_effort=none on models
        # explicitly verified to accept that value. Do not silently promise
        # disabled reasoning for an unknown model.
        requested = "none" if reasoning in {"off", "false", "none"} else effort_used
        if requested:
            if requested in _verified_vllm_reasoning_efforts(model):
                if use_responses_api:
                    options["reasoning"] = {"effort": requested}
                else:
                    options["reasoning_effort"] = requested
                effort_used = requested
            else:
                if reasoning != "auto":
                    warnings.warn(
                        f"vLLM model {model!r} has no verified reasoning_effort="
                        f"{requested!r}; the option was omitted, so reasoning "
                        "behavior remains model-controlled.",
                        RuntimeWarning,
                        stacklevel=2,
                    )
                effort_used = None
    elif effort_used:
        if use_responses_api:
            options["reasoning"] = {"effort": effort_used}
        elif provider_key not in {"foundry_local", "sarashina"}:
            # These Chat Completions surfaces do not document reasoning_effort.
            # Let the model/runtime own reasoning rather than sending an
            # unsupported request field.
            options["reasoning_effort"] = effort_used

    response_format = native_structured_output_request_for_runtime(
        messages, model_id=model, provider=provider
    )
    if response_format is not None:
        if use_responses_api:
            if response_format.get("type") == "json_schema":
                schema = response_format["json_schema"]
                options["text"] = {
                    "format": {
                        "type": "json_schema",
                        "name": schema["name"],
                        "strict": (
                            True if provider_key == "perplexity" else schema["strict"]
                        ),
                        "schema": schema["schema"],
                    }
                }
            elif provider_key == "perplexity":
                # Router Responses accepts JSON Schema but rejects json_object.
                options["text"] = {
                    "format": {
                        "type": "json_schema",
                        "name": "json_output",
                        "strict": True,
                        "schema": {"type": "object"},
                    }
                }
            else:
                options["text"] = {"format": {"type": "json_object"}}
        else:
            options["response_format"] = response_format

    verbosity = (env_get("UAGENT_VERBOSITY", "") or "").strip().lower()
    if use_responses_api and verbosity in {"low", "medium", "high"}:
        text = options.get("text")
        text = dict(text) if isinstance(text, dict) else {}
        text["verbosity"] = verbosity
        options["text"] = text

    max_tokens = (env_get("UAGENT_MAX_TOKENS", "") or "").strip()
    if max_tokens:
        try:
            limit = llmcapa_util.clamp_max_tokens(int(max_tokens), model, provider)
            if provider_key == "sarashina":
                # Sarashina currently accepts max_completion_tokens up to 8000.
                limit = min(limit, 8000)
            if use_responses_api:
                options["max_output_tokens"] = limit
            elif provider_key == "sarashina" or str(model or "").lower().startswith(
                ("gpt-5", "o1", "o2", "o3", "o4")
            ):
                options["max_completion_tokens"] = limit
            else:
                options["max_tokens"] = limit
        except ValueError:
            pass

    top_p = (env_get("UAGENT_TOP_P", "") or "").strip()
    if not use_responses_api and top_p:
        try:
            options["top_p"] = float(top_p)
        except ValueError:
            pass

    if not use_responses_api:
        # Provider-specific temperature wins over the shared setting. Avoid
        # adding a generic default on the registry path: some reasoning models
        # reject any explicit temperature. vLLM and Inception retain their
        # provider-specific defaults from the legacy path.
        temp_name = temperature_env_name(provider_key)
        temperature = (env_get(temp_name) if temp_name else "") or ""
        if not temperature.strip():
            temperature = env_get("UAGENT_TEMPERATURE", "") or ""
        default_temperature = 0.75 if provider_key == "inception" else 0.2
        provider_has_default = provider_key in {"inception", "vllm"}
        resolved_temperature: float | None = None
        if temperature.strip():
            try:
                resolved_temperature = float(temperature.strip())
            except ValueError:
                if provider_has_default:
                    resolved_temperature = default_temperature
        elif provider_has_default:
            resolved_temperature = default_temperature
        if resolved_temperature is not None:
            if provider_key == "inception":
                resolved_temperature = min(1.0, max(0.5, resolved_temperature))
            options["temperature"] = resolved_temperature

    if provider == "openai" and (
        env_get("UAGENT_OPENAI_FAST_MODE", "") or ""
    ).strip().lower() in {"1", "true", "yes", "on", "fast"}:
        options["service_tier"] = "fast"

    if use_responses_api:
        # Perplexity Router's Responses endpoint is stateless and rejects
        # unknown fields such as OpenAI's context_management extension.
        if provider_key != "perplexity":
            options["context_management"] = [
                {"type": "compaction", "compact_threshold": compaction_threshold}
            ]

    if provider_key == "vllm":
        budget_text = (env_get("UAGENT_VLLM_THINKING_TOKEN_BUDGET", "") or "").strip()
        if budget_text:
            # This is a numerical, per-request reasoning ceiling, not an effort.
            if not budget_text.isascii() or not budget_text.isdecimal():
                raise ValueError(
                    "UAGENT_VLLM_THINKING_TOKEN_BUDGET must be a positive integer"
                )
            budget = int(budget_text)
            if budget <= 0:
                raise ValueError(
                    "UAGENT_VLLM_THINKING_TOKEN_BUDGET must be a positive integer"
                )
            if use_responses_api:
                raise ValueError(
                    "thinking_token_budget is not verified for vLLM Responses API; "
                    "set UAGENT_RESPONSES=0 to use Chat Completions"
                )
            cap = llmcapa_util.get_capability(model, "vllm", scoped_only=True)
            control = cap.get_thinking_control() if cap is not None else None
            if (
                getattr(cap, "supports_thinking_budget", None) is not True
                or not isinstance(control, dict)
                or control.get("kind") != "budget"
                or control.get("parameter") != "thinking_token_budget"
            ):
                raise ValueError(
                    f"vLLM model {model!r} has no verified thinking_token_budget "
                    "support in llmcapa"
                )
            options["extra_body"] = {"thinking_token_budget": budget}

    if send_tools:
        options["tool_choice"] = "auto"
        if not use_responses_api and provider_key in {"openai", "azure"}:
            options["reasoning_effort"] = "none"

    return OpenAIProjection(
        options=options,
        reasoning=reasoning,
        auto_user_text=auto_user_text,
        effort_used=effort_used,
    )


__all__ = [
    "OpenAIProjection",
    "build_openai_projection",
    "sanitize_sarashina_messages",
    "sanitize_sarashina_tool_specs",
    "sarashina_message_shapes",
    "sarashina_tool_schema_field_names",
    "sarashina_tool_schema_fields_by_tool",
]
