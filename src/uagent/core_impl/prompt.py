"""System prompt helpers (split from core.py)."""

from __future__ import annotations

from typing import Any

from ..env_utils import env_get
from ..i18n import _
from .. import core as _core


def _strip_catalog_steering_text(text: str) -> str:
    """Remove catalog-before-answer steering bullets from prompt text.

    Catalog steering lines always mention tool_catalog (EN/JA and other
    locales keep the tool name). Safe for Rules blocks that only use that
    name on the catalog bullet.
    """
    if not text:
        return text
    out_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("-") and "tool_catalog" in stripped:
            continue
        out_lines.append(line)
    result = "\n".join(out_lines)
    while "\n\n\n" in result:
        result = result.replace("\n\n\n", "\n\n")
    if text.endswith("\n") and not result.endswith("\n"):
        result += "\n"
    return result


def _should_emit_catalog_steering(
    *,
    provider: str | None = None,
    depname: str | None = None,
    use_responses_api: bool | None = None,
) -> bool:
    """False when native GPT-5.4 tool_search is active (no catalog message)."""
    try:
        from ..tools.llm_tool_narrowing import should_emit_catalog_steering

        return bool(
            should_emit_catalog_steering(
                provider=provider,
                depname=depname,
                use_responses_api=use_responses_api,
            )
        )
    except Exception:
        return True


def _build_system_prompt_full() -> str:
    parts = [
        _core.SYSTEM_PROMPT_FULL_MISSION,
        "",
        _core.SYSTEM_PROMPT_FULL_RULES,
        "",
        _core.SYSTEM_PROMPT_FULL_NOTES,
        "",
        _core.SYSTEM_PROMPT_EXTERNAL_CONTENT_POLICY,
        "",
        _core.SYSTEM_PROMPT_WINDOWS_CMD_PASTE_TIP,
        "",
        _core.SYSTEM_PROMPT_DANGEROUS_DELETE_FILE,
    ]
    return "\n".join(parts).strip() + "\n"


def _build_system_prompt_compact() -> str:
    parts = [
        _core.SYSTEM_PROMPT_COMPACT_MISSION,
        "",
        _core.SYSTEM_PROMPT_COMPACT_RULES,
        "",
        _core.SYSTEM_PROMPT_COMPACT_NOTES,
        "",
        _core.SYSTEM_PROMPT_EXTERNAL_CONTENT_POLICY,
        "",
        _core.SYSTEM_PROMPT_WINDOWS_CMD_PASTE_TIP,
        "",
        _core.SYSTEM_PROMPT_DANGEROUS_DELETE_FILE,
    ]
    return "\n".join(parts).strip() + "\n"


def _base_system_prompt_for_mode() -> str:
    mode = (env_get("UAGENT_SYSTEM_PROMPT") or "").strip().lower()

    # Default (env unset): compact.
    if mode in ("full",):
        return _core.SYSTEM_PROMPT_MSGID
    if mode in ("", "compact", "short", "lite"):
        return _core.SYSTEM_PROMPT_COMPACT_MSGID

    # Unknown value: fall back to the full prompt (safer/more compatible).
    return _core.SYSTEM_PROMPT_MSGID


def get_system_prompt(
    *,
    provider: str | None = None,
    depname: str | None = None,
    use_responses_api: bool | None = None,
) -> str:
    """Return system prompt, omitting catalog steering under native tool_search."""
    text = _base_system_prompt_for_mode()
    if not _should_emit_catalog_steering(
        provider=provider,
        depname=depname,
        use_responses_api=use_responses_api,
    ):
        text = _strip_catalog_steering_text(text)
    return text


def _select_system_prompt() -> str:
    return get_system_prompt()


def refresh_system_prompt(
    *,
    provider: str | None = None,
    depname: str | None = None,
    use_responses_api: bool | None = None,
) -> str:
    """Rebuild module-level SYSTEM_PROMPT for the current provider/mode."""
    _core.SYSTEM_PROMPT = get_system_prompt(
        provider=provider,
        depname=depname,
        use_responses_api=use_responses_api,
    )
    return _core.SYSTEM_PROMPT


def build_tools_system_prompt(
    tool_specs: list[dict[str, Any]],
    *,
    provider: str | None = None,
    depname: str | None = None,
    use_responses_api: bool | None = None,
) -> str:
    lines: list[str] = []
    lines.append("[Available Tools]")
    if _should_emit_catalog_steering(
        provider=provider,
        depname=depname,
        use_responses_api=use_responses_api,
    ):
        lines.append(
            _(
                "The following tools are currently loaded in this session. Choose the most appropriate tool for the task. "
                "If none of these tools can do the job, or you are unsure which capability exists, call tool_catalog "
                "before answering or guessing; describe what you need in query, then tool_load any unloaded tool you need."
            )
        )
    else:
        lines.append(
            _(
                "The following tools are currently loaded in this session. "
                "Choose the most appropriate tool for the task."
            )
        )
    for spec in tool_specs:
        func = spec.get("function", {})
        name = func.get("name", "(unknown)")
        sp = func.get("system_prompt") or func.get("description") or ""
        lines.append(f"- {name}: {sp}")
    return "\n".join(lines)
