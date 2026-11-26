"""CLI entry point implementation (split from cli.py)."""

from __future__ import annotations

import contextvars
import json
import os
import sys
import threading
import time
from typing import Any

from ..i18n import _
from ..env_utils import env_get
from .. import core
from .. import tools
from .. import util_tools as tools_util
from ..providers import util_providers as providers
from ..runtime.execution import lifecycle_execution
from ..runtime.turn_context_runtime import call_with_resolved_turn_context
from ..runtime.logging_setup import configure_event_logging, log_event
from ..runtime.local_messaging import (
    LocalMessageRuntime,
    accept_incoming_message,
    local_messaging_enabled,
    safe_message_preview,
    start_host_local_messaging,
    stop_host_local_messaging,
)
from ..runtime.round_outcome import project_round_outcome
from ..scheduler import start_background_scheduler, stop_background_scheduler
from ..tools.pybitchat_shared import (
    cancel_bitchat_turn,
    finish_bitchat_turn,
    set_active_bitchat_turn,
    set_llm_event_queue,
)
from ..util_tools import (
    build_multimodal_user_message,
    extract_image_paths,
    extract_video_paths,
    handle_command,
    provider_allows_chat_vision,
)
from ..cli_startup import run_cli_startup as _run_cli_startup
from ..runtime.sandbox_config import sandbox_startup_label
from ..runtime.startup_timing import checkpoint
from .history import _append_prompt_history_entry, _bootstrap_prompt_history
from .startup import (
    INITIAL_FILE_ARG,
    UAGENT_COMPLETE_REGEX,
    UAGENT_DECISION_PROVIDER,
    UAGENT_ENABLE_TOOLS,
    UAGENT_INJECT_MESSAGE,
    UAGENT_INJECT_MESSAGE_AUTO,
    UAGENT_NON_INTERACTIVE,
    UAGENT_ROLE_FILE_ARG,
    UAGENT_REALTIME,
    resolve_sandbox_mode,
    _cli_workdir,
    _env_workdir,
)
from .state import _CLI_SHUTDOWN
from .stdin_loop import stdin_loop
from .sub_agent_receipt_review import dispatch_cli_receipt_command_event
from .sub_agent_jobs import (
    CLIJobConfirmationBroker,
    cli_confirmation_supported,
    current_cli_job_owner,
    display_job_notice,
    handle_cli_job_command,
    is_cli_session_transition_command,
    prepare_cli_session_transition,
    refresh_cli_job_owner,
)
from ..runtime.sub_agent_host_policy import cli_scoped_handoff_policy_from_environment
from ..runtime.sub_agent_cli_receipt import deliver_cli_finished_job_notice
from ..runtime.sub_agent_receipt_context import queue_cli_sub_agent_receipt
from ..runtime.sub_agent_jobs import SubAgentJobManager


def _start_cli_local_messaging(core_obj: Any) -> tuple[Any, list[dict[str, Any]]]:
    return start_host_local_messaging(core_obj, core_obj.event_queue, entrypoint="cli")


def _stop_cli_local_messaging(core_obj: Any) -> bool:
    runtime = getattr(core_obj, "_local_messaging_runtime", None)
    if runtime is None:
        return False
    try:
        return stop_host_local_messaging(core_obj)
    except Exception as exc:
        log_event("local_messaging.stop_failed", error_type=type(exc).__name__)
    finally:
        if getattr(core_obj, "_local_messaging_runtime", None) is not None:
            try:
                delattr(core_obj, "_local_messaging_runtime")
            except Exception:
                pass
    return True


def _print_local_message_peers(peers: list[dict[str, Any]]) -> None:
    if not peers:
        print(_("[LOCAL] No other participating UAG peers are currently online."))
        return
    print(_("[LOCAL] Available UAG peers:"))
    for peer in peers:
        print(
            "  %(endpoint)s (%(entrypoint)s, pid=%(pid)s, started=%(started)s)"
            % {
                "endpoint": safe_message_preview(str(peer.get("endpoint_id") or "")),
                "entrypoint": peer.get("entrypoint", "cli"),
                "pid": peer.get("pid", "?"),
                "started": time.strftime(
                    "%Y-%m-%d %H:%M:%S",
                    time.localtime(float(peer.get("create_time") or 0)),
                ),
            }
        )


def _accept_cli_local_message(
    core_obj: Any,
    runtime: LocalMessageRuntime | None,
    message: dict[str, Any],
    run_cli_turn: Any,
    tool_runner: Any,
) -> dict[str, str] | None:
    """Confirm one queued inbox item and convert approval to a user turn."""

    def ask_user(prompt: str) -> str:
        core_obj.set_status(False, "")
        result = run_cli_turn(
            tool_runner,
            "human_ask",
            {"message": prompt, "is_password": False},
        )
        return str(json.loads(result).get("user_reply", ""))

    result = accept_incoming_message(runtime, message, ask_user)
    if result is None:
        print(_("[LOCAL] Incoming message was rejected or expired."))
    return result


def _exit_code_for_round_outcome(core: Any) -> int:
    outcome = project_round_outcome(getattr(core, "_last_round_outcome", {}) or {})
    status = str(outcome.get("status") or "")
    if status in {"cancelled", "interrupted"}:
        return 130
    if status == "failed":
        return 1
    return 0


