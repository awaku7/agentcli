"""DeepSeek-specific chat completion helper.

Differences from the generic OpenAI-compatible path:
- Thinking Mode: ``extra_body={"thinking": {"type": "enabled/disabled"}}``
  + ``reasoning_effort="high/max"`` (passed as a top-level kwarg).
- ``reasoning_content``: CoT text returned alongside ``content``.
  * No tool calls  -> drop from next-turn context (model ignores it anyway).
  * Tool calls present -> MUST be carried forward in the assistant message,
    otherwise the API returns HTTP 400.
- Unsupported parameters in Thinking Mode: ``temperature``, ``top_p``,
  ``presence_penalty``, ``frequency_penalty`` are silently ignored by the API,
  but ``logprobs``/``top_logprobs`` cause a 400 error.  We never send them.
- Default base_url is ``https://api.deepseek.com`` (no ``/v1`` suffix).
- Default model is ``deepseek-v4-flash`` (``deepseek-chat`` is deprecated 2026-07-24).
"""

from __future__ import annotations

import json
import sys
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
from ..llm_helpers import (
    _choose_auto_effort,
    _extract_latest_user_text,
    _is_thinking_task,
    _maybe_print_certifi_where,
)

# ---------------------------------------------------------------------------
# Thinking-mode effort mapping
# ---------------------------------------------------------------------------
# DeepSeek maps low/medium -> high, xhigh -> max (API docs).
# We mirror that locally so status display is accurate.
_EFFORT_MAP: dict[str, str] = {
    "minimal": "high",
    "low": "high",
    "medium": "high",
    "high": "high",
    "xhigh": "max",
    "max": "max",
}

_VALID_EFFORTS = frozenset({"high", "max"})


def _resolve_deepseek_effort(raw: str) -> str | None:
    """Map a UAGENT_REASONING value to a DeepSeek-valid reasoning_effort string.

    Returns None when thinking should be disabled or is not configured.
    """
    r = raw.strip().lower()
    if r in ("off", ""):
        return None
    if r == "auto":
        return None  # caller handles "auto" before calling this
    return _EFFORT_MAP.get(r)


# ---------------------------------------------------------------------------
# reasoning_content helpers
# ---------------------------------------------------------------------------


def extract_reasoning_content(msg: Any) -> str:
    """Pull reasoning_content out of an OpenAI SDK message object or dict."""
    # SDK object attribute
    rc = getattr(msg, "reasoning_content", None)
    if isinstance(rc, str):
        return rc
    # dict form
    if isinstance(msg, dict):
        rc = msg.get("reasoning_content")
        if isinstance(rc, str):
            return rc
    return ""


def build_assistant_message_with_reasoning(
    *,
    assistant_text: str,
    tool_calls_list: list[dict[str, Any]],
    reasoning_content: str,
) -> dict[str, Any]:
    """Build an assistant message dict, injecting reasoning_content when tool
    calls were present (DeepSeek API requirement).

    When there are NO tool calls, reasoning_content is intentionally omitted:
    the API ignores it and sending it wastes context tokens.
    """
    msg: dict[str, Any] = {
        "role": "assistant",
        "content": assistant_text,
    }
    if tool_calls_list:
        msg["tool_calls"] = tool_calls_list
        # With tool calls, reasoning_content MUST be forwarded or API returns 400.
        if reasoning_content:
            msg["reasoning_content"] = reasoning_content
    return msg


# ---------------------------------------------------------------------------
# chat_kwargs builder
# ---------------------------------------------------------------------------


