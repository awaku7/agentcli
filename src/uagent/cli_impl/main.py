"""CLI entry point implementation (split from cli.py)."""

from __future__ import annotations

import json
import os
import sys
import threading
from typing import Any

from ..i18n import _
from ..env_utils import env_get
from .. import core
from .. import tools
from .. import util_tools as tools_util
from ..providers import util_providers as providers
from ..runtime.execution import lifecycle_execution
from ..runtime.logging_setup import log_event
from ..scheduler import start_background_scheduler, stop_background_scheduler
from ..tools.pybitchat_shared import reply_to_mesh, set_llm_event_queue
from ..util_tools import (
    build_multimodal_user_message,
    extract_image_paths,
    extract_video_paths,
    handle_command,
    provider_allows_chat_vision,
)
from ..cli_startup import run_cli_startup as _run_cli_startup
from .history import _append_prompt_history_entry, _bootstrap_prompt_history
from .startup import (
    INITIAL_FILE_ARG,
    UAGENT_ENABLE_TOOLS,
    UAGENT_INJECT_MESSAGE,
    UAGENT_INJECT_MESSAGE_AUTO,
    UAGENT_NON_INTERACTIVE,
    UAGENT_REALTIME,
    UAGENT_TOOL_GENRE_MASK,
    _cli_workdir,
    _env_workdir,
)
from .state import _CLI_SHUTDOWN
from .stdin_loop import stdin_loop


