"""CLI display and commands for foreground-owned Sub-Agent Jobs."""

from __future__ import annotations

import os
import queue
import re
import shlex
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

_TERMINAL_CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def _safe_terminal_text(value: Any, limit: int = 4000) -> str:
    text = _TERMINAL_CONTROL_RE.sub("", str(value or ""))
    return text[: max(0, limit)]


from ..runtime.sub_agent_jobs import SubAgentJobOwner
from ..runtime.sub_agent_jobs import (
    SubAgentConfirmationUnavailable,
    SubAgentJobExecutionContext,
)


@dataclass
class _JobConfirmationRequest:
    job: SubAgentJobExecutionContext
    message: str
    is_password: bool
    replies: queue.Queue[str] = field(default_factory=queue.Queue)


def cli_confirmation_supported(*, enabled: bool = True) -> bool:
    """Enable Job confirmations only on the cancellable prompt_toolkit path."""
    if not enabled:
        return False
    if os.environ.get("UAGENT_NON_INTERACTIVE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return False
    if os.environ.get("UAGENT_SIMPLE_PROMPT", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return False
    try:
        from ..tools.pybitchat_shared import is_chat_mode

        if is_chat_mode() == "llm":
            return False
    except Exception:
        pass
    if (
        not getattr(sys.stdin, "isatty", lambda: False)()
        or not getattr(sys.stdout, "isatty", lambda: False)()
    ):
        return False
    try:
        from .prompt_session import _get_prompt_session

        return _get_prompt_session(reply=True) is not None
    except Exception:
        return False


class CLIJobConfirmationBroker:
    """FIFO, cancellable confirmation requests for CLI-owned background Jobs."""

    def __init__(self, core: Any, *, enabled: bool) -> None:
        self.core = core
        self.enabled = bool(enabled)
        self._condition = threading.Condition(threading.RLock())
        self._pending: deque[_JobConfirmationRequest] = deque()
        self._active: _JobConfirmationRequest | None = None
        self._stopping = False

    def ask(
        self,
        job: SubAgentJobExecutionContext,
        message: str,
        is_password: bool,
    ) -> str:
        if not self.enabled:
            raise SubAgentConfirmationUnavailable(
                "CLI Job confirmation requires an interactive cancellable prompt"
            )
        job.raise_if_cancelled()
        request = _JobConfirmationRequest(
            job=job,
            message=str(message or "").strip(),
            is_password=bool(is_password),
        )
        with self._condition:
            if self._stopping:
                raise SubAgentConfirmationUnavailable("CLI is shutting down")
            self._pending.append(request)
        try:
            activated = self._activate_next()
            if activated is not None:
                display_job_confirmation(self.core, activated)
            job.log("confirmation", "Confirmation request queued")
            while True:
                job.raise_if_cancelled()
                activated = self._activate_next()
                if activated is not None:
                    display_job_confirmation(self.core, activated)
                remaining = job.remaining
                wait_for = 0.1 if remaining is None else min(0.1, remaining)
                if wait_for <= 0:
                    job.raise_if_cancelled()
                try:
                    reply = request.replies.get(timeout=wait_for)
                except queue.Empty:
                    continue
                job.raise_if_cancelled()
                self._withdraw(request)
                job.log("confirmation", "Confirmation reply received")
                return reply
        except BaseException:
            self._withdraw(request)
            raise

    def _activate_next(self) -> _JobConfirmationRequest | None:
        with self._condition:
            if self._stopping or self._active is not None or not self._pending:
                return None
            with self.core.human_ask_lock:
                if self.core.human_ask_active:
                    return None
                request = self._pending.popleft()
                self._active = request
                self.core.human_ask_active = True
                self.core.human_ask_is_password = request.is_password
                self.core.human_ask_prompt = f"[REPLY job:{request.job.job_id}] > "
                self.core.human_ask_job_id = request.job.job_id
                self.core.human_ask_queue = request.replies
                self.core.human_ask_multiline_active = False
                self.core.human_ask_generation += 1
                try:
                    self.core.human_ask_lines.clear()
                except Exception:
                    pass
                request.job.set_waiting_for_user(True)
            self._condition.notify_all()
        return request

    def _withdraw(self, request: _JobConfirmationRequest) -> None:
        with self._condition:
            try:
                self._pending.remove(request)
            except ValueError:
                pass
            if self._active is request:
                with self.core.human_ask_lock:
                    if self.core.human_ask_job_id == request.job.job_id:
                        self.core.human_ask_active = False
                        self.core.human_ask_is_password = False
                        self.core.human_ask_prompt = ""
                        self.core.human_ask_job_id = None
                        self.core.human_ask_queue = None
                        self.core.human_ask_multiline_active = False
                        self.core.human_ask_generation += 1
                        self.core.prompt_needs_redraw = True
                        request.job.set_waiting_for_user(False)
                self._active = None
            self._condition.notify_all()

    def shutdown(self) -> None:
        with self._condition:
            self._stopping = True
            pending = list(self._pending)
            active = self._active
            self._pending.clear()
            if active is not None:
                try:
                    active.replies.put_nowait("cancel")
                except queue.Full:
                    pass
                self._withdraw(active)
            for request in pending:
                request.replies.put_nowait("cancel")
            self._condition.notify_all()


def display_job_confirmation(core: Any, request: _JobConfirmationRequest) -> None:
    message = _safe_terminal_text(_mask_inline_secrets(request.message))
    line = _safe_terminal_text(
        f"[JOB {request.job.job_id} {request.job.agent_name}] confirmation required",
        256,
    )
    with core.print_lock:
        if getattr(core, "_stream_line_open", False) or getattr(
            core, "_prompt_line_open", False
        ):
            try:
                sys.stdout.write("\n")
                sys.stdout.flush()
            except Exception:
                pass
            core._stream_line_open = False
            core._reasoning_stream_open = False
            core._prompt_line_open = False
        print(line, flush=True)
        if message:
            print(message, flush=True)
        print(
            "Reply at the Job prompt; type 'c' or 'cancel' to cancel the request.",
            flush=True,
        )


from ..utils.secret_mask import _mask_inline_secrets


def format_job_notice(notice: dict[str, Any]) -> str:
    job_id = _safe_terminal_text(notice.get("job_id") or "unknown", 64)
    agent = _safe_terminal_text(notice.get("agent_name") or "agent", 128)
    state = _safe_terminal_text(notice.get("state") or "running", 32)
    if notice.get("event") == "started":
        detail = "started"
    elif state == "completed":
        elapsed = notice.get("elapsed_sec")
        detail = (
            f"completed ({float(elapsed):.1f}s)" if elapsed is not None else "completed"
        )
    elif state == "blocked":
        detail = "blocked"
    elif state == "failed":
        detail = "failed"
    elif state == "cancelled":
        detail = "cancelled"
    elif state == "timed_out":
        detail = "timed out"
    else:
        detail = state
    reason = _safe_terminal_text(
        _mask_inline_secrets(str(notice.get("reason") or "").strip()), 160
    )
    if reason and state in {"failed", "blocked", "cancelled", "timed_out"}:
        detail += f": {reason[:160]}"
    return f"[JOB {job_id} {agent}] {detail}"


def display_job_notice(core: Any, notice: dict[str, Any]) -> str:
    """Print a short lifecycle notice without changing foreground BUSY state."""
    text = format_job_notice(notice)
    toolkit_prompt = bool(getattr(core, "_cli_prompt_toolkit_active", False))
    busy = bool(getattr(core, "status_busy", False))
    lock = getattr(core, "print_lock", None)
    if lock is None:
        print(text, flush=True)
        return text

    with lock:
        if not toolkit_prompt:
            if getattr(core, "_stream_line_open", False) or getattr(
                core, "_prompt_line_open", False
            ):
                try:
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                except Exception:
                    print("")
            core._stream_line_open = False
            core._reasoning_stream_open = False
            core._prompt_line_open = False
        print(text, flush=True)
        if not busy and not toolkit_prompt:
            core.prompt_needs_redraw = True
    return text


def handle_cli_job_command(
    line: str,
    *,
    manager: Any,
    owner: Any,
    poll_interval: float = 0.2,
) -> bool:
    """Handle :jobs / :job CLI commands; return False for unrelated input."""
    stripped = str(line or "").strip()
    if stripped != ":jobs" and not stripped.startswith(":job"):
        return False
    try:
        parts = shlex.split(stripped)
    except ValueError as exc:
        print(f"Invalid job command: {exc}")
        return True
    if not parts:
        return True
    if parts[0] == ":jobs":
        if len(parts) != 1:
            print("Usage: :jobs")
            return True
        _show_jobs(manager, owner)
        return True
    if parts[0] != ":job":
        return False
    if len(parts) == 1:
        print(
            "Usage: :job <job_id> | :job logs <job_id> | :job follow <job_id> | :job cancel <job_id>"
        )
        return True
    if manager is None or owner is None:
        print("Sub-Agent Job Runtime is not available in this CLI session.")
        return True

    action = parts[1].lower()
    if action in {"logs", "follow", "cancel"}:
        if len(parts) != 3:
            print(f"Usage: :job {action} <job_id>")
            return True
        job_id = parts[2]
        if action == "logs":
            _show_job_logs(manager, owner, job_id)
        elif action == "cancel":
            result = manager.cancel(
                owner=owner, job_id=job_id, reason="cancelled from CLI"
            )
            if result.get("state"):
                print(f"Job {job_id}: {result['state']}")
            else:
                print(f"Job {job_id} not found.")
        else:
            _follow_job(manager, owner, job_id, poll_interval)
        return True

    if len(parts) != 2:
        print("Usage: :job <job_id>")
        return True
    _show_job(manager, owner, parts[1])
    return True


def _show_jobs(manager: Any, owner: Any) -> None:
    if manager is None or owner is None:
        print("Sub-Agent Job Runtime is not available in this CLI session.")
        return
    jobs = manager.summary(owner=owner)
    if not jobs:
        print("No Sub-Agent Jobs.")
        return
    for item in jobs:
        agent = _safe_terminal_text(item.get("agent_name", "agent"), 128)
        print(
            f"{_safe_terminal_text(item['job_id'], 64)}  "
            f"{_safe_terminal_text(item['state'], 32):<12}  {agent}  "
            f"{_safe_terminal_text(item['updated_at'], 64)}"
        )


def _show_job(manager: Any, owner: Any, job_id: str) -> None:
    result = manager.get(owner=owner, job_id=job_id)
    if result.get("reason") == "not_found":
        print(f"Job {job_id} not found.")
        return
    for key in (
        "job_id",
        "state",
        "agent_name",
        "created_at",
        "started_at",
        "completed_at",
        "reason",
    ):
        value = result.get(key)
        if value not in (None, ""):
            print(f"{key}: {_safe_terminal_text(value, 512)}")
    if result.get("truncated"):
        print(
            "note: Job events or result were truncated to stay within configured limits"
        )
    if result.get("orphaned_on_shutdown"):
        print("note: worker did not stop before shutdown grace period")
    if result.get("result") is not None:
        print("result: available (not printed; retrieve by joining the Job)")


def _show_job_logs(
    manager: Any, owner: Any, job_id: str, *, after: int = 0, quiet: bool = False
) -> int:
    result = manager.get_events(owner=owner, job_id=job_id, after=after)
    if result.get("reason") == "not_found":
        print(f"Job {job_id} not found.")
        return after
    events = result.get("events") or []
    if not events:
        if not quiet:
            print("No Job log events.")
        return after
    for event in events:
        sequence = int(event.get("sequence", after))
        raw_message = _mask_inline_secrets(str(event.get("message") or ""))
        display_limit = 4000
        message = _safe_terminal_text(raw_message, display_limit)
        if len(raw_message) > display_limit:
            message += " [display truncated]"
        print(f"[{sequence} {event.get('kind', 'event')}] {message}")
        after = max(after, sequence)
    if result.get("truncated"):
        print("note: older Job log events or content were truncated")
    return after


def _follow_job(manager: Any, owner: Any, job_id: str, poll_interval: float) -> None:
    result = manager.get(owner=owner, job_id=job_id)
    if result.get("reason") == "not_found":
        print(f"Job {job_id} not found.")
        return
    after = 0
    try:
        while True:
            after = _show_job_logs(manager, owner, job_id, after=after, quiet=True)
            result = manager.get(owner=owner, job_id=job_id)
            if result.get("reason") == "not_found":
                print(f"Job {job_id} expired from retention.")
                return
            if result.get("state") in {
                "completed",
                "blocked",
                "failed",
                "cancelled",
                "timed_out",
            }:
                return
            time.sleep(max(0.05, poll_interval))
    except KeyboardInterrupt:
        print("Stopped following the Job; the Job continues running.")


def is_cli_session_transition_command(line: str) -> bool:
    try:
        parts = shlex.split(str(line or "").strip())
    except ValueError:
        return False
    if not parts:
        return False
    command = parts[0].lstrip(":").lower()
    if command == "cont":
        return True
    if command == "load":
        return len(parts) > 1
    if command in {"session", "sessions"}:
        return (
            len(parts) > 2
            and parts[1].lower() in {"load", "resume"}
            and bool(parts[2].strip())
        )
    return False


def current_cli_job_owner(core: Any, fallback_session_id: str = "") -> SubAgentJobOwner:
    session_id = str(
        getattr(core, "_session_store_active_id", "")
        or getattr(core, "session_id", "")
        or fallback_session_id
        or getattr(core, "SESSION_ID", "cli")
        or "cli"
    )
    return SubAgentJobOwner(entry_point="cli", session_id=session_id)


def prepare_cli_session_transition(
    manager: Any, owner: SubAgentJobOwner, *, timeout: float = 5.0
) -> tuple[bool, list[str]]:
    """Cancel old-owner work before a CLI session can be rebound."""
    manager.pause_owner(owner)
    manager.cancel_all(owner=owner, reason="CLI session transition")
    if manager.wait_owner_workers(owner, timeout=max(0.0, timeout)):
        return True, []
    lingering = manager.active_job_ids(owner)
    manager.resume_owner(owner)
    return False, lingering


__all__ = [
    "display_job_notice",
    "format_job_notice",
    "handle_cli_job_command",
    "current_cli_job_owner",
    "is_cli_session_transition_command",
    "prepare_cli_session_transition",
]
