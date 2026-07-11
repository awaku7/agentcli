"""OpenAI/Azure Responses API: request builder and response/stream parser."""

from __future__ import annotations

import json
import os
import time
from typing import Any, Optional

from .. import tools
from ..env_utils import env_get
from ..i18n import _
from ..llm_image_helpers import build_image_default_prompt
from ..reasoning_display import show_reasoning

from .responses_common import (
    as_str,
    attachment_to_content_item,
    debug_emit,
    debug_stream_enabled,
    emit_web_search_event,
    extract_url_citations,
    extract_web_search_call_info,
    normalize_content_items,
    responses_item_to_dict,
)
from .responses_web_search_openai import (
    normalize_openai_builtin_tool,
    openai_web_search_tool_from_env,
)

# Module-level constants (reused across calls, avoids re-allocation).
_TOOL_CALLING_RULES: str = _("""[Tool calling rules]
        - When calling a tool/function, you MUST provide function_call.arguments as a JSON object.
        - The JSON object MUST include all required parameters defined by the tool schema.
        - Never call a tool with an empty object {} unless the tool has no required parameters.
        - If you do not have a required parameter, ask the user for it using human_ask instead of guessing.
        """)

_WEB_SEARCH_RULES: str = _("""[Web search rules]
        - Use web search only when fresh or external information is necessary.
        - Do not use web search for local or stable information.
        - Prefer answering without web search when the answer is already sufficient.
        """)

# ---------------------------------------------------------------------------
# Request builder
# ---------------------------------------------------------------------------