def run_turn_on_worker(
    core: Any,
    fn: Any,
    /,
    *args: Any,
    channel: Any = None,
    **kwargs: Any,
) -> Any:
    """Run one CLI turn (LLM rounds / auto-pilot) on a worker thread.

    Stage 2a of the CLI single-writer refactor: the event-loop thread no
    longer runs rounds itself.  The worker inherits the caller's context
    (turn context, execution profile, and the other ContextVar state the
    round machinery uses) and binds the display channel's stream relay,
    so streamed answer/reasoning deltas are rendered by the display
    pump thread instead of being printed from the round's call threads.
    Before returning, the worker waits for the relayed stream to drain
    so the caller's own post-turn output cannot overtake its tail.

    Ctrl+C while waiting no longer raises inside the round: it sets the
    core interrupt flag and the auto-pilot exit request (the same
    signals F12 uses; provider waits poll the interrupt flag and
    receive loops honour it, and the auto-pilot loop checks its exit
    request before every follow-up) and the wait continues until the
    round has wound down; KeyboardInterrupt is then re-raised so the
    caller's existing interrupt handling runs unchanged.

    ``core`` and ``fn`` are positional-only: the wrapped turn functions
    take their own ``core=`` keyword, which must flow through
    ``**kwargs`` to them untouched.
    """
    from ..runtime.display_channel import (
        bind_stream_relay,
        default_channel,
        ensure_pump,
    )

    if channel is None:
        channel = default_channel()
    ensure_pump()
    # Keep the session's per-turn ContextVar states across worker
    # turns: the auto-unload counters and the loop-guard state are
    # lazily created inside run_llm_rounds, so a state bound only
    # inside a worker's copied context would be discarded with it and
    # restart empty every turn (the loop guard also has to survive
    # the handoff into the auto-pilot continuation, which explicitly
    # preserves it).  The core object is the CLI session's owner (the
    # Web side carries the same states on its room object), so bind
    # its stored states into this context before copying; the worker
    # stores the loop-guard state back when it finishes.
    try:
        from .. import uagent_llm as _llm_util
        from ..llm_loop_guards import _bind_loop_guard_state

        _llm_util._bind_auto_unload_state(core)
        _bind_loop_guard_state(core)
    except Exception:
        pass
    caller_context = contextvars.copy_context()
    outcome: dict[str, Any] = {}
    # Completion is tracked with this event, never with Thread.join /
    # is_alive: on CPython 3.11 an interrupted join can mark the thread
    # stopped while its target is still running, which would let the
    # caller resume while the old worker is still active.
    done = threading.Event()

    def _target() -> None:
        try:
            with bind_stream_relay(channel):
                outcome["result"] = fn(*args, **kwargs)
        except BaseException as exc:  # re-raised on the waiting thread
            outcome["error"] = exc
        finally:
            # Hand the loop-guard counters back to the session owner:
            # a fresh state begun inside this worker (begin_loop_guard_
            # turn) replaces the bound one in this context only, and
            # the auto-pilot continuation binds from the owner in a
            # separate worker with preserve_tool_loop_state=True.
            try:
                from ..llm_loop_guards import _store_loop_guard_state

                _store_loop_guard_state(core)
            except Exception:
                pass
            # A stuck pump must not hang the CLI forever; on timeout
            # the turn still ends and anything unrendered stays queued
            # and renders late.
            channel.wait_for_stream_drain(timeout=10.0)
            done.set()

    worker = threading.Thread(
        target=lambda: caller_context.run(_target),
        name="uagent-cli-round",
        daemon=True,
    )
    worker.start()
    interrupted = False
    while True:
        try:
            if done.wait(0.05):
                break
        except KeyboardInterrupt:
            interrupted = True
            try:
                with core.interrupt_lock:
                    core.interrupt_requested = True
            except Exception:
                pass
            # Mirror the F12 monitor: auto-pilot consumes and clears
            # interrupt_requested per round, so stopping it also needs
            # its exit request; the auto-pilot loop checks that flag
            # before every follow-up round.
            try:
                with core.auto_pilot_exit_lock:
                    core.auto_pilot_exit_requested = True
            except Exception:
                pass
            # Release a pending human_ask wait: the worker blocks on
            # its answer queue, which neither flag reaches (before the
            # worker move, KeyboardInterrupt hit that wait directly).
            # Delivering "cancel" ends the ask as a user cancellation,
            # the same result typing cancel at the prompt produces; the
            # per-call queue is discarded afterwards, so a late real
            # answer racing this is harmless.
            try:
                ask_queue = getattr(core, "human_ask_queue", None)
                if ask_queue is not None:
                    ask_queue.put("cancel")
            except Exception:
                pass
    if interrupted:
        raise KeyboardInterrupt
    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("result")


def _reset_startup_responses_continuation(
    core: Any, provider: str, depname: str
) -> None:
    """Drop stale Responses continuation state when the provider supports it."""
    from ..providers.responses_manager import get_responses_capabilities

    if not get_responses_capabilities(provider).previous_response_id:
        return
    state = getattr(core, "responses_state", None)
    if not isinstance(state, dict):
        return
    state["provider"] = provider
    state["model"] = depname
    state.pop("previous_response_id", None)
    state.pop("active_response_id", None)


def _set_status_for_command_result(core: Any, result: Any) -> bool:
    """Keep the CLI busy when a command immediately hands off to an LLM round.

    Clearing BUSY between an interactive command (such as ``:skills`` after
    human confirmation) and its follow-up round lets ``stdin_loop`` redraw a
    normal prompt. The prompt watcher then races the spinner while abandoning
    that prompt. Transition directly to the LLM status instead.
    """
    run_llm = bool(getattr(result, "run_llm", False))
    if run_llm:
        core.set_status(True, "LLM")
    else:
        core.set_status(False, "")
    return run_llm


def _nostr_remote_status_text(core: Any) -> str:
    from ..nostr_remote_runtime import format_nostr_remote_status

    return format_nostr_remote_status(core)


def _send_nostr_remote_reply(
    core: Any, request_event: dict[str, Any], text: str
) -> None:
    """Best-effort NIP-17 reply; never fail the local CLI turn on send errors."""
    runtime = getattr(core, "_nostr_remote_runtime", None)
    if runtime is None:
        return
    try:
        result = runtime.send_reply(request_event, text)
    except Exception as exc:
        log_event("nostr.remote_reply_failed", error_type=type(exc).__name__)
    else:
        if result.get("queued"):
            log_event(
                "nostr.remote_reply_queued",
                event_count=len(result.get("event_ids", [])),
            )
        else:
            log_event(
                "nostr.remote_reply_sent",
                delivery_count=len(result.get("event_ids", [])),
            )


def _finish_nostr_remote_request(
    core: Any, request_event: dict[str, Any], outcome: str
) -> None:
    """Persist the actual outcome after the foreground action has run."""
    runtime = getattr(core, "_nostr_remote_runtime", None)
    if runtime is None:
        return
    try:
        if not runtime.finish_event(request_event, outcome):
            log_event(
                "nostr.remote_request_finalize_failed",
                outcome=outcome,
                reason="inbox row was not dispatching",
            )
    except Exception as exc:
        log_event(
            "nostr.remote_request_finalize_failed",
            outcome=outcome,
            error_type=type(exc).__name__,
        )


def _interrupt_nostr_remote_request(core: Any, request_event: dict[str, Any]) -> None:
    """Terminally record an interrupted request and notify its sender."""
    _finish_nostr_remote_request(core, request_event, "failed")
    _send_nostr_remote_reply(
        core, request_event, "The remote request was interrupted on the CLI."
    )


def _chat_room_record(core: Any, chat_room: dict[str, Any]):
    """Return the pairing record for a chat-room descriptor, or None.

    The descriptor names the transport's pairing store and the
    device key (a Nostr pubkey, or a BitChat Noise key — BitChat
    descriptors always carry the Noise key, even for peers reached
    over Nostr, because the room assignment hangs off the record).
    """
    store_kind = chat_room.get("store")
    peer_key = chat_room.get("peer_key")
    if not isinstance(peer_key, str) or not peer_key:
        return None
    if store_kind == "nostr":
        runtime = getattr(core, "_nostr_remote_runtime", None)
        store = getattr(runtime, "pairing_store", None)
        return store.record_for(peer_key) if store is not None else None
    if store_kind == "bitchat":
        from ..bitchat_pairing import open_bitchat_pairing_store

        with open_bitchat_pairing_store() as store:
            return store.record_for(peer_key)
    return None


def _chat_room_store_room_session(
    core: Any,
    chat_room: dict[str, Any],
    peer_key: str,
    session_id: str,
    *,
    overwrite: bool,
) -> None:
    """Persist a room session id on the pairing record (best effort)."""
    store_kind = chat_room.get("store")
    try:
        if store_kind == "nostr":
            runtime = getattr(core, "_nostr_remote_runtime", None)
            store = getattr(runtime, "pairing_store", None)
            if store is None:
                return
            if overwrite:
                store.assign_room_session_id(peer_key, session_id)
            else:
                store.ensure_room_session_id(peer_key, session_id)
        elif store_kind == "bitchat":
            from ..bitchat_pairing import open_bitchat_pairing_store

            with open_bitchat_pairing_store() as store:
                if overwrite:
                    store.assign_room_session_id(peer_key, session_id)
                else:
                    store.ensure_room_session_id(peer_key, session_id)
    except Exception:
        pass


