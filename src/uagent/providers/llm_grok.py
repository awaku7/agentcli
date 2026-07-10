"""Grok (xAI) provider implementation using xai_sdk (gRPC).

Only management tools (tool_catalog, tool_load, unload_tool) are sent to the model.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from xai_sdk.chat import (
    user,
    system,
    tool_result,
    tool as xai_tool,
)

from ..env_utils import env_get
from ..reasoning_display import show_reasoning


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
) -> Optional[list[Any]]:
    """Build xai_sdk Tool list: management tools + tools loaded via tool_load."""
    if not send_tools_this_round:
        return None

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

            all_specs = _tools.get_tool_specs()
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


def parse_xai_stream(
    stream_iter: Any,
    *,
    core: Any = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Parse an xai_sdk stream iterator.

    Yields (response, chunk) pairs. The final response is accumulated.
    Returns (assistant_text, tool_calls_list) from the final response.
    """
    assistant_text = ""
    tool_calls_list: list[dict[str, Any]] = []
    _reasoning_printed = False

    try:
        for response, chunk in stream_iter:
            # Accumulate text from chunk
            if hasattr(chunk, "content"):
                text = chunk.content or ""
                if text:
                    print(text, end="", flush=True)
                    assistant_text += text
            # Print reasoning content (not added to assistant_text)
            if hasattr(chunk, "reasoning_content"):
                rc = chunk.reasoning_content or ""
                if rc:
                    show_reasoning(
                        rc,
                        provider="Grok",
                        is_first=(not _reasoning_printed),
                        core=core,
                    )
                    _reasoning_printed = True

            # Tool calls from chunk
            if hasattr(chunk, "tool_calls"):
                for tc in chunk.tool_calls:
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
                    if fn_name:
                        _tid = tc_id if tc_id else uuid.uuid4().hex[:12]
                        tool_calls_list.append(
                            {
                                "id": _tid,
                                "type": "function",
                                "function": {"name": fn_name, "arguments": fn_args},
                            }
                        )

    except Exception as e:
        _debug_log("stream_error", error=str(e))

    # Print final newline after streaming to avoid state messages on same line
    print()
    return assistant_text, tool_calls_list