def build_responses_request(
    call_messages: list[dict[str, Any]],
    *,
    send_tools_this_round: bool,
    provider: str = "openai",
    tool_specs: Optional[list[dict[str, Any]]] = None,
    previous_response_id: Optional[str] = None,
) -> tuple[Optional[str], list[dict[str, Any]], Optional[list[dict[str, Any]]]]:
    """Build payload for OpenAI/Azure Responses API.

    Returns:
      (instructions_str_or_none, input_msgs, tools_or_none)
    """
    instructions_list: list[str] = []
    input_msgs: list[dict[str, Any]] = []
    _latest_user: Optional[dict[str, Any]] = None
    _latest_user_index: int = -1
    _last_tool_call_assistant_index: int = -1
    _pending_call_ids: set[str] = set()

    # Pre-scan for tool-continuation detection
    for _idx, _msg in enumerate(call_messages):
        if not isinstance(_msg, dict):
            continue
        _role = _msg.get("role")
        if _role == "user":
            _latest_user_index = _idx
        elif _role == "assistant":
            _tcs = _msg.get("tool_calls")
            if isinstance(_tcs, list) and _tcs:
                _last_tool_call_assistant_index = _idx
                _pending_call_ids.clear()
                for _tc in _tcs:
                    if not isinstance(_tc, dict):
                        continue
                    _tcid = _tc.get("id") or _tc.get("call_id")
                    if isinstance(_tcid, str) and _tcid:
                        _pending_call_ids.add(_tcid)

    _tool_continuation = (
        _last_tool_call_assistant_index >= 0
        and _latest_user_index < _last_tool_call_assistant_index
    )

    instructions_list.append(_TOOL_CALLING_RULES)
    instructions_list.append(_WEB_SEARCH_RULES)

    for _idx, m in enumerate(call_messages):
        role = m.get("role")

        # -- previous_response_id mode --
        if previous_response_id is not None:
            if role == "system":
                instructions_list.append(as_str(m.get("content", "")))
            elif role == "tool":
                if _tool_continuation and _idx > _last_tool_call_assistant_index:
                    tm = dict(m)
                    for _k in ("attachments", "saved_path", "saved_files"):
                        tm.pop(_k, None)
                    call_id = tm.pop("tool_call_id", None) or tm.get("id", "")
                    if isinstance(call_id, str) and call_id in _pending_call_ids:
                        output = as_str(tm.get("content", ""))
                        input_msgs.append(
                            {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": output,
                            }
                        )
            elif role == "user":
                if not _tool_continuation:
                    _latest_user = dict(m)
                    _latest_user_index = _idx
                    for _k in ("attachments", "saved_path", "saved_files"):
                        if _k in _latest_user:
                            try:
                                del _latest_user[_k]
                            except Exception:
                                pass
            continue

        # -- Full history mode --
        if role == "system":
            instructions_list.append(as_str(m.get("content", "")))
            continue

        m_clean: dict[str, Any] = dict(m)

        attachment_items: list[dict[str, Any]] = []
        if role == "user":
            raw_attachments = m_clean.get("attachments")
            if isinstance(raw_attachments, list):
                for att in raw_attachments:
                    item = attachment_to_content_item(att)
                    if item is not None:
                        attachment_items.append(item)
            elif isinstance(raw_attachments, dict):
                item = attachment_to_content_item(raw_attachments)
                if item is not None:
                    attachment_items.append(item)

            saved_path = m_clean.get("saved_path")
            if isinstance(saved_path, str) and saved_path.strip():
                item = attachment_to_content_item(
                    {"type": "image", "saved_path": saved_path.strip()}
                )
                if item is not None:
                    attachment_items.append(item)

            saved_files = m_clean.get("saved_files")
            if isinstance(saved_files, list):
                for sf in saved_files:
                    if isinstance(sf, str) and sf.strip():
                        item = attachment_to_content_item(
                            {"type": "image", "saved_path": sf.strip()}
                        )
                        if item is not None:
                            attachment_items.append(item)
                    elif isinstance(sf, dict):
                        item = attachment_to_content_item(sf)
                        if item is not None:
                            attachment_items.append(item)

            content_text = as_str(m_clean.get("content", ""))
            if attachment_items and not content_text.strip():
                attachment_items.insert(
                    0,
                    {
                        "type": "input_text",
                        "text": build_image_default_prompt("describe"),
                    },
                )

        for _k in ("attachments", "saved_path", "saved_files"):
            if _k in m_clean:
                try:
                    del m_clean[_k]
                except Exception:
                    pass

        _responses_items = m_clean.pop("_responses_output_items", None)
        if isinstance(_responses_items, list) and _responses_items:
            for _item in _responses_items:
                if isinstance(_item, dict) and _item.get("type"):
                    input_msgs.append(dict(_item))
            continue

        if "tool_calls" in m_clean:
            tc_info: list[str] = []
            tcs = m_clean.get("tool_calls")
            if isinstance(tcs, list):
                for tc in tcs:
                    if isinstance(tc, dict):
                        fn = (
                            (tc.get("function") or {})
                            if isinstance(tc.get("function"), dict)
                            else {}
                        )
                        name = fn.get("name", "unknown")
                        args = fn.get("arguments", "{}")
                        tc_info.append(f"{name}({args})")
            try:
                del m_clean["tool_calls"]
            except Exception:
                pass
            if tc_info:
                instructions_list.append(
                    "[System: The assistant previously executed tools: "
                    + ", ".join(tc_info)
                    + "]"
                )

        if role == "tool":
            tool_name = m_clean.pop("name", "unknown")
            if "tool_call_id" in m_clean:
                try:
                    del m_clean["tool_call_id"]
                except Exception:
                    pass
            original_content = m_clean.get("content")
            prefix = f"[System: Tool '{tool_name}' returned result]\n"
            merged = prefix + as_str(original_content).lstrip("\r\n")
            m_clean["role"] = "user"
            m_clean["content"] = normalize_content_items(merged, role="user")
            input_msgs.append(m_clean)
            continue

        if role not in ("user", "assistant"):
            role = "user"
            m_clean["role"] = "user"

        normalized_content = normalize_content_items(m_clean.get("content"), role=role)
        if role == "user" and attachment_items:
            normalized_content.extend(attachment_items)
        m_clean["content"] = normalized_content

        if "tool_call_id" in m_clean:
            try:
                del m_clean["tool_call_id"]
            except Exception:
                pass
        if "name" in m_clean and m_clean.get("role") != "tool":
            try:
                del m_clean["name"]
            except Exception:
                pass

        input_msgs.append(m_clean)

    if previous_response_id is not None and _latest_user is not None:
        _latest_user["content"] = normalize_content_items(
            _latest_user.get("content"), role="user"
        )
        for _k in ("attachments", "saved_path", "saved_files"):
            _latest_user.pop(_k, None)
        input_msgs.append(_latest_user)

    instructions_str: Optional[str] = None
    if instructions_list:
        tmp = "\n".join([s for s in instructions_list if s is not None])
        if tmp.strip() != "":
            instructions_str = tmp

    req_tools: Optional[list[dict[str, Any]]] = None
    if send_tools_this_round:
        raw_specs = tools.get_tool_specs() if tool_specs is None else tool_specs
        flat_tools: list[dict[str, Any]] = []

        env_web_search_tool = None
        if provider in ("openai", "azure"):
            env_web_search_tool = openai_web_search_tool_from_env()
            if env_web_search_tool is not None:
                flat_tools.append(env_web_search_tool)

        _excluded_local: set[str] = set()
        if env_web_search_tool is not None:
            _excluded_local.add("search_web")

        for t in raw_specs or []:
            if not isinstance(t, dict):
                continue
            builtin_tool = normalize_openai_builtin_tool(t)
            if builtin_tool is not None:
                flat_tools.append(builtin_tool)
                continue
            fn = t.get("function") or {}
            if not isinstance(fn, dict):
                continue
            name = fn.get("name")
            if not name:
                continue
            if name in _excluded_local:
                continue
            flat_tools.append(
                {
                    "type": "function",
                    "name": name,
                    "description": fn.get("description") or "",
                    "parameters": fn.get("parameters")
                    or {"type": "object", "properties": {}},
                }
            )
        req_tools = flat_tools

    return instructions_str, input_msgs, req_tools


