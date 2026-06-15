from __future__ import annotations

from typing import Any, Optional

from ..env_utils import env_get

from .. import tools


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

    # Do not load tool_catalog unless the gate is explicitly enabled.
    if not use_responses_api:
        return False

    model = (depname or "").strip().lower()

    marker = "gpt-5."
    idx = model.find(marker)
    if idx < 0:
        return False

    tail = model[idx + len(marker) :]
    digits: list[str] = []
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
    call_messages: list[dict[str, Any]],
) -> Optional[list[dict[str, Any]]]:
    """Narrow tool surface for GPT-5.4 (Responses API) using tool_catalog.

    Policy:
    - Always include tool_catalog and human_ask when narrowing is applied.
    - If tool_catalog has hits: include only hit tools (+ tool_catalog + human_ask).
    - If tool_catalog has zero hits, or user text is empty: fail open (return full tool set).

    This function is stateless: it does not depend on previous tool calls.
    """

    specs = tools.get_tool_specs() or []

    try:
        from .catalog_tool import TOOL_SPEC as catalog_tool_spec
    except Exception:
        catalog_tool_spec = None
    try:
        from .human_ask_tool import TOOL_SPEC as human_ask_tool_spec
    except Exception:
        human_ask_tool_spec = None

    helper_specs: list[dict[str, Any]] = []
    helper_names: set[str] = set()
    for helper_spec in (catalog_tool_spec, human_ask_tool_spec):
        if isinstance(helper_spec, dict):
            fn = helper_spec.get("function") or {}
            if isinstance(fn, dict):
                helper_name = str(fn.get("name") or "").strip()
                if helper_name and helper_name not in helper_names:
                    helper_names.add(helper_name)
                    helper_specs.append(helper_spec)

    if not specs:
        return helper_specs

    def _is_low_info_user_text(text: str) -> bool:
        stripped = (text or "").strip()
        if not stripped:
            return True

        compact = "".join(stripped.split())
        if not compact:
            return True

        lowered = stripped.lower()
        if "://" in lowered or "/" in stripped or "\\" in stripped:
            return False
        if any(ch.isdigit() for ch in stripped):
            return False
        if "." in stripped:
            tail = stripped.rsplit(".", 1)[-1]
            if 1 <= len(tail) <= 8 and all(ch.isalnum() for ch in tail):
                return False

        tokens = [part for part in stripped.split() if part]
        if len(tokens) <= 1 and len(compact) <= 2:
            return True
        if len(tokens) <= 2 and len(compact) <= 6:
            return True
        return False

    user_texts: list[str] = []
    for m in reversed(call_messages):
        if m.get("role") != "user":
            continue
        content = m.get("content")
        text = ""
        if isinstance(content, str):
            text = content.strip()
        elif isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") in (
                    "text",
                    "input_text",
                    "output_text",
                ):
                    txt = item.get("text")
                    if isinstance(txt, str) and txt.strip():
                        parts.append(txt.strip())
            if parts:
                text = "\\n".join(parts).strip()

        if text and not _is_low_info_user_text(text):
            user_texts.append(text)
        if len(user_texts) >= 5:
            break

    latest_user_text = "\\n".join(reversed(user_texts)).strip()
    if not latest_user_text:
        if env_get("UAGENT_DEBUG_TOOLS") == "1":
            try:
                print("[debug] gpt54.latest_user_text=", latest_user_text)
                print("[debug] gpt54.tool_catalog_hits=", [])
                print(
                    "[debug] gpt54.narrowing=skip_empty_or_low_info_query(full_tools)"
                )
            except Exception:
                pass
        return specs

    rows = tools.get_tool_catalog(query=latest_user_text, max_results=12)
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
        return helper_specs + [
            spec
            for spec in specs
            if isinstance(spec, dict)
            and str((spec.get("function") or {}).get("name") or "").strip()
            not in helper_names
        ]

    selected_names = {
        "tool_catalog",
        "human_ask",
        "read_file",
        "list_dir",
        "file_exists",
        "finish_skill",
    }
    selected_names.update(hit_names)

    if "search_files" in hit_names or "file_grep" in hit_names:
        selected_names.add("read_file")
    if "create_file" in hit_names or "replace_in_file" in hit_names:
        selected_names.update({"python_compile", "lint_format"})

    narrowed: list[dict[str, Any]] = []
    for spec in helper_specs + list(specs):
        if not isinstance(spec, dict):
            continue
        fn = spec.get("function") or {}
        if not isinstance(fn, dict):
            continue
        name = str(fn.get("name") or "").strip()
        if name in selected_names:
            narrowed.append(spec)

    return narrowed


def _select_tool_specs_for_gpt54_old(
    call_messages: list[dict[str, Any]],
) -> Optional[list[dict[str, Any]]]:
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
            parts: list[str] = []
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

    narrowed: list[dict[str, Any]] = []
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
