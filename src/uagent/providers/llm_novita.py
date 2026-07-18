"""Novita AI chat completion helper.

OpenAI-compatible Chat Completions API. Reasoning models return
``reasoning_content`` alongside ``content`` in the same format as DeepSeek's
API, so the parsing logic mirrors that of ``llm_deepseek`` but is fully
independent (no imports from DeepSeek modules).

- No extra_body / thinking.type / reasoning_effort parameters needed.
- No temperature suppression in thinking mode (Novita handles it server-side).
- No tool repair complexity (Novita uses standard OpenAI tool format).
"""

from __future__ import annotations

import json
import uuid
from typing import Any
from urllib.error import URLError

try:
    from openai import APIConnectionError, BadRequestError
except Exception:
    APIConnectionError = None
    BadRequestError = None

from .. import tools as _tools
from ..env_utils import env_get
from ..i18n import _
from ..llm_errors import _rate_limit_retry_step
from ..llm_helpers import _maybe_print_certifi_where
from ..reasoning_display import show_reasoning

_LABEL = "Novita"
_ENV_PREFIX = "UAGENT_NOVITA"


# ---------------------------------------------------------------------------
# reasoning_content helpers
# ---------------------------------------------------------------------------


def _extract_reasoning_content(msg: Any) -> str:
    """Pull reasoning_content out of an OpenAI SDK message object or dict."""
    rc = getattr(msg, "reasoning_content", None)
    if isinstance(rc, str):
        return rc
    if isinstance(msg, dict):
        rc = msg.get("reasoning_content")
        if isinstance(rc, str):
            return rc
    return ""


