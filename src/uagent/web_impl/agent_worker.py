"""Web agent worker loop (split from web.py)."""

from __future__ import annotations

import asyncio
import os
import time
import traceback
from typing import Any, Optional

from ..i18n import _, set_thread_lang
from .. import core
from ..env_utils import env_get
from .. import util_tools as tools_util
from ..providers import util_providers as providers
from .. import uagent_llm as llm_util
from ..runtime.logging_setup import log_event
from ..runtime.execution import lifecycle_execution
from ..runtime.turn_context_runtime import call_with_resolved_turn_context
from ..runtime.session_store import project_id_from_path
from ..runtime.identity_context import (
    IdentityContext,
    IdentityResolutionError,
    TurnContext,
    call_with_turn_context,
    resolve_identity_mode,
)
from ..runtime.round_outcome import project_round_outcome, round_outcome_event
from ..runtime.memory_projection import memory_projection_access_is_current
from ..image_session import build_image_session_message
from ..llm_helpers import LLMWaitInterrupted
from .helpers import _save_input_history
from .history import _ensure_room_history_initialized
from .io import _web_server_log
from .rooms import WebRoom, _thread_ctx, web_manager


def run_agent_worker(
    room: WebRoom,
    user_input: str,
    attachments: Optional[list[dict[str, Any]]] = None,
    *,
    turn_context: TurnContext | None = None,
    identity_context: IdentityContext | None = None,
    project_path: str | None = None,
):
    """Run one user turn for a room.

    Lock/status contract:
    - room.worker_lock: per-room serialization (non-blocking acquire)
    - global_worker_lock: process-wide cwd/tool safety
    - room status BUSY is set only after both locks are held
    - finally always clears room/core status and releases locks
    """

    if turn_context is None and resolve_identity_mode() != "local":
        raise IdentityResolutionError("Web worker requires connection identity")
    if turn_context is not None:
        if turn_context.entry_point != "web" or turn_context.room_id != room.room_id:
            raise IdentityResolutionError("Web turn room mismatch")
        if identity_context is None or not identity_context.authenticated:
            raise IdentityResolutionError("Web turn requires authenticated identity")
        if (
            turn_context.principal_id != identity_context.principal_id
            or turn_context.authenticated != identity_context.authenticated
            or turn_context.authn_kind != identity_context.authn_kind
        ):
            raise IdentityResolutionError("Web identity/turn mismatch")
        if not project_path or turn_context.project_id != project_id_from_path(
            project_path
        ):
            raise IdentityResolutionError("Web turn project mismatch")

    def _run_web_turn(fn, *args, **kwargs):
        if turn_context is not None:
            return call_with_turn_context(
                turn_context, fn, *args, identity_context=identity_context, **kwargs
            )
        # Legacy direct worker calls use the selected resolver; non-local modes
        # fail closed because no authenticated connection was supplied.
        return call_with_resolved_turn_context(
            fn,
            *args,
            entry_point="web",
            room_id=str(getattr(room, "room_id", "") or ""),
            project_path=str(getattr(room, "base_dir", "") or os.getcwd()),
            session_id=str(getattr(core, "session_id", "") or ""),
            **kwargs,
        )

    # Ensure logs/status go to this room (thread-local). Parallel tool workers
    # inherit room via tools.run_tool wrapper (see init_web).
    _thread_ctx.room = room
    set_thread_lang(getattr(room, "lang", "en"))
    log_event(
        "web.room.task.started",
        room_id=getattr(room, "room_id", ""),
        locale=getattr(room, "lang", "en"),
    )

    # Serialize per-room runs to avoid history/tool collisions
    if not room.worker_lock.acquire(blocking=False):
        room.add_message(
            {
                "role": "assistant",
                "content": _(
                    "[WARN] Another task is already running in this room. Please retry after it completes."
                ),
            }
        )
        try:
            set_thread_lang(None)
        except Exception:
            pass
        _thread_ctx.room = None
        return

    acquired_global = False
    _orig_cwd = os.getcwd()
    _orig_log_message = getattr(core, "log_message", None)

    try:
        # Switch to this room's base_dir for the duration of the worker
        try:
            os.chdir(project_path if turn_context is not None else room.base_dir)
        except Exception:
            pass

        # Acquire global lock BEFORE marking BUSY so a blocked waiter never
        # appears BUSY while still queued on the lock.
        web_manager.global_worker_lock.acquire()
        acquired_global = True

        with web_manager.active_room_lock:
            web_manager.active_room = room

        # Suppress CLI [STATE] before first status update (Windows WriteConsoleW
        # bypasses sys.stderr redirection and leaks to the server console).
        try:
            setattr(core, "_is_web", True)
        except Exception:
            pass

        room.set_status(True, "BUSY")
        try:
            # Keep core.status_busy in sync for interrupt / genre guards.
            # Call original directly to avoid recursive room.set_status.
            if web_manager.original_set_status:
                web_manager.original_set_status(True, "BUSY")
            else:
                core.status_busy = True
                core.status_label = "BUSY"
        except Exception:
            pass
        try:
            _web_server_log(
                f"[web-worker] start room={str(room.room_id)[:8]} busy=1 label=BUSY"
            )
        except Exception:
            pass

        # Streaming helpers for Web UI
        stream_state: dict[str, Any] = {
            "id": None,
            "active": False,
            "suppress_next_assistant_message": False,
            "memory_invalidated": False,
        }
        try:
            core._memory_projection_invalidated = False
        except Exception:
            pass

        def _web_stream_send(payload: dict[str, Any]) -> None:
            stream_types = {
                "assistant_stream_start",
                "assistant_stream_delta",
                "assistant_stream_replace",
                "assistant_stream_end",
                "reasoning",
            }
            if payload.get("type") in stream_types:
                snapshot = getattr(core, "memory_projection_snapshot", None)
                if not memory_projection_access_is_current(snapshot, core):
                    stream_state["memory_invalidated"] = True
                    try:
                        core._memory_projection_invalidated = True
                        with core.interrupt_lock:
                            core.interrupt_requested = True
                    except Exception:
                        pass
                    return
                if stream_state.get("memory_invalidated"):
                    return
            try:
                if room.loop:
                    asyncio.run_coroutine_threadsafe(room.broadcast(payload), room.loop)
            except Exception:
                pass

        def _emit_round_outcome() -> None:
            outcome = project_round_outcome(
                getattr(core, "_last_round_outcome", {}) or {}
            )
            if not outcome:
                return
            payload = round_outcome_event(outcome)
            _web_stream_send(payload)
            try:
                room.status["round_outcome"] = dict(outcome)
            except Exception:
                pass

        def _stream_start() -> str:
            sid = f"asst_{int(time.time() * 1000)}"
            stream_state["id"] = sid
            stream_state["active"] = True
            stream_state["suppress_next_assistant_message"] = True
            _web_stream_send({"type": "assistant_stream_start", "id": sid})
            return sid

        def _stream_delta(delta: str, *, reasoning: bool = False) -> None:
            if not delta:
                return
            if not stream_state.get("active"):
                _stream_start()
            if reasoning:
                _web_stream_send({"type": "reasoning", "content": delta})
            else:
                _web_stream_send(
                    {
                        "type": "assistant_stream_delta",
                        "id": stream_state.get("id"),
                        "delta": delta,
                    }
                )

        def _stream_replace(content: str) -> None:
            if not stream_state.get("active"):
                _stream_start()
            _web_stream_send(
                {
                    "type": "assistant_stream_replace",
                    "id": stream_state.get("id"),
                    "content": content,
                }
            )

        def _stream_end() -> None:
            if stream_state.get("active"):
                _web_stream_send(
                    {"type": "assistant_stream_end", "id": stream_state.get("id")}
                )
            stream_state["active"] = False
            stream_state["suppress_next_assistant_message"] = False

        # Patch core.log_message during this worker run so streaming deltas can go to WebSocket.
        _orig_log_message = getattr(core, "log_message", None)

        def _patched_log_message(msg: dict[str, Any]) -> None:
            try:
                if (
                    isinstance(msg, dict)
                    and msg.get("type") == "assistant_reasoning_delta"
                ):
                    _stream_delta(str(msg.get("delta") or ""), reasoning=True)
                    return
                if (
                    isinstance(msg, dict)
                    and msg.get("type") == "assistant_stream_delta"
                ):
                    _stream_delta(str(msg.get("delta") or ""))
                    return
                if (
                    isinstance(msg, dict)
                    and msg.get("type") == "assistant_stream_replace"
                ):
                    _stream_replace(str(msg.get("content") or ""))
                    return
                if isinstance(msg, dict) and msg.get("type") == "assistant_stream_end":
                    _stream_end()
                    return
                if (
                    isinstance(msg, dict)
                    and msg.get("type") == "assistant_stream_interrupted"
                ):
                    _stream_end()
                    return
            except Exception:
                pass
            if callable(_orig_log_message):
                try:
                    _orig_log_message(msg)
                except Exception:
                    pass
            try:
                if isinstance(msg, dict):
                    role = msg.get("role")
                    # UI-only assistant (e.g. empty-no-tool WARN) must be visible in Web,
                    # but must not enter room.history (model prompt).
                    if role == "assistant" and msg.get("_uagent_ui_only"):
                        room.add_message(dict(msg))
                    elif role in ("user", "tool") and not msg.get("_uagent_internal"):
                        room.add_message(dict(msg))
            except Exception:
                pass

        try:
            if callable(_orig_log_message):
                setattr(core, "log_message", _patched_log_message)
        except Exception:
            pass

        try:
            if not (env_get("UAGENT_PROVIDER") or "").strip():
                room.add_message(
                    {
                        "role": "assistant",
                        "content": _(
                            "[FATAL] Environment variable UAGENT_PROVIDER is not set.\nPlease check environment variables when starting the web server."
                        ),
                    }
                )
                return

            provider_name, client, depname = providers.make_client(core)

            user_input = str(user_input or "")
            attachment_lines: list[str] = []
            clean_attachments: list[dict[str, Any]] = []
            for att in attachments or []:
                if not isinstance(att, dict):
                    continue
                item = dict(att)
                path = str(
                    item.get("saved_path")
                    or item.get("path")
                    or item.get("file_path")
                    or ""
                ).strip()
                if not path:
                    continue
                name = str(item.get("name") or os.path.basename(path) or path).strip()
                mime = (
                    str(
                        item.get("mime")
                        or item.get("content_type")
                        or item.get("type")
                        or ""
                    )
                    .lower()
                    .strip()
                )
                is_image = mime.startswith("image/") or mime == "image"
                is_video = (
                    mime.startswith("video/") and os.path.getsize(path) <= 50_000_000
                )
                label = os.path.basename(name) or os.path.basename(path) or path
                if is_image:
                    attachment_lines.append(
                        _("[Attached Image] %(name)s") % {"name": label}
                    )
                    attachment_lines.append(_("[Image Path] %(path)s") % {"path": path})
                    item["type"] = "image"
                else:
                    attachment_lines.append(
                        _("[Attached File] %(name)s") % {"name": label}
                    )
                    attachment_lines.append(_("[File Path] %(path)s") % {"path": path})
                    item["type"] = "file"
                item["saved_path"] = path
                if mime:
                    item["mime"] = mime
                # Ensure data_url is set for images if missing
                if is_image and not item.get("data_url"):
                    try:
                        item["data_url"] = tools_util.image_file_to_data_url(path)
                    except Exception:
                        pass
                if is_video and not item.get("data_url"):
                    try:
                        item["data_url"] = tools_util.media_file_to_data_url(
                            path, max_bytes=50_000_000
                        )
                    except Exception:
                        item["type"] = "file"
                clean_attachments.append(item)

            # Build multimodal content for images and guarded llama.cpp videos.
            has_image = any(
                att.get("type") == "image" for att in (clean_attachments or [])
            )
            has_video = provider_name == "llama_cpp" and any(
                att.get("type") == "video" and att.get("data_url")
                for att in (clean_attachments or [])
            )
            if has_image or has_video:
                # Use multimodal format (Chat Completions standard image_url)
                parts: list[dict[str, Any]] = (
                    [{"type": "text", "text": user_input}] if user_input.strip() else []
                )
                for att in clean_attachments or []:
                    data_url = att.get("data_url")
                    if data_url and att.get("type") == "image":
                        parts.append(
                            {
                                "type": "image_url",
                                "image_url": {"url": data_url},
                            }
                        )
                    elif (
                        data_url
                        and att.get("type") == "video"
                        and provider_name == "llama_cpp"
                    ):
                        parts.append(
                            {
                                "type": "input_video",
                                "input_video": {"url": data_url},
                            }
                        )
                user_msg = {"role": "user", "content": parts}
            else:
                # Fallback: text-only with attachment lines
                prompt_text = user_input
                if attachment_lines:
                    prompt_text = (
                        (prompt_text.rstrip() + "\n\n") if prompt_text.strip() else ""
                    ) + "\n".join(attachment_lines)
                user_msg = {"role": "user", "content": prompt_text}

            if turn_context is not None:
                user_msg["actor_id"] = turn_context.principal_id
                session_store = getattr(core, "session_store", None)
                bind_identity = getattr(session_store, "bind_identity_context", None)
                if callable(bind_identity):
                    bind_identity(
                        str(
                            getattr(core, "_session_store_active_id", "")
                            or turn_context.session_id
                        ),
                        principal_id=turn_context.principal_id,
                        room_id=turn_context.room_id,
                    )

            if clean_attachments:
                user_msg["attachments"] = clean_attachments
            core.log_message(user_msg)

            # History/instructions may already be initialized on websocket connect.
            _ensure_room_history_initialized(room)

            # UserPromptSubmit: stdin JSON + optional block (skip LLM turn)
            try:
                from ..hooks_engine import (
                    fire_user_prompt_submit,
                    inject_hook_context,
                    collect_hook_block_decision,
                )

                _ups_results = fire_user_prompt_submit(user_input)
                _ups_block = collect_hook_block_decision(_ups_results)
                if _ups_block is not None:
                    _reason = (_ups_block.get("reason") or "").strip()
                    if not _reason:
                        _reason = "Blocked by UserPromptSubmit hook."
                    room.add_message({"role": "assistant", "content": _reason})
                    return
                inject_hook_context(
                    room.history,
                    _ups_results,
                    event_name="UserPromptSubmit",
                    replace_event=True,
                )
            except Exception:
                pass

            # Strip attachments from user_msg before saving to history to avoid
            # accumulating large data_urls that cause API context overflow on subsequent turns.
            history_msg = dict(user_msg)
            history_msg.pop("attachments", None)
            room.history.append(history_msg)
            _save_input_history(user_input)
            room.image_session = build_image_session_message(room.history, depname)

            # Inject Generative UI instructions into the system prompt for Web mode
            generative_ui_prompt = _("""

    ## Generative UI (Artifacts) Instructions
    When the user asks for a UI, dashboard, interactive tool, or visualization:
    1. Write a complete, self-contained HTML page inside a single ```html code block.
    2. Use Tailwind CSS (via CDN: <script src="https://cdn.tailwindcss.com"></script>) for styling and Lucide Icons or FontAwesome for icons.
    3. Include interactive JavaScript (e.g., Chart.js for charts, or simple state management).
    4. Do not split the code into multiple blocks; keep it in one unified ```html block.
    """)
            if room.history and room.history[0].get("role") == "system":
                sys_content = room.history[0].get("content") or ""
                if "Generative UI (Artifacts) Instructions" not in sys_content:
                    room.history[0]["content"] = sys_content + generative_ui_prompt
            else:
                room.history.insert(
                    0, {"role": "system", "content": generative_ui_prompt.strip()}
                )

            # Track history length before LLM round to sync new messages to room after
            _before_hist_len = len(room.history)

            def _on_lifecycle(snapshot) -> None:
                payload = {
                    "type": "lifecycle",
                    "status": snapshot.status.value,
                    "updated_at": snapshot.updated_at,
                }
                _web_stream_send(payload)
                try:
                    room.set_status(
                        snapshot.status.value
                        not in {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT"},
                        snapshot.status.value,
                    )
                except Exception:
                    pass

            with lifecycle_execution(
                cancel_exceptions=(LLMWaitInterrupted,),
                on_transition=_on_lifecycle,
            ) as lifecycle:
                try:
                    room.agent_lifecycle = lifecycle
                except Exception:
                    pass
                _run_web_turn(
                    llm_util.run_llm_rounds,
                    provider_name,
                    client,
                    depname,
                    room.history,
                    core=core,
                    make_client_fn=providers.make_client,
                    append_result_to_outfile_fn=tools_util.append_result_to_outfile,
                    try_open_images_from_text_fn=tools_util.try_open_images_from_text,
                )
                _emit_round_outcome()
                if getattr(core, "_memory_projection_invalidated", False):
                    # Do not retain or display output produced from a revoked
                    # projection, and do not enter an auto-pilot continuation.
                    del room.history[_before_hist_len:]
                else:
                    # Auto-pilot loop
                    if core.auto_pilot_active:
                        _run_web_turn(
                            tools_util._run_auto_pilot_loop,
                            provider_name,
                            client,
                            depname,
                            room.history,
                            core=core,
                            make_client_fn=providers.make_client,
                            append_result_to_outfile_fn=tools_util.append_result_to_outfile,
                            try_open_images_from_text_fn=tools_util.try_open_images_from_text,
                        )
                    _emit_round_outcome()
            # Sync new assistant messages missed due to skip_log_when_web in _append_assistant_message.
            if not getattr(core, "_memory_projection_invalidated", False):
                for m in room.history[_before_hist_len:]:
                    if isinstance(m, dict) and m.get("role") == "assistant":
                        room.add_message(dict(m))

        except LLMWaitInterrupted:
            # Clean Stop during blocking LLM wait: no FATAL banner.
            try:
                with core.interrupt_lock:
                    core.interrupt_requested = False
            except Exception:
                pass
            try:
                room.add_message(
                    {
                        "role": "assistant",
                        "content": "[INTERRUPT] Stopped by user.",
                    }
                )
            except Exception:
                pass
        except BaseException as e:
            err = repr(e)
            tb = ""
            try:
                tb = traceback.format_exc()
            except Exception:
                tb = ""

            msg = _("[FATAL] Web worker error.\n%(err)s") % {"err": err}
            if (
                isinstance(e, (SystemExit, ValueError))
                and not (env_get("UAGENT_PROVIDER") or "").strip()
            ):
                msg = _(
                    "[FATAL] Environment variable UAGENT_PROVIDER is not set.\nPlease check environment variables when starting the web server."
                )
            if tb and tb != "NoneType: None\n":
                msg = msg + "\n\n" + tb

            room.add_message({"role": "assistant", "content": msg})

    finally:
        log_event("web.room.task.completed", room_id=getattr(room, "room_id", ""))
        # Best-effort cleanup; never let one failure skip lock release / IDLE.
        try:
            if callable(_orig_log_message):
                setattr(core, "log_message", _orig_log_message)
        except Exception:
            pass

        try:
            room.set_status(False, "IDLE")
        except Exception:
            pass
        try:
            _web_server_log(
                f"[web-worker] end room={str(room.room_id)[:8]} busy=0 label=IDLE"
            )
        except Exception:
            pass

        # Always clear core busy even if room broadcast failed.
        # Call original directly (not core.set_status=web_set_status) to avoid
        # re-broadcast races after active_room is cleared.
        try:
            if web_manager.original_set_status:
                web_manager.original_set_status(False, "")
            else:
                core.status_busy = False
                core.status_label = ""
        except Exception:
            try:
                core.status_busy = False
                core.status_label = ""
            except Exception:
                pass

        # Unblock any leftover human_ask waiter for this room.
        try:
            room.human_ask_pending = False
            room.human_ask_cancelled = True
            room.human_ask_sync_event.set()
        except Exception:
            pass

        # End any open assistant stream so the UI does not stay mid-stream.
        try:
            _stream_end()
        except Exception:
            pass

        try:
            with web_manager.active_room_lock:
                if web_manager.active_room is room:
                    web_manager.active_room = None
        except Exception:
            pass

        try:
            os.chdir(_orig_cwd)
        except Exception:
            pass

        if acquired_global:
            try:
                web_manager.global_worker_lock.release()
            except Exception:
                pass

        try:
            room.worker_lock.release()
        except Exception:
            pass

        try:
            set_thread_lang(None)
        except Exception:
            pass

        _thread_ctx.room = None
