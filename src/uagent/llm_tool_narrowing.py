from typing import Any, Dict, List, Optional

from .env_utils import env_get

from . import tools


def _is_gpt54_tool_search_target(
    *,
    provider: str,
    depname: str,
    use_responses_api: bool,
) -> bool:
    """Return True when GPT-5.4 tool narrowing is explicitly enabled.

    Guarded by env:
    - UAGENT_ENABLE_GPT54_TOOL_SEARCH=1|true|yes|on

    Only applies when using the Responses API.
    """

    enabled = (env_get("UAGENT_ENABLE_GPT54_TOOL_SEARCH") or "").strip().lower()
    if enabled not in ("1", "true", "yes", "on"):
        return False

    if not use_responses_api:
        return False

    model = (depname or "").strip().lower()

    marker = "gpt-5."
    idx = model.find(marker)
    if idx < 0:
        return False

    tail = model[idx + len(marker) :]
    digits: List[str] = []
    for ch in tail:
        if ch.isdigit():
            digits.append(ch)
        else:
            break

    if not digits:
        return False

    try:
        minor = int("".join(digits))
    except Exception:
        return False

    return minor >= 4


def _select_tool_specs_for_gpt54(
    call_messages: List[Dict[str, Any]],
) -> Optional[List[Dict[str, Any]]]:
    """Narrow tool surface for GPT-5.4 (Responses API) using tool_catalog.

    Policy:
    - Always include tool_catalog and human_ask when narrowing is applied.
    - If tool_catalog has hits: include only hit tools (+ tool_catalog + human_ask).
    - If tool_catalog has zero hits, or user text is empty: fail open (return full tool set).

    This function is stateless: it does not depend on previous tool calls.
    """

    specs = tools.get_tool_specs() or []
    if not specs:
        return []

    # latest user text
    latest_user_text = ""
    for m in reversed(call_messages):
        if m.get("role") != "user":
            continue
        content = m.get("content")
        if isinstance(content, str):
            latest_user_text = content
            break
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") in (
                    "text",
                    "input_text",
                    "output_text",
                ):
                    txt = item.get("text")
                    if isinstance(txt, str) and txt.strip():
                        parts.append(txt)
            if parts:
                latest_user_text = "\n".join(parts)
                break

    latest_user_text = (latest_user_text or "").strip()
    if not latest_user_text:
        if env_get("UAGENT_DEBUG_TOOLS") == "1":
            try:
                print("[debug] gpt54.latest_user_text=", latest_user_text)
                print("[debug] gpt54.tool_catalog_hits=", [])
                print("[debug] gpt54.narrowing=skip_empty_query(full_tools)")
            except Exception:
                pass
        return specs

    rows = tools.get_tool_catalog(query=latest_user_text, max_results=8)
    hit_names = {
        str(row.get("name") or "").strip()
        for row in (rows or [])
        if isinstance(row, dict)
    }
    hit_names.discard("")

    if env_get("UAGENT_DEBUG_TOOLS") == "1":
        try:
            print("[debug] gpt54.latest_user_text=", latest_user_text)
            print("[debug] gpt54.tool_catalog_hits=", sorted(hit_names))
        except Exception:
            pass

    if not hit_names:
        if env_get("UAGENT_DEBUG_TOOLS") == "1":
            try:
                print("[debug] gpt54.narrowing=zero_hit_fail_open(full_tools)")
            except Exception:
                pass
        return specs

    # Always keep these when narrowing applies
    selected_names = {"tool_catalog", "human_ask"}
    selected_names.update(hit_names)

    narrowed: List[Dict[str, Any]] = []
    for spec in specs:
        if not isinstance(spec, dict):
            continue
        fn = spec.get("function") or {}
        if not isinstance(fn, dict):
            continue
        name = str(fn.get("name") or "").strip()
        if name in selected_names:
            narrowed.append(spec)

    return narrowed
