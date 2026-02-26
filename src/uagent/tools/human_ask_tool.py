from __future__ import annotations

# tools/human_ask_tool.py
from typing import Any, Dict
import json
import queue

from .context import get_callbacks
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = False  # human_ask disables Busy (handled specially by tools/__init__.py)

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "human_ask",
        "x_scheck": {"emit_tool_trace": False},
        "description": _(
            "tool.description",
            default=(
                "A tool to ask the human user for an input/decision that the model cannot complete by itself. "
                "Security note: when requesting secrets (passwords/tokens), set is_password=True and ask for exactly one item per call."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "This tool is used for the following purpose: ask the human user for an input/decision that the model cannot complete by itself and receive a single reply text.\n\n"
                "Important: This tool can receive only one reply text per call. Do not split input into multiple fields.\n\n"
                "SECURITY (MOST IMPORTANT):\n"
                "- When requesting secrets (passwords, API keys, tokens, private keys, session cookies, etc.), you MUST set is_password=True.\n"
                "- Never repeat a secret obtained with is_password=True in any later assistant messages.\n"
                "- Do not store secrets in long-term memory or shared memory.\n\n"
                "Operational guidelines:\n"
                "- If additional user input is needed, always use the human_ask tool.\n"
                "- With is_password=True, ask for only one secret item.\n"
                "- If both username and password are required, call human_ask multiple times.\n"
                "- Do not request multiple items in a single call.\n"
                "- For relative date expressions (today/this year/etc.), call get_current_time.\n"
                "- When outputting files or code, do not omit the full original content unless the user explicitly requests it.\n\n"
                "Cancellation:\n"
                "- To cancel, reply with a single line: 'c' or 'cancel'.\n"
            ),
        ),
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


def run_tool(args: Dict[str, Any]) -> str:
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

    print(_("ui.title", default="=== Human request (human_ask) ==="), flush=True)
    print(message, flush=True)
    print(_("ui.footer", default="=== /human_ask ==="), flush=True)

    # For GUI, do not print extra how-to text (GUI has its own controls).
    if not cb.is_gui:
        print(
            _(
                "ui.howto",
                default=(
                    "How to reply:\n"
                    "  - Type your answer and press Enter\n"
                    "  - Type 'f' to enter multi-line mode\n"
                    "  - In multi-line mode: '\"\"\"retry' clears, '\"\"\"end' sends\n"
                    "  - Type 'c' or 'cancel' to cancel\n"
                ),
            ),
            flush=True,
        )

    if cb.human_ask_lock is None:
        return _(
            "err.lock_uninitialized",
            default="[human_ask error] human_ask_lock callback is not initialized.",
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

        # stdin_loop/GUI sends the user input to local_q
        user_reply = local_q.get() or ""

        def _split_keep_lines(s: str) -> list[str]:
            # normalize CRLF/CR to LF
            s2 = str(s).replace("\r\n", "\n").replace("\r", "\n")
            return s2.split("\n")

        def _strip_trailing_end_sentinel(text: str) -> str:
            """Remove a trailing end-marker (triple-quote + end) that may be appended by some frontends."""
            t = "" if text is None else str(text)
            # normalize CRLF/CR to LF for stable handling
            t = t.replace("\r\n", "\n").replace("\r", "\n")
            marker = "\"\"\"end"
            while True:
                t2 = t.rstrip("\n")
                if t2.endswith("\n" + marker):
                    t = t2[: -len("\n" + marker)]
                    continue
                if t2.endswith(marker):
                    t = t2[: -len(marker)]
                    continue
                break
            # Avoid leaving only trailing newlines
            t = t.rstrip("\n")
            return t

        def _ensure_gui_sentinel(text: str) -> str:
            """Ensure GUI replies always end with multi_input_sentinel line."""
            t = str(text or "")
            # For cancel, do not append sentinel
            if t.strip().lower() in ("c", "cancel"):
                return t
            lines0 = _split_keep_lines(t)
            # If sentinel line is already present, keep as-is.
            if any((ln.strip() == cb.multi_input_sentinel) for ln in lines0):
                return t
            # Allow confirmation with sentinel even for empty input
            if t.endswith("\n") or t == "":
                return t + cb.multi_input_sentinel + "\n"
            return t + "\n" + cb.multi_input_sentinel + "\n"

        # For GUI, normalize with sentinel
        if cb.is_gui:
            user_reply = _ensure_gui_sentinel(user_reply)

        # Strip trailing """end marker if present
        user_reply = _strip_trailing_end_sentinel(user_reply)

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
