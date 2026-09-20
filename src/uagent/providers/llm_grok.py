"""Grok (xAI) provider implementation using xai_sdk (gRPC).

Only management tools (tool_catalog, tool_load, unload_tool) are sent to the model.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Iterator, Optional


from ..env_utils import env_get
from ..reasoning_display import show_reasoning
from ..runtime.stream_renderer import StreamCallbacks


def _ensure_xai_chat() -> None:
    from .._pip_auto import install_with_status

    if not install_with_status("xai-sdk", module_name="xai_sdk"):
        raise ModuleNotFoundError("No module named 'xai_sdk'")
    global user, system, tool_result, xai_tool
    from xai_sdk.chat import (
        user as _user,
        system as _system,
        tool_result as _tool_result,
        tool as _xai_tool,
    )

    user, system, tool_result, xai_tool = _user, _system, _tool_result, _xai_tool


def _as_str(x: Any) -> str:
    if x is None:
        return ""
    return str(x)


def _debug_log(prefix: str, **kwargs: Any) -> None:
    """Print debug log when UAGENT_DEBUG_GROK=1."""
    if (env_get("UAGENT_DEBUG_GROK") or "").strip() not in ("1", "true", "yes"):
        return
    import sys as _sys

    parts = [f"[GROK_DEBUG] {prefix}"]
    for k, v in kwargs.items():
        try:
            vs = json.dumps(v, ensure_ascii=False)[:2000]
        except Exception:
            vs = str(v)[:2000]
        parts.append(f"  {k}={vs}")
    print("\n".join(parts), file=_sys.__stderr__, flush=True)


# ── Message conversion ──────────────────────────────────────────


def build_xai_messages(
    call_messages: list[dict[str, Any]],
) -> tuple[Optional[str], list[Any]]:
    """Convert OpenAI-format messages to xai_sdk messages.

    Returns (instruction_text, xai_messages) where instruction_text
    is the concatenated system prompts (for 'instructions' field).
    """

    _ensure_xai_chat()
    instructions_list: list[str] = []
    xai_msgs: list[Any] = []

    for m in call_messages:
        role = m.get("role")
        content = _as_str(m.get("content", ""))

        if role == "system":
            instructions_list.append(content)
            # xai_sdk system() is also added as message
            xai_msgs.append(system(content))

        elif role == "user":
            raw_content = m.get("content", "")
            if isinstance(raw_content, list):
                # Multimodal content: build xai_sdk message with text + images
                text_parts = []
                image_urls = []
                for part in raw_content:
                    if not isinstance(part, dict):
                        continue
                    ptype = part.get("type", "")
                    if ptype == "text":
                        text_parts.append(_as_str(part.get("text", "")))
                    elif ptype in ("input_image", "image_url"):
                        img_url = ""
                        if ptype == "image_url":
                            img_data = part.get("image_url", {})
                            if isinstance(img_data, dict):
                                img_url = img_data.get("url", "")
                        else:
                            img_url = part.get("image_url", "")
                        if img_url:
                            image_urls.append(img_url)
                combined_text = " ".join(text_parts)
                if image_urls:
                    # xai_sdk supports image_url in content via proto
                    from xai_sdk.proto import chat_pb2
                    from xai_sdk.chat import text as xchat_text

                    chat_content = []
                    if combined_text:
                        chat_content.append(xchat_text(combined_text))
                    for img_url in image_urls:
                        chat_content.append(
                            chat_pb2.Content(image_url={"image_url": img_url})
                        )
                    msg = chat_pb2.Message(
                        role=chat_pb2.MessageRole.ROLE_USER,
                        content=chat_content,
                    )
                    xai_msgs.append(msg)
                else:
                    xai_msgs.append(user(combined_text))
            else:
                xai_msgs.append(user(_as_str(raw_content)))

        elif role == "assistant":
            # xai_sdk assistant() does not accept tool_calls; build raw proto
            from xai_sdk.proto import chat_pb2
            from xai_sdk.chat import text as xchat_text

            msg = chat_pb2.Message(
                role=chat_pb2.MessageRole.ROLE_ASSISTANT,
                content=[xchat_text(content)] if content else [],
            )
            tc_list = m.get("tool_calls")
            if tc_list and isinstance(tc_list, list):
                for tc in tc_list:
                    if isinstance(tc, dict):
                        fn = tc.get("function", {})
                        tc_id = tc.get("id", "") or uuid.uuid4().hex[:12]
                        fn_name = fn.get("name", "")
                        fn_args = fn.get("arguments", "")
                        if isinstance(fn_args, dict):
                            fn_args = json.dumps(fn_args, ensure_ascii=False)
                        elif not isinstance(fn_args, str):
                            fn_args = str(fn_args)
                        tc_pb = chat_pb2.ToolCall(
                            id=tc_id,
                            function=chat_pb2.FunctionCall(
                                name=fn_name,
                                arguments=fn_args,
                            ),
                        )
                        msg.tool_calls.append(tc_pb)
            xai_msgs.append(msg)

        elif role == "tool":
            tool_call_id = m.get("tool_call_id", "") or m.get("id", "")
            xai_msgs.append(tool_result(content, tool_call_id=tool_call_id))

    instructions_str: Optional[str] = None
    if instructions_list:
        tmp = "\n".join(s for s in instructions_list if s)
        if tmp.strip():
            instructions_str = tmp

    return instructions_str, xai_msgs


def build_xai_tools(
    send_tools_this_round: bool,
    call_messages: Optional[list[dict[str, Any]]] = None,
    core: Any = None,
    tool_specs: Optional[list[dict[str, Any]]] = None,
) -> Optional[list[Any]]:
    """Build xai_sdk tools from the registry projection or legacy state."""
    if not send_tools_this_round:
        return None
    _ensure_xai_chat()

    # Registry rounds already computed the exact tool projection for this request.
    # Treat it as authoritative instead of reconstructing stale state from messages.
    if tool_specs is not None:
        xai_tool_list: list[Any] = []
        seen_names: set[str] = set()
        for spec in tool_specs:
            if not isinstance(spec, dict):
                continue
            fn = spec.get("function") or {}
            if not isinstance(fn, dict):
                continue
            name = fn.get("name")
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            xai_tool_list.append(
                xai_tool(
                    name=name,
                    description=_as_str(fn.get("description", "")),
                    parameters=fn.get("parameters")
                    or {"type": "object", "properties": {}},
                )
            )
        _debug_log(
            "xai_tools_sent",
            tools=[t.function.name for t in xai_tool_list],
        )
        return xai_tool_list or None

    # Always include management tools
    try:
        from ..tools.catalog_tool import TOOL_SPEC, TOOL_SPEC_2, TOOL_SPEC_3

        mgmt_specs = [TOOL_SPEC, TOOL_SPEC_2, TOOL_SPEC_3]
    except ImportError:
        mgmt_specs = []

    # Collect loaded tool names from tool_load calls in the conversation
    loaded_names: set[str] = set()
    if call_messages:
        for m in call_messages:
            if not isinstance(m, dict):
                continue
            role = m.get("role")
            tc_list = m.get("tool_calls") if role == "assistant" else None
            if tc_list:
                for tc in tc_list:
                    if not isinstance(tc, dict):
                        continue
                    fn = tc.get("function", {})
                    _fn_name = fn.get("name", "")
                    if _fn_name == "tool_load":
                        try:
                            args = (
                                json.loads(fn.get("arguments", "{}"))
                                if isinstance(fn.get("arguments"), str)
                                else fn.get("arguments", {})
                            )
                            if isinstance(args, dict):
                                name = args.get("name") or args.get("tool_name") or ""
                                if name:
                                    loaded_names.add(name)
                                names = args.get("names")
                                if isinstance(names, list):
                                    loaded_names.update(
                                        item for item in names if isinstance(item, str)
                                    )
                        except Exception:
                            pass
            # Also check tool results for successful load
            if role == "tool":
                try:
                    content = _as_str(m.get("content", ""))
                    if content:
                        result = json.loads(content)
                        if isinstance(result, dict):
                            # tool_load result: {"name": "tool_name", "loaded": true, ...}
                            if result.get("name"):
                                loaded_names.add(result["name"])
                            # tool_catalog auto_loaded: {"auto_loaded": "tool_name", ...}
                            auto_loaded = result.get("auto_loaded")
                            if auto_loaded and isinstance(auto_loaded, str):
                                loaded_names.add(auto_loaded)
                except Exception:
                    pass

    # Build the tool list: start with management tools
    xai_tool_list: list[Any] = []
    seen_names: set[str] = set()

    for spec in mgmt_specs:
        if not isinstance(spec, dict):
            continue
        fn = spec.get("function") or {}
        if not isinstance(fn, dict):
            continue
        name = fn.get("name")
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        description = _as_str(fn.get("description", ""))
        parameters = fn.get("parameters") or {"type": "object", "properties": {}}
        xai_tool_list.append(
            xai_tool(name=name, description=description, parameters=parameters)
        )

    # Add loaded tools
    if loaded_names:
        try:
            from .. import tools as _tools

            context_tool_specs = getattr(core, "context_tool_specs", None)
            all_specs = (
                list(context_tool_specs)
                if context_tool_specs is not None
                else _tools.get_tool_specs()
            )
            if context_tool_specs is not None:
                # Explicitly loaded tools remain available even when lexical
                # task selection would otherwise omit them.
                for _spec in _tools.get_tool_specs() or []:
                    _fn = _spec.get("function") or {}
                    if isinstance(_fn, dict) and _fn.get("name") in loaded_names:
                        if not any(
                            isinstance(_existing.get("function"), dict)
                            and _existing["function"].get("name") == _fn.get("name")
                            for _existing in all_specs
                            if isinstance(_existing, dict)
                        ):
                            all_specs.append(_spec)
        except Exception:
            all_specs = None

        if all_specs:
            for spec in all_specs:
                if not isinstance(spec, dict):
                    continue
                fn = spec.get("function") or {}
                if not isinstance(fn, dict):
                    continue
                name = fn.get("name")
                if not name or name in seen_names:
                    continue
                if name in loaded_names:
                    seen_names.add(name)
                    description = _as_str(fn.get("description", ""))
                    parameters = fn.get("parameters") or {
                        "type": "object",
                        "properties": {},
                    }
                    xai_tool_list.append(
                        xai_tool(
                            name=name, description=description, parameters=parameters
                        )
                    )

        # For tools that were loaded via tool_load but not yet in get_tool_specs(),
        # try to find the spec directly from the tool module.
        still_missing = loaded_names - seen_names
        if still_missing:
            try:
                from ..tools._genre_control_util import _find_tool_modules

                for mname, mod in _find_tool_modules():
                    for attr_name in ("TOOL_SPEC", "TOOL_SPEC_2", "TOOL_SPEC_3"):
                        spec = getattr(mod, attr_name, None)
                        if not isinstance(spec, dict):
                            continue
                        fn = spec.get("function") or {}
                        if not isinstance(fn, dict):
                            continue
                        name = fn.get("name")
                        if not name or name in seen_names:
                            continue
                        if name in still_missing:
                            seen_names.add(name)
                            description = _as_str(fn.get("description", ""))
                            parameters = fn.get("parameters") or {
                                "type": "object",
                                "properties": {},
                            }
                            xai_tool_list.append(
                                xai_tool(
                                    name=name,
                                    description=description,
                                    parameters=parameters,
                                )
                            )
            except Exception:
                pass

    _debug_log(
        "xai_tools_sent",
        tools=[t.function.name for t in xai_tool_list],
    )
    return xai_tool_list if xai_tool_list else None


# ── Response parsing ────────────────────────────────────────────


def parse_xai_response(
    response: Any,
    *,
    core: Any = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Parse an xai_sdk Response object.

    Returns (assistant_text, tool_calls_list).
    tool_calls_list items are dicts with keys: id, type, function (name, arguments).
    """
    assistant_text = ""
    tool_calls_list: list[dict[str, Any]] = []

    if response is None:
        return assistant_text, tool_calls_list

    # Extract reasoning content (print to console, not added to assistant_text)
    if hasattr(response, "reasoning_content"):
        rc = response.reasoning_content
        if rc:
            show_reasoning(_as_str(rc), provider="Grok", is_first=True, core=core)
    # Extract text content
    if hasattr(response, "content"):
        assistant_text = _as_str(response.content)

    # Extract tool calls
    try:
        raw_tc = response.tool_calls
    except Exception:
        raw_tc = []

    for tc in raw_tc:
        fn_name = ""
        fn_args = ""
        tc_id = ""
        if hasattr(tc, "id"):
            tc_id = tc.id or ""
        if hasattr(tc, "function"):
            fn = tc.function
            if hasattr(fn, "name"):
                fn_name = fn.name or ""
            if hasattr(fn, "arguments"):
                fn_args = fn.arguments or ""
        if isinstance(fn_args, dict):
            fn_args = json.dumps(fn_args, ensure_ascii=False)
        elif not isinstance(fn_args, str):
            fn_args = str(fn_args)

        if not fn_name:
            continue

        _tid = tc_id if tc_id else uuid.uuid4().hex[:12]
        tool_calls_list.append(
            {
                "id": _tid,
                "type": "function",
                "function": {"name": fn_name, "arguments": fn_args},
            }
        )

    _debug_log(
        "parse_xai_result",
        assistant_text_len=len(assistant_text),
        tool_calls=len(tool_calls_list),
    )
    return assistant_text, tool_calls_list


