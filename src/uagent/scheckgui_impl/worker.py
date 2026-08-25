"""GUI background worker (split from scheckgui.py)."""

from __future__ import annotations

import os
import sys
import threading
from typing import Any, Optional
from queue import Empty as QueueEmpty

from PySide6 import QtCore

from ..i18n import _, detect_lang, set_thread_lang
from .. import core
from .. import tools
from ..runtime import runtime_init as _runtime_init
from ..runtime.execution import lifecycle_execution
from ..scheduler import start_background_scheduler
from ..util_tools import (
    append_result_to_outfile,
    build_initial_messages,
    build_long_memory_system_message,
    build_multimodal_user_message,
    extract_last_assistant_text,
    handle_command,
    _run_auto_pilot_loop,
    provider_allows_chat_vision,
)
from ..tools.pybitchat_shared import (
    is_chat_mode,
    reply_to_mesh,
    set_llm_event_queue,
)
from ..uagent_llm import run_llm_rounds as util_run_llm_rounds
from ..image_session import build_image_session_message
from ..providers.util_providers import make_client as util_make_client
from ..tools.context import ToolCallbacks, get_callbacks
from ..tools.skill_history import make_finish_skill_handler
from .config import GuiConfig
from .state import _log_buffer, _log_lock


def _run_lifecycle(fn, *args, **kwargs):
    def _on_lifecycle(snapshot) -> None:
        try:
            core.set_status(
                snapshot.status.value
                not in {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT"},
                snapshot.status.value,
            )
        except Exception:
            pass

    with lifecycle_execution(on_transition=_on_lifecycle):
        return fn(*args, **kwargs)


class ScheckWorker(QtCore.QObject):
    """Worker that runs the LLM loop."""

    sig_finished = QtCore.Signal()
    sig_history_bootstrap = QtCore.Signal(list)

    def __init__(self, cfg: GuiConfig):
        super().__init__()
        self.cfg = cfg
        self.tools = tools
        self.messages: list[dict[str, Any]] = []
        self.image_session: Optional[dict[str, Any]] = None
        self._stop = threading.Event()
        self._provider = ""
        self._client = None
        self._depname = ""

    def _init_callbacks(self):
        cb = ToolCallbacks(
            set_status=core.set_status,
            debug=getattr(core, "debug", None),
            log=getattr(core, "log", None),
            error=getattr(core, "error", None),
            exception=getattr(core, "exception", None),
            rewrite_current_log_from_messages=getattr(
                core, "rewrite_current_log_from_messages", None
            ),
            log_message=getattr(core, "log_message", None),
            get_env=core.get_env,
            truncate_output=core.truncate_output,
            human_ask_lock=core.human_ask_lock,
            human_ask_active_ref=(lambda: core.human_ask_active),
            human_ask_set_active=(lambda v: setattr(core, "human_ask_active", bool(v))),
            human_ask_queue_ref=(lambda: core.human_ask_queue),
            human_ask_set_queue=(lambda q: setattr(core, "human_ask_queue", q)),
            human_ask_lines_ref=(lambda: core.human_ask_lines),
            human_ask_multiline_active_ref=(lambda: core.human_ask_multiline_active),
            human_ask_set_multiline_active=(
                lambda v: setattr(core, "human_ask_multiline_active", bool(v))
            ),
            human_ask_set_password=(
                lambda v: setattr(core, "human_ask_is_password", bool(v))
            ),
            is_auto_pilot_active=(lambda: core.auto_pilot_active),
            event_queue=core.event_queue,
            session_id=getattr(core, "session_id", None),
            cmd_encoding=core.CMD_ENCODING,
            cmd_exec_timeout_ms=core.CMD_EXEC_TIMEOUT_MS,
            python_exec_timeout_ms=core.PYTHON_EXEC_TIMEOUT_MS,
            url_fetch_timeout_ms=core.URL_FETCH_TIMEOUT_MS,
            url_fetch_max_bytes=core.URL_FETCH_MAX_BYTES,
            read_file_max_bytes=core.READ_FILE_MAX_BYTES,
            is_gui=True,
        )
        self.tools.init_callbacks(cb)

    @QtCore.Slot()
    def run(self):
        prev_finish_skill = None
        try:
            self._init_callbacks()
            start_background_scheduler(core.event_queue)
            # Allow pybitchat chat_mode="llm" to inject peer messages into the LLM.
            set_llm_event_queue(core.event_queue)
            try:
                self.tools.start_tools_warmup()
            except Exception:
                pass

            # Load and activate enabled plugins (MCP / agents / hooks)
            # Same surface as CLI/Web: one-line "[plugins] N enabled: ..."
            try:
                set_thread_lang(detect_lang())
            except Exception:
                pass
            try:
                from ..runtime.runtime_plugins import load_plugins_status_at_startup

                _plugins, _plugins_status = load_plugins_status_at_startup(
                    activate=True
                )
                if _plugins_status:
                    # stdout redirected to GUI log (same path as memory [INFO])
                    print(_plugins_status, flush=True)
            except Exception as e:
                try:
                    print(
                        "[WARN] " + _("Plugin load failed: %(err)s") % {"err": e},
                        flush=True,
                    )
                except Exception:
                    pass

            # Provider/client/model are decided by util_make_client.
            try:
                self._provider, self._client, self._depname = util_make_client(core)
            except Exception as e:
                print(
                    "[FATAL] "
                    + _("Failed to initialize LLM client: %(err)s") % {"err": e},
                    file=sys.stderr,
                )
                return
            if (
                self._provider == "openrouter"
                and (self._depname or "").strip() == "openrouter/auto"
            ):
                raw_fb = (
                    os.environ.get("UAGENT_OPENROUTER_FALLBACK_MODELS", "") or ""
                ).strip()
                if raw_fb:
                    print("[INFO] " + _("OpenRouter fallback models enabled."))

            self.messages = build_initial_messages(core=core)
            # Bootstrap input history from past user messages
            history_entries = []
            for msg in self.messages:
                if msg.get("role") != "user":
                    continue
                content = msg.get("content")
                if isinstance(content, str) and content.strip():
                    normalized = content.replace("\r", "").strip()
                    if normalized and normalized not in history_entries:
                        history_entries.append(normalized)
            if history_entries:
                self.sig_history_bootstrap.emit(history_entries)
            cb = get_callbacks()
            prev_finish_skill = cb.finish_skill
            cb.finish_skill = make_finish_skill_handler(self.messages, core)

            # Long-term memory
            from ..tools import long_memory as personal_long_memory
            from ..tools import shared_memory

            print("[INFO] " + _("Loaded long-term memory."))

            try:
                before_len = len(self.messages)
                flags = _runtime_init.append_long_memory_system_messages(
                    core=core,
                    messages=self.messages,
                    build_long_memory_system_message_fn=build_long_memory_system_message,
                    personal_long_memory_mod=personal_long_memory,
                    shared_memory_mod=shared_memory,
                )

                if flags.get("shared_enabled"):
                    print("[INFO] " + _("Loaded shared long-term memory."))

                for m in self.messages[before_len:]:
                    core.log_message(m)

            except Exception as e:
                print(
                    "[WARN] "
                    + _(
                        "Exception occurred while loading shared long-term memory: %(err)s"
                    )
                    % {"err": e}
                )

            from ..scheduler import SchedulerRunStore, SchedulerWorker

            scheduled_run_store = SchedulerRunStore()

            def _run_scheduled_lifecycle(event, *args, **kwargs):
                run_id = str(event.get("run_id") or "").strip()
                if not run_id:
                    return _run_lifecycle(*args, **kwargs)
                run = scheduled_run_store.get(run_id)
                metadata = dict((run.metadata if run else {}) or {})
                try:
                    result = SchedulerWorker(scheduled_run_store).execute(
                        run_id,
                        lambda _payload: _run_lifecycle(*args, **kwargs),
                        timeout_sec=float(metadata.get("timeout_sec") or 0),
                        retry_limit=int(metadata.get("retry_limit") or 0),
                        retry_backoff_sec=int(metadata.get("retry_backoff_sec") or 0),
                    )
                except Exception as exc:
                    try:
                        scheduled_run_store.finish(
                            run_id, status="failed", error=str(exc)
                        )
                    except Exception:
                        pass
                    raise
                else:
                    try:
                        scheduled_run_store.finish(run_id)
                    except Exception:
                        pass
                    return result

            while not self._stop.is_set():
                try:
                    ev = core.event_queue.get(timeout=0.5)
                    kind = ev.get("kind")

                    if kind == "command":
                        result = handle_command(
                            ev.get("text", ""),
                            self.messages,
                            self._client,
                            self._depname,
                            core=core,
                        )
                        if not result:
                            self._stop.set()
                            break
                        if getattr(result, "run_llm", False):
                            prompt = (
                                getattr(result, "prompt", None)
                                or "Run the loaded skill."
                            )
                            m = {"role": "user", "content": prompt}
                            self.messages.append(m)
                            core.log_message(m)
                            self.image_session = build_image_session_message(
                                self.messages, self._depname
                            )
                            _run_scheduled_lifecycle(
                                ev,
                                util_run_llm_rounds,
                                self._provider,
                                self._client,
                                self._depname,
                                self.messages,
                                core=core,
                                make_client_fn=util_make_client,
                                append_result_to_outfile_fn=append_result_to_outfile,
                                try_open_images_from_text_fn=lambda _: None,
                            )
                            # Auto-pilot loop (first call)
                            if core.auto_pilot_active:
                                _run_lifecycle(
                                    _run_auto_pilot_loop,
                                    self._provider,
                                    self._client,
                                    self._depname,
                                    self.messages,
                                    core=core,
                                    make_client_fn=util_make_client,
                                    append_result_to_outfile_fn=append_result_to_outfile,
                                    try_open_images_from_text_fn=lambda _: None,
                                )
                    elif kind == "schedule_notice":
                        notice = (ev.get("text", "") or "").strip()
                        if notice:
                            print("[INFO] " + notice)
                        continue
                    elif kind in ("user", "timer", "gui_user"):
                        text = ev.get("text", "")
                        if kind != "timer" and is_chat_mode() == "on":
                            continue
                        files = list(ev.get("files", []) or [])

                        if files:
                            file_lines = [
                                _("[Attached File] %(name)s (%(path)s)")
                                % {"name": os.path.basename(p), "path": p}
                                for p in files
                            ]
                            if file_lines:
                                if text.strip():
                                    text = (
                                        text.rstrip() + "\n\n" + "\n".join(file_lines)
                                    )
                                else:
                                    text = "\n".join(file_lines)

                        # UserPromptSubmit: stdin JSON + optional block
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
                                self.messages,
                                _ups_results,
                                event_name="UserPromptSubmit",
                                replace_event=True,
                            )
                        except Exception:
                            pass

                        use_responses_api = (
                            os.environ.get("UAGENT_RESPONSES", "") or ""
                        ).lower() in (
                            "1",
                            "true",
                        )
                        prov = (os.environ.get("UAGENT_PROVIDER") or "").lower()
                        allow_multimodal = provider_allows_chat_vision(
                            prov,
                            use_responses_api=use_responses_api,
                            model_id=getattr(self, "_depname", None),
                        )

                        if allow_multimodal:
                            img_paths = [
                                p
                                for p in (ev.get("images") or [])
                                if isinstance(p, str) and os.path.isfile(p)
                            ]
                            video_paths = [
                                p
                                for p in (ev.get("videos") or [])
                                if (
                                    isinstance(p, str)
                                    and os.path.isfile(p)
                                    and os.path.getsize(p) <= 50_000_000
                                    and prov == "llama_cpp"
                                )
                            ]
                            m = build_multimodal_user_message(
                                text.strip(),
                                img_paths,
                                video_paths=video_paths,
                                provider=prov,
                                use_responses_api=use_responses_api,
                            )
                            self.messages.append(m)
                            core.log_message(m)

                            _run_scheduled_lifecycle(
                                ev,
                                util_run_llm_rounds,
                                self._provider,
                                self._client,
                                self._depname,
                                self.messages,
                                core=core,
                                make_client_fn=util_make_client,
                                append_result_to_outfile_fn=append_result_to_outfile,
                                try_open_images_from_text_fn=lambda _: None,
                            )
                            # Auto-pilot loop (native multimodal path)
                            if core.auto_pilot_active:
                                _run_lifecycle(
                                    _run_auto_pilot_loop,
                                    self._provider,
                                    self._client,
                                    self._depname,
                                    self.messages,
                                    core=core,
                                    make_client_fn=util_make_client,
                                    append_result_to_outfile_fn=append_result_to_outfile,
                                    try_open_images_from_text_fn=lambda _: None,
                                )
                            # bitchat 経由のメッセージ: LLM 応答を mesh に自動返信
                            if ev.get("src") == "bitchat":
                                _reply = extract_last_assistant_text(self.messages)
                                if _reply:
                                    reply_to_mesh(_reply)
                            continue

                        # Fallback: analyze_image tool -> text injection
                        for p in ev.get("images", []):
                            if os.path.isfile(p):
                                core.set_status(True, "analyze_image")
                                try:
                                    res = self.tools.run_tool(
                                        "analyze_image", {"image_path": p}
                                    )
                                except Exception as e:
                                    res = (
                                        f"[analyze_image error] {type(e).__name__}: {e}"
                                    )
                                text += (
                                    _("[Attached Image] %(path)s") % {"path": p}
                                    + "\n"
                                    + _("[Image Path] %(path)s") % {"path": p}
                                    + "\n"
                                    + str(res)
                                )
                        if text.strip():
                            m = {"role": "user", "content": text.strip()}
                            self.messages.append(m)
                            core.log_message(m)
                            self.image_session = build_image_session_message(
                                self.messages, self._depname
                            )
                            _run_scheduled_lifecycle(
                                ev,
                                util_run_llm_rounds,
                                self._provider,
                                self._client,
                                self._depname,
                                self.messages,
                                core=core,
                                make_client_fn=util_make_client,
                                append_result_to_outfile_fn=append_result_to_outfile,
                                try_open_images_from_text_fn=lambda _: None,
                            )
                            # Auto-pilot loop (fallback path)
                            if core.auto_pilot_active:
                                _run_lifecycle(
                                    _run_auto_pilot_loop,
                                    self._provider,
                                    self._client,
                                    self._depname,
                                    self.messages,
                                    core=core,
                                    make_client_fn=util_make_client,
                                    append_result_to_outfile_fn=append_result_to_outfile,
                                    try_open_images_from_text_fn=lambda _: None,
                                )
                            # bitchat 経由のメッセージ: LLM 応答を mesh に自動返信
                            if ev.get("src") == "bitchat":
                                _reply = extract_last_assistant_text(self.messages)
                                if _reply:
                                    reply_to_mesh(_reply)
                except QueueEmpty:
                    continue
                except Exception:
                    try:
                        with _log_lock:
                            _log_buffer.write(_("[ERROR] Worker exception:\n"))
                            import traceback

                            traceback.print_exc(file=_log_buffer)
                    except Exception:
                        pass
                    continue
        finally:
            if prev_finish_skill is not None:
                get_callbacks().finish_skill = prev_finish_skill
            self.sig_finished.emit()

    def stop(self):
        self._stop.set()
