"""GUI owner binding and non-blocking Sub-Agent Job confirmations."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Callable

from ..runtime.sub_agent_jobs import (
    SubAgentJobExecutionContext,
    SubAgentJobManager,
    SubAgentJobOwner,
)


@dataclass
class GUIJobConfirmationRequest:
    job_id: str
    agent_name: str
    message: str
    is_password: bool
    completed: threading.Event = field(default_factory=threading.Event)
    response: str = ""
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def respond(self, value: str) -> None:
        with self._lock:
            if self.completed.is_set():
                return
            self.response = str(value or "")
            self.completed.set()

    def cancel(self) -> None:
        self.respond("")


class GUIJobConfirmationBroker:
    """Serialize Job confirmations and marshal dialog ownership to Qt's main thread."""

    def __init__(
        self,
        request_callback: Callable[[GUIJobConfirmationRequest], None],
        cancel_callback: Callable[[str], None],
    ) -> None:
        self._request_callback = request_callback
        self._cancel_callback = cancel_callback
        self._serial = threading.Lock()

    def ask(
        self,
        context: SubAgentJobExecutionContext,
        message: str,
        is_password: bool,
    ) -> str:
        while not self._serial.acquire(timeout=0.1):
            context.raise_if_cancelled()
        request = GUIJobConfirmationRequest(
            job_id=context.job_id,
            agent_name=context.agent_name,
            message=str(message),
            is_password=bool(is_password),
        )
        try:
            context.raise_if_cancelled()
            self._request_callback(request)
            while not request.completed.wait(0.1):
                try:
                    context.raise_if_cancelled()
                except Exception:
                    request.cancel()
                    self._cancel_callback(context.job_id)
                    raise
            context.raise_if_cancelled()
            response = request.response
            return response if response.strip() else "cancel"
        finally:
            self._serial.release()


def initialize_gui_job_runtime(core: object, worker: object) -> SubAgentJobManager:
    """Attach one bounded Job manager to the GUI host process."""
    existing = getattr(core, "_sub_agent_job_manager", None)
    if existing is not None and not getattr(existing, "_closed", False):
        return existing
    session_id = str(getattr(core, "session_id", "") or "gui")
    owner = SubAgentJobOwner(entry_point="gui", session_id=session_id)
    broker = GUIJobConfirmationBroker(
        request_callback=getattr(worker, "sig_job_confirmation_request").emit,
        cancel_callback=getattr(worker, "sig_job_confirmation_cancel").emit,
    )

    def confirmation_handler(
        context: SubAgentJobExecutionContext, message: str, is_password: bool
    ) -> str:
        context.set_waiting_for_user(True)
        try:
            return broker.ask(context, message, is_password)
        finally:
            context.set_waiting_for_user(False)

    manager = SubAgentJobManager(
        notice_callback=getattr(worker, "sig_job_notice").emit,
        confirmation_handler=confirmation_handler,
    )
    setattr(core, "_sub_agent_job_manager", manager)
    setattr(core, "_sub_agent_job_owner", owner)
    setattr(core, "_sub_agent_job_confirmation_broker", broker)
    return manager


def refresh_gui_job_owner(core: object, session_id: str) -> SubAgentJobOwner | None:
    """Update GUI's UI-visible owner when the host session changes."""
    session = str(session_id or "").strip()
    if not session:
        return None
    owner = SubAgentJobOwner(entry_point="gui", session_id=session)
    previous = getattr(core, "_sub_agent_job_owner", None)
    manager = getattr(core, "_sub_agent_job_manager", None)
    if manager is not None and previous is not None and previous != owner:
        try:
            manager.cancel_all(owner=previous, reason="GUI session changed")
            manager.wait_owner_workers(owner=previous, timeout=5.0)
        except Exception:
            pass
    setattr(core, "_sub_agent_job_owner", owner)
    return owner


def shutdown_gui_job_runtime(core: object) -> None:
    manager = getattr(core, "_sub_agent_job_manager", None)
    if manager is None:
        return
    try:
        manager.shutdown()
    finally:
        for attr in (
            "_sub_agent_job_manager",
            "_sub_agent_job_owner",
            "_sub_agent_job_confirmation_broker",
        ):
            try:
                delattr(core, attr)
            except AttributeError:
                pass


__all__ = [
    "GUIJobConfirmationBroker",
    "GUIJobConfirmationRequest",
    "initialize_gui_job_runtime",
    "refresh_gui_job_owner",
    "shutdown_gui_job_runtime",
]