def build_deepseek_chat_kwargs(
    *,
    depname: str,
    call_messages: list[dict[str, Any]],
    send_tools: bool,
    req_tools: list[dict[str, Any]] | None,
    reasoning: str,
    auto_user_text: str,
    provider: str = "deepseek",
) -> tuple[dict[str, Any], str | None]:
    """Build the kwargs dict for ``client.chat.completions.create``.

    Returns ``(chat_kwargs, effort_used)`` where ``effort_used`` is the
    resolved reasoning_effort string (or None if thinking is disabled).
    """
    _env_prefix = "UAGENT_ZAI" if provider == "zai" else "UAGENT_DEEPSEEK"
    # Strip reasoning_content from incoming messages to avoid 400.
    # (Only relevant when reasoning_content was stored in tool-call turns.)
    clean_messages = _strip_reasoning_content_no_tool(call_messages)

    chat_kwargs: dict[str, Any] = {
        "model": depname,
        "messages": clean_messages,
    }

    if send_tools and req_tools:
        chat_kwargs["tools"] = req_tools
        chat_kwargs["tool_choice"] = "auto"

    effort_used: str | None = None

    if reasoning == "auto":
        if _is_thinking_task(auto_user_text):
            effort_used = _choose_auto_effort(auto_user_text)
            # Map to DeepSeek valid value
            effort_used = _EFFORT_MAP.get(effort_used, "high")
    elif reasoning in ("off", ""):
        # Explicitly disable thinking
        chat_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
    else:
        mapped = _EFFORT_MAP.get(reasoning)
        if mapped:
            effort_used = mapped

    if effort_used in _VALID_EFFORTS:
        chat_kwargs["reasoning_effort"] = effort_used
        chat_kwargs.setdefault("extra_body", {})
        chat_kwargs["extra_body"]["thinking"] = {"type": "enabled"}
    elif "extra_body" not in chat_kwargs:
        # No explicit thinking toggle -> API default (enabled for v4 models)
        pass

    # Non-thinking-mode parameters: temperature, top_p, presence_penalty,
    # frequency_penalty.  In thinking mode these are silently ignored or
    # rejected by the API, so we only send them when thinking is disabled.
    # logprobs/top_logprobs are intentionally NOT sent (400 in thinking mode).
    if effort_used not in _VALID_EFFORTS:
        # temperature
        temp_env = (
            env_get(f"{_env_prefix}_TEMPERATURE") or env_get("UAGENT_TEMPERATURE") or ""
        ).strip()
        try:
            resolved_temp = float(temp_env) if temp_env else 0.0
        except ValueError:
            resolved_temp = 0.0
        chat_kwargs["temperature"] = resolved_temp

        # top_p (default: 1.0)
        top_p_env = (env_get(f"{_env_prefix}_TOP_P") or "").strip()
        try:
            chat_kwargs["top_p"] = float(top_p_env) if top_p_env else 1.0
        except ValueError:
            chat_kwargs["top_p"] = 1.0

        # presence_penalty (default: 0.0)
        pp_env = (env_get(f"{_env_prefix}_PRESENCE_PENALTY") or "").strip()
        try:
            chat_kwargs["presence_penalty"] = float(pp_env) if pp_env else 0.0
        except ValueError:
            chat_kwargs["presence_penalty"] = 0.0

        # frequency_penalty (default: 0.0)
        fp_env = (env_get(f"{_env_prefix}_FREQUENCY_PENALTY") or "").strip()
        try:
            chat_kwargs["frequency_penalty"] = float(fp_env) if fp_env else 0.0
        except ValueError:
            chat_kwargs["frequency_penalty"] = 0.0

    return chat_kwargs, effort_used