# ---------------------------------------------------------------------------
# Response parser (non-streaming)
# ---------------------------------------------------------------------------


def parse_responses_response(
    resp: Any, *, core: Any = None
) -> tuple[str, str, list[dict[str, Any]], Optional[str], list[dict[str, Any]]]:
    """Parse a Responses API response and preserve output items for replay."""

    response_id: Optional[str] = None
    try:
        response_id = as_str(getattr(resp, "id", None) or "")
    except Exception:
        pass
    if not response_id:
        response_id = None

    assistant_text = ""
    reasoning_content = ""
    tool_calls_list: list[dict[str, Any]] = []
    output_items: list[dict[str, Any]] = []
    seen_web_search_ids: set[str] = set()

    if hasattr(resp, "output") and resp.output:
        for item in resp.output:
            item_dict = responses_item_to_dict(item)
            if item_dict is not None:
                output_items.append(item_dict)
            item_type = as_str(getattr(item, "type", "")).strip().lower()
            if item_type == "message":
                for c in getattr(item, "content", []) or []:
                    ct = getattr(c, "type", None)
                    if ct in ("output_text", "text"):
                        assistant_text += as_str(getattr(c, "text", ""))
                    elif ct == "reasoning":
                        rc = as_str(getattr(c, "text", ""))
                        if rc:
                            reasoning_content += rc
                citations = extract_url_citations(getattr(item, "content", []) or [])
                if citations:
                    debug_emit(
                        None,
                        "parse_responses_response",
                        note="OPENAI_RESPONSES_URL_CITATION",
                        citations=citations,
                    )

            elif getattr(item, "type", None) == "function_call":
                args_val = getattr(item, "arguments", None)
                if isinstance(args_val, dict):
                    args_str = json.dumps(args_val, ensure_ascii=False)
                elif args_val is None:
                    args_str = "{}"
                else:
                    args_str = as_str(args_val)

                cid = (
                    getattr(item, "call_id", None)
                    or getattr(item, "id", None)
                    or f"call_{int(time.time() * 1000)}"
                )

                tool_calls_list.append(
                    {
                        "id": cid,
                        "type": "function",
                        "function": {
                            "name": getattr(item, "name", "unknown"),
                            "arguments": args_str,
                        },
                    }
                )
            elif "web_search_call" in item_type:
                info = extract_web_search_call_info(item)
                if info:
                    wid = as_str(info.get("id"))
                    if wid and wid in seen_web_search_ids:
                        continue
                    if wid:
                        seen_web_search_ids.add(wid)
                    emit_web_search_event(core, "update", **info)

            elif item_type == "compaction":
                print(
                    "[Responses API] "
                    + _("Server-side compaction triggered (context compressed).")
                )

    if core is not None:
        try:
            setattr(core, "_last_responses_output_items", output_items)
        except Exception:
            pass
    return assistant_text, reasoning_content, tool_calls_list, response_id, output_items


