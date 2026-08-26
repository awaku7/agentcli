from __future__ import annotations

# tools/human_ask_tool.py
import os
from typing import Any
import json
import queue
import threading

from .context import get_callbacks
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = False  # human_ask disables Busy (handled specially by tools/__init__.py)

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "basic",
    "function": {
        "name": "human_ask",
        "x_scheck": {"emit_tool_trace": False},
        "description": _(
            "tool.description",
            default="A tool to ask the human user for an input/decision that the model cannot complete by itself. Security note: when requesting secrets (passwords/tokens) the input is masked.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "human_ask",
                "human ask",
                "ask user",
                "prompt user",
                "human input",
                "decision",
            ],
        ),
        "x_search_terms_en": [
            "human_ask",
            "human ask",
            "ask user",
            "prompt user",
            "human input",
            "decision",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": _(
                        "param.message.description",
                        default="Message to show to the human user.",
                    ),
                },
                "is_password": {
                    "type": "boolean",
                    "description": _(
                        "param.is_password.description",
                        default=(
                            "If true, hide input characters (mask). Use this when requesting passwords or tokens."
                        ),
                    ),
                    "default": False,
                },
            },
            "required": ["message"],
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    """human_ask does not read from stdin directly.

    It delegates handling to the host's stdin_loop thread (in scheck.py) and receives the
    result via the shared callbacks.
    """

    cb = get_callbacks()

    message = args.get("message") or _(
        "msg.empty_request",
        default=(
            "(The request message from the model is empty. Please describe the required action/decision here.)"
        ),
    )

    is_password = bool(args.get("is_password", False))

    def _error_result(error_message: str) -> str:
        """Return JSON when the host did not initialize human_ask callbacks."""
        return json.dumps(
            {
                "tool": "human_ask",
                "message": message,
                "user_reply": "",
                "display_reply": error_message,
                "cancelled": True,
                "error": error_message,
            },
            ensure_ascii=False,
        )

    # Non-interactive mode has no stdin/UI consumer. Never block waiting
    # for a reply; return an autonomous continuation result.
    non_interactive = os.environ.get("UAGENT_NON_INTERACTIVE", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    inject_absconfirm = False
    if non_interactive and os.environ.get("UAGENT_INJECT_MODE") == "1":
        try:
            from .enterprise_policy import get_enterprise_policy

            inject_absconfirm = get_enterprise_policy().inject_requires_confirmation(
                str(args.get("_auto_pilot_tool") or "human_ask"),
                {
                    "server_name": args.get("_server_name", ""),
                    "tool_name": args.get("_mcp_tool", ""),
                },
            )
        except Exception:
            inject_absconfirm = False
    if non_interactive and not inject_absconfirm:
        print(
            _(
                "ui.non_interactive_skip",
                default="[NON-INTERACTIVE] human_ask skipped; the model must decide autonomously.",
            ),
            flush=True,
        )
        payload = {
            "tool": "human_ask",
            "message": message,
            "user_reply": "",
            "display_reply": "[NON-INTERACTIVE mode] Cannot ask the user. Decide autonomously based on the available information and continue working toward the goal.",
            "cancelled": False,
            "non_interactive_skipped": True,
        }
        return json.dumps(payload, ensure_ascii=False)

    # Auto-pilot normally skips interaction.  A tool can opt into an
    # absolute confirmation via enterprise-policy.yaml.
    auto_pilot_absconfirm = False
    if cb.is_auto_pilot_active and cb.is_auto_pilot_active():
        try:
            from .enterprise_policy import get_enterprise_policy

            auto_tool = str(args.get("_auto_pilot_tool") or "human_ask")
            auto_pilot_absconfirm = (
                get_enterprise_policy().auto_pilot_requires_confirmation(
                    auto_tool,
                    {"_auto_pilot_mcp_key": args.get("_auto_pilot_mcp_key", "")},
                )
            )
        except Exception:
            auto_pilot_absconfirm = False
    if (
        cb.is_auto_pilot_active
        and cb.is_auto_pilot_active()
        and not auto_pilot_absconfirm
        and not inject_absconfirm
    ):
        print(
            _(
                "ui.auto_pilot_skip",
                default="[AUTO] human_ask skipped (auto-pilot mode). The model must decide autonomously.",
            ),
            flush=True,
        )
        payload = {
            "tool": "human_ask",
            "message": message,
            "user_reply": "",
            "display_reply": "[AUTO-PILOT mode] Cannot ask the user during auto-pilot. Please decide autonomously based on the available information and continue working toward the goal.",
            "cancelled": False,
            "auto_pilot_skipped": True,
        }
        return json.dumps(payload, ensure_ascii=False)

    print(_("ui.title", default="=== Human request (human_ask) ==="), flush=True)
    print(message, flush=True)
    print(_("ui.footer", default="=== /human_ask ==="), flush=True)

    # For GUI, do not print extra how-to text (GUI has its own controls).
    if not cb.is_gui:
        print(
            _(
                "ui.howto",
                default=(
                    "How to answer:\n"
                    "  - Type your answer and press Enter\n"
                    "  - Type 'f' to enter multi-line mode\n"
                    "  - Type 'c' or 'cancel' to cancel\n"
                ),
            ),
            flush=True,
        )
        if bool(args.get("confirmation", False)):
            print(
                _(
                    "ui.all_yes",
                    default="  - Type 'all' to allow this tool for the rest of the session\n",
                ),
                flush=True,
            )

    if cb.human_ask_lock is None:
        return _error_result(
            _(
                "err.lock_uninitialized",
                default="[human_ask error] human_ask_lock callback is not initialized.",
            )
        )

    if cb.human_ask_active_ref is None or cb.human_ask_set_active is None:
        return _(
            "err.active_uninitialized",
            default="[human_ask error] human_ask_active callbacks are not initialized.",
        )

    if cb.human_ask_set_queue is None:
        return _(
            "err.queue_uninitialized",
            default="[human_ask error] human_ask_queue callback is not initialized.",
        )

    if cb.human_ask_lines_ref is None:
        return _(
            "err.lines_uninitialized",
            default="[human_ask error] human_ask_lines callback is not initialized.",
        )

    if cb.human_ask_set_multiline_active is None:
        return _(
            "err.multiline_uninitialized",
            default="[human_ask error] human_ask_multiline_active callback is not initialized.",
        )

    if cb.human_ask_set_password is None:
        return _(
            "err.password_uninitialized",
            default="[human_ask error] human_ask_set_password callback is not initialized.",
        )

    # Queue dedicated to this human_ask call
    local_q: "queue.Queue[str]" = queue.Queue()

    with cb.human_ask_lock:
        if cb.human_ask_active_ref():
            return _(
                "err.already_active",
                default="[human_ask error] Another human_ask is already active.",
            )

        cb.human_ask_set_active(True)
        cb.human_ask_set_password(is_password)
        cb.human_ask_set_queue(local_q)

        lines = cb.human_ask_lines_ref()
        try:
            lines.clear()
        except Exception:
            pass

        cb.human_ask_set_multiline_active(False)

    try:
        # After all state is set, clear Busy so the frontend can show input.
        if cb.set_status:
            cb.set_status(False, "")

        # Keep browser sessions alive while waiting for human input.
        # human_ask can take longer than browser session TTL (default 300s).
        stop_keepalive = threading.Event()

        def _keepalive_browser_sessions() -> None:
            while not stop_keepalive.wait(30.0):
                try:
                    from . import browser_playwright_tool as bp

                    if hasattr(bp, "_touch_all_sessions"):
                        bp._touch_all_sessions()
                except Exception:
                    pass

        keepalive_thread = threading.Thread(
            target=_keepalive_browser_sessions,
            name="human-ask-browser-keepalive",
            daemon=True,
        )
        keepalive_thread.start()
        try:
            # stdin_loop/GUI sends the user input to local_q.  Never wait
            # forever: an unanswered confirmation must fail closed.
            try:
                timeout_sec = float(
                    os.environ.get("UAGENT_HUMAN_ASK_TIMEOUT_SEC", "300")
                )
            except (TypeError, ValueError):
                timeout_sec = 300.0
            if timeout_sec <= 0:
                timeout_sec = 300.0
            try:
                user_reply = local_q.get(timeout=timeout_sec) or ""
            except queue.Empty:
                with cb.human_ask_lock:
                    cb.human_ask_set_active(False)
                return json.dumps(
                    {
                        "tool": "human_ask",
                        "message": message,
                        "user_reply": "",
                        "display_reply": "[confirmation timeout]",
                        "cancelled": True,
                        "timed_out": True,
                    },
                    ensure_ascii=False,
                )
            # The answer has been received. Release stdin ownership before
            # post-processing the reply so the CLI cannot spin waiting for
            # human_ask to finish its JSON cleanup.
            with cb.human_ask_lock:
                cb.human_ask_set_active(False)
        finally:
            stop_keepalive.set()
            try:
                keepalive_thread.join(timeout=1.0)
            except Exception:
                pass
            # Final touch after answer arrives.
            try:
                from . import browser_playwright_tool as bp

                if hasattr(bp, "_touch_all_sessions"):
                    bp._touch_all_sessions()
            except Exception:
                pass

        def _split_keep_lines(s: str) -> list[str]:
            # normalize CRLF/CR to LF
            s2 = str(s).replace("\r\n", "\n").replace("\r", "\n")
            return s2.split("\n")

        reply_lines = _split_keep_lines(user_reply) if user_reply else []

        # ---------------------------------------------------------
        # Sync internal state (core.human_ask_lines)
        # ---------------------------------------------------------
        lines.clear()
        for line in reply_lines:
            lines.append(line)
        cb.human_ask_set_multiline_active(True)

        if not user_reply:
            user_reply = _("msg.no_user_reply", default="(no user reply)")

        # normalize cancel
        ur = user_reply.strip().lower()
        cancelled = ur in ("c", "cancel")

        display_reply = "[SECRET]" if is_password and not cancelled else user_reply
        payload = {
            "tool": "human_ask",
            "message": message,
            "user_reply": user_reply,
            "display_reply": display_reply,
            "cancelled": cancelled,
        }
        return json.dumps(payload, ensure_ascii=False)

    finally:
        with cb.human_ask_lock:
            cb.human_ask_set_active(False)
            cb.human_ask_set_password(False)
            cb.human_ask_set_queue(None)
            cb.human_ask_set_multiline_active(False)
