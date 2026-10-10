"""Explicit, local operator commands for Sub-Agent receipt audit reviews.

Only a foreground interactive CLI command can write a review. Nothing here
accepts model-proposed reviewer identities or automatically promotes a report
to verified AgentState, Memory or Goal completion.
"""

from __future__ import annotations

import os
import re
import shlex
import sys
from typing import Any

from ..i18n import _
from ..runtime.compaction_record import SourceRef
from ..runtime.session_store import SessionStore, SessionStoreError
from ..runtime.sub_agent_jobs import SubAgentJobOwner
from .sub_agent_jobs import _safe_terminal_text

_ROOT_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,128}")
_MAX_SQLITE_ID = 9_223_372_036_854_775_807


def _active_cli_session(
    core: Any, store: SessionStore, owner: SubAgentJobOwner
) -> str | None:
    if not isinstance(store, SessionStore):
        return None
    if not isinstance(owner, SubAgentJobOwner) or owner.entry_point != "cli":
        return None
    active = str(getattr(core, "_session_store_active_id", "") or "")
    if active != owner.session_id:
        return None
    try:
        session = store.get_session(active)
    except (SessionStoreError, ValueError):
        return None
    if session["entry_point"] != "cli":
        return None
    return active


def _human_review_available(core: Any) -> bool:
    """Fail closed for injected, headless and Auto-pilot commands."""
    return (
        getattr(sys.stdin, "isatty", lambda: False)()
        and getattr(sys.stdout, "isatty", lambda: False)()
        and os.environ.get("UAGENT_NON_INTERACTIVE", "").lower()
        not in {"1", "true", "yes", "on"}
        and not bool(getattr(core, "auto_pilot_active", False))
    )


def handle_cli_receipt_command(
    line: str,
    *,
    core: Any,
    store: SessionStore,
    owner: SubAgentJobOwner,
) -> bool:
    """Handle :receipt commands; never claim factual verification."""
    stripped = str(line or "").strip()
    if stripped != ":receipt" and not stripped.startswith(":receipt "):
        return False
    try:
        parts = shlex.split(stripped)
    except ValueError:
        print(
            _(
                "Usage: :receipt [evidence | review <root-id> <supported|rejected> <message-id> <seq>]"
            )
        )
        return True
    if not parts or parts[0] != ":receipt":
        return False
    session_id = _active_cli_session(core, store, owner)
    if session_id is None:
        print(_("Receipt review is unavailable for the current CLI Session."))
        return True

    if len(parts) == 1:
        receipts = store.list_visible_sub_agent_receipts(session_id, limit=10)
        if not receipts:
            print(_("No currently accessible unverified receipts."))
            return True
        for item in receipts:
            root = item["root_handoff_id"]
            audit = store.get_sub_agent_receipt_review(session_id, root)
            status = audit["outcome"] if audit is not None else "not-reviewed"
            print(
                f"{_safe_terminal_text(root, 128)} "
                f"{_('role')}={_safe_terminal_text(item['role'], 80)} "
                f"{_('review')}={status}"
            )
        return True

    if len(parts) == 2 and parts[1] == "evidence":
        entries = store.list_recent_exact_user_message_refs(session_id, limit=20)
        if not entries:
            print(_("No indexed Main user messages available as evidence."))
            return True
        print(_("Candidate evidence IDs (content intentionally hidden):"))
        for item in entries:
            print(
                f"message-id={_safe_terminal_text(item['ref_id'], 32)} "
                f"seq={item['session_seq']}"
            )
        return True

    if len(parts) != 6 or parts[1] != "review":
        print(
            _(
                "Usage: :receipt review <root-id> <supported|rejected> <message-id> <seq>"
            )
        )
        print(_("Use :receipt evidence to list candidate Main user message IDs."))
        return True
    if not _human_review_available(core):
        print(
            _("Receipt review requires an interactive local operator (not Auto-pilot).")
        )
        return True
    root_id, outcome, message_id, seq_value = parts[2:]
    if (
        _ROOT_ID_RE.fullmatch(root_id) is None
        or outcome not in {"supported", "rejected"}
        or not message_id.isascii()
        or not message_id.isdecimal()
        or len(message_id) > 19
        or int(message_id) < 1
        or int(message_id) > _MAX_SQLITE_ID
        or not seq_value.isascii()
        or not seq_value.isdecimal()
        or len(seq_value) > 19
        or int(seq_value) < 1
        or int(seq_value) > _MAX_SQLITE_ID
    ):
        print(_("Invalid receipt review command arguments."))
        return True
    evidence = SourceRef("message", message_id, session_id, int(seq_value))
    try:
        earlier = store.get_sub_agent_receipt_review(session_id, root_id)
        expected_revision = store.get_agent_state_revision(session_id)
        if (
            earlier is not None
            and earlier["reviewer_id"] == "cli:local-operator"
            and earlier["outcome"] == outcome
            and earlier["evidence_refs"] == [evidence.to_dict()]
        ):
            # An identical retry must use the original revision that was
            # persisted with the audit decision, even if Main moved forward.
            expected_revision = earlier["base_revision"]
        receipt = store.review_sub_agent_receipt(
            session_id,
            root_id,
            reviewer_id="cli:local-operator",
            outcome=outcome,
            evidence_refs=(evidence,),
            expected_revision=expected_revision,
            source_access_check=lambda ref: (
                ref == evidence and store.is_exact_indexed_message_available(ref)
            ),
        )
    except (SessionStoreError, ValueError, TypeError, OverflowError) as exc:
        print(
            _("Receipt review rejected: %(error)s")
            % {"error": _safe_terminal_text(type(exc).__name__, 80)}
        )
        return True
    label = _("already recorded") if receipt["already_reviewed"] else _("recorded")
    print(
        _(
            "Receipt review %(status)s: %(outcome)s (audit only; no Goal or state changes)"
        )
        % {"status": label, "outcome": outcome}
    )
    return True


def dispatch_cli_receipt_command_event(
    line: str,
    *,
    core: Any,
    store: SessionStore,
    owner: SubAgentJobOwner,
) -> bool:
    """Run a command event and always release stdin's command-pending state."""
    stripped = str(line or "").strip()
    if stripped != ":receipt" and not stripped.startswith(":receipt "):
        return False
    try:
        return handle_cli_receipt_command(line, core=core, store=store, owner=owner)
    finally:
        core.set_status(False, "")