def _normalize_xai_stream_tool_call(tool_call: Any) -> dict[str, Any] | None:
    function = getattr(tool_call, "function", None)
    name = getattr(function, "name", "") if function is not None else ""
    if not name:
        return None
    arguments = getattr(function, "arguments", "") or ""
    if isinstance(arguments, dict):
        arguments = json.dumps(arguments, ensure_ascii=False)
    elif not isinstance(arguments, str):
        arguments = str(arguments)
    tool_call_id = getattr(tool_call, "id", "") or uuid.uuid4().hex[:12]
    return {
        "id": tool_call_id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


def iter_xai_stream_parts(stream_iter: Any) -> Iterator[tuple[str, Any]]:
    """Yield normalized xAI stream parts without buffering provider output."""
    for _response, chunk in stream_iter:
        content = getattr(chunk, "content", "") or ""
        if content:
            yield "text", _as_str(content)
        reasoning = getattr(chunk, "reasoning_content", "") or ""
        if reasoning:
            yield "reasoning", _as_str(reasoning)
        for tool_call in getattr(chunk, "tool_calls", None) or ():
            normalized = _normalize_xai_stream_tool_call(tool_call)
            if normalized is not None:
                yield "tool_call", normalized


def parse_xai_stream(
    stream_iter: Any,
    *,
    core: Any = None,
    callbacks: StreamCallbacks | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Parse an xai_sdk stream iterator for the legacy callback path."""
    assistant_text = ""
    tool_calls_list: list[dict[str, Any]] = []
    callbacks = callbacks or StreamCallbacks()
    if callable(callbacks.on_terminal):
        try:
            callbacks.on_terminal("ResponseStarted", {})
        except Exception:
            pass
    reasoning_started = False
    saw_reasoning = False

    def _print_delta(s: str) -> None:
        if callable(callbacks.on_delta):
            try:
                callbacks.on_delta(s)
                return
            except Exception:
                pass
        print_stream_delta = (
            getattr(core, "print_stream_delta", None) if core is not None else None
        )
        if callable(print_stream_delta):
            print_stream_delta(s)
        else:
            print(s, end="", flush=True)

    try:
        for part_type, value in iter_xai_stream_parts(stream_iter):
            if part_type == "text":
                if saw_reasoning:
                    _print_delta("\n")
                    saw_reasoning = False
                _print_delta(value)
                assistant_text += value
            elif part_type == "reasoning":
                if callable(callbacks.on_reasoning):
                    try:
                        callbacks.on_reasoning(value)
                    except Exception:
                        pass
                else:
                    show_reasoning(
                        value,
                        provider="Grok",
                        is_first=(not reasoning_started),
                        print_fn=_print_delta,
                        core=core,
                    )
                reasoning_started = True
                saw_reasoning = True
            elif part_type == "tool_call":
                tool_calls_list.append(value)
    except Exception as exc:
        _debug_log("stream_error", error=str(exc))

    # Print final newline after streaming to avoid state messages on same line.
    _print_delta(chr(10))
    if callable(callbacks.on_tool_call):
        for tool_call in tool_calls_list:
            try:
                callbacks.on_tool_call(dict(tool_call))
            except Exception:
                pass
    if callable(callbacks.on_terminal):
        try:
            callbacks.on_terminal("ResponseCompleted", {})
        except Exception:
            pass
    return assistant_text, tool_calls_list


def simple_xai_chat(
    client: Any,
    model_name: str,
    messages: list[dict[str, Any]],
    *,
    max_tokens: int = 2048,
    temperature: float = 0.0,
) -> str:
    """Run a simple non-tool xai_sdk chat completion and return text content.

    Converts OpenAI-format messages to xai_sdk protobuf messages, then calls
    ``client.chat.create(...).sample()``.
    """
    _instructions, xai_msgs = build_xai_messages(messages)
    create_kwargs: dict[str, Any] = {
        "model": model_name,
        "messages": xai_msgs,
        "temperature": temperature,
    }
    if max_tokens and max_tokens > 0:
        try:
            from uagent.llmcapa_util import clamp_max_tokens

            create_kwargs["max_tokens"] = clamp_max_tokens(
                int(max_tokens), model_name, "grok"
            )
        except Exception:
            create_kwargs["max_tokens"] = int(max_tokens)

    chat_obj = client.chat.create(**create_kwargs)
    resp = chat_obj.sample()
    return _as_str(getattr(resp, "content", None) or "")
