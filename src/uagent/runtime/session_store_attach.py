"""Attach/detach the opt-in session store to a running core (split out of
session_store.py).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
import atexit
import os
import re

from ..i18n import _
from .session_store_common import (
    Session,
    SessionStoreError,
    normalize_tool_call,
    project_id_from_path,
)

if TYPE_CHECKING:
    from .session_store import SessionStore


def attach_opt_in_session_store(
    core: Any,
    *,
    project_path: str | Path,
    entry_point: str,
    existing_session_id: str | None = None,
) -> tuple[SessionStore | None, str | None]:
    """Attach the opt-in store to any UAG entry point using its log callback."""
    # session_store re-exports this module, so import the class at call time.
    from .session_store import SessionStore

    store = SessionStore.from_environment()
    if store is None:
        return None, None
    if existing_session_id:
        saved = store.get_session(existing_session_id)
        if not saved:
            store.close()
            raise SessionStoreError("existing session is unavailable")
        session = Session(existing_session_id, saved.get("project"), entry_point)
    else:
        session = store.create_session(
            project=project_id_from_path(project_path),
            project_path=project_path,
            entry_point=entry_point,
        )
    original_log_message = core.log_message
    core._session_store_original_log_message = original_log_message
    # The CLI can switch the loaded conversation with :load. Keep the active
    # persistence target on core so the callback does not permanently capture
    # the session created at startup.
    core._session_store_active_id = session.session_id
    from .agent_state import AgentState, AgentStateManager

    persisted_agent_state = store.get_agent_state(session.session_id)
    agent_state_manager = AgentStateManager(
        AgentState.from_dict(persisted_agent_state)
        if persisted_agent_state
        else AgentState()
    )
    pending_tool_calls: dict[str, tuple[str, dict[str, Any]]] = {}

    jsonl_enabled = (
        os.environ.get("UAGENT_SESSION_BACKEND", "sqlite").strip().lower() != "sqlite"
    )

    def degrade_session_persistence(exc: BaseException) -> None:
        """Stop persisting this run instead of aborting the LLM round.

        The store is an auxiliary audit sink, so a competing process or a
        storage-level failure must not terminate the interactive operation.
        The callback is disabled for the remainder of this entry point.
        """
        if getattr(core, "_session_store_write_disabled", False):
            return
        core._session_store_write_disabled = True
        print(
            _("[sessions warn] Session persistence disabled for this run: %(error)s")
            % {"error": exc}
        )

    def log_message(message: dict[str, Any]) -> None:
        try:
            from .observability.content_runtime import capture_logged_message

            capture_logged_message(message)
        except Exception:
            pass
        if jsonl_enabled:
            original_log_message(message)
        if getattr(core, "_session_store_write_disabled", False):
            return
        role = message.get("role") if isinstance(message, dict) else None
        if role not in {"system", "user", "assistant", "tool"}:
            return
        content = str(message.get("content") or "")
        active_session_id = getattr(
            core, "_session_store_active_id", session.session_id
        )
        try:
            store.append_message(
                active_session_id,
                str(role),
                content,
                payload=message if isinstance(message, dict) else None,
            )
        except SessionStoreError as exc:
            degrade_session_persistence(exc)
            return
        if role == "assistant":
            for call in message.get("tool_calls") or []:
                if isinstance(call, dict):
                    call_id, name, args = normalize_tool_call(call)
                    if call_id:
                        pending_tool_calls[call_id] = (name, args)
        elif role == "tool" and message.get("tool_call_id"):
            call_id = str(message["tool_call_id"])
            name, args = pending_tool_calls.pop(
                call_id, (str(message.get("name") or "tool"), {})
            )
            status = "failed" if "[tool runtime error]" in content else "success"
            try:
                store.record_tool_call(
                    active_session_id,
                    tool_name=name,
                    args=args,
                    result=content,
                    status=status,
                    call_id=call_id,
                )
            except SessionStoreError as exc:
                degrade_session_persistence(exc)

    def record_tool_result(record: dict[str, Any], persistent_history: Any) -> None:
        active_session_id = getattr(
            core, "_session_store_active_id", session.session_id
        )
        try:
            store.record_tool_result(
                active_session_id,
                record,
                persistent_history,
            )
        except SessionStoreError as exc:
            degrade_session_persistence(exc)
            return
        raw_max_rows = os.environ.get("UAGENT_TOOL_RESULT_MAX_ROWS", "500")
        try:
            max_rows = int(raw_max_rows)
        except (TypeError, ValueError):
            max_rows = 500
        if max_rows > 0:
            try:
                store.prune_tool_results(active_session_id, max_rows=max_rows)
            except SessionStoreError as exc:
                degrade_session_persistence(exc)

    def prune_tool_results(max_rows: int = 500, evictable_only: bool = True) -> int:
        active_session_id = getattr(
            core, "_session_store_active_id", session.session_id
        )
        return store.prune_tool_results(
            active_session_id,
            max_rows=max_rows,
            evictable_only=evictable_only,
        )

    def save_agent_state(
        state: dict[str, Any], *, expected_revision: int | None = None
    ) -> None:
        active_session_id = getattr(
            core, "_session_store_active_id", session.session_id
        )
        store.save_agent_state(
            active_session_id, state, expected_revision=expected_revision
        )

    def complete_agent_step(step: str, next_action: str = "") -> dict[str, Any]:
        active_session_id = getattr(
            core, "_session_store_active_id", session.session_id
        )
        persisted, expected_revision = store.get_agent_state_snapshot(active_session_id)
        manager = AgentStateManager(
            AgentState.from_dict(persisted) if persisted else AgentState()
        )
        state = manager.mark_step_complete(step, next_action=next_action)
        core.agent_state_manager = manager
        store.save_agent_state(
            active_session_id, state.to_dict(), expected_revision=expected_revision
        )
        return state.to_dict()

    def fail_agent_step(step: str, next_action: str = "") -> dict[str, Any]:
        active_session_id = getattr(
            core, "_session_store_active_id", session.session_id
        )
        persisted, expected_revision = store.get_agent_state_snapshot(active_session_id)
        manager = AgentStateManager(
            AgentState.from_dict(persisted) if persisted else AgentState()
        )
        state = manager.mark_step_failed(step, next_action=next_action)
        core.agent_state_manager = manager
        store.save_agent_state(
            active_session_id, state.to_dict(), expected_revision=expected_revision
        )
        return state.to_dict()

    def update_agent_state(**changes: Any) -> dict[str, Any]:
        active_session_id = getattr(
            core, "_session_store_active_id", session.session_id
        )
        persisted, expected_revision = store.get_agent_state_snapshot(active_session_id)
        manager = AgentStateManager(
            AgentState.from_dict(persisted) if persisted else AgentState()
        )
        state = manager.update(**changes)
        core.agent_state_manager = manager
        store.save_agent_state(
            active_session_id, state.to_dict(), expected_revision=expected_revision
        )
        return state.to_dict()

    def get_agent_state() -> dict[str, Any] | None:
        active_session_id = getattr(
            core, "_session_store_active_id", session.session_id
        )
        state = store.get_agent_state(active_session_id)
        core.agent_state_manager = AgentStateManager(
            AgentState.from_dict(state) if state else AgentState()
        )
        return state

    def get_tool_result(result_id: str) -> dict[str, Any] | None:
        active_session_id = getattr(
            core, "_session_store_active_id", session.session_id
        )
        return store.get_tool_result(active_session_id, result_id)

    def artifact_cleanup(execute: bool = False) -> dict[str, Any]:
        """Return or execute cleanup for the active Session."""
        active_session_id = getattr(
            core, "_session_store_active_id", session.session_id
        )
        from .artifact_manager import ArtifactManager

        workdir = Path(os.environ.get("UAGENT_WORKDIR") or os.getcwd())
        manager = ArtifactManager(workdir, store=store)
        try:
            records = store.list_tool_results(active_session_id, limit=10_000)
            referenced = {
                str(record.get("artifact_ref") or "").removeprefix("artifact://")
                for record in records
                if record.get("artifact_ref")
            }
            return manager.cleanup(
                referenced_ids={item for item in referenced if item},
                session_id=active_session_id,
                execute=execute,
            )
        finally:
            manager.close()

    def artifact_cleanup_report() -> dict[str, Any]:
        """Return a dry-run cleanup report for the active Session."""
        active_session_id = getattr(
            core, "_session_store_active_id", session.session_id
        )
        from .artifact_manager import ArtifactManager

        workdir = Path(os.environ.get("UAGENT_WORKDIR") or os.getcwd())
        manager = ArtifactManager(workdir, store=store)
        try:
            records = store.list_tool_results(active_session_id, limit=10_000)
            referenced = {
                str(record.get("artifact_ref") or "").removeprefix("artifact://")
                for record in records
                if record.get("artifact_ref")
            }
            return manager.cleanup_report(
                referenced_ids={item for item in referenced if item},
                session_id=active_session_id,
            )
        finally:
            manager.close()

    def read_artifact_preview(reference: str, max_chars: int = 4000) -> str:
        """Read a bounded textual Artifact preview owned by the active session."""
        active_session_id = getattr(
            core, "_session_store_active_id", session.session_id
        )
        artifact_id = str(reference or "").strip().removeprefix("artifact://")
        if not re.fullmatch(r"[0-9a-f]{32}", artifact_id):
            return ""
        from .artifact_manager import ArtifactManager

        workdir = Path(os.environ.get("UAGENT_WORKDIR") or os.getcwd())
        manager = ArtifactManager(workdir, store=store)
        try:
            item = manager.get(artifact_id)
            if item.session_id != active_session_id:
                return ""
            media_type = (item.media_type or "").lower()
            if not (media_type.startswith("text/") or "json" in media_type):
                return ""
            return manager.open(artifact_id).read_text(
                encoding="utf-8", errors="replace"
            )[: max(0, int(max_chars))]
        except Exception:
            return ""
        finally:
            manager.close()

    def search_tool_results(query: str, limit: int = 10) -> list[dict[str, Any]]:
        active_session_id = getattr(
            core, "_session_store_active_id", session.session_id
        )
        return store.search_tool_results(active_session_id, query, limit=limit)

    def retrieve_tool_context(
        query: str, limit: int = 10, max_chars: int = 12_000
    ) -> str:
        from .tool_result_manager import ContextResultManager

        records = search_tool_results(query, limit=limit)
        for record in records:
            artifact_ref = str(record.get("artifact_ref") or "")
            if artifact_ref:
                preview = read_artifact_preview(artifact_ref, max_chars=2000)
                if preview:
                    record["artifact_preview"] = preview
        return ContextResultManager().format_retrieved_context(
            records, max_chars=max_chars
        )

    core.log_message = log_message
    core.record_tool_result = record_tool_result
    core.prune_tool_results = prune_tool_results
    core.agent_state_manager = agent_state_manager
    core.save_agent_state = save_agent_state
    core.update_agent_state = update_agent_state
    core.complete_agent_step = complete_agent_step
    core.fail_agent_step = fail_agent_step
    core.get_agent_state = get_agent_state
    core.get_tool_result = get_tool_result
    core.artifact_cleanup_report = artifact_cleanup_report
    core.artifact_cleanup = artifact_cleanup
    core.read_artifact_preview = read_artifact_preview
    core.search_tool_results = search_tool_results
    core.retrieve_tool_context = retrieve_tool_context
    core.session_store = store
    try:
        from ..tools.context import get_callbacks

        callbacks = get_callbacks()
        callbacks.session_store = store
        callbacks.session_id = session.session_id
    except Exception:
        pass
    atexit.register(detach_opt_in_session_store, core)
    core.session_id = session.session_id
    try:
        from .memory_consolidation import run_startup_consolidation

        run_startup_consolidation(core, store, current_session_id=session.session_id)
    except Exception:
        pass
    return store, session.session_id


def detach_opt_in_session_store(core: Any) -> None:
    """Close and detach a store previously attached to an entry point."""
    store = getattr(core, "session_store", None)
    try:
        if store is not None:
            store.close()
    finally:
        original = getattr(core, "_session_store_original_log_message", None)
        if original is not None:
            core.log_message = original
        # Attach mutates the process-wide tool callback object. Clear only the
        # state belonging to this store so a later entry point cannot retain a
        # closed SQLite connection or stale session ID.
        try:
            from ..tools.context import get_callbacks

            callbacks = get_callbacks()
            if getattr(callbacks, "session_store", None) is store:
                callbacks.session_store = None
                callbacks.session_id = None
        except Exception:
            pass
        for name in (
            "session_store",
            "session_id",
            "record_tool_result",
            "prune_tool_results",
            "agent_state_manager",
            "save_agent_state",
            "update_agent_state",
            "complete_agent_step",
            "fail_agent_step",
            "get_agent_state",
            "get_tool_result",
            "artifact_cleanup_report",
            "artifact_cleanup",
            "read_artifact_preview",
            "search_tool_results",
            "retrieve_tool_context",
            "_session_store_active_id",
            "_session_store_original_log_message",
        ):
            try:
                delattr(core, name)
            except AttributeError:
                pass
