"""Message construction / history helpers (moved from util_tools.py)."""

from __future__ import annotations

import json
import os
import time
from typing import Any

from .i18n import _

# Default translation function used when core.tr is not provided.
tr = _
tr_ = _


def _startup_timing_detail(name: str, elapsed: float) -> None:
    enabled = (os.environ.get("UAGENT_STARTUP_TIMING") or "").strip().lower()
    if enabled in {"1", "true", "yes", "on"}:
        print(
            f"[startup-timing] detail.{name}={elapsed:.3f}s",
            file=__import__("sys").stderr,
            flush=True,
        )


def _cwd_marker_prefix() -> str:
    # Used to detect/parse workdir markers in message history.
    return "[CWD] "


def _format_cwd_system_content(
    *,
    event: str,
    path: str,
    extra: dict[str, Any] | None = None,
) -> str:
    payload: dict[str, Any] = {"event": str(event), "path": str(path)}
    if isinstance(extra, dict):
        payload.update(extra)
    return _cwd_marker_prefix() + json.dumps(payload, ensure_ascii=False)


def _insert_cwd_system_message(
    messages_ref: list[dict[str, Any]], msg: dict[str, Any]
) -> None:
    # Insert at the end of the leading system-message block.
    idx = 0
    while idx < len(messages_ref) and messages_ref[idx].get("role") == "system":
        idx += 1
    messages_ref.insert(idx, msg)


def _extract_last_cwd_from_messages(messages: list[dict[str, Any]]) -> str | None:
    prefix = _cwd_marker_prefix()
    for m in reversed(messages or []):
        if not isinstance(m, dict):
            continue
        if m.get("role") != "system":
            continue
        content = m.get("content")
        if not isinstance(content, str):
            continue
        if not content.startswith(prefix):
            continue
        tail = content[len(prefix) :].strip()
        try:
            obj = json.loads(tail)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        p = obj.get("path")
        if isinstance(p, str) and p.strip():
            return p
    return None


