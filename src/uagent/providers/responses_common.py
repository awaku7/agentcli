"""Shared utilities for Responses API implementations (OpenAI, Azure, Bedrock, etc.)."""

from __future__ import annotations

import json
import sys
from typing import Any, Optional

from ..env_utils import env_get
from ..i18n import _
from ..util_tools import image_file_to_data_url

# ---------------------------------------------------------------------------
# String helpers
# ---------------------------------------------------------------------------


def as_str(x: Any) -> str:
    if x is None:
        return ""
    return str(x)


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
# Streaming debug helpers (extracted from parse_responses_stream closures)
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