def _strip_reasoning_content_no_tool(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return a copy of messages with reasoning_content removed from assistant
    messages that have NO tool_calls.

    Assistant messages WITH tool_calls must retain reasoning_content (API rule).
    Assistant messages WITHOUT tool_calls must NOT include reasoning_content
    (API returns 400 if reasoning_content is present without preceding tool call).
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
# Diagnostic helper for "insufficient tool messages" error
# ---------------------------------------------------------------------------


def _diagnose_message_structure(messages: list[dict[str, Any]]) -> None:
    """Print diagnostic info about message structure to stderr
    when DeepSeek API reports 'insufficient tool messages'."""
    try:
        tail = messages[-8:] if len(messages) > 8 else messages
        print(
            "[DeepSeek Debug] Last %d messages (diagnosing 'insufficient tool messages'):"
            % len(tail),
            file=sys.stderr,
        )
        for idx, m in enumerate(tail):
            role = m.get("role", "?")
            raw_c = m.get("content")
            if isinstance(raw_c, str):
                content_preview = raw_c[:80]
            elif raw_c is None:
                content_preview = "(null)"
            else:
                try:
                    content_preview = str(raw_c)[:80]
                except Exception:
                    content_preview = f"({type(raw_c).__name__})"

            tcs = m.get("tool_calls")
            tc_count = len(tcs) if isinstance(tcs, list) else 0
            tc_ids = set()
            if isinstance(tcs, list):
                for _tc in tcs:
                    if isinstance(_tc, dict):
                        _tid = _tc.get("id")
                        if isinstance(_tid, str):
                            tc_ids.add(_tid)

            tc_id_val = m.get("tool_call_id", "")
            rc = m.get("reasoning_content", "")
            rc_flag = " reasoning" if rc else ""

            extra = ""
            if tc_count:
                extra += " tool_calls=%d ids=%s" % (tc_count, sorted(tc_ids))
            if tc_id_val:
                extra += " tool_call_id=%r" % tc_id_val
            if rc_flag:
                extra += rc_flag

            print(
                "  [%d] role=%s%s content=%r" % (idx, role, extra, content_preview),
                file=sys.stderr,
            )
    except Exception:
        pass


def _repair_incomplete_tool_sequences(
    messages: list[dict[str, Any]],
) -> bool:
    """Remove tool_calls (and their reasoning_content) from assistant messages
    that lack complete tool responses immediately following them.

    This is a more aggressive repair than sanitize_messages_for_tools:
    it also handles empty-ID tool calls that the sanitizer may miss.

    Returns True if any messages were modified in-place.
    """
    modified = False
    i = 0
    while i < len(messages):
        m = messages[i]
        if m.get("role") == "assistant" and "tool_calls" in m:
            tcs = m.get("tool_calls") or []
            if not isinstance(tcs, list) or not tcs:
                i += 1
                continue

            # Collect tool_call IDs from this assistant message
            tool_ids: set[str] = set()
            for tc in tcs:
                if isinstance(tc, dict):
                    tid = tc.get("id")
                    if isinstance(tid, str):
                        tool_ids.add(tid)

            # Look ahead for consecutive tool messages
            j = i + 1
            found_ids: set[str] = set()
            while j < len(messages) and messages[j].get("role") == "tool":
                tcid = messages[j].get("tool_call_id")
                if isinstance(tcid, str):
                    found_ids.add(tcid)
                j += 1

            # Check completeness: every tool_call_id from the assistant
            # must have a matching tool response.
            missing = tool_ids - found_ids
            if missing:
                new_tcs = [
                    tc
                    for tc in tcs
                    if isinstance(tc, dict) and tc.get("id") not in missing
                ]
                if new_tcs:
                    m["tool_calls"] = new_tcs
                else:
                    # All tool_calls are missing responses -> remove entirely
                    del m["tool_calls"]
                    # Also strip reasoning_content since tool_calls are gone
                    if "reasoning_content" in m:
                        del m["reasoning_content"]
                modified = True
        i += 1
    return modified


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------


def parse_deepseek_response(resp: Any) -> tuple[str, str, list[dict[str, Any]]]:
    """Parse a non-streaming chat completion response from DeepSeek.

    Returns ``(assistant_text, reasoning_content, tool_calls_list)``.
    """
    choice = resp.choices[0]
    msg = choice.message

    # reasoning_content
    reasoning_content = extract_reasoning_content(msg)

    # tool_calls
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
        tool_calls_list.append(
            {
                "id": tc_id or "",
                "type": "function",
                "function": {"name": fn_name, "arguments": fn_args},
            }
        )

    # content
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


def parse_deepseek_stream(
    stream: Any,
    *,
    print_delta_fn: Any = None,
    core: Any = None,
) -> tuple[str, str, list[dict[str, Any]]]:
    """Consume a streaming response from DeepSeek.

    Returns ``(assistant_text, reasoning_content, tool_calls_list)``.
    ``reasoning_content`` deltas are accumulated but NOT printed to stdout
    (they are internal CoT; only the final content is shown).
    """
    text_parts: list[str] = []
    reasoning_parts: list[str] = []
    tool_calls_acc: dict[int, dict[str, Any]] = {}
    is_web = bool(getattr(core, "_is_web", False)) if core else False

    try:
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            # reasoning_content delta (DeepSeek-specific field)
            rc_delta = getattr(delta, "reasoning_content", None)
            if isinstance(rc_delta, str) and rc_delta:
                reasoning_parts.append(rc_delta)
                # Do NOT print CoT to stdout / web

            # content delta
            content_delta = getattr(delta, "content", None)
            if isinstance(content_delta, str) and content_delta:
                text_parts.append(content_delta)
                if print_delta_fn and not is_web:
                    print_delta_fn(content_delta)
                elif is_web and core is not None:
                    try:
                        core.log_stream_delta(content_delta)
                    except Exception:
                        pass

            # tool_calls delta
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

    # Ensure newline after streaming content
    if text_parts and not is_web:
        last = text_parts[-1] if text_parts else ""
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
# Main round function
# ---------------------------------------------------------------------------


def deepseek_chat_with_tools(
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
    provider: str = "deepseek",
) -> tuple[bool, Any, str, str, list[dict[str, Any]]]:
    """Run one DeepSeek/z.ai chat completion round.

    Returns ``(ok, client, assistant_text, reasoning_content, tool_calls_list)``.
    """
    attempt_429 = 0
    tool_repair_attempted = False

    # Provider-specific env var prefix and display label
    _env_prefix = "UAGENT_ZAI" if provider == "zai" else "UAGENT_DEEPSEEK"
    _label = "Z.AI" if provider == "zai" else "DeepSeek"

    _reasoning = (env_get("UAGENT_REASONING") or "").strip().lower()
    _auto_user_text = (
        _extract_latest_user_text(call_messages) if _reasoning == "auto" else ""
    )

    req_tools = _tools.get_tool_specs() if send_tools_this_round else None

    while True:
        try:
            chat_kwargs, effort_used = build_deepseek_chat_kwargs(
                depname=depname,
                call_messages=call_messages,
                send_tools=send_tools_this_round,
                req_tools=req_tools,
                reasoning=_reasoning,
                auto_user_text=_auto_user_text,
                provider=provider,
            )

            if effort_used:
                label = (
                    f"LLM:auto->{effort_used}"
                    if _reasoning == "auto"
                    else f"LLM:{effort_used}"
                )
                try:
                    core.set_status(True, label)
                except Exception:
                    pass

            if stream:
                assistant_text, reasoning_content, tool_calls_list = (
                    call_maybe_thread_fn(
                        lambda: parse_deepseek_stream(
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
                    parse_deepseek_response(resp)
                )

            return True, client, assistant_text, reasoning_content, tool_calls_list

        except Exception as e:
            attempt_429, new_client, action = _rate_limit_retry_step(
                exception=e,
                provider=provider,
                model=depname,
                attempt=attempt_429,
                max_retries=max_retries_429,
                base=retry_base,
                cap=retry_cap,
                recreate_client_fn=(lambda: (make_client_fn(core)[1])),
            )
            if action == "retry":
                if new_client is not None:
                    client = new_client
                continue
            if action == "give_up":
                print(
                    f"[{_label} Error] "
                    + _("429 retry limit (%(max_retries)s) reached.")
                    % {"max_retries": max_retries_429}
                )
                _maybe_print_certifi_where(e)
                print(repr(e))
                return False, client, "", "", []

            err = str(e)
            # Context window
            if "context window" in err.lower() or "exceeds the context" in err.lower():
                print(f"[{_label} Error] " + _("Input exceeds the context window."))
                _maybe_print_certifi_where(e)
                print(repr(e))
                return False, client, "", "", []
            # 400 BadRequest
            if BadRequestError is not None and isinstance(e, BadRequestError):
                err_text_lower = err.lower()
                if (
                    "insufficient tool messages" in err_text_lower
                    and not tool_repair_attempted
                ):
                    # Diagnose the problem
                    print(
                        f"[{_label} Error] 400 BadRequest - 'insufficient tool messages'"
                    )
                    _diagnose_message_structure(call_messages)
                    # Attempt repair: strip incomplete tool-call sequences
                    if _repair_incomplete_tool_sequences(call_messages):
                        tool_repair_attempted = True
                        print(
                            f"[{_label}] Repaired incomplete tool sequences, retrying...",
                            file=sys.stderr,
                        )
                        continue  # Retry with repaired messages
                    # Repair didn't change anything; fall through to normal error
                    print(
                        f"[{_label}] Repair did not change messages, giving up.",
                        file=sys.stderr,
                    )
                print(f"[{_label} Error] 400 BadRequest")
                print(f"Error code: 400 - {e}")
                return False, client, "", "", []
            if APIConnectionError is not None and isinstance(e, APIConnectionError):
                print(f"[{_label} Error] " + _("Connection error"))
                _maybe_print_certifi_where(e)
                print(repr(e))
                return False, client, "", "", []
            if isinstance(e, URLError):
                print(_("[Network Error]"))
                _maybe_print_certifi_where(e)
                print(repr(e))
                return False, client, "", "", []

            print(
                f"[{_label} Error] "
                + _("An error occurred while generating a response.")
            )
            _maybe_print_certifi_where(e)
            print(repr(e))
            return False, client, "", "", []
