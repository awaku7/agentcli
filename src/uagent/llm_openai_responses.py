import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from . import tools

# -----------------------------------------------------------------------------
# Responses API helpers
# -----------------------------------------------------------------------------


def _as_str(x: Any) -> str:
    if x is None:
        return ""
    return str(x)


def _normalize_content_items(content: Any, *, role: str) -> List[Dict[str, Any]]:
    """Normalize a message's content into Responses content items.

    Azure/OpenAI Responses API accepts content items with (at least) these types:
      - input_text, input_image
      - output_text
      - refusal, input_file, computer_screenshot, summary_text

    Rule in this project:
      - role=user      -> input_text/input_image
      - role=assistant -> output_text (text only)

    Conservative policy:
      - Unknown multimodal items are stringified into a text item.
      - Assistant images in history are stringified into output_text warnings.
    """

    text_type = "output_text" if role == "assistant" else "input_text"

    if content is None:
        return [{"type": text_type, "text": ""}]

    if isinstance(content, str):
        return [{"type": text_type, "text": content}]

    if isinstance(content, list):
        out: List[Dict[str, Any]] = []
        for item in content:
            if isinstance(item, dict):
                t = item.get("type")

                if t in ("text", "input_text", "output_text"):
                    out.append(
                        {"type": text_type, "text": _as_str(item.get("text", ""))}
                    )
                    continue

                if t in ("image_url", "input_image"):
                    if role == "assistant":
                        out.append(
                            {
                                "type": "output_text",
                                "text": "[WARN] assistant history contained image content; converted to text.",
                            }
                        )
                        continue

                    iu = item.get("image_url")
                    if isinstance(iu, dict) and iu.get("url"):
                        out.append(
                            {
                                "type": "input_image",
                                "image_url": {"url": _as_str(iu.get("url"))},
                            }
                        )
                        continue
                    if isinstance(iu, str) and iu:
                        out.append({"type": "input_image", "image_url": {"url": iu}})
                        continue

                    out.append(
                        {
                            "type": "input_text",
                            "text": "[WARN] invalid image content (missing url).",
                        }
                    )
                    continue

                out.append(
                    {
                        "type": text_type,
                        "text": f"[WARN] unsupported content item: {item!r}",
                    }
                )
                continue

            out.append(
                {
                    "type": text_type,
                    "text": f"[WARN] unsupported content item: {item!r}",
                }
            )

        if not out:
            out = [{"type": text_type, "text": ""}]
        return out

    return [{"type": text_type, "text": _as_str(content)}]