# ---------------------------------------------------------------------------
def _ensure_tool_buf(
    tool_calls_buf: dict[str, dict[str, Any]],
    key: str,
) -> dict[str, Any]:
    """Get or create a tool-call buffer entry."""
    buf = tool_calls_buf.get(key)
    if buf is None:
        buf = {
            "name": "unknown",
            "arguments_parts": [],
            "call_id": None,
            "item_id": None,
        }
        tool_calls_buf[key] = buf
    return buf


def _merge_tool_buf(
    tool_calls_buf: dict[str, dict[str, Any]],
    dst_key: str,
    src_key: str,
) -> None:
    """Merge src buffer into dst and delete src."""
    if dst_key == src_key:
        return
    src = tool_calls_buf.get(src_key)
    if src is None:
        return
    dst = tool_calls_buf.get(dst_key)
    if dst is None:
        tool_calls_buf[dst_key] = src
        try:
            del tool_calls_buf[src_key]
        except Exception:
            pass
        return

    src_name = as_str(src.get("name") or "")
    dst_name = as_str(dst.get("name") or "")
    if (not dst_name or dst_name == "unknown") and src_name and src_name != "unknown":
        dst["name"] = src_name

    dst_parts = dst.get("arguments_parts") or []
    src_parts = src.get("arguments_parts") or []
    if isinstance(dst_parts, list) and isinstance(src_parts, list):
        dst_parts.extend(src_parts)
        dst["arguments_parts"] = dst_parts

    if not dst.get("call_id") and src.get("call_id"):
        dst["call_id"] = src.get("call_id")
    if not dst.get("item_id") and src.get("item_id"):
        dst["item_id"] = src.get("item_id")

    try:
        del tool_calls_buf[src_key]
    except Exception:
        pass


# Stream parser
# ---------------------------------------------------------------------------


