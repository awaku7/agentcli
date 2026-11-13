"""Background consolidation of long-term memory from conversation logs.

The conversational agent saves durable notes as they come up, but some
are missed. This pass re-reads the conversation in a background thread
(the same shape as profile learning, ``run_profiling_async``), asks the
model for durable facts, decisions and commitments, and saves them
through the checked save path with ``source="consolidation"``.

Two boundaries keep the pass safe:

- It only runs under the local identity. The checked save path writes
  to the legacy unscoped store, which is fenced to local mode; scoped
  Web memory is written through the agent tools instead.
- It can never resurrect a forgotten note. Saves carry a
  content-derived ``source_id``, and the checked save path refuses
  background sources whose content matches a tombstone.

Saved counts are kept in a small state file next to the memory file
and surfaced once, the next time a session prints pending memory
notices. Opt out with ``UAGENT_MEMORY_CONSOLIDATION=0`` (or the master
``UAGENT_MEMORY=0``).
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any

from ..env_utils import env_get

_MAX_NOTES_PER_PASS = 5
_STATE_FILE_NAME = "memory_consolidation_state.json"

_EXTRACTION_PROMPT = (
    "You are a memory consolidation agent. Analyze the conversation log "
    "and extract facts about the user that are worth keeping in "
    "long-term memory across sessions:\n"
    "- durable personal facts (who they are, where they live or work, "
    "the people and projects that matter to them)\n"
    "- decisions they made and commitments they took on\n\n"
    "Do NOT include preferences, habits or constraints (those belong "
    "to the user profile, not long-term memory).\n"
    "Do NOT include one-off task details, temporary questions, "
    "chit-chat, or sensitive credentials.\n"
    "Only include facts the user themselves stated or clearly "
    "confirmed.\n"
    "Write each note as one short sentence in the same language as "
    "the conversation.\n"
    "You MUST respond ONLY with a valid JSON object matching this "
    "schema:\n"
    '{"notes": ["string"]}\n'
    'If nothing is worth keeping, respond with {"notes": []}.'
)


def consolidation_enabled() -> bool:
    """Whether the background consolidation pass is active."""
    master = (env_get("UAGENT_MEMORY") or "").strip().lower()
    if master in ("0", "false", "no", "off"):
        return False
    value = (env_get("UAGENT_MEMORY_CONSOLIDATION") or "1").strip().lower()
    return value not in ("0", "false", "no", "off")


def consolidation_source_id(note: str) -> str:
    """Stable origin id for one consolidated note (content-derived)."""
    digest = hashlib.sha256(str(note).encode("utf-8")).hexdigest()
    return f"consolidation:{digest}"


def save_consolidation_notes(notes: list[str]) -> int:
    """Save extracted notes through the checked save path.

    Returns how many notes were newly saved. Duplicates, secrets and
    notes matching a tombstone are refused by the save path itself.
    """
    from ..tools.long_memory import save_long_memory

    saved = 0
    for raw in notes[:_MAX_NOTES_PER_PASS]:
        note = str(raw or "").strip()
        if not note:
            continue
        result = save_long_memory(
            note,
            source="consolidation",
            source_id=consolidation_source_id(note),
        )
        if result.get("saved"):
            saved += 1
    if saved:
        _record_pending_notice(saved)
    return saved


def run_memory_consolidation_async(messages: list[dict[str, Any]], core: Any) -> None:
    """Run one consolidation pass over ``messages`` in a background thread."""
    if not consolidation_enabled():
        return
    if not messages:
        return
    try:
        from .identity_context import current_turn_is_local

        if not current_turn_is_local():
            return
    except Exception:
        return
    # Deep copy messages to avoid thread-safety issues with the main loop
    try:
        messages_copy = json.loads(json.dumps(messages))
    except Exception:
        return
    thread = threading.Thread(
        target=_consolidation_worker,
        args=(messages_copy, core),
        daemon=True,
    )
    thread.start()


def _consolidation_worker(messages: list[dict[str, Any]], core: Any) -> None:
    """Background worker: extract durable notes and save them."""
    try:
        from ..profile_manager import _llm_simple_text, _sanitize_log_for_profiling
        from ..providers import util_providers

        provider, client, model_name = util_providers.make_client(core)
        if not client:
            return
        sanitized_log = _sanitize_log_for_profiling(messages)
        if not sanitized_log.strip():
            return
        raw_response = _llm_simple_text(
            provider=provider,
            client=client,
            model_name=model_name,
            system_prompt=_EXTRACTION_PROMPT,
            user_prompt=f"CONVERSATION LOG:\n{sanitized_log}",
            max_tokens=1200,
            temperature=0.0,
        )
        notes = _parse_notes(raw_response)
        if notes:
            save_consolidation_notes(notes)
    except Exception:
        # Fail silently in background thread to avoid interrupting the user
        pass


def _parse_notes(raw_response: str) -> list[str]:
    """Parse the extraction response into a list of note strings."""
    cleaned = str(raw_response or "").strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    try:
        payload = json.loads(cleaned)
    except Exception:
        return []
    items = payload.get("notes") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        return []
    return [
        str(item).strip()
        for item in items
        if isinstance(item, str) and str(item).strip()
    ]


def _state_path() -> Path:
    from ..tools.long_memory import get_memory_file_path

    return Path(get_memory_file_path()).expanduser().parent / _STATE_FILE_NAME


def _record_pending_notice(saved_count: int) -> None:
    """Accumulate auto-saved counts until they are shown to the user."""
    try:
        path = _state_path()
        pending = 0
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            pending = int(payload.get("pending_saved") or 0)
        except Exception:
            pending = 0
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {"pending_saved": pending + saved_count, "updated_at": time.time()}
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


def pop_pending_consolidation_count() -> int:
    """Return and clear the number of auto-saved notes not yet shown."""
    try:
        path = _state_path()
        payload = json.loads(path.read_text(encoding="utf-8"))
        count = int(payload.get("pending_saved") or 0)
        if count:
            path.write_text(
                json.dumps({"pending_saved": 0, "updated_at": time.time()}),
                encoding="utf-8",
            )
        return count
    except Exception:
        return 0