def build_responses_request(
    call_messages: List[Dict[str, Any]],
    *,
    send_tools_this_round: bool,
    provider: str = "openai",  # kept for compatibility with caller
) -> Tuple[Optional[str], List[Dict[str, Any]], Optional[List[Dict[str, Any]]]]:
    """Build payload for OpenAI/Azure Responses API.

    Returns:
      (instructions_str_or_none, input_msgs, tools_or_none)

    Notes:
      - system messages are aggregated into `instructions`.
      - role=tool messages are converted into role=user with a system prefix.
      - assistant tool_calls are removed and summarized into `instructions`.
      - If instructions would be empty, returns None so caller can omit the field.

    Additional policy (tool-arguments stability):
      - Insert a strict tool-calling guideline into instructions so that the model
        MUST provide a valid JSON object for function_call.arguments.
      - This is specifically to avoid cases where Azure/OpenAI returns
        function_call arguments={} for tools with required parameters.
    """

    instructions_list: List[str] = []
    input_msgs: List[Dict[str, Any]] = []

    # Force the model to produce usable tool arguments.
    # Without this, some Azure/Responses combinations repeatedly emit
    # function_call arguments={} even for tools with required parameters.
    TOOL_CALLING_RULES = (
        "[Tool calling rules]\n"
        "- When calling a tool/function, you MUST provide function_call.arguments as a JSON object.\n"
        "- The JSON object MUST include all required parameters defined in the tool schema.\n"
        "- Never call a tool with an empty object {} unless the tool has no required parameters.\n"
        "- If you do not have a required parameter, ask the user for it using human_ask instead of guessing.\n"
    )
    instructions_list.append(TOOL_CALLING_RULES)

    for m in call_messages:
        role = m.get("role")

        if role == "system":
            instructions_list.append(_as_str(m.get("content", "")))
            continue

        m_clean: Dict[str, Any] = dict(m)

        # If assistant had tool_calls, remove them and write a trace into instructions
        if "tool_calls" in m_clean:
            tc_info: List[str] = []
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

        # Convert tool role to user role
        if role == "tool":
            tool_name = m_clean.pop("name", "unknown")
            if "tool_call_id" in m_clean:
                try:
                    del m_clean["tool_call_id"]
                except Exception:
                    pass

            original_content = m_clean.get("content")
            prefix = f"[System: Tool '{tool_name}' returned result]\n"
            merged = prefix + _as_str(original_content)

            m_clean["role"] = "user"
            m_clean["content"] = _normalize_content_items(merged, role="user")
            input_msgs.append(m_clean)
            continue

        # Normal user/assistant
        if role not in ("user", "assistant"):
            role = "user"
            m_clean["role"] = "user"

        m_clean["content"] = _normalize_content_items(m_clean.get("content"), role=role)

        # Cleanup keys that shouldn't be sent
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

    # Build instructions (omit if empty)
    instructions_str: Optional[str] = None
    if instructions_list:
        tmp = "\n".join([s for s in instructions_list if s is not None])
        if tmp.strip() != "":
            instructions_str = tmp

    # Tools (Responses API)
    #
    # Policy (avoid impacting non-streaming / legacy behavior):
    # - For Azure Responses, a flatter tool schema is often more reliable, especially with streaming.
    # - We therefore convert ChatCompletions-style tool specs
    #     {"type":"function","function":{"name":...,"description":...,"parameters":...}}
    #   into Responses-friendly flat specs
    #     {"type":"function","name":...,"description":...,"parameters":...}
    # - This mirrors the behavior in the known-good codebase under ../TEST and reduces
    #   the risk that tool-call arguments are emitted/transported in unexpected shapes.
    req_tools: Optional[List[Dict[str, Any]]] = None
    if send_tools_this_round:
        flat_tools: List[Dict[str, Any]] = []
        for t in tools.get_tool_specs() or []:
            if not isinstance(t, dict):
                continue
            fn = t.get("function") or {}
            if not isinstance(fn, dict):
                continue
            name = fn.get("name")
            if not name:
                continue
            flat_tools.append(
                {
                    "type": t.get("type") or "function",
                    "name": name,
                    "description": fn.get("description") or "",
                    "parameters": fn.get("parameters")
                    or {"type": "object", "properties": {}},
                }
            )
        req_tools = flat_tools

    return instructions_str, input_msgs, req_tools


def parse_responses_response(resp: Any) -> Tuple[str, List[Dict[str, Any]]]:
    """Parse Responses API response into (assistant_text, tool_calls_list)."""

    assistant_text = ""
    tool_calls_list: List[Dict[str, Any]] = []

    if hasattr(resp, "output") and resp.output:
        for item in resp.output:
            if getattr(item, "type", None) == "message":
                for c in getattr(item, "content", []) or []:
                    ct = getattr(c, "type", None)
                    if ct in ("output_text", "text"):
                        assistant_text += _as_str(getattr(c, "text", ""))

            elif getattr(item, "type", None) == "function_call":
                args_val = getattr(item, "arguments", None)
                if isinstance(args_val, dict):
                    args_str = json.dumps(args_val, ensure_ascii=False)
                elif args_val is None:
                    args_str = "{}"
                else:
                    # Some SDKs return arguments as a JSON string; keep it as-is.
                    args_str = _as_str(args_val)

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

    return assistant_text, tool_calls_list