def _strip_reasoning_content(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return a copy of messages with reasoning_content removed from assistant
    messages that have NO tool_calls.

    Assistant messages WITH tool_calls must retain reasoning_content.
    Assistant messages WITHOUT tool_calls must NOT include reasoning_content.
    """
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.get("role") == "assistant" and "reasoning_content" in m:
            has_tool_calls = bool(m.get("tool_calls"))
            if not has_tool_calls:
                m = {k: v for k, v in m.items() if k != "reasoning_content"}
        out.append(m)
    return out


# ---------------------------------------------------------------------------
# Response parser (non-streaming)
# ---------------------------------------------------------------------------


def _parse_novita_response(resp: Any) -> tuple[str, str, list[dict[str, Any]]]:
    """Parse a non-streaming chat completion response from Novita.

    Returns ``(assistant_text, reasoning_content, tool_calls_list)``.
    """
    choice = resp.choices[0]
    msg = choice.message

    reasoning_content = _extract_reasoning_content(msg)

    tool_calls_list: list[dict[str, Any]] = []
    raw_tool_calls = getattr(msg, "tool_calls", None) or []
    for tc in raw_tool_calls:
        tc_id = getattr(tc, "id", None)
        fn_obj = getattr(tc, "function", None)
        if fn_obj is None and isinstance(tc, dict):
            tc_id = tc.get("id")
            fn_obj = tc.get("function") or {}
        fn_name = getattr(fn_obj, "name", None)
        fn_args = getattr(fn_obj, "arguments", None)
        if isinstance(fn_obj, dict):
            fn_name = fn_obj.get("name")
            fn_args = fn_obj.get("arguments")
        if not isinstance(fn_name, str) or not fn_name:
            continue
        if isinstance(fn_args, dict):
            fn_args = json.dumps(fn_args, ensure_ascii=False)
        elif fn_args is None:
            fn_args = "{}"
        elif not isinstance(fn_args, str):
            fn_args = str(fn_args)
        # Generate synthetic ID when the API returns empty/missing tool_call_id.
        # This prevents sanitize_messages_for_tools from dropping tool results
        # as orphans, which would cause the model to repeat the same tool call.
        _tid = tc_id if tc_id else uuid.uuid4().hex[:12]
        tool_calls_list.append(
            {
                "id": _tid,
                "type": "function",
                "function": {"name": fn_name, "arguments": fn_args},
            }
        )

    raw_content = getattr(msg, "content", "")
    if isinstance(raw_content, str):
        assistant_text = raw_content
    elif raw_content is None:
        assistant_text = ""
    elif isinstance(raw_content, list):
        parts: list[str] = []
        for item in raw_content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                for key in ("text", "content", "value"):
                    if isinstance(item.get(key), str):
                        parts.append(item[key])
                        break
            else:
                txt = getattr(item, "text", None)
                if isinstance(txt, str):
                    parts.append(txt)
        assistant_text = "".join(parts)
    else:
        assistant_text = str(raw_content)

    return assistant_text, reasoning_content, tool_calls_list


# ---------------------------------------------------------------------------
# Streaming parser
# ---------------------------------------------------------------------------


def _parse_novita_stream(
    stream: Any,
    *,
    print_delta_fn: Any = None,
    core: Any = None,
) -> tuple[str, str, list[dict[str, Any]]]:
    """Consume a streaming response from Novita.

    Returns ``(assistant_text, reasoning_content, tool_calls_list)``.
    ``reasoning_content`` deltas are accumulated but NOT printed to stdout.
    """
    text_parts: list[str] = []
    reasoning_parts: list[str] = []
    tool_calls_acc: dict[int, dict[str, Any]] = {}
    is_web = bool(getattr(core, "_is_web", False)) if core else False
    _reasoning_printed = False

    try:
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            rc_delta = getattr(delta, "reasoning_content", None)
            if isinstance(rc_delta, str) and rc_delta:
                reasoning_parts.append(rc_delta)
                # Print reasoning as gray text in CLI streaming
                show_reasoning(
                    rc_delta,
                    provider="Novita",
                    is_first=(not _reasoning_printed),
                    print_fn=print_delta_fn,
                    core=core,
                )
                _reasoning_printed = True

            content_delta = getattr(delta, "content", None)
            if isinstance(content_delta, str) and content_delta:
                text_parts.append(content_delta)
                if print_delta_fn and not is_web:
                    # Prepend newline when transitioning from reasoning to content
                    if _reasoning_printed:
                        _reasoning_printed = False
                        print_delta_fn("\n" + content_delta)
                    else:
                        print_delta_fn(content_delta)
                elif is_web and core is not None:
                    try:
                        lm = getattr(core, "log_message", None)
                        if callable(lm):
                            lm(
                                {
                                    "type": "assistant_stream_delta",
                                    "delta": content_delta,
                                }
                            )
                    except Exception:
                        pass

            tc_deltas = getattr(delta, "tool_calls", None) or []
            for tc_delta in tc_deltas:
                idx = getattr(tc_delta, "index", 0) or 0
                if idx not in tool_calls_acc:
                    tool_calls_acc[idx] = {
                        "id": "",
                        "type": "function",
                        "function": {"name": "", "arguments": ""},
                    }
                acc = tool_calls_acc[idx]
                tc_id = getattr(tc_delta, "id", None)
                if isinstance(tc_id, str) and tc_id:
                    acc["id"] = tc_id
                fn_delta = getattr(tc_delta, "function", None)
                if fn_delta is not None:
                    fn_name = getattr(fn_delta, "name", None)
                    fn_args = getattr(fn_delta, "arguments", None)
                    if isinstance(fn_name, str) and fn_name:
                        acc["function"]["name"] += fn_name
                    if isinstance(fn_args, str):
                        acc["function"]["arguments"] += fn_args
    except Exception:
        pass

    # Web UI: signal stream end
    if is_web and core is not None:
        try:
            lm = getattr(core, "log_message", None)
            if callable(lm):
                lm({"type": "assistant_stream_end"})
        except Exception:
            pass

    if (text_parts or reasoning_parts) and not is_web:
        last = (
            text_parts[-1]
            if text_parts
            else (reasoning_parts[-1] if reasoning_parts else "")
        )
        if last and not last.endswith("\n"):
            if print_delta_fn:
                print_delta_fn("\n")
            else:
                print("")

    tool_calls_list = [
        v for _, v in sorted(tool_calls_acc.items()) if v["function"]["name"]
    ]

    return "".join(text_parts), "".join(reasoning_parts), tool_calls_list


# ---------------------------------------------------------------------------
# chat_kwargs builder
# ---------------------------------------------------------------------------


def build_novita_chat_kwargs(
    *,
    depname: str,
    call_messages: list[dict[str, Any]],
    send_tools: bool,
    req_tools: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Build the kwargs dict for ``client.chat.completions.create``.

    Novita uses a standard OpenAI-compatible API. No special parameters
    like extra_body, reasoning_effort, or thinking.type are needed.
    """
    clean_messages = _strip_reasoning_content(call_messages)

    chat_kwargs: dict[str, Any] = {
        "model": depname,
        "messages": clean_messages,
    }

    if send_tools and req_tools:
        chat_kwargs["tools"] = req_tools
        chat_kwargs["tool_choice"] = "auto"

    temp_env = (
        env_get(f"{_ENV_PREFIX}_TEMPERATURE") or env_get("UAGENT_TEMPERATURE") or ""
    ).strip()
    try:
        resolved_temp = float(temp_env) if temp_env else 0.0
    except ValueError:
        resolved_temp = 0.0
    chat_kwargs["temperature"] = resolved_temp

    try:
        from uagent.llmcapa_util import apply_shared_max_tokens

        apply_shared_max_tokens(chat_kwargs, model_id=depname, provider="novita")
    except Exception:
        pass

    # top_p shared fallback
    top_p_env = (
        env_get(f"{_ENV_PREFIX}_TOP_P") or env_get("UAGENT_TOP_P") or ""
    ).strip()
    if top_p_env:
        try:
            chat_kwargs["top_p"] = float(top_p_env)
        except ValueError:
            pass

    return chat_kwargs


# ---------------------------------------------------------------------------
# Main chat completion round
# ---------------------------------------------------------------------------


def novita_chat_with_tools(
    client: Any,
    depname: str,
    call_messages: list[dict[str, Any]],
    *,
    core: Any,
    make_client_fn: Any,
    call_maybe_thread_fn: Any,
    send_tools_this_round: bool,
    max_retries_429: int,
    retry_base: float,
    retry_cap: float,
    stream: bool = True,
) -> tuple[bool, Any, str, str, list[dict[str, Any]]]:
    """Run one Novita AI chat completion round.

    Returns ``(ok, client, assistant_text, reasoning_content, tool_calls_list)``.
    """
    attempt_429 = 0

    req_tools = _tools.get_tool_specs() if send_tools_this_round else None

    while True:
        try:
            chat_kwargs = build_novita_chat_kwargs(
                depname=depname,
                call_messages=call_messages,
                send_tools=send_tools_this_round,
                req_tools=req_tools,
            )

            if stream:
                assistant_text, reasoning_content, tool_calls_list = (
                    call_maybe_thread_fn(
                        lambda: _parse_novita_stream(
                            client.chat.completions.create(**chat_kwargs, stream=True),
                            print_delta_fn=(
                                None
                                if bool(getattr(core, "_is_web", False))
                                else (
                                    lambda s: (
                                        print(s, end="", flush=True) if s else None
                                    )
                                )
                            ),
                            core=core,
                        )
                    )
                )
            else:
                resp = call_maybe_thread_fn(
                    lambda: client.chat.completions.create(**chat_kwargs)
                )
                assistant_text, reasoning_content, tool_calls_list = (
                    _parse_novita_response(resp)
                )

            return True, client, assistant_text, reasoning_content, tool_calls_list

        except Exception as e:
            attempt_429, new_client, action = _rate_limit_retry_step(
                exception=e,
                provider="novita",
                model=depname,
                attempt=attempt_429,
                max_retries=max_retries_429,
                base=retry_base,
                cap=retry_cap,
                recreate_client_fn=(lambda: make_client_fn(core)[1]),
            )
            if action == "retry":
                if new_client is not None:
                    client = new_client
                continue
            if action == "give_up":
                print(
                    f"[{_LABEL} Error] "
                    + _("429 retry limit (%(max_retries)s) reached.")
                    % {"max_retries": max_retries_429}
                )
                _maybe_print_certifi_where(e)
                print(repr(e))
                return False, client, "", "", []

            err = str(e)
            if "context window" in err.lower() or "exceeds the context" in err.lower():
                print(f"[{_LABEL} Error] " + _("Input exceeds the context window."))
                _maybe_print_certifi_where(e)
                print(repr(e))
                return False, client, "", "", []

            if BadRequestError is not None and isinstance(e, BadRequestError):
                err_text_lower = err.lower()
                if "does not support tools" in err_text_lower:
                    print(
                        f"[{_LABEL} Error] Model does not support tools. "
                        "Auto-disabling tools and retrying..."
                    )
                    from .. import core as _core_module

                    _core_module.tools_enabled = False
                    send_tools_this_round = False
                    req_tools = None
                    continue
                print(f"[{_LABEL} Error] " + _("400 BadRequest"))
                print(
                    f"[{_LABEL} Error] "
                    + _("Error code: %(code)d - %(err)s") % {"code": 400, "err": e}
                )
                return False, client, "", "", []

            if APIConnectionError is not None and isinstance(e, APIConnectionError):
                print(f"[{_LABEL} Error] " + _("Connection error"))
                _maybe_print_certifi_where(e)
                print(repr(e))
                return False, client, "", "", []

            if isinstance(e, URLError):
                print(_("[Network Error]"))
                _maybe_print_certifi_where(e)
                print(repr(e))
                return False, client, "", "", []

            print(
                f"[{_LABEL} Error] "
                + _("An error occurred while generating a response.")
            )
            _maybe_print_certifi_where(e)
            print(repr(e))
            return False, client, "", "", []