def _enter_chat_room_turn(
    core: Any,
    session_store: Any,
    messages: list[dict[str, Any]],
    chat_room: dict[str, Any],
) -> dict[str, Any] | None:
    """Bind this loop iteration to a room-bound device's own session.

    Uses the same session binding as the Web rooms
    (``bind_room_session_runtime``): the core's session-bound state
    is swapped for the room's for the duration of the turn, and the
    loop's message list is replaced with the room session's history
    (persisted in the session store). Returns a context the caller
    hands to :func:`_leave_chat_room_turn`, or None when the room
    cannot be entered (the caller then fails the request closed
    rather than running it in the operator's session).
    """
    from types import SimpleNamespace

    from ..runtime.agent_state import AgentStateManager
    from ..runtime.session_command_service import SessionCommandService
    from ..runtime.session_restore import apply_persisted_state
    from ..util_cmd_session import bind_room_session_runtime

    if session_store is None:
        return None
    peer_key = chat_room.get("peer_key")
    try:
        record = _chat_room_record(core, chat_room)
        if record is None or not record.active or record.binding != "room":
            return None
        room_session_id = record.room_session_id
        if room_session_id is not None:
            try:
                session_store.get_session(room_session_id)
            except Exception:
                room_session_id = None
        if room_session_id is None:
            project = None
            project_path = None
            try:
                main_row = session_store.get_session(str(core.session_id))
                project = main_row.get("project")
                project_path = main_row.get("project_path")
            except Exception:
                pass
            created = session_store.create_session(
                project=project, entry_point="cli-room", project_path=project_path
            )
            room_session_id = created.session_id
            _chat_room_store_room_session(
                core,
                chat_room,
                peer_key,
                room_session_id,
                overwrite=record.room_session_id is not None,
            )

        loaded = session_store.list_messages(room_session_id)
        sanitize = getattr(core, "sanitize_messages_for_tools", None)
        if callable(sanitize):
            loaded = sanitize(loaded)
        plan = SessionCommandService(session_store).build_restore_plan(
            room_session_id,
            loaded,
            system_prompt=getattr(core, "SYSTEM_PROMPT", None),
        )
        states = getattr(core, "_chat_room_states", None)
        if not isinstance(states, dict):
            states = {}
            core._chat_room_states = states
        room = states.get(room_session_id)
        if room is None:
            room = SimpleNamespace(
                session_id=room_session_id,
                responses_state={},
                tool_context={},
                agent_state_manager=AgentStateManager(),
                mcp_request_generation=0,
            )
            apply_persisted_state(room, plan)
            states[room_session_id] = room
        saved_messages = messages[:]
        messages[:] = plan.messages
        binding = bind_room_session_runtime(core, room)
        try:
            binding.__enter__()
        except Exception:
            messages[:] = saved_messages
            raise
        return {"binding": binding, "saved_messages": saved_messages}
    except Exception as exc:
        log_event(
            "chat_room.enter_failed",
            error_type=type(exc).__name__,
            store=chat_room.get("store"),
        )
        return None


def _leave_chat_room_turn(
    core: Any, messages: list[dict[str, Any]], room_ctx: dict[str, Any] | None
) -> None:
    """Undo :func:`_enter_chat_room_turn` (best effort, never raises)."""
    if room_ctx is None:
        return
    try:
        room_ctx["binding"].__exit__(None, None, None)
    except Exception:
        pass
    try:
        messages[:] = room_ctx["saved_messages"]
    except Exception:
        pass


def _new_assistant_text(messages: list[dict[str, Any]], start_index: int) -> str:
    """Return assistant text added since one CLI event began, if any."""
    try:
        return tools_util.extract_last_assistant_text(messages[start_index:]) or ""
    except Exception:
        return ""


def _resolve_realtime_sandbox_mode() -> str:
    """Load the selected workdir configuration and resolve its Sandbox mode."""
    from ..runtime.runtime_init import (
        apply_workdir,
        decide_workdir,
        reload_dotenv_custom,
    )

    decision = decide_workdir(
        cli_workdir=_cli_workdir,
        env_workdir=_env_workdir,
    )
    apply_workdir(decision)
    reload_dotenv_custom()
    from ..runtime.process_registry import activate_tracking

    activate_tracking("cli")
    return resolve_sandbox_mode()


