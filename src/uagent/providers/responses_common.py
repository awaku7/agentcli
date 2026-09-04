"""Shared utilities for Responses API implementations (OpenAI, Azure, Bedrock, etc.)."""

from __future__ import annotations

import html
import json
import os
import re
import sys
import time
import uuid
from typing import Any, Optional

from ..env_utils import env_get
from ..i18n import _
from ..reasoning_display import show_reasoning
from ..util_tools import image_file_to_data_url

# ---------------------------------------------------------------------------
# String helpers
# ---------------------------------------------------------------------------


def as_str(x: Any) -> str:
    if x is None:
        return ""
    return str(x)


def _emit_compaction_notice(core: Any = None) -> None:
    """Print compaction notices through the stream-aware console writer."""
    message = (
        chr(10)
        + "[Responses API] "
        + _("Server-side compaction triggered (context compressed).")
        + chr(10)
    )
    target = core or sys.modules.get("uagent.core")
    stream_writer = getattr(target, "print_stream_delta", None)
    if callable(stream_writer):
        stream_writer(message)
    else:
        print(message, end="", flush=True)


_OPENROUTER_INVOKE_RE = re.compile(
    r"<invoke\b(?P<attrs>[^>]*)>(?P<body>.*?)</invoke>", re.I | re.S
)
_OPENROUTER_PARAM_RE = re.compile(
    r"<parameter\b(?P<attrs>[^>]*)>(?P<body>.*?)</parameter>", re.I | re.S
)
_OPENROUTER_ATTR_RE = re.compile(
    r'(?P<key>[A-Za-z_:][A-Za-z0-9_.:-]*)\s*=\s*(?:"(?P<dq>.*?)"|\'(?P<sq>.*?)\'|(?P<bare>[^\s>]+))',
    re.S,
)


