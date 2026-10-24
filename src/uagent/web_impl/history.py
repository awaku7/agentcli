"""Room history initialization and connection bootstrap (split from web.py)."""

from __future__ import annotations

import os
import threading
import time

from ..i18n import _, set_thread_lang
from .. import core
from ..runtime import runtime_init as _runtime_init
from ..runtime.identity_context import (
    IdentityResolutionError,
    resolve_identity_mode,
)
from .. import util_tools as tools_util
from .io import _web_server_log
from .rooms import WebRoom, _thread_ctx, web_manager


def _restore_private_room_session(room: WebRoom, *, store, principal_id: str) -> bool:
    """Rehydrate a server-restarted private Room from its bound SQLite session.

    The RoomAccessPolicy binding supplies the session ID; this extra check keeps
    the persisted transcript bound to the same principal and Room. Tool catalog
    restoration is intentionally omitted here: Remote Web must not import Host
    plugins merely to display/continue a recovered transcript.
    """
    session_id = str(getattr(room, "session_id", "") or "").strip()
    if not session_id or getattr(room, "history_initialized", False):
        return False
    try:
        saved = store.get_session(session_id)
    except Exception as exc:
        raise IdentityResolutionError("private Room session is unavailable") from exc
    if str(saved.get("principal_id") or "") != str(principal_id or "") or str(
        saved.get("room_id") or ""
    ) != str(room.room_id):
        raise IdentityResolutionError("private Room session binding does not match")

    messages = store.list_messages(session_id)
    if not messages:
        return False
    sanitize = getattr(core, "sanitize_messages_for_tools", None)
    if callable(sanitize):
        messages = sanitize(messages)

    from ..runtime.agent_state import AgentStateManager
    from ..runtime.session_command_service import SessionCommandService
    from ..runtime.session_restore import apply_persisted_state
    from ..util_cmd_session import _extract_last_cwd_from_messages

    restore_plan = SessionCommandService(store).build_restore_plan(
        session_id,
        messages,
        system_prompt=getattr(core, "SYSTEM_PROMPT", None),
    )
    room.history = restore_plan.messages
    room.responses_state = {}
    room.tool_context = {}
    room.agent_state_manager = AgentStateManager()
    room.mcp_request_generation = 0
    apply_persisted_state(room, restore_plan)

    workdir_plan = SessionCommandService.plan_workdir(
        session_id,
        message_workdir=_extract_last_cwd_from_messages(restore_plan.messages),
        session_project_path=saved.get("project_path"),
        current_workdir=room.base_dir,
    )
    if workdir_plan is not None:
        room.base_dir = workdir_plan.target_path
    room.history_initialized = True
    room.welcome_shown = True
    return True


