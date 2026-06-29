from __future__ import annotations

import json
import os
import sys
from ..env_utils import env_get
from ..i18n import _
import time
from typing import Any, Optional

from .. import tools
from ..util_tools import image_file_to_data_url
from ..llm_image_helpers import build_image_default_prompt

# -----------------------------------------------------------------------------
# Responses API helpers
# -----------------------------------------------------------------------------


def _as_str(x: Any) -> str:
    if x is None:
        return ""
    return str(x)


def _normalize_content_items(content: Any, *, role: str) -> list[dict[str, Any]]:
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
                        {"type": text_type, "text": _as_str(item.get("text", ""))}
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
                        # Azure/OpenAI Responses expects image_url to be a string.
                        out.append(
                            {
                                "type": "input_image",
                                "image_url": _as_str(iu.get("url")),
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

    return [{"type": text_type, "text": _as_str(content)}]


def _attachment_to_openai_content_item(att: Any) -> Optional[dict[str, Any]]:
    """Convert a stored attachment into an OpenAI Responses content item."""

    if not isinstance(att, dict):
        return None

    att_type = _as_str(att.get("type")).strip().lower()
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


_OPENAI_WEB_SEARCH_TYPE_ALIASES = {
    "web_search": "web_search",
    "web_search_preview": "web_search_preview",
    "openai:web_search": "web_search",
    # Friendly alias for users/configs that describe the capability rather than
    # the exact hosted tool name.
    "url_search": "web_search",
}

_OPENAI_WEB_SEARCH_TOOL_KEYS = {
    "filters",
    "search_context_size",
    "user_location",
    "external_web_access",
    "return_token_budget",
}


def _env_truthy(name: str) -> bool:
    return (env_get(name) or "").strip().lower() in ("1", "true", "yes", "on")


def _env_json_obj(name: str) -> Optional[dict[str, Any]]:
    raw = (env_get(name) or "").strip()
    if not raw:
        return None
    try:
        obj = json.loads(raw)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _normalize_openai_builtin_tool(t: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Return an OpenAI Responses built-in tool spec, if *t* names one.

    Latest OpenAI docs recommend the hosted Responses tool:
      {"type": "web_search"}

    `web_search_preview` is still accepted for legacy integrations but lacks
    newer controls such as filters, external_web_access, and return_token_budget.
    This helper accepts direct built-in specs and function-shaped pseudo specs so
    external/user tool specs can request OpenAI-hosted web search without adding
    a local runner.
    """

    ty = _as_str(t.get("type")).strip()
    mapped = _OPENAI_WEB_SEARCH_TYPE_ALIASES.get(ty)

    if mapped is None:
        fn = t.get("function") if isinstance(t.get("function"), dict) else None
        if isinstance(fn, dict):
            mapped = _OPENAI_WEB_SEARCH_TYPE_ALIASES.get(
                _as_str(fn.get("name")).strip()
            )

    if mapped is None:
        return None

    out: dict[str, Any] = {"type": mapped}
    for key in _OPENAI_WEB_SEARCH_TOOL_KEYS:
        if key in t:
            out[key] = t[key]

    if mapped == "web_search_preview":
        # Keep only controls supported by the legacy preview tool.
        return {
            k: v
            for k, v in out.items()
            if k in ("type", "search_context_size", "user_location")
        }

    return out


def _openai_web_search_tool_from_env() -> Optional[dict[str, Any]]:
    """Build an optional OpenAI hosted web_search tool from env settings.

    Opt-in with UAGENT_OPENAI_WEB_SEARCH=1. Supported controls mirror the current
    OpenAI Responses web_search documentation.
    """

    raw_enabled = (env_get("UAGENT_OPENAI_WEB_SEARCH") or "").strip().lower()
    if raw_enabled not in ("1", "true", "yes", "on"):
        return None

    requested_type = (env_get("UAGENT_OPENAI_WEB_SEARCH_TYPE") or "web_search").strip()
    tool_type = _OPENAI_WEB_SEARCH_TYPE_ALIASES.get(requested_type, "web_search")
    out: dict[str, Any] = {"type": tool_type}

    context_size = (
        (env_get("UAGENT_OPENAI_WEB_SEARCH_CONTEXT_SIZE") or "").strip().lower()
    )
    if context_size in ("low", "medium", "high"):
        out["search_context_size"] = context_size

    user_location = _env_json_obj("UAGENT_OPENAI_WEB_SEARCH_USER_LOCATION_JSON")
    if user_location is not None:
        out["user_location"] = user_location

    if tool_type == "web_search":
        filters = _env_json_obj("UAGENT_OPENAI_WEB_SEARCH_FILTERS_JSON")
        if filters is not None:
            out["filters"] = filters

        external_web_access = (
            (env_get("UAGENT_OPENAI_WEB_SEARCH_EXTERNAL_WEB_ACCESS") or "")
            .strip()
            .lower()
        )
        if external_web_access in ("1", "true", "yes", "on"):
            out["external_web_access"] = True
        elif external_web_access in ("0", "false", "no", "off"):
            out["external_web_access"] = False

        return_token_budget = (
            (env_get("UAGENT_OPENAI_WEB_SEARCH_RETURN_TOKEN_BUDGET") or "")
            .strip()
            .lower()
        )
        if return_token_budget in ("default", "unlimited"):
            out["return_token_budget"] = return_token_budget

    return out


def _env_enabled_default_true(name: str) -> bool:
    raw = (env_get(name) or "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    if raw in ("1", "true", "yes", "on"):
        return True
    return True


def _web_emit(core: Any, payload: dict[str, Any]) -> None:
    try:
        if core is not None and bool(getattr(core, "_is_web", False)):
            lm = getattr(core, "log_message", None)
            if callable(lm):
                lm(payload)
    except Exception:
        pass


def _maybe_dict(obj: Any) -> Optional[dict[str, Any]]:
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


def _extract_url_citations(content: Any) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    items = content if isinstance(content, list) else [content]
    for item in items:
        item_dict = _maybe_dict(item)
        if not item_dict:
            continue
        annotations = item_dict.get("annotations")
        if not isinstance(annotations, list):
            continue
        for ann in annotations:
            ann_dict = _maybe_dict(ann)
            if not ann_dict:
                continue
            ann_type = _as_str(ann_dict.get("type")).strip().lower()
            if ann_type != "url_citation":
                continue
            url = _as_str(ann_dict.get("url")).strip()
            title = _as_str(ann_dict.get("title")).strip()
            start_index = ann_dict.get("start_index")
            end_index = ann_dict.get("end_index")
            location = _as_str(ann_dict.get("location")).strip()
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


def _extract_web_search_call_info(item: Any) -> Optional[dict[str, Any]]:
    item_dict = _maybe_dict(item)
    if not item_dict:
        return None

    item_type = _as_str(item_dict.get("type")).strip().lower()
    if "web_search_call" not in item_type:
        return None

    action = item_dict.get("action")
    action_dict = _maybe_dict(action) if action is not None else None
    if action_dict is None:
        action_dict = {}

    def _get_any(obj: Any, *names: str) -> Any:
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

    queries = (
        _get_any(action, "queries", "query")
        or action_dict.get("queries")
        or action_dict.get("query")
        or item_dict.get("queries")
        or item_dict.get("query")
        or []
    )
    domains = (
        _get_any(action, "domains", "domain")
        or action_dict.get("domains")
        or action_dict.get("domain")
        or item_dict.get("domains")
        or item_dict.get("domain")
        or []
    )
    sources = (
        _get_any(action, "sources")
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
        "id": _as_str(item_dict.get("call_id") or item_dict.get("id") or ""),
        "type": item_type,
        "status": _as_str(item_dict.get("status") or action_dict.get("status") or ""),
        "action": _as_str(
            _get_any(action, "type", "name") or item_dict.get("action") or ""
        ),
        "queries": [q for q in (_as_str(x).strip() for x in queries) if q],
        "domains": [d for d in (_as_str(x).strip() for x in domains) if d],
        "sources_count": len([s for s in sources if s is not None]),
    }


def _append_web_sources_suffix(text: str, citations: list[dict[str, Any]]) -> str:
    if not citations:
        return text
    seen = set()
    lines = ["", "", _("Sources:")]
    for citation in citations:
        url = _as_str(citation.get("url")).strip()
        title = _as_str(citation.get("title")).strip()
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
    suffix = "\
".join(lines)
    return (base + "\
\
" + suffix).rstrip()


def _websearch_debug_enabled() -> bool:
    return _env_truthy("UAGENT_WEBSEARCH_DEBUG")


def _debug_stream_enabled() -> bool:
    return _websearch_debug_enabled()


def _debug_emit(core: Any, stage: str, **payload: Any) -> None:
    if not _debug_stream_enabled():
        return
    data: dict[str, Any] = {"type": "debug", "stage": _as_str(stage) or "update"}
    for key, value in payload.items():
        if value is None:
            continue
        data[key] = value
    _web_emit(core, data)


def _emit_web_search_event(core: Any, stage: str, **payload: Any) -> None:
    data: dict[str, Any] = {
        "type": "assistant_web_search",
        "stage": _as_str(stage) or "update",
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
        a = _as_str(action).strip().lower()
        if a == "search":
            return _("search")
        if a == "open_page":
            return _("open page")
        if a == "find_in_page":
            return _("find in page")
        return a or _("web search")

    def _progress_text() -> str:
        stage = _as_str(data.get("stage") or "update").lower()
        status = _as_str(data.get("status") or "").lower()
        st = status or stage
        action = _action_label(_as_str(data.get("action") or "web search"))
        queries = data.get("queries") or []
        if isinstance(queries, list) and queries:
            q_text = ", ".join(_as_str(x) for x in queries[:3] if _as_str(x))
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
            _web_emit(core, {"type": "assistant_status", "text": _progress_text()})
            return
    except Exception:
        pass

    try:
        if _env_enabled_default_true("UAGENT_WEBSEARCH_STATUS"):
            msg = _progress_text()
            if msg:
                print(msg, file=sys.stderr, flush=True)
    except Exception:
        pass


def build_responses_request(
    call_messages: list[dict[str, Any]],
    *,
    send_tools_this_round: bool,
    provider: str = "openai",  # kept for compatibility with caller
    tool_specs: Optional[list[dict[str, Any]]] = None,
) -> tuple[Optional[str], list[dict[str, Any]], Optional[list[dict[str, Any]]]]:
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

    instructions_list: list[str] = []
    input_msgs: list[dict[str, Any]] = []

    # Force the model to produce usable tool arguments.
    # Without this, some Azure/Responses combinations repeatedly emit
    # function_call arguments={} even for tools with required parameters.
    TOOL_CALLING_RULES = _("""[Tool calling rules]
        - When calling a tool/function, you MUST provide function_call.arguments as a JSON object.
        - The JSON object MUST include all required parameters defined by the tool schema.
        - Never call a tool with an empty object {} unless the tool has no required parameters.
        - If you do not have a required parameter, ask the user for it using human_ask instead of guessing.
        """)
    instructions_list.append(TOOL_CALLING_RULES)
    instructions_list.append(_("""[Web search rules]
        - Use web search only when fresh or external information is necessary.
        - Do not use web search for local or stable information.
        - Prefer answering without web search when the answer is already sufficient.
        """))
    for m in call_messages:
        role = m.get("role")

        if role == "system":
            instructions_list.append(_as_str(m.get("content", "")))
            continue

        m_clean: dict[str, Any] = dict(m)

        attachment_items: list[dict[str, Any]] = []
        if role == "user":
            raw_attachments = m_clean.get("attachments")
            if isinstance(raw_attachments, list):
                for att in raw_attachments:
                    item = _attachment_to_openai_content_item(att)
                    if item is not None:
                        attachment_items.append(item)
            elif isinstance(raw_attachments, dict):
                item = _attachment_to_openai_content_item(raw_attachments)
                if item is not None:
                    attachment_items.append(item)

            saved_path = m_clean.get("saved_path")
            if isinstance(saved_path, str) and saved_path.strip():
                item = _attachment_to_openai_content_item(
                    {"type": "image", "saved_path": saved_path.strip()}
                )
                if item is not None:
                    attachment_items.append(item)

            saved_files = m_clean.get("saved_files")
            if isinstance(saved_files, list):
                for sf in saved_files:
                    if isinstance(sf, str) and sf.strip():
                        item = _attachment_to_openai_content_item(
                            {"type": "image", "saved_path": sf.strip()}
                        )
                        if item is not None:
                            attachment_items.append(item)
                    elif isinstance(sf, dict):
                        item = _attachment_to_openai_content_item(sf)
                        if item is not None:
                            attachment_items.append(item)

            content_text = _as_str(m_clean.get("content", ""))
            if attachment_items and not content_text.strip():
                attachment_items.insert(
                    0,
                    {
                        "type": "input_text",
                        "text": build_image_default_prompt("describe"),
                    },
                )

        # Responses API input must not contain project-specific attachment metadata.
        # Keep it in internal history, but drop it from the payload we send.
        for _k in ("attachments", "saved_path", "saved_files"):
            if _k in m_clean:
                try:
                    del m_clean[_k]
                except Exception:
                    pass

        # If assistant had tool_calls, remove them and write a trace into instructions
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
            merged = prefix + _as_str(original_content).lstrip("\r\n")

            m_clean["role"] = "user"
            m_clean["content"] = _normalize_content_items(merged, role="user")
            input_msgs.append(m_clean)
            continue

        # Normal user/assistant
        if role not in ("user", "assistant"):
            role = "user"
            m_clean["role"] = "user"

        normalized_content = _normalize_content_items(m_clean.get("content"), role=role)
        if role == "user" and attachment_items:
            normalized_content.extend(attachment_items)
        m_clean["content"] = normalized_content

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
    req_tools: Optional[list[dict[str, Any]]] = None
    if send_tools_this_round:
        raw_specs = tools.get_tool_specs() if tool_specs is None else tool_specs
        flat_tools: list[dict[str, Any]] = []

        # OpenAI-hosted web search is not a local function tool.  It must be
        # sent as a Responses built-in tool, e.g. {"type": "web_search"}.
        # Allow opt-in through env without requiring a dummy local tool module.
        if provider == "openai":
            env_web_search_tool = _openai_web_search_tool_from_env()
            if env_web_search_tool is not None:
                flat_tools.append(env_web_search_tool)

        for t in raw_specs or []:
            if not isinstance(t, dict):
                continue

            builtin_tool = _normalize_openai_builtin_tool(t)
            if builtin_tool is not None:
                flat_tools.append(builtin_tool)
                continue

            fn = t.get("function") or {}
            if not isinstance(fn, dict):
                continue
            name = fn.get("name")
            if not name:
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


def parse_responses_response(
    resp: Any, *, core: Any = None
) -> tuple[str, list[dict[str, Any]]]:
    """Parse Responses API response into (assistant_text, tool_calls_list)."""

    assistant_text = ""
    tool_calls_list: list[dict[str, Any]] = []
    seen_web_search_ids: set[str] = set()

    if hasattr(resp, "output") and resp.output:
        for item in resp.output:
            item_type = _as_str(getattr(item, "type", "")).strip().lower()
            if item_type == "message":
                for c in getattr(item, "content", []) or []:
                    ct = getattr(c, "type", None)
                    if ct in ("output_text", "text"):
                        assistant_text += _as_str(getattr(c, "text", ""))
                citations = _extract_url_citations(getattr(item, "content", []) or [])
                if citations:
                    _debug_emit(
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
            elif "web_search_call" in item_type:
                info = _extract_web_search_call_info(item)
                if info:
                    wid = _as_str(info.get("id"))
                    if wid and wid in seen_web_search_ids:
                        continue
                    if wid:
                        seen_web_search_ids.add(wid)
                    _emit_web_search_event(core, "update", **info)

    return assistant_text, tool_calls_list


def parse_responses_stream(
    stream: Any,
    *,
    print_delta_fn: Any = None,
    core: Any = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Parse Responses API streaming iterator into (assistant_text, tool_calls_list).

    Debugging:
      - If UAGENT_STREAMING_DEBUG is enabled, dumps each event as JSON to:
          - ./outputs/responses_stream_events.jsonl

    This function is intentionally defensive because the exact event names/shape
    vary across OpenAI SDK versions and Azure deployments.

    Strategy:
      - Iterate events.
      - If an event carries output_text delta, append and optionally print it.
      - If an event carries function-call name/arguments delta, accumulate.
      - IMPORTANT: Some events may carry only item_id (no call_id). We therefore
        buffer by (call_id OR item_id) and later promote/merge when call_id becomes known.
      - At end, return the full assistant_text and ChatCompletions-like tool_calls_list.
    """

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

    def _dump_event(ev: Any) -> None:
        """Dump a single streaming event as one-line JSON (JSONL)."""
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
                debug_fp.write(line + chr(10))
                debug_fp.flush()
            except Exception:
                pass

    assistant_text_parts: list[str] = []
    fallback_full_text = ""

    # key -> buffer (key is call_id OR item_id OR synthetic)
    tool_calls_buf: dict[str, dict[str, Any]] = {}

    # item_id (e.g. "fc_...") -> call_id (e.g. "call_...")
    item_id_map: dict[str, str] = {}

    def _print_delta(s: str) -> None:
        if not s:
            return
        if callable(print_delta_fn):
            try:
                print_delta_fn(s)
                return
            except Exception:
                pass

    def _ensure_buf(key: str) -> dict[str, Any]:
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

    def _merge_buf(dst_key: str, src_key: str) -> None:
        """Merge src into dst and delete src (best-effort)."""
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

        src_name = _as_str(src.get("name") or "")
        dst_name = _as_str(dst.get("name") or "")
        if (
            (not dst_name or dst_name == "unknown")
            and src_name
            and src_name != "unknown"
        ):
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

    try:
        # Web streaming: signal start (a single growing assistant bubble)
        try:
            if core is not None and bool(getattr(core, "_is_web", False)):
                lm = getattr(core, "log_message", None)
                if callable(lm):
                    lm({"type": "assistant_stream_start"})
        except Exception:
            pass

        # Normalize stream iterator
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

            if _debug_stream_enabled():
                _dump_event(ev)

            ev_type = getattr(ev, "type", None) or getattr(ev, "event", None) or ""

            if "web_search_call" in _as_str(ev_type).lower():
                info = _extract_web_search_call_info(ev)
                if info:
                    _emit_web_search_event(core, "update", **info)

            # 1) Output text deltas
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

            # 1.5) Reasoning text deltas (o1/o3-mini reasoning_content)
            if ev_type == "response.reasoning_text.delta":
                reasoning_delta = getattr(ev, "delta", None)
                if isinstance(reasoning_delta, str) and reasoning_delta:
                    try:
                        if core is not None and bool(getattr(core, "_is_web", False)):
                            lm = getattr(core, "log_message", None)
                            if callable(lm):
                                lm(
                                    {
                                        "type": "assistant_stream_delta",
                                        "delta": f"\033[90m{reasoning_delta}\033[0m",
                                    }
                                )
                        else:
                            _print_delta(f"\033[90m{reasoning_delta}\033[0m")
                    except Exception:
                        _print_delta(f"\033[90m{reasoning_delta}\033[0m")

            if ev_type == "response.output_text.done":
                t = getattr(ev, "text", None)
                if isinstance(t, str) and t:
                    fallback_full_text = t

            # 2) Tool call accumulation
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

            if ev_type in ("response.output_item.added", "response.output_item.delta"):
                item = getattr(ev, "item", None) or getattr(ev, "output_item", None)
                if (
                    item is not None
                    and "web_search_call" in _as_str(getattr(item, "type", "")).lower()
                ):
                    info = _extract_web_search_call_info(item)
                    if info:
                        _emit_web_search_event(core, "update", **info)
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

            # Register mapping and promote/merge buffers when possible
            if cid_candidate and iid_candidate:
                item_id_map[iid_candidate] = cid_candidate
                # If we already started buffering under item_id, merge into call_id
                if iid_candidate in tool_calls_buf:
                    _merge_buf(cid_candidate, iid_candidate)

            # Resolve call_id via item_id map if needed
            if iid_candidate and not cid_candidate:
                cid_candidate = item_id_map.get(iid_candidate)

            # Function name extraction
            if not fn_name:
                if hasattr(ev, "name"):
                    fn_name = getattr(ev, "name")
                elif hasattr(ev, "function") and hasattr(
                    getattr(ev, "function"), "name"
                ):
                    fn_name = getattr(getattr(ev, "function"), "name")
                elif hasattr(ev, "delta") and hasattr(getattr(ev, "delta"), "name"):
                    fn_name = getattr(getattr(ev, "delta"), "name")

            # Function arguments delta extraction
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
                if (
                    item is not None
                    and "web_search_call" in _as_str(getattr(item, "type", "")).lower()
                ):
                    info = _extract_web_search_call_info(item)
                    if info:
                        _emit_web_search_event(core, "update", **info)
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

                buf = _ensure_buf(key)

                if cid_candidate:
                    buf["call_id"] = cid_candidate
                if iid_candidate:
                    buf["item_id"] = iid_candidate

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

                # If we just learned call_id for a buffer keyed by item_id, promote
                if cid_candidate and iid_candidate and key == iid_candidate:
                    _merge_buf(cid_candidate, iid_candidate)

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

    assistant_text = "".join(assistant_text_parts) or fallback_full_text

    tool_calls_list: list[dict[str, Any]] = []
    for key, buf in tool_calls_buf.items():
        args_str = "".join(buf.get("arguments_parts") or [])
        if not args_str:
            args_str = "{}"

        call_id_out = _as_str(buf.get("call_id") or key)
        tool_calls_list.append(
            {
                "id": call_id_out,
                "type": "function",
                "function": {
                    "name": _as_str(buf.get("name") or "unknown"),
                    "arguments": args_str,
                },
            }
        )

    return assistant_text, tool_calls_list
