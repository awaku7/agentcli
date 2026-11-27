"""Google Gemini Interactions API adapter for legacy UAG rounds.

UAG keeps conversation state locally and sends stateless Interactions requests
(``store=False``). Provider-generated steps are retained on assistant messages
so thought signatures and function-call history can be replayed on later turns.
"""

from __future__ import annotations

import base64
import json
import uuid
from copy import deepcopy
from typing import Any

from ..env_utils import env_get
from ..llm_helpers import stream_stop_requested, stream_terminal_event
from ..llm_image_helpers import build_image_default_prompt
from ..reasoning_display import show_reasoning

_INTERACTIONS_HISTORY_KEY = "_gemini_interactions_steps"


def _get(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _dump(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return deepcopy(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        for kwargs in (
            {"mode": "json", "exclude_none": True},
            {"exclude_none": True},
            {},
        ):
            try:
                result = model_dump(**kwargs)
                if isinstance(result, dict):
                    return result
            except Exception:
                continue
    return {}


def _message_text(message: dict[str, Any]) -> str:
    try:
        from .llm_gemini import _message_content_text

        return _message_content_text(message).strip()
    except Exception:
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            return "\n".join(
                str(part.get("text") or "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            ).strip()
        return ""


def _native_interaction_steps(message: dict[str, Any]) -> list[dict[str, Any]]:
    """Return previously received Interactions steps, preserving signatures."""
    payload = message.get("_gemini_content")
    if not isinstance(payload, dict):
        return []
    steps = payload.get(_INTERACTIONS_HISTORY_KEY)
    if not isinstance(steps, list):
        return []
    return [step for step in steps if isinstance(step, dict)]


def _media_content_from_attachment(attachment: Any) -> dict[str, Any] | None:
    """Reuse the Gemini attachment reader and map its bytes to Interactions."""
    if not isinstance(attachment, dict):
        return None
    try:
        from .llm_gemini import _attachment_to_gemini_part

        part = _attachment_to_gemini_part(attachment)
    except Exception:
        return None
    if part is None:
        return None
    dumped = _dump(part)
    inline = dumped.get("inline_data") or dumped.get("inlineData")
    if not isinstance(inline, dict):
        return None
    mime = str(inline.get("mime_type") or inline.get("mimeType") or "").strip()
    data = inline.get("data")
    if isinstance(data, bytes):
        data = base64.b64encode(data).decode("ascii")
    if not isinstance(data, str) or not data:
        return None
    if mime.startswith("image/"):
        kind = "image"
    elif mime.startswith("audio/"):
        kind = "audio"
    else:
        return None
    return {"type": kind, "mime_type": mime, "data": data}


def _function_arguments(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {"_raw": value}
    return {}


def _tool_result_content(message: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert a local tool result into Interactions text/media content blocks."""
    content = message.get("content")
    if not isinstance(content, str):
        try:
            content = json.dumps(content, ensure_ascii=False, default=str)
        except Exception:
            content = str(content or "")
    content = content or ""
    try:
        parsed = json.loads(content) if content else None
    except Exception:
        parsed = None
    if isinstance(parsed, dict) and isinstance(parsed.get("screenshot_data"), str):
        text_result = {
            key: value for key, value in parsed.items() if key != "screenshot_data"
        }
        result = [
            {
                "type": "text",
                "text": json.dumps(text_result, ensure_ascii=False, default=str),
            }
        ]
        mime = str(parsed.get("screenshot_media_type") or "image/png")
        result.append(
            {"type": "image", "mime_type": mime, "data": parsed["screenshot_data"]}
        )
        return result
    return [{"type": "text", "text": content}]


def _build_interaction_input(
    messages: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str | None]:
    steps: list[dict[str, Any]] = []
    system_parts: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        text = _message_text(message)
        if role == "system":
            if text:
                system_parts.append(text)
            continue
        if role == "assistant":
            native_steps = _native_interaction_steps(message)
            if native_steps:
                steps.extend(deepcopy(native_steps))
                continue
            if text:
                steps.append(
                    {
                        "type": "model_output",
                        "content": [{"type": "text", "text": text}],
                    }
                )
            for call in message.get("tool_calls") or ():
                if not isinstance(call, dict):
                    continue
                function = call.get("function") or {}
                if not isinstance(function, dict):
                    continue
                name = function.get("name")
                if not isinstance(name, str) or not name:
                    continue
                call_id = str(call.get("id") or f"uag_fc_{uuid.uuid4().hex}")
                steps.append(
                    {
                        "type": "function_call",
                        "id": call_id,
                        "name": name,
                        "arguments": _function_arguments(function.get("arguments")),
                    }
                )
            continue
        if role == "user":
            content: list[dict[str, Any]] = []
            attachments = message.get("attachments")
            has_attachments = isinstance(attachments, list) and bool(attachments)
            if not text and has_attachments:
                text = build_image_default_prompt("describe")
            if text:
                content.append({"type": "text", "text": text})
            if has_attachments:
                for attachment in attachments:
                    part = _media_content_from_attachment(attachment)
                    if part is not None:
                        content.append(part)
            if content:
                steps.append({"type": "user_input", "content": content})
            continue
        if role == "tool":
            call_id = str(message.get("tool_call_id") or "").strip()
            if not call_id:
                continue
            name = message.get("name")
            step: dict[str, Any] = {
                "type": "function_result",
                "call_id": call_id,
                "result": _tool_result_content(message),
            }
            if isinstance(name, str) and name:
                step["name"] = name
            try:
                result_obj = json.loads(str(message.get("content") or ""))
                if isinstance(result_obj, dict) and result_obj.get("success") is False:
                    step["is_error"] = True
            except Exception:
                pass
            steps.append(step)
    return steps, "\n\n".join(system_parts) or None


def _build_interaction_tools(
    *, core: Any, provider: str, send_tools: bool, use_google_search: bool
) -> tuple[list[dict[str, Any]], bool]:
    from ..runtime.execution_broker import (
        computer_use_allowed,
        is_computer_use_tool_spec,
    )
    from .llm_gemini import _gemini_round_tool_specs

    tools_list: list[dict[str, Any]] = []
    computer_allowed = computer_use_allowed()
    native_tool = (
        getattr(core, "computer_use_native_tool", None)
        if core is not None and computer_allowed
        else None
    )
    if isinstance(native_tool, dict) and isinstance(
        native_tool.get("computer_use"), dict
    ):
        native_config = native_tool["computer_use"]
        environment = str(native_config.get("environment") or "browser").strip().lower()
        if environment.startswith("environment_"):
            environment = environment[len("environment_") :]
        computer_config: dict[str, Any] = {
            "type": "computer_use",
            "environment": environment,
        }
        if "enable_prompt_injection_detection" in native_config:
            computer_config["enable_prompt_injection_detection"] = bool(
                native_config["enable_prompt_injection_detection"]
            )
        tools_list.append(computer_config)

    if send_tools:
        context_specs = getattr(core, "context_tool_specs", None)
        if context_specs is None:
            try:
                from .. import tools

                context_specs = tools.get_tool_specs() or []
            except Exception:
                context_specs = []
        tool_specs = (
            list(context_specs) if isinstance(context_specs, (list, tuple)) else []
        )
        if not computer_allowed:
            tool_specs = [
                spec for spec in tool_specs if not is_computer_use_tool_spec(spec)
            ]
        if (
            core is not None
            and computer_allowed
            and getattr(core, "computer_use_runtime", None) is not None
        ):
            from ..computer_use.native import local_computer_tool_spec

            if not any(
                isinstance(spec, dict)
                and (spec.get("function") or {}).get("name") == "computer"
                for spec in tool_specs
            ):
                tool_specs.append(local_computer_tool_spec())

        initial_discovery = (
            (provider or "").strip().lower() in {"gemini", "vertexai"}
            and core is not None
            and not getattr(core, "_gemini_tool_catalog_ready", False)
            and any(
                isinstance(spec, dict)
                and isinstance(spec.get("function"), dict)
                and str(spec["function"].get("name") or "").strip() == "tool_catalog"
                for spec in tool_specs
            )
        )
        tool_specs = _gemini_round_tool_specs(tool_specs, core=core, provider=provider)
        if use_google_search and not initial_discovery:
            tool_specs = [
                spec
                for spec in tool_specs
                if not (
                    isinstance(spec, dict)
                    and isinstance(spec.get("function"), dict)
                    and str(spec["function"].get("name") or "").strip() == "search_web"
                )
            ]
        for spec in tool_specs:
            if not isinstance(spec, dict):
                continue
            function = spec.get("function")
            if not isinstance(function, dict):
                continue
            name = function.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            parameters = function.get("parameters")
            if not isinstance(parameters, dict):
                parameters = {"type": "object", "properties": {}}
            tools_list.append(
                {
                    "type": "function",
                    "name": name,
                    "description": str(function.get("description") or ""),
                    "parameters": deepcopy(parameters),
                }
            )
    elif (
        core is not None
        and computer_allowed
        and getattr(core, "computer_use_runtime", None) is not None
    ):
        from ..computer_use.native import local_computer_tool_spec

        tools_list.append(local_computer_tool_spec())

    initial_discovery = bool(
        core is not None
        and not getattr(core, "_gemini_tool_catalog_ready", False)
        and any(
            item.get("type") == "function" and item.get("name") == "tool_catalog"
            for item in tools_list
        )
    )
    if use_google_search and not initial_discovery:
        tools_list.append({"type": "google_search", "search_types": ["web_search"]})
    return tools_list, initial_discovery


def _reasoning_level(model_name: str, user_text: str, force: str | None) -> str | None:
    from .llm_gemini import (
        _choose_auto_thinking_level,
        _llmcapa_reasoning_levels,
        _normalize_reasoning_env,
    )

    mode = _normalize_reasoning_env(env_get("UAGENT_REASONING"))
    if force:
        mode = force.strip().lower() or mode
    if not mode or mode == "off":
        return None
    if mode == "auto":
        mode = _choose_auto_thinking_level(user_text)
    if mode in {"xhigh", "max"}:
        mode = "high"
    levels = _llmcapa_reasoning_levels(model_name)
    if levels is not None:
        if not levels:
            return None
        if mode not in levels:
            strength_order = ("minimal", "low", "medium", "high", "max", "xhigh")
            mode = next(
                (level for level in strength_order if level in levels),
                sorted(levels)[0],
            )
    return mode if mode in {"minimal", "low", "medium", "high"} else None


def _normalise_tool_call(step: Any) -> dict[str, Any] | None:
    name = _get(step, "name")
    if not isinstance(name, str) or not name:
        return None
    call_id = str(_get(step, "id") or f"gemini_interactions_fc_{uuid.uuid4().hex}")
    arguments = _function_arguments(_get(step, "arguments"))
    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(arguments, ensure_ascii=False),
        },
    }


def _read_response(
    response: Any, *, callbacks: Any, core: Any, stream: bool
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    assistant_text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    raw_steps: list[dict[str, Any]] = []
    for step in _get(response, "steps", []) or []:
        step_data = _dump(step)
        if step_data:
            raw_steps.append(step_data)
        step_type = str(_get(step, "type") or step_data.get("type") or "")
        if step_type == "function_call":
            call = _normalise_tool_call(step)
            if call is not None:
                tool_calls.append(call)
        elif step_type == "model_output":
            for content in _get(step, "content", []) or []:
                if str(_get(content, "type") or "") == "text":
                    text = str(_get(content, "text") or "")
                    if text:
                        assistant_text_parts.append(text)
        elif step_type == "thought":
            for content in _get(step, "summary", []) or []:
                if str(_get(content, "type") or "") != "text":
                    continue
                text = str(_get(content, "text") or "")
                if not text:
                    continue
                callback = getattr(callbacks, "on_reasoning", None)
                if callable(callback):
                    try:
                        callback(text)
                    except Exception:
                        pass
                else:
                    try:
                        show_reasoning(text, provider="Gemini", core=core)
                    except Exception:
                        pass
    assistant_text = "".join(assistant_text_parts)
    if not assistant_text:
        assistant_text = str(_get(response, "output_text") or "")
    content_dump = {_INTERACTIONS_HISTORY_KEY: raw_steps} if raw_steps else {}
    return assistant_text, tool_calls, content_dump


def _record_usage(core: Any, usage: Any) -> None:
    if core is None or usage is None:
        return
    mapping = {
        "input_tokens": "total_input_tokens",
        "output_tokens": "total_output_tokens",
        "total_tokens": "total_tokens",
        "cache_read_input_tokens": "total_cached_tokens",
        "reasoning_output_tokens": "total_thought_tokens",
    }
    measured: dict[str, int] = {}
    for output_name, usage_name in mapping.items():
        value = _get(usage, usage_name)
        if isinstance(value, (int, float)) and value >= 0:
            measured[output_name] = int(value)
    if measured:
        try:
            core._last_responses_usage = measured
        except (AttributeError, TypeError):
            pass


def _emit_stream_delta(callbacks: Any, core: Any, text: str) -> None:
    if not text:
        return
    callback = getattr(callbacks, "on_delta", None)
    if callable(callback):
        try:
            callback(text)
            return
        except Exception:
            pass
    try:
        if core is not None and bool(getattr(core, "_is_web", False)):
            log_message = getattr(core, "log_message", None)
            if callable(log_message):
                log_message({"type": "assistant_stream_delta", "delta": text})
                return
    except Exception:
        pass
    print_delta = (
        getattr(core, "print_stream_delta", None) if core is not None else None
    )
    if callable(print_delta):
        print_delta(text)
    else:
        print(text, end="", flush=True)


def gemini_interactions_chat_with_tools(
    client: Any,
    model_name: str,
    messages: list[dict[str, Any]],
    *,
    stream: bool = False,
    core: Any = None,
    force_thinking_level: str | None = None,
    send_tools: bool = True,
    provider: str = "gemini",
    callbacks: Any = None,
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    """Call the Gemini Interactions API and normalize its result for UAG."""
    callbacks = callbacks or object()
    interactions = getattr(client, "interactions", None)
    create = getattr(interactions, "create", None)
    if not callable(create):
        raise RuntimeError(
            "The configured google-genai client has no Interactions API; "
            "upgrade google-genai to 2.3.0 or newer."
        )

    try:
        from ..llmcapa_util import get_capability

        capability = get_capability(model_name, provider)
        if (
            capability is not None
            and getattr(capability, "supports_interactions_api", None) is False
        ):
            raise ValueError(
                f"Model {model_name!r} is not listed as supporting the Interactions API "
                f"for provider {provider!r}. Select a supported model or set "
                "UAGENT_GEMINI_API_MODE=generate_content."
            )
    except ValueError:
        raise
    except Exception:
        # Capability data is optional; the API remains the final authority for
        # custom model IDs and installations with an older llmcapa snapshot.
        pass

    api_key_search = (env_get("UAGENT_GEMINI_WEB_SEARCH") or "").strip().lower()
    use_google_search = (
        True if api_key_search == "" else api_key_search in {"1", "true", "yes", "on"}
    )
    input_steps, system_instruction = _build_interaction_input(messages)
    tools_list, initial_discovery = _build_interaction_tools(
        core=core,
        provider=provider,
        send_tools=send_tools,
        use_google_search=use_google_search,
    )
    if not input_steps:
        input_steps = [
            {"type": "user_input", "content": [{"type": "text", "text": "Continue."}]}
        ]

    from .llm_gemini import _extract_latest_user_text, _verbosity_to_max_output_tokens

    latest_user = _extract_latest_user_text(messages)
    reasoning_level = _reasoning_level(model_name, latest_user, force_thinking_level)
    generation_config: dict[str, Any] = {}
    max_output_tokens = _verbosity_to_max_output_tokens("off")
    if max_output_tokens is not None:
        try:
            from ..llmcapa_util import clamp_max_tokens, current_provider

            max_output_tokens = clamp_max_tokens(
                max_output_tokens, model_name, current_provider() or provider
            )
        except Exception:
            pass
    if isinstance(max_output_tokens, int) and max_output_tokens > 0:
        generation_config["max_output_tokens"] = max_output_tokens
    if reasoning_level:
        generation_config["thinking_level"] = reasoning_level
    include_thoughts = (
        (env_get("UAGENT_GEMINI_INCLUDE_THOUGHTS") or "1").strip().lower()
    )
    generation_config["thinking_summaries"] = (
        "none" if include_thoughts in {"0", "false", "no", "off"} else "auto"
    )
    if initial_discovery:
        generation_config["tool_choice"] = {
            "allowed_tools": {"mode": "any", "tools": ["tool_catalog"]}
        }

    request: dict[str, Any] = {
        "model": model_name,
        "input": input_steps,
        # UAG owns and persists the conversation locally. Do not store prompts
        # or tool results in Google's Interaction history by default.
        "store": False,
    }
    if system_instruction:
        request["system_instruction"] = system_instruction
    if tools_list:
        # Interactions tool definitions are request-scoped; resend them even
        # when the stateless input contains previous function-call/result steps.
        request["tools"] = tools_list
    if generation_config:
        request["generation_config"] = generation_config
    try:
        from ..runtime.capability_resolver import (
            native_structured_output_request_for_runtime,
        )

        output_format = native_structured_output_request_for_runtime(
            messages, model_id=model_name, provider=provider
        )
        if isinstance(output_format, dict):
            if output_format.get("type") == "json_schema":
                schema = (output_format.get("json_schema") or {}).get("schema")
                if isinstance(schema, dict):
                    request["response_format"] = {
                        "type": "text",
                        "mime_type": "application/json",
                        "schema": schema,
                    }
            elif output_format.get("type") == "json_object":
                request["response_format"] = {
                    "type": "text",
                    "mime_type": "application/json",
                }
    except Exception:
        # Keep structured-output fallback prompt markers intact if the optional
        # runtime capability resolver is unavailable or rejects this model.
        pass
    safety_off = (env_get("UAGENT_GEMINI_SAFETY_OFF") or "1").strip().lower()
    if safety_off in {"1", "true", "yes", "on"}:
        request["safety_settings"] = [
            {"type": category, "threshold": "block_none"}
            for category in (
                "harassment",
                "hate_speech",
                "sexually_explicit",
                "dangerous_content",
                "civic_integrity",
            )
        ]

    # Temperature is documented for Interactions generation_config, but is
    # absent from some google-genai typed schemas. Send it through extra_body
    # while retaining the other typed generation_config fields.
    temperature_env = (
        env_get("UAGENT_GEMINI_TEMPERATURE") or env_get("UAGENT_TEMPERATURE") or ""
    ).strip()
    try:
        temperature = float(temperature_env) if temperature_env else 0.2
    except ValueError:
        temperature = 0.2
    generation_config_extra = dict(generation_config)
    generation_config_extra["temperature"] = temperature
    extra_body = {"generation_config": generation_config_extra}

    if stream:
        if callable(getattr(callbacks, "on_terminal", None)):
            try:
                callbacks.on_terminal("ResponseStarted", {})
            except Exception:
                pass
        try:
            if core is not None and bool(getattr(core, "_is_web", False)):
                log_message = getattr(core, "log_message", None)
                if callable(log_message):
                    log_message({"type": "assistant_stream_start"})
        except Exception:
            pass

    try:
        from .util_providers import call_vertexai_with_region_fallback

        response = call_vertexai_with_region_fallback(
            core,
            client,
            model_name,
            lambda active_client: active_client.interactions.create(
                **request, extra_body=extra_body
            ),
            provider=provider,
        )
    except Exception:
        if stream:
            try:
                if core is not None and bool(getattr(core, "_is_web", False)):
                    log_message = getattr(core, "log_message", None)
                    if callable(log_message):
                        log_message({"type": "assistant_stream_end"})
            except Exception:
                pass
            callback = getattr(callbacks, "on_terminal", None)
            if callable(callback):
                try:
                    callback("ResponseFailed", {})
                except Exception:
                    pass
        raise
    status = str(_get(response, "status") or "").strip().lower()
    if status in {"failed", "cancelled", "budget_exceeded"}:
        errors = _get(response, "errors") or []
        error_text = "; ".join(str(_get(error, "message") or error) for error in errors)
        if stream:
            try:
                if core is not None and bool(getattr(core, "_is_web", False)):
                    log_message = getattr(core, "log_message", None)
                    if callable(log_message):
                        log_message({"type": "assistant_stream_end"})
            except Exception:
                pass
            callback = getattr(callbacks, "on_terminal", None)
            if callable(callback):
                try:
                    callback("ResponseFailed", {"status": status})
                except Exception:
                    pass
        raise RuntimeError(
            f"Gemini Interactions API returned status {status}"
            + (f": {error_text}" if error_text else ".")
        )
    assistant_text, tool_calls, content_dump = _read_response(
        response, callbacks=callbacks, core=core, stream=stream
    )
    if core is not None and stream_stop_requested(core):
        assistant_text = ""
        tool_calls = []
        content_dump = {}
    elif stream:
        _emit_stream_delta(callbacks, core, assistant_text)
        for tool_call in tool_calls:
            callback = getattr(callbacks, "on_tool_call", None)
            if callable(callback):
                try:
                    callback(dict(tool_call))
                except Exception:
                    pass

    _record_usage(core, _get(response, "usage"))
    if stream:
        try:
            if core is not None and bool(getattr(core, "_is_web", False)):
                log_message = getattr(core, "log_message", None)
                if callable(log_message):
                    log_message({"type": "assistant_stream_end"})
        except Exception:
            pass
        callback = getattr(callbacks, "on_terminal", None)
        if callable(callback):
            try:
                callback(stream_terminal_event(core), {})
            except Exception:
                pass
        if (
            assistant_text
            and not bool(getattr(core, "_is_web", False))
            and not assistant_text.endswith("\n")
        ):
            print("")

    return assistant_text, tool_calls, content_dump


__all__ = ["gemini_interactions_chat_with_tools"]