def _ensure_room_history_initialized(room: WebRoom) -> None:
    """Initialize room.history once (system prompt, AGENTS.md prompt, memory).

    Safe to call from connect-time bootstrap or the first worker turn.
    Web instruction selection uses human_ask and therefore requires room.loop
    plus thread-local/active room binding.
    """
    if getattr(room, "history_initialized", False):
        return

    # Bind room context so human_ask / status updates reach this room.
    prev_room = getattr(_thread_ctx, "room", None)
    _thread_ctx.room = room
    prev_active = None
    try:
        with web_manager.active_room_lock:
            prev_active = web_manager.active_room
            web_manager.active_room = room
    except Exception:
        prev_active = None

    _orig_cwd = os.getcwd()
    try:
        try:
            os.chdir(room.base_dir)
        except Exception:
            pass
        try:
            set_thread_lang(getattr(room, "lang", "en"))
        except Exception:
            pass
        try:
            setattr(core, "_is_web", True)
        except Exception:
            pass

        try:
            _web_server_log(f"[web-init] history start room={str(room.room_id)[:8]}")
        except Exception:
            pass

        # Keep UI responsive indicator while prompting.
        try:
            room.set_status(True, "INIT")
            if web_manager.original_set_status:
                web_manager.original_set_status(True, "INIT")
        except Exception:
            pass

        room.history = tools_util.build_initial_messages(core=core)
        room.history.extend(getattr(room, "portable_history", []))
        room.portable_history = []
        # Surface instruction-load result in the Web chat (print alone is console-only).
        # Prefer session-tracked paths (I18N-safe) over parsing translated headers.
        try:
            from ..runtime.runtime_instructions import (
                _find_instruction_files,
                get_loaded_instruction_paths,
            )

            loaded_abs = get_loaded_instruction_paths()
            loaded_files: list[str] = []
            base = os.path.abspath(room.base_dir or ".")
            for p in loaded_abs:
                try:
                    loaded_files.append(os.path.relpath(p, base))
                except Exception:
                    loaded_files.append(os.path.basename(p) or p)
            if loaded_files:
                lines = [
                    _("[INFO] Loading %(n)d project instruction file(s).")
                    % {"n": len(loaded_files)}
                ]
                for rel in loaded_files:
                    lines.append(f"  - {rel}")
                room.add_message({"role": "assistant", "content": chr(10).join(lines)})
            else:
                # Distinguish "none found" vs "user skipped";
                # only show skip notice when AGENTS/CLAUDE exists in workdir tree.
                try:
                    cands = _find_instruction_files(room.base_dir)
                except Exception:
                    cands = []
                if cands:
                    room.add_message(
                        {
                            "role": "assistant",
                            "content": _(
                                "[INFO] No project instruction files selected."
                            ),
                        }
                    )
        except Exception:
            pass

        # Surface enabled-plugins status in Web chat (print alone is console-only).
        # Format here so room locale (set_thread_lang) is applied.
        try:
            if not getattr(room, "_plugins_status_shown", False):
                from ..runtime.runtime_plugins import format_enabled_plugins_status

                _plugins_line = format_enabled_plugins_status(
                    getattr(web_manager, "plugins_startup_list", None) or []
                )
                if _plugins_line:
                    room.add_message({"role": "assistant", "content": _plugins_line})
                try:
                    setattr(room, "_plugins_status_shown", True)
                except Exception:
                    pass
        except Exception:
            pass

        # Apply SessionStart hook stdout stashed at server boot (if any)
        try:
            from ..hooks_engine import inject_pending_session_hook_context

            inject_pending_session_hook_context(room.history)
        except Exception:
            pass

        if resolve_identity_mode() == "local" and not getattr(
            room, "private_session", False
        ):
            # Legacy global Memory stores remain available only for the
            # single-user local deployment. Authenticated Web rooms receive
            # access-filtered turn-local projection in the LLM pipeline.
            from ..tools import long_memory as personal_long_memory
            from ..tools import shared_memory

            print(_("[INFO] Loaded long-term memory."))
            try:
                room.add_message(
                    {
                        "role": "assistant",
                        "content": _("[INFO] Loaded long-term memory."),
                    }
                )
            except Exception:
                pass
            try:
                flags = _runtime_init.append_long_memory_system_messages(
                    core=core,
                    messages=room.history,
                    build_long_memory_system_message_fn=tools_util.build_long_memory_system_message,
                    personal_long_memory_mod=personal_long_memory,
                    shared_memory_mod=shared_memory,
                )
                if flags.get("shared_enabled"):
                    print(_("[INFO] Loaded shared long-term memory."))
                    try:
                        room.add_message(
                            {
                                "role": "assistant",
                                "content": _("[INFO] Loaded shared long-term memory."),
                            }
                        )
                    except Exception:
                        pass
                # These are room-scoped provider instructions, not raw turns.
                # Logging them through the process-global core callback could
                # write one room's memory into another room's active session.
            except Exception as exc:
                print(
                    _(
                        "[WARN] Exception occurred while loading shared long-term memory: %(err)s"
                    )
                    % {"err": exc}
                )

        try:
            _web_server_log(
                f"[web-init] history done room={str(room.room_id)[:8]} msgs={len(room.history)}"
            )
        except Exception:
            pass
        room.history_initialized = True
    finally:
        try:
            room.set_status(False, "IDLE")
            if web_manager.original_set_status:
                web_manager.original_set_status(False, "")
        except Exception:
            pass
        try:
            os.chdir(_orig_cwd)
        except Exception:
            pass
        try:
            with web_manager.active_room_lock:
                if web_manager.active_room is room:
                    web_manager.active_room = prev_active
        except Exception:
            pass
        try:
            _thread_ctx.room = prev_room
        except Exception:
            pass
        try:
            set_thread_lang(None)
        except Exception:
            pass


def _bootstrap_room_on_connect(
    room: WebRoom,
    *,
    turn_context=None,
    identity_context=None,
) -> None:
    """Run once after first websocket connect so AGENTS.md is asked immediately."""
    if getattr(room, "history_initialized", False):
        return
    if getattr(room, "_bootstrap_started", False):
        return
    try:
        setattr(room, "_bootstrap_started", True)
    except Exception:
        pass
    # Disable the chat input immediately, before the delayed bootstrap thread
    # starts. Otherwise the browser can submit a turn while AGENTS.md selection
    # is still pending and race the history initialization.
    try:
        room.set_status(True, "INIT")
    except Exception:
        pass

    def _runner() -> None:
        try:
            # Wait briefly for room.loop assignment from websocket endpoint.
            for _ in range(50):
                if getattr(room, "loop", None) is not None:
                    break
                time.sleep(0.02)
            # Give the browser time to process the init frame and mount Svelte
            # before the human_ask modal arrives.
            time.sleep(0.6)
            if getattr(room, "history_initialized", False):
                return
            # Wait until at least one websocket is actually connected.
            for _ in range(50):
                if room.active_connections:
                    break
                time.sleep(0.05)
            if not room.active_connections:
                # Client already gone; skip prompt.
                room._bootstrap_started = False
                room.set_status(False, "IDLE")
                return
            pool = web_manager.room_worker_pool
            if pool is not None:
                pool.bootstrap(
                    room,
                    turn_context=turn_context,
                    identity_context=identity_context,
                    project_path=room.base_dir,
                )
            elif turn_context is not None:
                from ..runtime.identity_context import call_with_turn_context

                call_with_turn_context(
                    turn_context,
                    _ensure_room_history_initialized,
                    room,
                    identity_context=identity_context,
                )
            else:
                _ensure_room_history_initialized(room)
        except Exception as e:
            try:
                _web_server_log(
                    f"[web-init] bootstrap error room={str(getattr(room, 'room_id', ''))[:8]} err={e!r}"
                )
            except Exception:
                pass
        finally:
            if getattr(room, "history_initialized", False):
                room._bootstrap_started = False
            # Let a later reconnect retry bootstrap if initialization failed
            # before completing.
            if not getattr(room, "history_initialized", False):
                room._bootstrap_started = False
                try:
                    room.set_status(False, "IDLE")
                except Exception:
                    pass

    threading.Thread(
        target=_runner,
        daemon=True,
        name=f"uagent-web-init-{str(getattr(room, 'room_id', ''))[:8]}",
    ).start()
