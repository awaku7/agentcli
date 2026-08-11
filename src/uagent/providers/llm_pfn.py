"""PLaMo / Preferred Networks Chat Completions compatibility.

PLaMo exposes an OpenAI-compatible endpoint, but its documented Function
Calling shape differs from the generic OpenAI path: streaming tool-call
deltas are not documented. The live endpoint also validates function
parameters as an object despite the documentation saying ``string``. Keep
these workarounds isolated here so other providers retain their normal behaviour.
"""

from __future__ import annotations

import json
from typing import Any

from .. import tools as _tools
from ..env_utils import env_get
from ..llm_errors import _rate_limit_retry_step
from ..llm_helpers import _maybe_print_certifi_where


def _pfn_tool_specs() -> list[dict[str, Any]]:
    """Return tool specs accepted by the live PLaMo API.

    The public schema page describes ``parameters`` as a string, but the
    endpoint validates it as a JSON object (422 ``dict_type``). Keep the
    native OpenAI-style object and treat live API validation as the source of
    truth.
    """
    return _tools.get_tool_specs()


def _pfn_messages(
    messages: list[dict[str, Any]], *, send_tools_this_round: bool
) -> list[dict[str, Any]]:
    """Add explicit catalog-first steering for PLaMo's lazy tool surface."""
    if not send_tools_this_round:
        return messages
    out = [dict(message) for message in messages]
    instruction = (
        "When a user request may require an external tool, do not claim that "
        "the tool is unavailable. First call tool_catalog with a concise query "
        "to find the required tool, then call tool_load if needed, and only "
        "then answer the user. Use the available tool functions rather than "
        "printing a JSON example."
    )
    for index, message in enumerate(out):
        if message.get("role") == "system":
            content = message.get("content")
            if isinstance(content, str):
                out[index]["content"] = content.rstrip() + "\n\n" + instruction
            else:
                out[index]["content"] = instruction
            return out
    out.insert(0, {"role": "system", "content": instruction})
    return out


def _value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _embedded_tool_call(content: str) -> list[dict[str, Any]]:
    """Recover PFN's JSON-in-content tool-call fallback.

    Some PLaMo responses emit ``{"name": ..., "arguments": ...}`` as
    assistant content instead of populating ``message.tool_calls``. Only
    accept a complete JSON object with this exact shape; ordinary prose is
    never treated as a tool invocation.
    """
    text = content.strip()
    if text.startswith("```") and text.endswith("```"):
        text = text[3:-3].strip()
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
    try:
        value = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(value, dict):
        return []
    name = value.get("name")
    arguments = value.get("arguments", {})
    if not isinstance(name, str) or not name:
        return []
    if not isinstance(arguments, str):
        arguments = json.dumps(arguments, ensure_ascii=False)
    return [
        {
            "id": "pfn-content-tool-call",
            "type": "function",
            "function": {"name": name, "arguments": arguments},
        }
    ]


def parse_pfn_response(resp: Any) -> tuple[str, list[dict[str, Any]]]:
    """Parse a complete PLaMo Chat Completions response."""
    choices = _value(resp, "choices") or []
    if not choices:
        return "", []
    msg = _value(choices[0], "message") or {}
    content = _value(msg, "content", "")
    if content is None:
        content = ""
    if not isinstance(content, str):
        content = str(content)

    result: list[dict[str, Any]] = []
    for raw in _value(msg, "tool_calls", []) or []:
        tc_id = _value(raw, "id", "") or "pfn-tool-call"
        fn = _value(raw, "function", {}) or {}
        name = _value(fn, "name", "")
        arguments = _value(fn, "arguments", "{}")
        if not isinstance(name, str) or not name:
            continue
        if isinstance(arguments, dict):
            arguments = json.dumps(arguments, ensure_ascii=False)
        elif arguments is None:
            arguments = "{}"
        elif not isinstance(arguments, str):
            arguments = str(arguments)
        result.append(
            {
                "id": str(tc_id),
                "type": "function",
                "function": {"name": name, "arguments": arguments},
            }
        )
    # PLaMo may emit a tool call as ordinary content even when tools were
    # supplied. Convert that narrow fallback into the common tool-call shape
    # so the existing execution loop can dispatch it.
    if not result:
        embedded = _embedded_tool_call(content)
        if embedded:
            return "", embedded
    return content, result