def _parse_openrouter_attrs(attr_text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in _OPENROUTER_ATTR_RE.finditer(attr_text or ""):
        key = as_str(m.group("key") or "").strip()
        if not key:
            continue
        value = m.group("dq")
        if value is None:
            value = m.group("sq")
        if value is None:
            value = m.group("bare")
        out[key] = html.unescape(as_str(value or "").strip())
    return out


def parse_assistant_text_tool_calls(
    text: str,
) -> tuple[str, list[dict[str, Any]]]:
    """Parse assistant text and recover legacy ``<invoke>`` tool-call markup.

    This is intentionally lightweight in the spirit of LangChain's
    ``StrOutputParser``: preserve the text, but normalize any tool-call markup
    that leaked into the visible response.
    """

    if not isinstance(text, str) or "<invoke" not in text.lower():
        return text, []

    cleaned_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    last = 0

    for match in _OPENROUTER_INVOKE_RE.finditer(text):
        cleaned_parts.append(text[last : match.start()])
        last = match.end()

        invoke_attrs = _parse_openrouter_attrs(match.group("attrs") or "")
        invoke_name = as_str(invoke_attrs.get("name") or "").strip()
        if not invoke_name:
            cleaned_parts.append(match.group(0))
            continue

        params: dict[str, Any] = {}
        body = match.group("body") or ""
        for p_match in _OPENROUTER_PARAM_RE.finditer(body):
            p_attrs = _parse_openrouter_attrs(p_match.group("attrs") or "")
            p_name = as_str(p_attrs.get("name") or "").strip()
            if not p_name:
                continue
            p_value = html.unescape((p_match.group("body") or "").strip())
            if p_name in params and params[p_name] != p_value:
                prev = params[p_name]
                if isinstance(prev, list):
                    prev.append(p_value)
                else:
                    params[p_name] = [prev, p_value]
            else:
                params[p_name] = p_value

        tool_calls.append(
            {
                "id": f"invoke_{uuid.uuid4().hex[:12]}",
                "type": "function",
                "function": {
                    "name": invoke_name,
                    "arguments": json.dumps(params, ensure_ascii=False),
                },
            }
        )

    if not tool_calls:
        return text, []

    cleaned_parts.append(text[last:])
    return "".join(cleaned_parts), tool_calls


# Backward-compatible alias.
recover_openrouter_invoke_tool_calls = parse_assistant_text_tool_calls


def responses_usage_to_dict(usage: Any) -> dict[str, Any]:
    """Convert Responses API usage objects to JSON-friendly data."""
    if usage is None:
        return {}
    if hasattr(usage, "model_dump"):
        try:
            value = usage.model_dump()
            return value if isinstance(value, dict) else {}
        except Exception:
            pass
    result: dict[str, Any] = {}
    for name in (
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "input_tokens_details",
        "output_tokens_details",
    ):
        value = getattr(usage, name, None)
        if value is None:
            continue
        if hasattr(value, "model_dump"):
            try:
                value = value.model_dump()
            except Exception:
                pass
        result[name] = value
    return result


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------


def env_truthy(name: str) -> bool:
    return (env_get(name) or "").strip().lower() in ("1", "true", "yes", "on")


def env_json_obj(name: str) -> Optional[dict[str, Any]]:
    raw = (env_get(name) or "").strip()
    if not raw:
        return None
    try:
        obj = json.loads(raw)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def env_enabled_default_true(name: str) -> bool:
    raw = (env_get(name) or "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    if raw in ("1", "true", "yes", "on"):
        return True
    return True


# ---------------------------------------------------------------------------
# Content item normalization
# ---------------------------------------------------------------------------


_DEFAULT_HISTORY_TOOL_RESULT_MAX_CHARS = 12_000


def truncate_history_tool_result(text: Any) -> str:
    """Limit a tool result before it is replayed as Responses input.

    ``UAGENT_HISTORY_TOOL_RESULT_MAX_CHARS=0`` disables this limit. Invalid or
    negative values use the safe default. The returned text keeps both the
    beginning and end because command output often contains a summary at the end.
    """
    value = as_str(text)
    raw_limit = env_get("UAGENT_HISTORY_TOOL_RESULT_MAX_CHARS")
    if raw_limit is None or str(raw_limit).strip() == "":
        limit = _DEFAULT_HISTORY_TOOL_RESULT_MAX_CHARS
    else:
        try:
            limit = int(str(raw_limit).strip())
        except (TypeError, ValueError):
            limit = _DEFAULT_HISTORY_TOOL_RESULT_MAX_CHARS
    if limit == 0 or len(value) <= limit:
        return value
    if limit < 0:
        limit = _DEFAULT_HISTORY_TOOL_RESULT_MAX_CHARS
    marker = f"\n[tool output truncated: original length={len(value)}]\n"
    if limit <= len(marker):
        return marker[:limit]
    remaining = limit - len(marker)
    head_len = (remaining + 1) // 2
    tail_len = remaining - head_len
    return value[:head_len] + marker + (value[-tail_len:] if tail_len else "")


def normalize_content_items(content: Any, *, role: str) -> list[dict[str, Any]]:
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
        out: list[dict[str, Any]] = []
        for item in content:
            if isinstance(item, dict):
                t = item.get("type")

                if t in ("text", "input_text", "output_text"):
                    out.append(
                        {"type": text_type, "text": as_str(item.get("text", ""))}
                    )
                    continue

                if t in ("image_url", "input_image"):
                    if role == "assistant":
                        out.append(
                            {
                                "type": "output_text",
                                "text": _(
                                    "[WARN] assistant history contained image content; converted to text."
                                ),
                            }
                        )
                        continue

                    iu = item.get("image_url")
                    if isinstance(iu, dict) and iu.get("url"):
                        out.append(
                            {
                                "type": "input_image",
                                "image_url": as_str(iu.get("url")),
                            }
                        )
                        continue
                    if isinstance(iu, str) and iu:
                        out.append({"type": "input_image", "image_url": iu})
                        continue

                    out.append(
                        {
                            "type": "input_text",
                            "text": _("[WARN] invalid image content (missing url)."),
                        }
                    )
                    continue

                out.append(
                    {
                        "type": text_type,
                        "text": _("[WARN] unsupported content item: %(item)r")
                        % {"item": item},
                    }
                )
                continue

            out.append(
                {
                    "type": text_type,
                    "text": _("[WARN] unsupported content item: %(item)r")
                    % {"item": item},
                }
            )

        if not out:
            out = [{"type": text_type, "text": ""}]
        return out

    return [{"type": text_type, "text": as_str(content)}]


# ---------------------------------------------------------------------------
# Attachment handling
# ---------------------------------------------------------------------------


def attachment_to_content_item(att: Any) -> Optional[dict[str, Any]]:
    """Convert a stored attachment into an OpenAI Responses content item."""

    if not isinstance(att, dict):
        return None

    att_type = as_str(att.get("type")).strip().lower()
    if att_type not in (
        "image",
        "image/png",
        "image/jpeg",
        "image/webp",
        "image/gif",
        "image/jpg",
    ):
        return None

    data_url = att.get("data_url") or att.get("dataUrl") or att.get("data")
    if not (isinstance(data_url, str) and data_url.startswith("data:")):
        b64 = att.get("data_base64") or att.get("base64")
        if isinstance(b64, str) and b64:
            mime = as_str(att.get("mime") or "image/png")
            data_url = f"data:{mime};base64,{b64}"
    if isinstance(data_url, str) and data_url.startswith("data:"):
        return {"type": "input_image", "image_url": data_url}

    path = att.get("saved_path") or att.get("path") or att.get("file_path")
    if isinstance(path, str) and path.startswith("data:"):
        return {"type": "input_image", "image_url": path}
    if not isinstance(path, str) or not path.strip():
        return None

    try:
        data_url = image_file_to_data_url(path.strip())
    except Exception:
        return None

    return {"type": "input_image", "image_url": data_url}


# ---------------------------------------------------------------------------
# SDK output item conversion
# ---------------------------------------------------------------------------


def responses_item_to_dict(item: Any) -> dict[str, Any] | None:
    """Convert an SDK Responses output item to a JSON-compatible dict."""
    try:
        if hasattr(item, "model_dump"):
            value = item.model_dump(exclude_none=True)
        elif hasattr(item, "to_dict"):
            value = item.to_dict()
        elif isinstance(item, dict):
            value = dict(item)
        else:
            value = dict(getattr(item, "__dict__", {}) or {})
        return value if isinstance(value, dict) else None
    except Exception:
        return None


def maybe_dict(obj: Any) -> Optional[dict[str, Any]]:
    if isinstance(obj, dict):
        return obj
    if obj is None:
        return None
    out: dict[str, Any] = {}
    for key in (
        "type",
        "url",
        "title",
        "start_index",
        "end_index",
        "text",
        "location",
        "status",
        "id",
        "call_id",
        "action",
        "queries",
        "query",
        "domains",
        "domain",
        "sources",
    ):
        if hasattr(obj, key):
            try:
                out[key] = getattr(obj, key)
            except Exception:
                pass
    return out or None


def get_any(obj: Any, *names: str) -> Any:
    """Get first non-None attribute from nested names."""
    if isinstance(obj, dict):
        for name in names:
            if name in obj and obj[name] is not None:
                return obj[name]
    for name in names:
        if hasattr(obj, name):
            try:
                val = getattr(obj, name)
            except Exception:
                continue
            if val is not None:
                return val
    return None


# ---------------------------------------------------------------------------
# URL citation extraction
# ---------------------------------------------------------------------------


def extract_url_citations(content: Any) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    items = content if isinstance(content, list) else [content]
    for item in items:
        item_dict = maybe_dict(item)
        if not item_dict:
            continue
        annotations = item_dict.get("annotations")
        if not isinstance(annotations, list):
            continue
        for ann in annotations:
            ann_dict = maybe_dict(ann)
            if not ann_dict:
                continue
            ann_type = as_str(ann_dict.get("type")).strip().lower()
            if ann_type != "url_citation":
                continue
            url = as_str(ann_dict.get("url")).strip()
            title = as_str(ann_dict.get("title")).strip()
            start_index = ann_dict.get("start_index")
            end_index = ann_dict.get("end_index")
            location = as_str(ann_dict.get("location")).strip()
            entry = {
                "type": "url_citation",
                "url": url,
                "title": title,
                "location": location,
                "start_index": start_index,
                "end_index": end_index,
            }
            if entry not in citations:
                citations.append(entry)
    return citations


def extract_web_search_call_info(item: Any) -> Optional[dict[str, Any]]:
    item_dict = maybe_dict(item)
    if not item_dict:
        return None

    item_type = as_str(item_dict.get("type")).strip().lower()
    if "web_search_call" not in item_type:
        return None

    action = item_dict.get("action")
    action_dict = maybe_dict(action) if action is not None else None
    if action_dict is None:
        action_dict = {}

    queries = (
        get_any(action, "queries", "query")
        or action_dict.get("queries")
        or action_dict.get("query")
        or item_dict.get("queries")
        or item_dict.get("query")
        or []
    )
    domains = (
        get_any(action, "domains", "domain")
        or action_dict.get("domains")
        or action_dict.get("domain")
        or item_dict.get("domains")
        or item_dict.get("domain")
        or []
    )
    sources = (
        get_any(action, "sources")
        or action_dict.get("sources")
        or item_dict.get("sources")
        or []
    )

    if not isinstance(queries, list):
        queries = [queries] if queries else []
    if not isinstance(domains, list):
        domains = [domains] if domains else []
    if not isinstance(sources, list):
        sources = [sources] if sources else []

    return {
        "id": as_str(item_dict.get("call_id") or item_dict.get("id") or ""),
        "type": item_type,
        "status": as_str(item_dict.get("status") or action_dict.get("status") or ""),
        "action": as_str(
            get_any(action, "type", "name") or item_dict.get("action") or ""
        ),
        "queries": [q for q in (as_str(x).strip() for x in queries) if q],
        "domains": [d for d in (as_str(x).strip() for x in domains) if d],
        "sources_count": len([s for s in sources if s is not None]),
    }


def append_web_sources_suffix(text: str, citations: list[dict[str, Any]]) -> str:
    if not citations:
        return text
    seen = set()
    lines = ["", "", _("Sources:")]
    for citation in citations:
        url = as_str(citation.get("url")).strip()
        title = as_str(citation.get("title")).strip()
        if not url and not title:
            continue
        key = (url or title).lower()
        if key in seen:
            continue
        seen.add(key)
        label = title or url
        if url:
            lines.append(f"- {label} ({url})")
        else:
            lines.append(f"- {label}")
    if len(lines) <= 3:
        return text
    base = text.rstrip()
    suffix = "\n".join(lines)
    return (base + "\n\n" + suffix).rstrip()


# ---------------------------------------------------------------------------
# Web search event helpers
# ---------------------------------------------------------------------------


def web_emit(core: Any, payload: dict[str, Any]) -> None:
    try:
        if core is not None and bool(getattr(core, "_is_web", False)):
            lm = getattr(core, "log_message", None)
            if callable(lm):
                lm(payload)
    except Exception:
        pass


def websearch_debug_enabled() -> bool:
    return env_truthy("UAGENT_WEBSEARCH_DEBUG")


def debug_stream_enabled() -> bool:
    return websearch_debug_enabled()


def debug_emit(core: Any, stage: str, **payload: Any) -> None:
    if not debug_stream_enabled():
        return
    data: dict[str, Any] = {"type": "debug", "stage": as_str(stage) or "update"}
    for key, value in payload.items():
        if value is None:
            continue
        data[key] = value
    web_emit(core, data)


def emit_web_search_event(core: Any, stage: str, **payload: Any) -> None:
    data: dict[str, Any] = {
        "type": "assistant_web_search",
        "stage": as_str(stage) or "update",
    }
    for key, value in payload.items():
        if value is None:
            continue
        if value == "":
            continue
        if value == []:
            continue
        if value == {}:
            continue
        data[key] = value

    def _action_label(action: str) -> str:
        a = as_str(action).strip().lower()
        if a == "search":
            return _("search")
        if a == "open_page":
            return _("open page")
        if a == "find_in_page":
            return _("find in page")
        return a or _("web search")

    def _progress_text() -> str:
        stage = as_str(data.get("stage") or "update").lower()
        status = as_str(data.get("status") or "").lower()
        st = status or stage
        action = _action_label(as_str(data.get("action") or "web search"))
        queries = data.get("queries") or []
        if isinstance(queries, list) and queries:
            q_text = ", ".join(as_str(x) for x in queries[:3] if as_str(x))
        else:
            q_text = ""

        if st in ("in_progress", "searching"):
            msg = _("Web search: searching")
        elif st == "completed":
            msg = _("Web search: completed")
        else:
            msg = _("Web search: {action}").format(action=action)

        if q_text:
            msg += f" ({q_text})"

        sc = data.get("sources_count")
        if isinstance(sc, int) and sc > 0:
            msg += f" — {sc} sources"
        return msg

    try:
        if core is not None and bool(getattr(core, "_is_web", False)):
            web_emit(core, {"type": "assistant_status", "text": _progress_text()})
            return
    except Exception:
        pass

    try:
        if env_enabled_default_true("UAGENT_WEBSEARCH_STATUS"):
            msg = _progress_text()
            if msg:
                print(msg, file=sys.stderr, flush=True)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Streaming debug helpers
# ---------------------------------------------------------------------------


def dump_event_to_fp(ev: Any, debug_fp: Any) -> None:
    """Dump a single streaming event as one-line JSON (JSONL)."""
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
            debug_fp.write(line + chr(10))
            debug_fp.flush()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Tool-call buffer management
# ---------------------------------------------------------------------------


def ensure_tool_buf(
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


def merge_tool_buf(
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

            elif getattr(item, "type", None) == "computer_call":
                cid = (
                    getattr(item, "call_id", None)
                    or getattr(item, "id", None)
                    or f"computer_{int(time.time() * 1000)}"
                )
                tool_calls_list.append(
                    {
                        "id": cid,
                        "type": "function",
                        "function": {
                            "name": "computer",
                            "arguments": json.dumps(
                                {
                                    "actions": [
                                        responses_item_to_dict(a) or {}
                                        for a in (getattr(item, "actions", None) or [])
                                    ]
                                },
                                ensure_ascii=False,
                            ),
                        },
                    }
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
                _emit_compaction_notice(core)

    if not tool_calls_list:
        assistant_text, recovered_tool_calls = parse_assistant_text_tool_calls(
            assistant_text
        )
        if recovered_tool_calls:
            tool_calls_list = recovered_tool_calls

    if core is not None:
        try:
            setattr(core, "_last_responses_output_items", output_items)
            setattr(
                core,
                "_last_responses_usage",
                responses_usage_to_dict(getattr(resp, "usage", None)),
            )
        except Exception:
            pass
    return assistant_text, reasoning_content, tool_calls_list, response_id, output_items


# ---------------------------------------------------------------------------
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

    tool_calls_buf: dict[str, dict[str, Any]] = {}
    item_id_map: dict[str, str] = {}
    _stream_response_id: Optional[str] = None
    _stream_interrupted = False

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
            interrupt_source = core
            if interrupt_source is None or not hasattr(
                interrupt_source, "interrupt_lock"
            ):
                interrupt_source = sys.modules.get("uagent.core")
            if interrupt_source is not None and hasattr(
                interrupt_source, "interrupt_lock"
            ):
                with interrupt_source.interrupt_lock:
                    if interrupt_source.interrupt_requested:
                        # Keep interrupt_requested=True so the outer round can
                        # inject the Stop prompt. Clear Responses continuation
                        # here because this stream response is incomplete.
                        _stream_interrupted = True
                        try:
                            clear_fn = getattr(
                                interrupt_source, "clear_responses_continuation", None
                            )
                            if callable(clear_fn):
                                clear_fn()
                        except Exception:
                            pass
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
                            try:
                                active_fn = getattr(
                                    core or sys.modules.get("uagent.core"),
                                    "set_active_response",
                                    None,
                                )
                                if callable(active_fn):
                                    active_fn(rid, status="in_progress")
                            except Exception:
                                pass
                elif ev_type == "response.completed":
                    ev_resp = getattr(ev, "response", None)
                    if ev_resp is not None:
                        rid = as_str(getattr(ev_resp, "id", None) or "")
                        if rid:
                            _stream_response_id = rid
                        try:
                            if core is not None:
                                setattr(
                                    core,
                                    "_last_responses_usage",
                                    responses_usage_to_dict(
                                        getattr(ev_resp, "usage", None)
                                    ),
                                )
                        except Exception:
                            pass

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

            # Reasoning text deltas (stream immediately; do not break on '.')
            if ev_type == "response.reasoning_text.delta":
                reasoning_delta = getattr(ev, "delta", None)
                if isinstance(reasoning_delta, str) and reasoning_delta:
                    reasoning_parts.append(reasoning_delta)
                    disp_provider = (
                        provider.capitalize()
                        if provider and provider.islower()
                        else provider
                    )
                    show_reasoning(
                        reasoning_delta,
                        provider=disp_provider,
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
                _emit_compaction_notice(core)

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
                    merge_tool_buf(tool_calls_buf, cid_candidate, iid_candidate)

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
                    _emit_compaction_notice(core)
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

                buf = ensure_tool_buf(tool_calls_buf, key)

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
                    merge_tool_buf(tool_calls_buf, cid_candidate, iid_candidate)

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
    # An interrupted stream must not continue the Responses chain or execute
    # partially accumulated tool calls from the aborted response.
    if not _stream_interrupted:
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
    if not tool_calls_list:
        assistant_text, recovered_tool_calls = parse_assistant_text_tool_calls(
            assistant_text
        )
        if recovered_tool_calls:
            tool_calls_list = recovered_tool_calls
    if core is not None:
        try:
            setattr(
                core,
                "_last_responses_output_items",
                [] if _stream_interrupted else output_items,
            )
        except Exception:
            pass
    return (
        assistant_text,
        reasoning_content,
        tool_calls_list,
        None if _stream_interrupted else _stream_response_id,
        [] if _stream_interrupted else output_items,
    )