def parse_responses_stream(
    stream: Any,
    *,
    print_delta_fn: Any = None,
    core: Any = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """Parse Responses API streaming iterator into (assistant_text, tool_calls_list).

    Debugging:
      - If UAGENT_STREAMING_DEBUG is enabled, dumps each event as JSON to:
          - stderr
          - ./outputs/responses_stream_events.jsonl

    This function is intentionally defensive because the exact event names/shape
    vary across OpenAI SDK versions and Azure deployments.

    Strategy:
      - Iterate events.
      - If an event carries output_text delta, append and optionally print it.
      - If an event carries function-call name/arguments delta, accumulate per call_id.
      - At end, return the full assistant_text and ChatCompletions-like tool_calls_list.
    """

    debug_env = (os.environ.get("UAGENT_STREAMING_DEBUG", "") or "").strip().lower()
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

    def _dump_event(ev: Any) -> None:
        """Dump a single streaming event as one-line JSON (JSONL).

        Policy:
          - When UAGENT_STREAMING_DEBUG is enabled, write JSONL to:
              ./outputs/responses_stream_events.jsonl
          - Do NOT print to stdout/stderr (keeps terminal clean and avoids broken newlines).
        """
        if not debug_enabled:
            return

        # best-effort conversion
        obj: Any
        try:
            if hasattr(ev, "model_dump"):
                obj = ev.model_dump()
            elif hasattr(ev, "dict"):
                obj = ev.dict()
            elif hasattr(ev, "to_dict"):
                obj = ev.to_dict()
            else:
                obj = ev.__dict__ if hasattr(ev, "__dict__") else repr(ev)
        except Exception:
            obj = repr(ev)

        try:
            line = json.dumps(obj, ensure_ascii=False, default=str)
        except Exception:
            line = json.dumps({"repr": repr(ev)}, ensure_ascii=False)

        if debug_fp is not None:
            try:
                debug_fp.write(line + "\n")
                debug_fp.flush()
            except Exception:
                pass

    assistant_text_parts: List[str] = []
    fallback_full_text = ""

    # call_id -> {"name": str, "arguments_parts": [str]}
    tool_calls_buf: Dict[str, Dict[str, Any]] = {}

    # item_id (e.g. "fc_...") -> call_id (e.g. "call_...")
    item_id_map: Dict[str, str] = {}

    def _print_delta(s: str) -> None:
        if not s:
            return
        if callable(print_delta_fn):
            try:
                print_delta_fn(s)
                return
            except Exception:
                pass

    try:
        # Web streaming: signal start (a single growing assistant bubble)
        try:
            if core is not None and bool(getattr(core, "_is_web", False)):
                lm = getattr(core, "log_message", None)
                if callable(lm):
                    lm({"type": "assistant_stream_start"})
        except Exception:
            pass

        # Some SDK versions return an iterator of events only when stream=True,
        # but others return a ResponseStream object that must be iterated via
        # .__iter__() or .iter_events(). We normalize here.
        it = stream
        if hasattr(stream, "iter_events") and callable(getattr(stream, "iter_events")):
            it = stream.iter_events()
        for ev in it:
            _dump_event(ev)

            # Common fields across SDKs: ev.type (string)
            ev_type = getattr(ev, "type", None) or getattr(ev, "event", None) or ""

            # 1) Output text deltas (Azure/OpenAI Responses streaming)
            # Only print/accumulate the user-visible channel:
            #   - response.output_text.delta  -> ev.delta (string)
            # Do NOT print response.output_text.done (it is the full text and can duplicate output).
            # We keep it only as a fallback when no deltas arrived.

            delta_text = None
            if ev_type == "response.output_text.delta":
                d = getattr(ev, "delta", None)
                if isinstance(d, str) and d:
                    delta_text = d

            if isinstance(delta_text, str) and delta_text:
                assistant_text_parts.append(delta_text)

                # In Web mode, stream deltas via core.log_message instead of stdout.
                # This avoids stdout line buffering issues and allows the Web UI
                # to grow a single assistant bubble.
                try:
                    if core is not None and bool(getattr(core, "_is_web", False)):
                        lm = getattr(core, "log_message", None)
                        if callable(lm):
                            lm({"type": "assistant_stream_delta", "delta": delta_text})
                    else:
                        _print_delta(delta_text)
                except Exception:
                    _print_delta(delta_text)

            # Fallback full text (no printing)
            if ev_type == "response.output_text.done":
                t = getattr(ev, "text", None)
                if isinstance(t, str) and t:
                    # store full text as fallback; do not print
                    fallback_full_text = t

            # 2) Tool call accumulation (function_call)
            # NOTE:
            #   Some SDKs/Azure deployments emit function call fragments under
            #   response.output_item.added with item.type == "function_call".
            #   Others may emit response.function_call_arguments.delta.
            #   We handle both defensively.

            call_id = None
            fn_name = None
            fn_args_delta = None

            # 0) Identify call_id and item_id
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

            # a) Nested item for response.output_item.added/delta
            if ev_type in ("response.output_item.added", "response.output_item.delta"):
                item = getattr(ev, "item", None) or getattr(ev, "output_item", None)
                if item is not None:
                    item_type = getattr(item, "type", None)
                    if item_type == "function_call":
                        cid = getattr(item, "call_id", None) or getattr(
                            item, "id", None
                        )
                        if cid:
                            cid_candidate = cid
                        iid = getattr(item, "id", None)
                        if iid:
                            iid_candidate = iid

                        fn_name = fn_name or getattr(item, "name", None)

                        # Arguments
                        item_args = getattr(item, "arguments", None)
                        if isinstance(item_args, dict):
                            fn_args_delta = fn_args_delta or json.dumps(
                                item_args, ensure_ascii=False
                            )
                        elif isinstance(item_args, str) and item_args:
                            fn_args_delta = fn_args_delta or item_args

            # Register mapping
            if cid_candidate and iid_candidate:
                item_id_map[iid_candidate] = cid_candidate

            # Resolve call_id
            if iid_candidate and not cid_candidate:
                cid_candidate = item_id_map.get(iid_candidate)
            call_id = cid_candidate

            # b) Function name extraction
            if not fn_name:
                if hasattr(ev, "name"):
                    fn_name = getattr(ev, "name")
                elif hasattr(ev, "function") and hasattr(
                    getattr(ev, "function"), "name"
                ):
                    fn_name = getattr(getattr(ev, "function"), "name")
                elif hasattr(ev, "delta") and hasattr(getattr(ev, "delta"), "name"):
                    fn_name = getattr(getattr(ev, "delta"), "name")

            # c) Function arguments delta extraction
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

            # d) Handle 'done' events to overwrite arguments with the final complete string
            #    This is robust against missing deltas or complex streaming chunks.
            final_args = None
            if ev_type == "response.function_call_arguments.done":
                # Typically has .arguments (str)
                final_args = getattr(ev, "arguments", None)

            elif ev_type == "response.output_item.done":
                # item.type == function_call?
                item = getattr(ev, "item", None) or getattr(ev, "output_item", None)
                if item and getattr(item, "type", None) == "function_call":
                    # ensure we have call_id
                    cid = getattr(item, "call_id", None) or getattr(item, "id", None)
                    if cid:
                        call_id = cid
                    # extract final arguments
                    final_args = getattr(item, "arguments", None)
                    # ensure we have name
                    if getattr(item, "name", None):
                        fn_name = getattr(item, "name")

            if final_args is not None:
                looks_like_tool = True

            if looks_like_tool and call_id:
                buf = tool_calls_buf.get(call_id)
                if buf is None:
                    buf = {"name": "unknown", "arguments_parts": []}
                    tool_calls_buf[call_id] = buf

                if isinstance(fn_name, str) and fn_name:
                    buf["name"] = fn_name

                # If we got a final complete arguments string, overwrite everything
                if final_args is not None:
                    if isinstance(final_args, dict):
                        buf["arguments_parts"] = [
                            json.dumps(final_args, ensure_ascii=False)
                        ]
                    else:
                        buf["arguments_parts"] = [_as_str(final_args)]
                else:
                    # Otherwise append delta
                    if isinstance(fn_args_delta, dict):
                        buf["arguments_parts"].append(
                            json.dumps(fn_args_delta, ensure_ascii=False)
                        )
                    elif isinstance(fn_args_delta, str) and fn_args_delta:
                        buf["arguments_parts"].append(fn_args_delta)

    finally:
        # Web streaming: signal end
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
            except Exception:
                pass

    assistant_text = "".join(assistant_text_parts) or fallback_full_text

    tool_calls_list: List[Dict[str, Any]] = []
    for cid, buf in tool_calls_buf.items():
        args_str = "".join(buf.get("arguments_parts") or [])
        if not args_str:
            args_str = "{}"
        tool_calls_list.append(
            {
                "id": cid,
                "type": "function",
                "function": {
                    "name": _as_str(buf.get("name") or "unknown"),
                    "arguments": args_str,
                },
            }
        )

    return assistant_text, tool_calls_list