def main() -> int:
    _CLI_SHUTDOWN.clear()
    from ..runtime.logging_setup import bind_event_context

    configure_event_logging()
    bind_event_context(session_id="cli", correlation_id="cli")
    log_event("cli.start")
    sys.stdout.reconfigure(encoding="utf-8")
    # Keep a copy of everything startup prints from here on: once
    # the full-screen console view starts it hides the pre-view
    # terminal, so the view's document is seeded with this output
    # (welcome, banner, [INFO], warnings) when it is created.
    try:
        from .console_view import install_startup_output_capture

        install_startup_output_capture()
    except Exception:
        pass
    sandbox_manager = None
    sandbox_scope = None
    sandbox_mode = "off"

    def _initialize_cli_sandbox(mode: str, project_path: str, session_id: str) -> bool:
        nonlocal sandbox_manager, sandbox_scope, sandbox_mode
        sandbox_mode = mode
        if mode == "off":
            core._sandbox_enabled = False
            core._sandbox_scope = None
            print(sandbox_startup_label(False), file=sys.stderr)
            return True

        from ..runtime.mxc_backend import (
            MxcSessionManager,
            describe_probe,
            install_session_manager,
            mxc_sdk_is_installed,
            startup_scope,
        )

        allow_install = False
        if mode == "mxc" and not mxc_sdk_is_installed():
            if UAGENT_NON_INTERACTIVE:
                print(
                    "[sandbox] MXC SDK is missing; non-interactive startup will not install dependencies. "
                    "Run an interactive `uag --sandbox mxc` after reviewing the dependency prompt.",
                    file=sys.stderr,
                )
                return False
            try:
                answer = input(
                    "Install the pinned MXC SDK (about 105 MB) in your user profile? [y/N] "
                )
            except (EOFError, KeyboardInterrupt):
                answer = ""
            if answer.strip().lower() not in {"y", "yes"}:
                print(
                    "[sandbox] dependency installation declined; startup stopped",
                    file=sys.stderr,
                )
                return False
            allow_install = True
        try:
            sandbox_manager, sandbox_report = MxcSessionManager.initialize(
                allow_install=allow_install
            )
            install_session_manager(sandbox_manager)
            sandbox_scope = startup_scope(
                entry_point="cli",
                project_path=project_path,
                session_id=session_id,
            )
            core._sandbox_enabled = True
            core._sandbox_scope = sandbox_scope
            print(
                f"[sandbox] enabled: {describe_probe(sandbox_report)}", file=sys.stderr
            )
            print(sandbox_startup_label(True), file=sys.stderr)
            return True
        except Exception as exc:
            print(
                f"[sandbox] startup refused: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            return False

    def _initialize_cli_sandbox_after_dotenv(
        project_path: str, session_id: str
    ) -> bool:
        try:
            mode = resolve_sandbox_mode()
        except ValueError as exc:
            print(f"[sandbox] invalid configuration: {exc}", file=sys.stderr)
            raise SystemExit(2) from exc
        if not _initialize_cli_sandbox(mode, project_path, session_id):
            raise SystemExit(2)
        return mode != "off"

    if UAGENT_REALTIME:
        try:
            realtime_sandbox_mode = _resolve_realtime_sandbox_mode()
        except ValueError as exc:
            print(f"[sandbox] invalid configuration: {exc}", file=sys.stderr)
            return 2
        except Exception as exc:
            print(
                f"[sandbox] failed to load realtime startup configuration: {exc}",
                file=sys.stderr,
            )
            return 2
        if realtime_sandbox_mode != "off":
            print(
                "[sandbox] realtime mode is unavailable while Sandbox is enabled; "
                "use realtime with --sandbox off or disable realtime.",
                file=sys.stderr,
            )
            return 2
        from ..realtime import run as run_realtime

        print(sandbox_startup_label(False), file=sys.stderr)
        raise SystemExit(run_realtime())

    from .. import uagent_llm as llm_util  # lazy

    startup = _run_cli_startup(
        core=core,
        cli_workdir=_cli_workdir,
        env_workdir=_env_workdir,
        initial_file_arg=INITIAL_FILE_ARG,
        non_interactive=UAGENT_NON_INTERACTIVE,
        role_file=UAGENT_ROLE_FILE_ARG,
        inject_message=UAGENT_INJECT_MESSAGE,
        inject_message_auto=UAGENT_INJECT_MESSAGE_AUTO,
        complete_regex=UAGENT_COMPLETE_REGEX,
        decision_provider=UAGENT_DECISION_PROVIDER,
        enable_tools=UAGENT_ENABLE_TOOLS,
        sandbox_initializer=_initialize_cli_sandbox_after_dotenv,
    )
    checkpoint("cli_startup_returned")

    provider = startup.provider
    client = startup.client
    depname = startup.depname
    messages = startup.messages
    session_store = startup.session_store
    resume_id = getattr(core, "_portable_resume_id", None)
    if resume_id:
        del core._portable_resume_id
        from ..session_cli import restore_imported_session

        restore_imported_session(core, session_store, messages, resume_id)
    process_exit_code = 0

    def _run_rounds_turn(*args, **kwargs):
        # Stage 2a: rounds run on the round worker thread (see
        # run_turn_on_worker); the turn-context/profile wrapping that
        # _run_cli_turn applies still runs on this thread first, and the
        # worker inherits it through the copied context.
        return run_turn_on_worker(core, llm_util.run_llm_rounds, *args, **kwargs)

    def _run_auto_pilot_turn(*args, **kwargs):
        return run_turn_on_worker(
            core, tools_util._run_auto_pilot_loop, *args, **kwargs
        )

    def _run_cli_turn(fn, *args, **kwargs):
        if sandbox_mode != "off":
            from ..runtime.execution_broker import SecurityProfile, execution_profile
            from ..runtime.mxc_backend import (
                current_session_manager,
                startup_scope as _startup_scope,
            )

            active_scope = _startup_scope(
                entry_point="cli",
                project_path=os.getcwd(),
                session_id=str(
                    getattr(core, "session_id", "")
                    or getattr(startup, "session_id", "")
                    or ""
                ),
            )
            sandbox_manager = current_session_manager()
            if sandbox_manager is not None:
                sandbox_manager.activate_scope(active_scope)
            with execution_profile(
                SecurityProfile.LOCAL_TRUSTED,
                sandbox_enabled=True,
                scope=active_scope,
            ):
                return call_with_resolved_turn_context(
                    fn,
                    *args,
                    entry_point="cli",
                    project_path=os.getcwd(),
                    session_id=str(getattr(core, "session_id", "") or ""),
                    **kwargs,
                )
        return call_with_resolved_turn_context(
            fn,
            *args,
            entry_point="cli",
            project_path=os.getcwd(),
            session_id=str(getattr(core, "session_id", "") or ""),
            **kwargs,
        )

    def _noninteractive_exit_code() -> int:
        return _exit_code_for_round_outcome(core)

    _bootstrap_prompt_history(messages)

    def _startup_timing_mark(name: str) -> None:
        if not getattr(startup, "startup_timing_enabled", False):
            return
        started = getattr(startup, "startup_timing_started", None)
        if not isinstance(started, (int, float)):
            return
        elapsed = time.perf_counter() - started
        print(
            f"[startup-timing] {name}={elapsed:.3f}s",
            file=sys.stderr,
            flush=True,
        )

    if startup.should_exit:
        return _noninteractive_exit_code()

    fallback_session_id = str(getattr(startup, "session_id", "") or "")
    job_owner = current_cli_job_owner(core, fallback_session_id)

    def _enqueue_sub_agent_job_notice(notice: dict[str, Any]) -> None:
        # Keep background output out of the Main stream.  The foreground CLI
        # loop owns the eventual display and prompt redraw.
        core.event_queue.put({"kind": "sub_agent_job_notice", "notice": notice})

    confirmation_broker = CLIJobConfirmationBroker(
        core, enabled=cli_confirmation_supported(enabled=not UAGENT_NON_INTERACTIVE)
    )
    # Structured handoff is explicitly opt-in. Goal/source selections come
    # from the host environment, never model-supplied tool arguments.
    handoff_policy = cli_scoped_handoff_policy_from_environment(
        session_store, os.environ
    )
    structured_handoff_enabled = handoff_policy is not None
    core._sub_agent_receipt_context_enabled = structured_handoff_enabled
    job_manager = SubAgentJobManager(
        notice_callback=_enqueue_sub_agent_job_notice,
        confirmation_handler=confirmation_broker.ask,
        handoff_dispatch_policy=handoff_policy,
    )
    core._sub_agent_job_manager = job_manager
    core._sub_agent_job_owner = job_owner
    checkpoint("job_manager_ready")

    # Computer Use backends are created lazily by the action handler.
    # Merely enabling the capability must not open a browser or desktop session.

    # Do not automatically resume a saved Responses chain at startup.
    # Explicit :load selects a log and may restore its validated latest ID.
    _reset_startup_responses_continuation(core, provider, depname)

    start_background_scheduler(core.event_queue)
    # Allow pybitchat chat_mode="llm" to inject peer messages into the LLM.
    set_llm_event_queue(core.event_queue)
    if not UAGENT_NON_INTERACTIVE and local_messaging_enabled():
        try:
            _local_runtime, _local_peers = _start_cli_local_messaging(core)
            _print_local_message_peers(_local_peers)
        except Exception as exc:
            log_event("local_messaging.start_failed", error_type=type(exc).__name__)
            print(
                _("[LOCAL] Local messaging could not start: %(error)s")
                % {"error": f"{type(exc).__name__}: {exc}"}
            )
    core.start_interrupt_monitor()
    checkpoint("background_services_started")

    # Optional synchronous plugin preloading is disabled by default; tool
    # modules otherwise load when the registry is first accessed.
    if not UAGENT_NON_INTERACTIVE and sandbox_mode == "off":
        try:
            tools.start_tools_warmup()
        except Exception:
            pass
    checkpoint("tool_warmup_requested")

    def _run_cli_hook(fn, *args):
        if sandbox_mode == "off":
            return fn(*args)
        from ..runtime.execution_broker import SecurityProfile, execution_profile

        with execution_profile(
            SecurityProfile.LOCAL_TRUSTED,
            sandbox_enabled=True,
            scope=sandbox_scope,
        ):
            return fn(*args)

    # Fire SessionStart and Setup hooks (inject stdout context into messages)
    try:
        from ..hooks_engine import (
            fire_session_start,
            fire_event,
            load_hooks_registry,
            get_default_registry_path,
            inject_hook_context,
            take_pending_session_hook_texts,
        )

        _ss_results = _run_cli_hook(fire_session_start)
        inject_hook_context(
            messages, _ss_results, event_name="SessionStart", replace_event=False
        )
        # Avoid double-inject if a later path pulls the SessionStart stash.
        take_pending_session_hook_texts()
        _hooks = load_hooks_registry(get_default_registry_path())
        if _hooks:
            _setup_results = _run_cli_hook(fire_event, "Setup", _hooks)
            inject_hook_context(
                messages, _setup_results, event_name="Setup", replace_event=False
            )
    except Exception:
        pass
    checkpoint("session_hooks_complete")

    t = threading.Thread(
        target=stdin_loop,
        kwargs={"hook_runner": _run_cli_hook},
        daemon=True,
    )
    t.start()
    _startup_timing_mark("stdin_loop_started")
    checkpoint("stdin_thread_started")

    running = True
    first_event_received = False
    first_llm_started = False
    first_llm_completed = False
    try:
        # Scheduler execution records are updated when scheduled events enter
        # the interactive worker loop.  The store is durable and independent
        # from the event queue, so a restart does not erase the run history.
        from ..scheduler import (
            SchedulerRunStore,
            SchedulerWorker,
            run_scheduled_callback_with_tools,
        )

        scheduled_run_store = SchedulerRunStore()
        checkpoint("scheduler_store_ready")

        def _run_llm_event(event, fn, *args, **kwargs):
            run_id = str(event.get("run_id") or "").strip()
            if not run_id:
                return fn(*args, **kwargs)
            run = scheduled_run_store.get(run_id)
            metadata = dict((run.metadata if run else {}) or {})

            def _execute_scheduled(_payload):
                return run_scheduled_callback_with_tools(
                    fn,
                    *args,
                    tool_names=metadata.get("required_tools") or [],
                    reason=f"scheduled run:{run_id}",
                    sandbox_enabled=sandbox_mode != "off",
                    **kwargs,
                )

            return SchedulerWorker(scheduled_run_store).execute(
                run_id,
                _execute_scheduled,
                timeout_sec=float(metadata.get("timeout_sec") or 0),
                retry_limit=int(metadata.get("retry_limit") or 0),
                retry_backoff_sec=int(metadata.get("retry_backoff_sec") or 0),
            )

        def _run_direct_event(event):
            run_id = str(event.get("run_id") or "").strip()
            if not run_id:
                raise RuntimeError("direct scheduled event has no run_id")
            run = scheduled_run_store.get(run_id)
            metadata = dict((run.metadata if run else {}) or {})
            target_tool = str(metadata.get("target_tool") or "").strip()
            target_args = metadata.get("target_args") or {}
            required = list(metadata.get("required_tools") or [])
            if target_tool and target_tool not in required:
                required.append(target_tool)
            from ..scheduler import execute_direct_tool

            def _execute_scheduled(_payload):
                return run_scheduled_callback_with_tools(
                    _run_cli_turn,
                    execute_direct_tool,
                    target_tool,
                    target_args,
                    tool_names=required,
                    reason=f"scheduled direct run:{run_id}",
                    sandbox_enabled=sandbox_mode != "off",
                )

            result = SchedulerWorker(scheduled_run_store).execute(
                run_id,
                _execute_scheduled,
                timeout_sec=float(metadata.get("timeout_sec") or 0),
                retry_limit=int(metadata.get("retry_limit") or 0),
                retry_backoff_sec=int(metadata.get("retry_backoff_sec") or 0),
            )
            print(f"[SCHEDULE] direct tool {target_tool} completed: {result}")
            return result

        if startup.inject_message_auto:
            core.event_queue.put(
                {"kind": "command", "text": f":auto {startup.inject_message_auto}"}
            )

        checkpoint("event_loop_ready")
        active_room_ctx: dict[str, Any] | None = None
        while running:
            try:
                ev = core.event_queue.get()
            except KeyboardInterrupt:
                # Idle wait interrupted (ollama-like: no traceback, clean exit).
                print()
                print("[INFO] " + _("Received Ctrl+C. Starting shutdown..."))
                break
            if active_room_ctx is not None:
                # The previous iteration ran a room-bound device's
                # turn; restore the operator's session before anything
                # else in this iteration.
                _leave_chat_room_turn(core, messages, active_room_ctx)
                active_room_ctx = None
            if not first_event_received:
                first_event_received = True
                _startup_timing_mark("first_event_received")
            remote_request_event = None
            remote_execution_outcome = "completed"
            remote_message_start = len(messages)
            kind = ev.get("kind")

            if kind == "local_agent_started":
                peer = ev.get("peer") if isinstance(ev.get("peer"), dict) else {}
                endpoint_id = safe_message_preview(str(peer.get("endpoint_id") or ""))
                runtime = getattr(core, "_local_messaging_runtime", None)
                if runtime is not None and runtime.is_peer_active(endpoint_id):
                    print(
                        _(
                            "[LOCAL] Another UAG peer is online: %(endpoint)s (pid=%(pid)s)"
                        )
                        % {
                            "endpoint": endpoint_id,
                            "pid": peer.get("pid", "?"),
                        }
                    )
                continue

            if kind == "local_message_received":
                runtime = getattr(core, "_local_messaging_runtime", None)
                message = (
                    ev.get("message") if isinstance(ev.get("message"), dict) else {}
                )
                accepted_event = _accept_cli_local_message(
                    core,
                    runtime,
                    message,
                    _run_cli_turn,
                    tools.run_tool,
                )
                if accepted_event is None:
                    continue
                kind = accepted_event["kind"]
                ev = accepted_event

            if kind == "nostr_remote_request":
                # Revalidate durable inbox ownership, message identity, current
                # pairing, freshness, and session on the foreground CLI thread.
                from ..nostr_remote_dispatch import RemoteCLIRequestError

                remote_runtime = getattr(core, "_nostr_remote_runtime", None)
                try:
                    if remote_runtime is not None:
                        remote_action = remote_runtime.dispatch_event(
                            ev,
                            current_session_id=str(
                                getattr(core, "session_id", "") or ""
                            ),
                            # Only the foreground thread may ask the
                            # operator to pair an unknown sender; the
                            # status side worker dispatches without it.
                            allow_pairing_prompt=True,
                        )
                    else:
                        from ..nostr_remote_dispatch import (
                            authorize_nostr_remote_request,
                        )

                        remote_action = authorize_nostr_remote_request(
                            ev,
                            current_session_id=str(
                                getattr(core, "session_id", "") or ""
                            ),
                            authorize_sender=getattr(
                                core, "_nostr_remote_authorize_sender", None
                            ),
                        )
                except RemoteCLIRequestError as exc:
                    # Do not echo untrusted DM contents or expose detailed
                    # authorization state to the remote sender.
                    log_event("nostr.remote_request_rejected", reason=str(exc)[:160])
                    continue
                except Exception as exc:
                    log_event(
                        "nostr.remote_request_failed", error_type=type(exc).__name__
                    )
                    continue
                remote_request_event = ev
                kind = remote_action.kind
                ev = {"kind": kind, "text": remote_action.text}
                if remote_action.binding == "room" and kind in ("user", "command"):
                    ev["chat_room"] = {
                        "store": "nostr",
                        "peer_key": remote_action.sender_pubkey,
                    }

            if kind == "display" and remote_request_event is not None:
                # Chat mode "on": show the paired device's message and
                # stop there — nothing is executed and no reply is sent.
                _display_sender = remote_request_event.get("sender_pubkey") or ""
                _display_record = _chat_room_record(
                    core,
                    {"store": "nostr", "peer_key": _display_sender},
                )
                _display_label = (
                    _display_record.label
                    if _display_record is not None and _display_record.label
                    else _display_sender[:16]
                )
                print(
                    _("[nostr] %(sender)s: %(text)s")
                    % {"sender": _display_label, "text": ev.get("text", "")}
                )
                _finish_nostr_remote_request(core, remote_request_event, "completed")
                continue

            if kind in ("user", "command") and isinstance(ev, dict):
                chat_room = ev.get("chat_room")
                if isinstance(chat_room, dict):
                    active_room_ctx = _enter_chat_room_turn(
                        core, session_store, messages, chat_room
                    )
                    if active_room_ctx is None:
                        if remote_request_event is not None:
                            _finish_nostr_remote_request(
                                core, remote_request_event, "failed"
                            )
                            _send_nostr_remote_reply(
                                core,
                                remote_request_event,
                                "The device's room session is unavailable.",
                            )
                        continue
                    remote_message_start = len(messages)

            # Progress notes (tool / reasoning) for a bitchat peer are
            # scoped to the event whose turn is about to run.
            set_active_bitchat_turn(
                ev.get("reply_route") if ev.get("src") == "bitchat" else None
            )

            if kind == "status" and remote_request_event is not None:
                _finish_nostr_remote_request(core, remote_request_event, "completed")
                _send_nostr_remote_reply(
                    core, remote_request_event, _nostr_remote_status_text(core)
                )
                continue

            if kind == "command":
                line = ev.get("text", "")
                if dispatch_cli_receipt_command_event(
                    line, core=core, store=session_store, owner=job_owner
                ):
                    if remote_request_event is not None:
                        _finish_nostr_remote_request(
                            core, remote_request_event, "completed"
                        )
                    if remote_request_event is not None:
                        _send_nostr_remote_reply(
                            core, remote_request_event, "Command processed by CLI."
                        )
                    continue
                if handle_cli_job_command(line, manager=job_manager, owner=job_owner):
                    _set_status_for_command_result(core, None)
                    if remote_request_event is not None:
                        _finish_nostr_remote_request(
                            core, remote_request_event, "completed"
                        )
                    if remote_request_event is not None:
                        _send_nostr_remote_reply(
                            core, remote_request_event, "Command accepted by CLI."
                        )
                    continue
                session_transition = is_cli_session_transition_command(line)
                old_owner = job_owner
                if session_transition:
                    try:
                        switch_timeout = max(
                            0.0,
                            float(
                                os.environ.get(
                                    "UAGENT_SUB_AGENT_JOB_SESSION_SWITCH_TIMEOUT", "5"
                                )
                            ),
                        )
                    except (TypeError, ValueError):
                        switch_timeout = 5.0
                    prepared, lingering = prepare_cli_session_transition(
                        job_manager, old_owner, timeout=switch_timeout
                    )
                    if not prepared:
                        print(
                            "Session switch cancelled; Sub-Agent workers are still running: "
                            + ", ".join(lingering)
                        )
                        # The command-pending status was set by stdin_loop.
                        # A rejected session switch does not reach the common
                        # command-result status transition below.
                        _set_status_for_command_result(core, None)
                        if remote_request_event is not None:
                            _finish_nostr_remote_request(
                                core, remote_request_event, "rejected"
                            )
                            _send_nostr_remote_reply(
                                core,
                                remote_request_event,
                                "Session switch was cancelled.",
                            )
                        continue
                try:
                    result = handle_command(line, messages, client, depname, core=core)
                except Exception:
                    if remote_request_event is not None:
                        _finish_nostr_remote_request(
                            core, remote_request_event, "failed"
                        )
                    raise
                finally:
                    if session_transition:
                        job_owner = refresh_cli_job_owner(
                            job_manager, core, fallback_session_id
                        )
                if not result:
                    if remote_request_event is not None:
                        _finish_nostr_remote_request(
                            core, remote_request_event, "completed"
                        )
                        _send_nostr_remote_reply(
                            core, remote_request_event, "CLI is exiting."
                        )
                    running = False
                    break
                command_followed_by_llm = _set_status_for_command_result(core, result)
                if command_followed_by_llm:
                    prompt = getattr(result, "prompt", None) or "Run the loaded skill."
                    user_msg = {"role": "user", "content": prompt}
                    messages.append(user_msg)
                    _append_prompt_history_entry(prompt)
                    core.log_message(user_msg)
                    if not first_llm_started:
                        first_llm_started = True
                        _startup_timing_mark("first_llm_started")
                    with lifecycle_execution() as lifecycle:
                        try:
                            _run_llm_event(
                                ev,
                                _run_cli_turn,
                                _run_rounds_turn,
                                provider,
                                client,
                                depname,
                                messages,
                                core=core,
                                make_client_fn=providers.make_client,
                                append_result_to_outfile_fn=tools_util.append_result_to_outfile,
                                try_open_images_from_text_fn=tools_util.try_open_images_from_text,
                            )
                        except KeyboardInterrupt:
                            process_exit_code = max(process_exit_code, 130)
                            # Ctrl+C during generation: stop and return to the
                            # prompt like ollama (no traceback). The `with`
                            # block did not see the exception (caught here), so
                            # mark cancel explicitly. Never fail() here: a user
                            # stop is not a failure.
                            try:
                                lifecycle.cancel()
                            except Exception:
                                pass
                            try:
                                core.set_status(False, "")
                            except Exception:
                                pass
                            try:
                                core.input_prompt_active = False
                                core.prompt_needs_redraw = True
                            except Exception:
                                pass
                            try:
                                with core.interrupt_lock:
                                    core.interrupt_requested = False
                            except Exception:
                                pass
                            print()
                            print("[INTERRUPT] " + _("Stopped by user."))
                            print(_("Returning to prompt..."))
                            if remote_request_event is not None:
                                _interrupt_nostr_remote_request(
                                    core, remote_request_event
                                )
                            continue
                        except Exception as exc:
                            lifecycle.fail()
                            if remote_request_event is not None:
                                remote_execution_outcome = "failed"
                            print(_("LLM round interrupted: %(err)s") % {"err": exc})

                    if first_llm_started and not first_llm_completed:
                        first_llm_completed = True
                        _startup_timing_mark("first_llm_completed")

                    # Auto-pilot loop: if auto mode is active, continue rounds
                    if core.auto_pilot_active:
                        try:
                            with lifecycle_execution():
                                _run_cli_turn(
                                    _run_auto_pilot_turn,
                                    provider,
                                    client,
                                    depname,
                                    messages,
                                    core=core,
                                    make_client_fn=providers.make_client,
                                    append_result_to_outfile_fn=tools_util.append_result_to_outfile,
                                    try_open_images_from_text_fn=tools_util.try_open_images_from_text,
                                )
                        except KeyboardInterrupt:
                            process_exit_code = max(process_exit_code, 130)
                            # Auto-pilot aborted by the user: no traceback.
                            try:
                                core.set_status(False, "")
                            except Exception:
                                pass
                            print()
                            print("[INTERRUPT] " + _("Auto-pilot stopped by user."))
                        except Exception as exc:
                            print(
                                "[AUTO] "
                                + _("Auto-pilot interrupted: %(err)s") % {"err": exc}
                            )
                        core.set_status(False, "")
                    if UAGENT_NON_INTERACTIVE or UAGENT_INJECT_MESSAGE_AUTO:
                        process_exit_code = max(
                            process_exit_code, _noninteractive_exit_code()
                        )
                    if UAGENT_INJECT_MESSAGE_AUTO:
                        if remote_request_event is not None:
                            _finish_nostr_remote_request(
                                core, remote_request_event, remote_execution_outcome
                            )
                        running = False
                        break
                if remote_request_event is not None:
                    _finish_nostr_remote_request(
                        core, remote_request_event, remote_execution_outcome
                    )
                    reply = (
                        _new_assistant_text(messages, remote_message_start)
                        if command_followed_by_llm
                        else ""
                    )
                    _send_nostr_remote_reply(
                        core,
                        remote_request_event,
                        reply or "Command processed by CLI.",
                    )

                continue

            if kind == "sub_agent_job_notice":
                notice = ev.get("notice") or {}
                display_job_notice(core, notice)
                if structured_handoff_enabled:
                    try:
                        receipt = deliver_cli_finished_job_notice(
                            manager=job_manager,
                            owner=job_owner,
                            notice=notice,
                            store=session_store,
                        )
                    except Exception as exc:
                        # A rejected delivery never promotes model evidence.
                        # Record a diagnostic without exposing child content.
                        log_event(
                            "sub_agent.handoff_receipt_failed",
                            job_id=notice.get("job_id"),
                            error_type=type(exc).__name__,
                        )
                    else:
                        if receipt is not None:
                            if not receipt["already_received"]:
                                queue_cli_sub_agent_receipt(core, receipt)
                            log_event(
                                "sub_agent.handoff_receipt_recorded",
                                job_id=notice.get("job_id"),
                                already_received=receipt["already_received"],
                            )
                continue

            if kind == "schedule_notice":
                notice = (ev.get("text", "") or "").strip()
                if notice:
                    print("[INFO] " + notice)
                continue

            if kind == "scheduled_direct":
                try:
                    _run_direct_event(ev)
                except KeyboardInterrupt:
                    print()
                    print("[INFO] " + _("Scheduled task interrupted; skipped."))
                except Exception as exc:
                    print(_("Scheduled direct tool failed: %(err)s") % {"err": exc})
                continue

            if kind in ("user", "timer"):
                text = ev.get("text", "")
                if not text:
                    continue

                # Fire UserPromptSubmit hook (stdin JSON + context / block)
                try:
                    from ..hooks_engine import (
                        fire_user_prompt_submit,
                        inject_hook_context,
                        collect_hook_block_decision,
                    )

                    _ups_results = _run_cli_hook(fire_user_prompt_submit, text)
                    _ups_block = collect_hook_block_decision(_ups_results)
                    if _ups_block is not None:
                        _reason = (_ups_block.get("reason") or "").strip()
                        if not _reason:
                            _reason = "Blocked by UserPromptSubmit hook."
                        print(_reason)
                        core.set_status(False, "")
                        if remote_request_event is not None:
                            _finish_nostr_remote_request(
                                core, remote_request_event, "rejected"
                            )
                            _send_nostr_remote_reply(
                                core,
                                remote_request_event,
                                "Request blocked by local policy.",
                            )
                        continue
                    inject_hook_context(
                        messages,
                        _ups_results,
                        event_name="UserPromptSubmit",
                        replace_event=True,
                    )
                except Exception:
                    pass

                # If the active provider can accept images on the main chat path and the
                # user message contains local image paths, ask for permission before
                # embedding images as data URLs / attachments.
                use_responses_api = env_get("UAGENT_RESPONSES", "").lower() in (
                    "1",
                    "true",
                )
                prov = (env_get("UAGENT_PROVIDER") or "").lower()
                allow_multimodal = provider_allows_chat_vision(
                    prov,
                    use_responses_api=use_responses_api,
                    model_id=depname,
                )

                user_msg: dict[str, Any]

                if allow_multimodal:
                    paths = extract_image_paths(text)
                    video_paths = (
                        extract_video_paths(text) if prov == "llama_cpp" else []
                    )
                    if paths or video_paths:
                        # Build a candidate list with absolute paths and sizes (best-effort).
                        infos: list[str] = []
                        ok_paths: list[str] = []
                        ok_video_paths: list[str] = []
                        for p in paths + video_paths:
                            try:
                                expanded = os.path.expandvars(os.path.expanduser(p))
                                abspath = os.path.abspath(expanded)
                                if not os.path.isfile(abspath):
                                    infos.append(f"- {p} (not found)")
                                    continue
                                size = os.path.getsize(abspath)
                                infos.append(f"- {abspath} ({size} bytes)")
                                if p in video_paths:
                                    if size <= 50_000_000:
                                        ok_video_paths.append(abspath)
                                else:
                                    ok_paths.append(abspath)
                            except Exception as e:
                                infos.append(f"- {p} (error: {type(e).__name__}: {e})")

                        if ok_paths or ok_video_paths:
                            msg = (
                                _(
                                    "Image file paths were found in your input.\n"
                                    "Do you want to send these images to the LLM (external API) for analysis?\n\n"
                                )
                                + "\n".join(infos)
                                + "\n\n"
                                + _(
                                    "Reply with y to send, or n (or c/cancel) to skip sending."
                                )
                            )
                            try:
                                core.set_status(False, "")
                                res_json = _run_cli_turn(
                                    tools.run_tool,
                                    "human_ask",
                                    {"message": msg, "is_password": False},
                                )
                                try:
                                    res = json.loads(res_json)
                                    ans = (res.get("user_reply") or "").strip().lower()
                                except Exception:
                                    ans = (res_json or "").strip().lower()
                            except (Exception, SystemExit) as e:
                                ans = "n"
                                print(
                                    "[WARN] "
                                    + _(
                                        "Image send confirmation failed; will not send images: %(etype)s: %(err)s"
                                    )
                                    % {"etype": type(e).__name__, "err": e}
                                )

                            if ans in ("y", "yes"):
                                user_msg = build_multimodal_user_message(
                                    text,
                                    ok_paths,
                                    video_paths=ok_video_paths,
                                    provider=prov,
                                    use_responses_api=use_responses_api,
                                )
                            else:
                                user_msg = {"role": "user", "content": text}
                        else:
                            user_msg = {"role": "user", "content": text}
                    else:
                        user_msg = {"role": "user", "content": text}
                else:
                    user_msg = {"role": "user", "content": text}

                messages.append(user_msg)
                core.log_message(user_msg)

                with lifecycle_execution() as lifecycle:
                    try:
                        _run_llm_event(
                            ev,
                            _run_cli_turn,
                            _run_rounds_turn,
                            provider,
                            client,
                            depname,
                            messages,
                            core=core,
                            make_client_fn=providers.make_client,
                            append_result_to_outfile_fn=tools_util.append_result_to_outfile,
                            try_open_images_from_text_fn=tools_util.try_open_images_from_text,
                        )
                    except KeyboardInterrupt:
                        # Ctrl+C during a user/timer LLM round: clean cancel.
                        try:
                            lifecycle.cancel()
                        except Exception:
                            pass
                        try:
                            core.set_status(False, "")
                        except Exception:
                            pass
                        try:
                            core.input_prompt_active = False
                            core.prompt_needs_redraw = True
                        except Exception:
                            pass
                        try:
                            with core.interrupt_lock:
                                core.interrupt_requested = False
                        except Exception:
                            pass
                        print()
                        print("[INTERRUPT] " + _("Stopped by user."))
                        print(_("Returning to prompt..."))
                        if remote_request_event is not None:
                            _interrupt_nostr_remote_request(core, remote_request_event)
                        if ev.get("src") == "bitchat":
                            cancel_bitchat_turn()
                        continue
                    except Exception as exc:
                        lifecycle.fail()
                        if remote_request_event is not None:
                            remote_execution_outcome = "failed"
                        source = "[bitchat] " if ev.get("src") == "bitchat" else ""
                        print(
                            source + _("LLM round interrupted: %(err)s") % {"err": exc}
                        )
                # bitchat 経由の DM: LLM 応答を送信者の DM に自動返信
                if ev.get("src") == "bitchat":
                    reply = tools_util.extract_last_assistant_text(messages)
                    finish_bitchat_turn(reply or "", ev.get("reply_route"))
                    # 注入ラウンド中に手動プロンプトの行が閉じられているため、
                    # アイドルに戻ったら stdin_loop に再描画を要求する。
                    try:
                        core.prompt_needs_redraw = True
                    except Exception:
                        pass
                if remote_request_event is not None:
                    _finish_nostr_remote_request(
                        core, remote_request_event, remote_execution_outcome
                    )
                    reply = _new_assistant_text(messages, remote_message_start)
                    _send_nostr_remote_reply(
                        core,
                        remote_request_event,
                        reply or "No assistant response was produced.",
                    )

                continue

            print(
                "[WARN] "
                + _("Unknown event kind=%(kind)r: %(ev)r") % {"kind": kind, "ev": ev}
            )
    except KeyboardInterrupt:
        # Final safety net for strays outside the per-site handlers.
        # Cleanup in `finally` still runs.
        print()
        print("[INFO] " + _("Received Ctrl+C. Starting shutdown..."))
    finally:
        _CLI_SHUTDOWN.set()

        try:
            _stop_cli_local_messaging(core)
        except Exception as exc:
            log_event("local_messaging.shutdown_failed", error_type=type(exc).__name__)

        if getattr(core, "_nostr_remote_runtime", None) is not None:
            try:
                from ..nostr_remote_runtime import stop_nostr_remote_runtime

                remote_stop = stop_nostr_remote_runtime(core)
                if not remote_stop["stopped"]:
                    log_event("nostr.remote_listener_shutdown_timeout")
            except Exception:
                pass
        # stdin_loop is intentionally a daemon while the CLI is running, but
        # it should not still be inside prompt_toolkit when Python starts
        # interpreter finalization. The prompt watcher above exits the
        # blocking prompt; the manual input loops observe the same event.
        try:
            t.join(timeout=1.0)
        except Exception:
            pass
        try:
            job_manager.shutdown()
        except Exception:
            pass
        try:
            confirmation_broker.shutdown()
        except Exception:
            pass
        for attr in ("_sub_agent_job_manager", "_sub_agent_job_owner"):
            try:
                delattr(core, attr)
            except Exception:
                pass
        if active_room_ctx is not None:
            _leave_chat_room_turn(core, messages, active_room_ctx)
            active_room_ctx = None
        try:
            stop_background_scheduler()
        except Exception:
            pass
        try:
            core.stop_interrupt_monitor()
        except Exception:
            pass
        # Spinner must never survive shutdown (no-op when disabled).
        from ..runtime.spinner import stop_quietly as _spinner_stop_quietly

        _spinner_stop_quietly()
        # Fire Stop and SessionEnd hooks
        try:
            from ..hooks_engine import (
                fire_stop,
                fire_event,
                load_hooks_registry,
                get_default_registry_path,
            )

            _run_cli_hook(fire_stop)
            _hooks = load_hooks_registry(get_default_registry_path())
            if _hooks:
                _run_cli_hook(fire_event, "SessionEnd", _hooks)
        except Exception:
            pass
        # Keep the active SQLite session searchable after the CLI exits.  Use
        # the existing command handler with an explicit session id so shutdown
        # never summarizes every stored session (or a different session loaded
        # during this run). Shutdown summarization runs by default; set
        # UAGENT_SUMMARY_ON_EXIT=0 to opt out because it invokes another LLM
        # operation while the process is exiting.
        if session_store is not None and client is not None and depname:
            active_session_id = getattr(core, "session_id", None)
            summary_on_exit = (
                os.environ.get("UAGENT_SUMMARY_ON_EXIT", "1") or "1"
            ).strip().lower() in {"1", "true", "yes", "on"}
            try:
                has_conversation = any(
                    isinstance(_m, dict)
                    and _m.get("role") in ("user", "assistant")
                    and str(_m.get("content") or "").strip()
                    for _m in (messages or [])
                )
            except Exception:
                has_conversation = True
            # No user/assistant turns (e.g. immediate Ctrl+C after startup):
            # skip the shutdown summarize LLM call. Summarizing system-only
            # history only yields "LLM returned no summary" noise + a billed call.
            if active_session_id and summary_on_exit and has_conversation:
                # Shutdown summarization is synchronous and should not start
                # the separate profile-extraction LLM job by default. Opt in
                # with UAGENT_PROFILE_ON_EXIT=1.
                profile_on_exit = (
                    os.environ.get("UAGENT_PROFILE_ON_EXIT", "0") or "0"
                ).strip().lower() in {"1", "true", "yes", "on"}
                previous_profiling = os.environ.get("UAGENT_ENABLE_PROFILING")
                try:
                    from ..util_cmd_session import _handle_cmd_sessions

                    if not profile_on_exit:
                        os.environ["UAGENT_ENABLE_PROFILING"] = "0"

                    _handle_cmd_sessions(
                        f"summarize {active_session_id}",
                        messages_ref=messages,
                        client=client,
                        depname=depname,
                        core=core,
                        tr=_,
                    )
                except KeyboardInterrupt:
                    # Ctrl+C during the shutdown summary should not abort the
                    # CLI with a traceback; skip the summary and exit cleanly.
                    print(_("[sessions] Shutdown summary interrupted; skipped."))
                except Exception as exc:
                    print(
                        _("[sessions] Shutdown summary failed: %(error)s")
                        % {"error": exc}
                    )
                finally:
                    if previous_profiling is None:
                        os.environ.pop("UAGENT_ENABLE_PROFILING", None)
                    else:
                        os.environ["UAGENT_ENABLE_PROFILING"] = previous_profiling
        # Clear cache on program exit
        if provider in ("gemini", "vertexai") and client:
            try:
                from ..providers.gemini_cache_mgr import GeminiCacheManager

                mgr = GeminiCacheManager(depname)
                mgr.clear_cache(client)
            except Exception:
                pass

        if sandbox_manager is not None:
            try:
                sandbox_manager.close_all()
                from ..runtime.mxc_backend import install_session_manager

                install_session_manager(None)
            except Exception:
                pass
        if session_store is not None:
            try:
                session_store.close()
            except Exception:
                pass
        core.set_status(False, "")
        print(_("Exited uag."))

    return process_exit_code