def parse_pfn_stream(stream: Any, *, core: Any = None) -> str:
    """Consume PFN's documented text streaming response."""
    parts: list[str] = []
    is_web = bool(getattr(core, "_is_web", False)) if core is not None else False
    for chunk in stream:
        choices = _value(chunk, "choices") or []
        if not choices:
            continue
        delta = _value(choices[0], "delta") or {}
        text = _value(delta, "content")
        if not isinstance(text, str) or not text:
            continue
        parts.append(text)
        if is_web and core is not None:
            try:
                log_message = getattr(core, "log_message", None)
                if callable(log_message):
                    log_message({"type": "assistant_stream_delta", "delta": text})
            except Exception:
                pass
        else:
            print_fn = getattr(core, "print_stream_delta", None) if core else None
            if callable(print_fn):
                print_fn(text)
            else:
                print(text, end="", flush=True)
    if parts and not is_web:
        print("", flush=True)
    return "".join(parts)


def pfn_chat_with_tools(
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
) -> tuple[bool, Any, str, str, list[dict[str, Any]]]:
    """Make one PFN round and return the common agentcli result tuple.

    PFN uses streaming for ordinary text, as shown in its API example. Tool
    streaming is not documented, so tool-enabled rounds use a complete
    response for reliable ``message.tool_calls`` parsing.
    """
    # PFN's lazy-tool mode needs the management tools on the first round.
    # Do not let an upstream auto/judgment heuristic suppress the catalog;
    # without it PLaMo can only answer that tools are unavailable.
    send_tools_this_round = True
    stream_requested = (env_get("UAGENT_STREAMING") or "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )
    use_stream = stream_requested and not send_tools_this_round
    kwargs: dict[str, Any] = {
        "model": depname,
        "messages": _pfn_messages(
            call_messages, send_tools_this_round=send_tools_this_round
        ),
        "stream": use_stream,
    }
    temp = (
        env_get("UAGENT_PFN_TEMPERATURE") or env_get("UAGENT_TEMPERATURE") or "0.2"
    ).strip()
    try:
        kwargs["temperature"] = float(temp)
    except ValueError:
        kwargs["temperature"] = 0.2

    if send_tools_this_round:
        specs = _pfn_tool_specs()
        if specs:
            kwargs["tools"] = specs
            kwargs["tool_choice"] = "auto"

    max_tokens = (env_get("UAGENT_MAX_TOKENS") or "").strip()
    if max_tokens:
        try:
            from ..llmcapa_util import clamp_max_tokens

            kwargs["max_tokens"] = clamp_max_tokens(int(max_tokens), depname, "pfn")
        except (ValueError, TypeError):
            pass

    attempt = 0
    while True:
        try:
            if use_stream:
                stream = call_maybe_thread_fn(
                    lambda: client.chat.completions.create(**kwargs)
                )
                text = parse_pfn_stream(stream, core=core)
                calls = []
            else:
                resp = call_maybe_thread_fn(
                    lambda: client.chat.completions.create(**kwargs)
                )
                text, calls = parse_pfn_response(resp)
            return True, client, text, "", calls
        except Exception as exc:
            attempt, new_client, action = _rate_limit_retry_step(
                exception=exc,
                provider="pfn",
                model=depname,
                attempt=attempt,
                max_retries=max_retries_429,
                base=retry_base,
                cap=retry_cap,
                recreate_client_fn=lambda: make_client_fn(core)[1],
            )
            if action == "retry":
                if new_client is not None:
                    client = new_client
                continue
            _maybe_print_certifi_where(exc)
            print(f"[PFN Error] {exc!r}")
            return False, client, "", "", []