def _read_raw_log_messages(path: str) -> list[dict[str, Any]]:
    """Read a JSONL log into raw message dicts (roles/content preserved).

    Unlike ``load_conversation_from_log`` this does not strip system messages,
    so [CWD] markers can be inspected for :load workdir auto-restore.
    """
    raw: list[dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if isinstance(obj, dict) and "role" in obj:
                    raw.append(obj)
    except Exception:
        return []
    return raw


def _skills_marker_prefix() -> str:
    # Used to detect/remove skill injections in message history.
    return "[SKILL] "


def _format_skill_system_content(
    *,
    skill: dict[str, Any],
    doc: dict[str, Any],
    include_finish_skill: bool = False,
) -> str:
    name = str((skill or {}).get("name") or "(unknown)").strip()
    path = str((skill or {}).get("path") or "").strip()
    skill_md = str((skill or {}).get("skill_md") or "").strip()

    fm = (doc or {}).get("frontmatter")
    body = (doc or {}).get("body_markdown")
    if not isinstance(fm, dict):
        fm = {}
    if not isinstance(body, str):
        body = ""

    header_parts: list[str] = [f"{_skills_marker_prefix()}name={name}"]
    if path:
        header_parts.append(f"path={path}")
    if skill_md:
        header_parts.append(f"skill_md={skill_md}")

    allowed_tools = fm.get("allowed-tools")
    if allowed_tools is None:
        allowed_tools = (skill or {}).get("allowed_tools")
    if allowed_tools is not None:
        header_parts.append(f"allowed-tools={allowed_tools}")

    header = " ".join(header_parts)
    body_text = body.strip()
    exec_instructions = "\n\n" + _(
        "[Skill execution]\n"
        "This skill is intended to be run. Read the skill body carefully and follow the instructions.\n"
        "If the skill contains tasks, continue until they are complete.\n"
        "Use tools as needed.\n"
    )
    if include_finish_skill:
        exec_instructions += _(
            "When finished, always call `finish_skill` if available.\n"
        )
    if body_text:
        return header + "\n\n" + body_text + exec_instructions + "\n"
    return header + exec_instructions + "\n"


def _has_any_user_message(messages_ref: list[dict[str, Any]]) -> bool:
    for m in messages_ref or []:
        if isinstance(m, dict) and m.get("role") == "user":
            return True
    return False


def _trim_messages_after_last_user(messages_ref: list[dict[str, Any]]) -> bool:
    for idx in range(len(messages_ref) - 1, -1, -1):
        m = messages_ref[idx]
        if isinstance(m, dict) and m.get("role") == "user":
            del messages_ref[idx + 1 :]
            return True
    return False


def _clear_skill_messages(messages_ref: list[dict[str, Any]]) -> int:
    prefix = _skills_marker_prefix()
    before = len(messages_ref)
    messages_ref[:] = [
        m
        for m in messages_ref
        if not (
            isinstance(m, dict)
            and m.get("role") == "system"
            and isinstance(m.get("content"), str)
            and m.get("content").startswith(prefix)
        )
    ]
    return before - len(messages_ref)


def insert_tools_system_message(
    messages: list[dict[str, Any]],
    *,
    core: Any,
) -> list[dict[str, Any]]:
    return messages


def build_initial_messages(
    *,
    core: Any,
    provider: str | None = None,
    depname: str | None = None,
    use_responses_api: bool | None = None,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []

    # Rebuild system prompt so native tool_search can drop catalog steering
    # using the current provider/model (import-time default may differ).
    try:
        refresh = getattr(core, "refresh_system_prompt", None)
        if callable(refresh):
            _timing_started = time.perf_counter()
            refresh(
                provider=provider,
                depname=depname,
                use_responses_api=use_responses_api,
            )
            _startup_timing_detail(
                "messages.refresh_system_prompt", time.perf_counter() - _timing_started
            )
    except Exception:
        pass

    system_msg = {"role": "system", "content": core.SYSTEM_PROMPT}
    messages.append(system_msg)
    core.log_message(system_msg)

    # --- Load project instruction files (CLAUDE.md / AGENTS.md) ---
    try:
        from .runtime.runtime_instructions import load_project_instruction_files

        _timing_started = time.perf_counter()
        instructions = load_project_instruction_files()
        _startup_timing_detail(
            "messages.instructions", time.perf_counter() - _timing_started
        )
        for instr in instructions:
            msg = {"role": "system", "content": instr}
            messages.append(msg)
            core.log_message(msg)
    except Exception:
        pass

    # Record startup cwd into the message history + log.
    try:
        cwd = os.getcwd()
        cwd_msg = {
            "role": "system",
            "content": _format_cwd_system_content(event="startup", path=cwd),
        }
        _insert_cwd_system_message(messages, cwd_msg)
        core.log_message(cwd_msg)
    except Exception:
        pass

    return messages


def build_long_memory_system_message(long_mem_raw: Any) -> dict[str, Any]:
    if not long_mem_raw:
        return {}

    max_chars = 4000

    header = _(
        "The bullet points listed below are excerpts from this user's long-term memory (persistent memos). "
        "Use them as background information about the user. "
        "However, always prioritize newly provided information in the conversation, and if it contradicts older information, adopt the latest information.\n\n"
    )

    body_lines: list[str] = []

    try:
        if isinstance(long_mem_raw, list):
            for rec in long_mem_raw:
                if isinstance(rec, dict):
                    text = (
                        rec.get("summary")
                        or rec.get("text")
                        or rec.get("content")
                        or rec.get("memory")
                        or json.dumps(rec, ensure_ascii=False)
                    )
                else:
                    text = str(rec)

                text = str(text).replace("\r\n", " ").replace("\n", " ").strip()
                if not text:
                    continue

                body_lines.append(f"- {text}")
                candidate = header + "\n".join(body_lines)
                if len(candidate) > max_chars:
                    body_lines.append("...(truncated: long-term memory is too long)...")
                    break
        else:
            text = str(long_mem_raw).strip()
            if text:
                body_lines.append(text)
    except Exception:
        fallback = header + json.dumps(long_mem_raw, ensure_ascii=False)
        content = fallback[:max_chars]
    else:
        content = header + "\n".join(body_lines)
        if len(content) > max_chars:
            content = (
                content[:max_chars]
                + "\n...(truncated: long-term memory is too long)..."
            )

    return {"role": "system", "content": content}