def parse_responses_stream(
    stream: Any,
    *,
    print_delta_fn: Any = None,
    core: Any = None,
    provider: str = "OpenAI",
) -> tuple[str, str, list[dict[str, Any]], Optional[str], list[dict[str, Any]]]:
    """Parse streaming Responses output and preserve completed output items."""

    from .responses_common import dump_event_to_fp

    debug_env = (env_get("UAGENT_WEBSEARCH_DEBUG", "") or "").strip().lower()
    debug_enabled = debug_env in ("1", "true", "yes", "on")

    debug_fp = None
    if debug_enabled:
        try:
            os.makedirs("./outputs", exist_ok=True)
            debug_fp = open(
                "./outputs/responses_stream_events.jsonl",
                "a",
                encoding="utf-8",
            )
        except Exception:
            debug_fp = None

    assistant_text_parts: list[str] = []
    reasoning_parts: list[str] = []
    output_items: list[dict[str, Any]] = []
    _seen_output_item_keys: set[str] = set()
    _reasoning_printed = False
    fallback_full_text = ""

    # key -> buffer (key is call_id OR item_id OR synthetic)
    tool_calls_buf: dict[str, dict[str, Any]] = {}
    item_id_map: dict[str, str] = {}
    _stream_response_id: Optional[str] = None

    def _print_delta(s: str) -> None:
        if not s:
            return
        if callable(print_delta_fn):
            try:
                print_delta_fn(s)
                return
            except Exception:
                pass

    # Module-level _ensure_tool_buf / _merge_tool_buf used instead of closures.

    try:
        try:
            if core is not None and bool(getattr(core, "_is_web", False)):
                lm = getattr(core, "log_message", None)
                if callable(lm):
                    lm({"type": "assistant_stream_start"})
        except Exception:
            pass

        it = stream
        if hasattr(stream, "iter_events") and callable(getattr(stream, "iter_events")):
            it = stream.iter_events()

        for ev in it:
            # --- Interrupt check ---
            if core is not None:
                from uagent import core as _core_module

                with _core_module.interrupt_lock:
                    if _core_module.interrupt_requested:
                        _core_module.interrupt_requested = False
                        try:
                            if bool(getattr(core, "_is_web", False)):
                                lm = getattr(core, "log_message", None)
                                if callable(lm):
                                    lm({"type": "assistant_stream_interrupted"})
                        except Exception:
                            pass
                        break

            if debug_stream_enabled():
                dump_event_to_fp(ev, debug_fp)

            ev_type = getattr(ev, "type", None) or getattr(ev, "event", None) or ""

            if not _stream_response_id:
                if ev_type == "response.created":
                    ev_resp = getattr(ev, "response", None)
                    if ev_resp is not None:
                        rid = as_str(getattr(ev_resp, "id", None) or "")
                        if rid:
                            _stream_response_id = rid
                elif ev_type == "response.completed":
                    ev_resp = getattr(ev, "response", None)
                    if ev_resp is not None:
                        rid = as_str(getattr(ev_resp, "id", None) or "")
                        if rid:
                            _stream_response_id = rid

            if "web_search_call" in as_str(ev_type).lower():
                info = extract_web_search_call_info(ev)
                if info:
                    emit_web_search_event(core, "update", **info)

            # Output text deltas
            delta_text = None
            if ev_type == "response.output_text.delta":
                d = getattr(ev, "delta", None)
                if isinstance(d, str) and d:
                    delta_text = d

            if isinstance(delta_text, str) and delta_text:
                assistant_text_parts.append(delta_text)
                try:
                    if core is not None and bool(getattr(core, "_is_web", False)):
                        lm = getattr(core, "log_message", None)
                        if callable(lm):
                            lm({"type": "assistant_stream_delta", "delta": delta_text})
                    else:
                        _print_delta(delta_text)
                except Exception:
                    _print_delta(delta_text)

            # Reasoning text deltas
            if ev_type == "response.reasoning_text.delta":
                reasoning_delta = getattr(ev, "delta", None)
                if isinstance(reasoning_delta, str) and reasoning_delta:
                    reasoning_parts.append(reasoning_delta)
                    show_reasoning(
                        reasoning_delta,
                        provider=provider,
                        is_first=(not _reasoning_printed),
                        print_fn=_print_delta,
                        core=core,
                    )
                    _reasoning_printed = True

            if ev_type == "response.output_text.done":
                t = getattr(ev, "text", None)
                if isinstance(t, str) and t:
                    fallback_full_text = t

            # Tool call accumulation
            fn_name = None
            fn_args_delta = None

            cid_candidate = (
                getattr(ev, "call_id", None)
                or getattr(ev, "id", None)
                or (
                    getattr(getattr(ev, "delta", None), "call_id", None)
                    if hasattr(ev, "delta")
                    else None
                )
            )
            iid_candidate = getattr(ev, "item_id", None)

            if ev_type == "response.compaction.done":
                print(
                    "[Responses API] "
                    + _("Server-side compaction triggered (context compressed).")
                )

            if ev_type in ("response.output_item.added", "response.output_item.delta"):
                item = getattr(ev, "item", None) or getattr(ev, "output_item", None)
                if (
                    item is not None
                    and "web_search_call" in as_str(getattr(item, "type", "")).lower()
                ):
                    info = extract_web_search_call_info(item)
                    if info:
                        emit_web_search_event(core, "update", **info)
                if item is not None and getattr(item, "type", None) == "function_call":
                    cid = getattr(item, "call_id", None) or getattr(item, "id", None)
                    if cid:
                        cid_candidate = cid
                    iid = getattr(item, "id", None)
                    if iid:
                        iid_candidate = iid
                    fn_name = fn_name or getattr(item, "name", None)
                    item_args = getattr(item, "arguments", None)
                    if isinstance(item_args, dict):
                        fn_args_delta = fn_args_delta or json.dumps(
                            item_args, ensure_ascii=False
                        )
                    elif isinstance(item_args, str) and item_args:
                        fn_args_delta = fn_args_delta or item_args

            if cid_candidate and iid_candidate:
                item_id_map[iid_candidate] = cid_candidate
                if iid_candidate in tool_calls_buf:
                    _merge_tool_buf(tool_calls_buf, cid_candidate, iid_candidate)

            if iid_candidate and not cid_candidate:
                cid_candidate = item_id_map.get(iid_candidate)

            if not fn_name:
                if hasattr(ev, "name"):
                    fn_name = getattr(ev, "name")
                elif hasattr(ev, "function") and hasattr(
                    getattr(ev, "function"), "name"
                ):
                    fn_name = getattr(getattr(ev, "function"), "name")
                elif hasattr(ev, "delta") and hasattr(getattr(ev, "delta"), "name"):
                    fn_name = getattr(getattr(ev, "delta"), "name")

            if not fn_args_delta:
                if hasattr(ev, "arguments"):
                    fn_args_delta = getattr(ev, "arguments")
                elif hasattr(ev, "delta"):
                    d = getattr(ev, "delta")
                    if hasattr(d, "arguments"):
                        fn_args_delta = getattr(d, "arguments")
                    elif isinstance(d, str) and ev_type in (
                        "response.function_call_arguments.delta",
                        "response.tool_call_arguments.delta",
                        "response.function_call.delta",
                    ):
                        fn_args_delta = d

            looks_like_tool = (
                "function_call" in str(ev_type)
                or "tool_call" in str(ev_type)
                or fn_name is not None
                or fn_args_delta is not None
            )

            final_args = None
            if ev_type == "response.function_call_arguments.done":
                final_args = getattr(ev, "arguments", None)

            elif ev_type == "response.output_item.done":
                item = getattr(ev, "item", None) or getattr(ev, "output_item", None)
                item_dict = responses_item_to_dict(item) if item is not None else None
                if isinstance(item_dict, dict) and item_dict.get("type"):
                    _item_key = as_str(
                        item_dict.get("id")
                        or item_dict.get("call_id")
                        or f"{item_dict.get('type')}:{len(output_items)}"
                    )
                    if _item_key not in _seen_output_item_keys:
                        output_items.append(item_dict)
                        _seen_output_item_keys.add(_item_key)
                if item is not None and getattr(item, "type", None) == "compaction":
                    print(
                        "[Responses API] "
                        + _("Server-side compaction triggered (context compressed).")
                    )
                if (
                    item is not None
                    and "web_search_call" in as_str(getattr(item, "type", "")).lower()
                ):
                    info = extract_web_search_call_info(item)
                    if info:
                        emit_web_search_event(core, "update", **info)
                if item and getattr(item, "type", None) == "function_call":
                    cid = getattr(item, "call_id", None) or getattr(item, "id", None)
                    if cid:
                        cid_candidate = cid
                    final_args = getattr(item, "arguments", None)
                    if getattr(item, "name", None):
                        fn_name = getattr(item, "name")

            if final_args is not None:
                looks_like_tool = True

            if looks_like_tool:
                key = cid_candidate or iid_candidate
                if not key:
                    key = f"call_{int(time.time() * 1000)}_{len(tool_calls_buf)}"

                buf = _ensure_tool_buf(tool_calls_buf, key)

                if cid_candidate:
                    buf["call_id"] = cid_candidate
                if iid_candidate:
                    buf["item_id"] = iid_candidate

                if isinstance(fn_name, str) and fn_name:
                    buf["name"] = fn_name

                if final_args is not None:
                    if isinstance(final_args, dict):
                        buf["arguments_parts"] = [
                            json.dumps(final_args, ensure_ascii=False)
                        ]
                    else:
                        buf["arguments_parts"] = [as_str(final_args)]
                else:
                    if isinstance(fn_args_delta, dict):
                        buf["arguments_parts"].append(
                            json.dumps(fn_args_delta, ensure_ascii=False)
                        )
                    elif isinstance(fn_args_delta, str) and fn_args_delta:
                        buf["arguments_parts"].append(fn_args_delta)

                if cid_candidate and iid_candidate and key == iid_candidate:
                    _merge_tool_buf(tool_calls_buf, cid_candidate, iid_candidate)

    finally:
        try:
            if core is not None and bool(getattr(core, "_is_web", False)):
                lm = getattr(core, "log_message", None)
                if callable(lm):
                    lm({"type": "assistant_stream_end"})
        except Exception:
            pass
        if debug_fp is not None:
            try:
                debug_fp.close()
            except Exception:
                pass

    assistant_text = "".join(assistant_text_parts) or fallback_full_text

    tool_calls_list: list[dict[str, Any]] = []
    for key, buf in tool_calls_buf.items():
        args_str = "".join(buf.get("arguments_parts") or [])
        if not args_str:
            args_str = "{}"
        call_id_out = as_str(buf.get("call_id") or key)
        tool_calls_list.append(
            {
                "id": call_id_out,
                "type": "function",
                "function": {
                    "name": as_str(buf.get("name") or "unknown"),
                    "arguments": args_str,
                },
            }
        )

    reasoning_content = "".join(reasoning_parts)
    if core is not None:
        try:
            setattr(core, "_last_responses_output_items", output_items)
        except Exception:
            pass
    return (
        assistant_text,
        reasoning_content,
        tool_calls_list,
        _stream_response_id,
        output_items,
    )
