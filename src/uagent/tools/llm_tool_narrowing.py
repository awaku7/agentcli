from __future__ import annotations

from typing import Any, Optional

from ..env_utils import env_get
from .. import tools


def _get_gpt54_tool_search_mode() -> str:
    """Return the GPT-5.4 tool search mode.

    Reads UAGENT_GPT54_TOOL_SEARCH env:
      - unset / "native": Use OpenAI native tool_search (send all tools, let server narrow)
      - "legacy": Use old tool_catalog-based narrowing (send only relevant tools)
      - "off": Disable any GPT-5.4 specific handling
    """
    raw = (env_get("UAGENT_GPT54_TOOL_SEARCH") or "").strip().lower()
    if raw in ("off", "0", "false", "no"):
        return "off"
    if raw in ("legacy", "old"):
        return "legacy"
    return "native"


def _is_gpt54_tool_search_target(
    *,
    provider: str,
    depname: str,
    use_responses_api: bool,
) -> bool:
    """Return True when OpenAI/Azure Responses API with GPT-5.4+ is used.

    Only applies when mode is not 'off'.
    """

    mode = _get_gpt54_tool_search_mode()
    if mode == "off":
        return False

    if not use_responses_api:
        return False

    pv = (provider or "").strip().lower()
    if pv not in ("openai", "azure"):
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


def _is_legacy_mode() -> bool:
    """Return True if legacy tool_catalog narrowing mode is active."""
    return _get_gpt54_tool_search_mode() == "legacy"


def _select_tool_specs_legacy(
    call_messages: list[dict[str, Any]],
) -> Optional[list[dict[str, Any]]]:
    """Narrow tool surface for GPT-5.4 (Responses API) using tool_catalog.

    Legacy mode: only relevant tools (+ tool_catalog/tool_load/unload_tool/human_ask)
    are sent.  If tool_catalog has zero hits, or user text is empty, fail open
    (return full tool set).

    This function is stateless: it does not depend on previous tool calls.
    """

    specs = tools.get_tool_specs() or []

    try:
        from .catalog_tool import TOOL_SPEC as catalog_tool_spec
    except Exception:
        catalog_tool_spec = None
    try:
        from .catalog_tool import TOOL_SPEC_2 as tool_load_spec
    except Exception:
        tool_load_spec = None
    try:
        from .catalog_tool import TOOL_SPEC_3 as unload_tool_spec
    except Exception:
        unload_tool_spec = None
    try:
        from .human_ask_tool import TOOL_SPEC as human_ask_tool_spec
    except Exception:
        human_ask_tool_spec = None

    helper_specs: list[dict[str, Any]] = []
    helper_names: set[str] = set()
    for helper_spec in (
        catalog_tool_spec,
        tool_load_spec,
        unload_tool_spec,
        human_ask_tool_spec,
    ):
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
        "tool_load",
        "unload_tool",
        "human_ask",
        "read_file",
        "list_dir",
        "file_exists",
        "finish_skill",
    }
    # Include all currently loaded tools so tool_load results persist across rounds
    for spec in specs:
        if not isinstance(spec, dict):
            continue
        fn = spec.get("function") or {}
        if not isinstance(fn, dict):
            continue
        name = str(fn.get("name") or "").strip()
        if name:
            selected_names.add(name)
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
