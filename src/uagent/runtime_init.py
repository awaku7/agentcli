# -*- coding: utf-8 -*-
"""runtime_init.py

Runtime initialization helpers shared by CLI/WEB/GUI.

Design goals (Mode A: compatibility-first):
- Do not change behavior; only centralize duplicated logic.
- Do not print here; return strings so each UI can decide how to display
  (CLI can route to pager, WEB/GUI can send to their own sinks).

This module intentionally does NOT call os.chdir() or sys.exit() by itself.
Callers can use the returned plan/result to decide what to do.

Key functions:
- decide_workdir(...): compute chosen workdir and perform safety checks.
- apply_workdir(...): actually create/chdir.
- build_startup_banner(...): build human-readable startup info lines.

Security:
- Never include secrets (API keys) in banner.

"""

from __future__ import annotations

import os
from dataclasses import dataclass
from .i18n import _
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class WorkdirDecision:
    chosen: str
    chosen_source: str
    chosen_expanded: str


def decide_workdir(
    *, cli_workdir: Optional[str] = None, env_workdir: Optional[str] = None
) -> WorkdirDecision:
    """Decide workdir path without side-effects.

    Resolution order (same as CLI):
    1) CLI arg
    2) ENV(UAGENT_WORKDIR)
    3) auto (./)
    """

    if cli_workdir:
        chosen = str(cli_workdir)
        chosen_source = "CLI"
    elif env_workdir:
        chosen = str(env_workdir)
        chosen_source = "ENV(UAGENT_WORKDIR)"
    else:
        chosen = os.path.abspath("./")
        chosen_source = "auto"

    chosen_expanded = os.path.expanduser(str(chosen))

    # Safety check only (no mkdir/chdir here)
    if os.path.exists(chosen_expanded) and not os.path.isdir(chosen_expanded):
        raise NotADirectoryError(
            _("Specified workdir path is a file: %(path)s") % {"path": chosen_expanded}
        )

    return WorkdirDecision(
        chosen=chosen, chosen_source=chosen_source, chosen_expanded=chosen_expanded
    )


def apply_workdir(decision: WorkdirDecision) -> None:
    """Apply the decided workdir (mkdir + chdir)."""

    os.makedirs(decision.chosen_expanded, exist_ok=True)
    os.chdir(decision.chosen_expanded)


def _normalize_url(core: Any, url: str) -> str:
    try:
        return core.normalize_url(url)
    except Exception:
        return (url or "").strip().rstrip("/")


def build_startup_banner(*, core: Any, workdir: str, workdir_source: str) -> str:
    """Build startup info lines as a single text block.

    This returns the same information CLI/WEB/GUI were printing:
    - workdir + source
    - provider
    - base_url/api_version (provider-specific)
    - responses mode info

    Caller prints/pagers this text.
    """

    lines: List[str] = []

    lines.append(f"[INFO] workdir = {workdir} (source: {workdir_source})")

    provider = (os.environ.get("UAGENT_PROVIDER", "(unknown)") or "(unknown)").lower()
    lines.append(f"[INFO] provider = {provider}")

    if provider == "azure":
        lines.append(
            f"[INFO] base_url = {_normalize_url(core, os.environ.get('UAGENT_AZURE_BASE_URL', '(not set)'))}"
        )
        lines.append(
            f"[INFO] api_version = {os.environ.get('UAGENT_AZURE_API_VERSION', '(not set)')}"
        )
    elif provider == "openai":
        lines.append(
            f"[INFO] base_url = {_normalize_url(core, os.environ.get('UAGENT_OPENAI_BASE_URL', 'https://api.openai.com/v1'))}"
        )
    elif provider == "nvidia":
        lines.append(
            f"[INFO] base_url = {_normalize_url(core, os.environ.get('UAGENT_NVIDIA_BASE_URL', 'https://integrate.api.nvidia.com/v1'))}"
        )
    elif provider == "openrouter":
        lines.append(
            f"[INFO] base_url = {_normalize_url(core, os.environ.get('UAGENT_OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1'))}"
        )
    elif provider == "grok":
        lines.append(
            f"[INFO] base_url = {_normalize_url(core, os.environ.get('UAGENT_GROK_BASE_URL', 'https://api.x.ai/v1'))}"
        )

    if (os.environ.get("UAGENT_RESPONSES", "") or "").lower() in ("1", "true"):
        lines.append("[INFO] LLM API mode = Responses (UAGENT_RESPONSES is enabled)")

    return "\n".join(lines) + "\n"


def append_long_memory_system_messages(
    *,
    core: Any,
    messages: List[Dict[str, Any]],
    build_long_memory_system_message_fn: Any,
    personal_long_memory_mod: Any,
    shared_memory_mod: Any,
) -> Dict[str, bool]:
    """Append long-memory/shared-memory system messages to `messages` in-place.

    Purpose:
      - Centralize duplicated "long memory" and "shared memory" insertion logic.
      - Keep UI concerns (prints/pager/UI logs) in callers.

    Mode A (compatibility-first):
      - Do not print here.
      - Do not sys.exit() here.
      - Let exceptions propagate; callers handle and keep existing [WARN] prints.

    Expected call contract:
      - build_long_memory_system_message_fn(raw_text: str) -> Dict[str, Any] | None
      - personal_long_memory_mod.load_long_memory_raw() -> str
      - shared_memory_mod.is_enabled() -> bool
      - shared_memory_mod.load_shared_memory_raw() -> str

    Side effects:
      - Appends 0..N system messages to `messages` (in-place).
      - When shared memory is appended, prefixes its content with:
          _("【Shared long-term memory (shared memo)】\n")
        (caller-visible behavior kept compatible with CLI/GUI).

    Returns:
      Flags dict:
        - personal_appended: True if a personal long-memory system message was appended.
        - shared_enabled: True if shared_memory_mod.is_enabled() evaluated to True.
        - shared_appended: True if a shared-memory system message was appended.

      Note:
        shared_enabled == True does not necessarily mean shared_appended == True
        (e.g., build_long_memory_system_message_fn returned None).
    """

    # NOTE: `core` is currently unused; kept for compatibility.
    _ = core

    result = {
        "personal_appended": False,
        "shared_appended": False,
        "shared_enabled": False,
    }

    # Personal long memory
    long_mem_raw = personal_long_memory_mod.load_long_memory_raw()
    mem_system_msg = build_long_memory_system_message_fn(long_mem_raw)
    if mem_system_msg:
        messages.append(mem_system_msg)
        # Caller decides whether/how to log; keep behavior compatible by not logging here.
        result["personal_appended"] = True

    # Shared memory (optional)
    try:
        enabled = bool(shared_memory_mod.is_enabled())
    except Exception:
        enabled = False

    result["shared_enabled"] = enabled

    if enabled:
        shared_raw = shared_memory_mod.load_shared_memory_raw()
        shared_system_msg = build_long_memory_system_message_fn(shared_raw)
        if shared_system_msg:
            # Compatible prefix
            try:
                shared_system_msg["content"] = _("【Shared long-term memory (shared memo)】\n") + (
                    shared_system_msg.get("content") or ""
                )
            except Exception:
                pass

            messages.append(shared_system_msg)
            result["shared_appended"] = True

    return result