def main() -> None:
    _CLI_SHUTDOWN.clear()
    from ..runtime.logging_setup import bind_event_context

    bind_event_context(session_id="cli", correlation_id="cli")
    log_event("cli.start")
    sys.stdout.reconfigure(encoding="utf-8")
    if UAGENT_REALTIME:
        from ..realtime import run as run_realtime

        raise SystemExit(run_realtime())

    from .. import uagent_llm as llm_util  # lazy

    startup = _run_cli_startup(
        core=core,
        cli_workdir=_cli_workdir,
        env_workdir=_env_workdir,
        initial_file_arg=INITIAL_FILE_ARG,
        non_interactive=UAGENT_NON_INTERACTIVE,
        tool_genre_mask=UAGENT_TOOL_GENRE_MASK,
        inject_message=UAGENT_INJECT_MESSAGE,
        inject_message_auto=UAGENT_INJECT_MESSAGE_AUTO,
        enable_tools=UAGENT_ENABLE_TOOLS,
    )

    provider = startup.provider
    client = startup.client
    depname = startup.depname
    messages = startup.messages
    session_store = startup.session_store
    _bootstrap_prompt_history(messages)

    if startup.should_exit:
        return

    # Computer Use backends are created lazily by the action handler.
    # Merely enabling the capability must not open a browser or desktop session.

    # Do not automatically resume a saved Responses chain at startup.
    # Explicit :load selects a log and may restore its validated latest ID.
    if provider in ("openai", "azure"):
        core.responses_state["provider"] = provider
        core.responses_state["model"] = depname
        core.responses_state.pop("previous_response_id", None)
        core.responses_state.pop("active_response_id", None)

    start_background_scheduler(core.event_queue)
    # Allow pybitchat chat_mode="llm" to inject peer messages into the LLM.
    set_llm_event_queue(core.event_queue)
    core.start_interrupt_monitor()

    # Preload tool plugins in background so the first ':' command/completion
    # does not pay the full plugin-import cost on the interactive path.
    if not UAGENT_NON_INTERACTIVE:
        try:
            tools.start_tools_warmup()
        except Exception:
            pass

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

        _ss_results = fire_session_start()
        inject_hook_context(
            messages, _ss_results, event_name="SessionStart", replace_event=False
        )
        # Avoid double-inject if a later path pulls the SessionStart stash.
        take_pending_session_hook_texts()
        _hooks = load_hooks_registry(get_default_registry_path())
        if _hooks:
            _setup_results = fire_event("Setup", _hooks)
            inject_hook_context(
                messages, _setup_results, event_name="Setup", replace_event=False
            )
    except Exception:
        pass

    t = threading.Thread(target=stdin_loop, daemon=True)
    t.start()

    running = True
    try:
        # Scheduler execution records are updated when scheduled events enter
        # the interactive worker loop.  The store is durable and independent
        # from the event queue, so a restart does not erase the run history.
        from ..scheduler import SchedulerRunStore, SchedulerWorker

        scheduled_run_store = SchedulerRunStore()

        def _run_llm_event(event, fn, *args, **kwargs):
            run_id = str(event.get("run_id") or "").strip()
            if not run_id:
                return fn(*args, **kwargs)
            run = scheduled_run_store.get(run_id)
            metadata = dict((run.metadata if run else {}) or {})
            from ..scheduler import required_tools_guard

            def _execute_scheduled(_payload):
                with required_tools_guard(
                    metadata.get("required_tools") or [],
                    reason=f"scheduled run:{run_id}",
                ):
                    return fn(*args, **kwargs)

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
            from ..scheduler import execute_direct_tool, required_tools_guard

            def _execute_scheduled(_payload):
                with required_tools_guard(
                    required,
                    reason=f"scheduled direct run:{run_id}",
                ):
                    return execute_direct_tool(target_tool, target_args)

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

        while running:
            try:
                ev = core.event_queue.get()
            except KeyboardInterrupt:
                # Idle wait interrupted (ollama-like: no traceback, clean exit).
                print()
                print("[INFO] " + _("Received Ctrl+C. Starting shutdown..."))
                break
            kind = ev.get("kind")

            if kind == "command":
                line = ev.get("text", "")
                result = handle_command(line, messages, client, depname, core=core)
                if not result:
                    running = False
                    break
                core.set_status(False, "")
                if getattr(result, "run_llm", False):
                    prompt = getattr(result, "prompt", None) or "Run the loaded skill."
                    user_msg = {"role": "user", "content": prompt}
                    messages.append(user_msg)
                    _append_prompt_history_entry(prompt)
                    core.log_message(user_msg)
                    with lifecycle_execution() as lifecycle:
                        try:
                            _run_llm_event(
                                ev,
                                llm_util.run_llm_rounds,
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
                            continue
                        except Exception as exc:
                            lifecycle.fail()
                            print(_("LLM round interrupted: %(err)s") % {"err": exc})

                    # Auto-pilot loop: if auto mode is active, continue rounds
                    if core.auto_pilot_active:
                        try:
                            with lifecycle_execution():
                                tools_util._run_auto_pilot_loop(
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
                    if UAGENT_INJECT_MESSAGE_AUTO:
                        running = False
                        break
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

                    _ups_results = fire_user_prompt_submit(text)
                    _ups_block = collect_hook_block_decision(_ups_results)
                    if _ups_block is not None:
                        _reason = (_ups_block.get("reason") or "").strip()
                        if not _reason:
                            _reason = "Blocked by UserPromptSubmit hook."
                        print(_reason)
                        core.set_status(False, "")
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
                                res_json = tools.run_tool(
                                    "human_ask", {"message": msg, "is_password": False}
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
                            llm_util.run_llm_rounds,
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
                        continue
                    except Exception as exc:
                        lifecycle.fail()
                        print(
                            "[bitchat] "
                            + _("LLM round interrupted: %(err)s") % {"err": exc}
                        )
                # bitchat 経由のメッセージ: LLM 応答を mesh に自動返信
                if ev.get("src") == "bitchat":
                    reply = tools_util.extract_last_assistant_text(messages)
                    if reply:
                        reply_to_mesh(reply)
                    # 注入ラウンド中に手動プロンプトの行が閉じられているため、
                    # アイドルに戻ったら stdin_loop に再描画を要求する。
                    try:
                        core.prompt_needs_redraw = True
                    except Exception:
                        pass
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
        # stdin_loop is intentionally a daemon while the CLI is running, but
        # it should not still be inside prompt_toolkit when Python starts
        # interpreter finalization. The prompt watcher above exits the
        # blocking prompt; the manual input loops observe the same event.
        try:
            t.join(timeout=1.0)
        except Exception:
            pass
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

            fire_stop()
            _hooks = load_hooks_registry(get_default_registry_path())
            if _hooks:
                fire_event("SessionEnd", _hooks)
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

        if session_store is not None:
            try:
                session_store.close()
            except Exception:
                pass
        core.set_status(False, "")
        print(_("Exited uag."))
