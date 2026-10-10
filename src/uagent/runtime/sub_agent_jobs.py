"""Bounded, process-local runtime for asynchronous Sub-Agent jobs.

The runtime is deliberately independent of tool/UI registration. Hosts provide a
trusted owner and a worker callback; the callback runs in the ContextVar snapshot
captured at spawn time and receives a cooperative cancellation/deadline context.
"""

from __future__ import annotations

import json
import math
import os
import threading
import time
import uuid
from collections import OrderedDict, deque
from contextvars import Context, ContextVar, copy_context
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from enum import Enum
from typing import Any, Callable

from ..utils.secret_mask import _mask_inline_secrets
from .compaction_record import CompactionValidationError
from .handoff_projection import SourceAccessCheck
from .sub_agent_handoff import SubAgentDispatch
from .sub_agent_receipt import receive_compact_sub_agent_return
from .sub_agent_return import build_compact_sub_agent_return
from .session_store import SessionStore

CURRENT_SUB_AGENT_JOB_ID: ContextVar[str | None] = ContextVar(
    "uagent_current_sub_agent_job_id", default=None
)
CURRENT_SUB_AGENT_JOB_MODE: ContextVar[str | None] = ContextVar(
    "uagent_current_sub_agent_job_mode", default=None
)
CURRENT_SUB_AGENT_JOB_ROOT: ContextVar[str | None] = ContextVar(
    "uagent_current_sub_agent_job_root", default=None
)
_CURRENT_SUB_AGENT_JOB_EXECUTION: ContextVar["SubAgentJobExecutionContext | None"] = (
    ContextVar("uagent_current_sub_agent_job_execution", default=None)
)


class SubAgentJobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_USER = "waiting_for_user"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"

    @property
    def terminal(self) -> bool:
        return self in {
            SubAgentJobState.COMPLETED,
            SubAgentJobState.BLOCKED,
            SubAgentJobState.FAILED,
            SubAgentJobState.CANCELLED,
            SubAgentJobState.TIMED_OUT,
        }


@dataclass(frozen=True)
class SubAgentJobOwner:
    """Trusted lifecycle identity captured by the host, never by an LLM."""

    entry_point: str
    session_id: str
    room_id: str | None = None
    a2a_task_id: str | None = None

    def __post_init__(self) -> None:
        entry_point = str(self.entry_point or "").strip().lower()
        session_id = str(self.session_id or "").strip()
        if not entry_point:
            raise ValueError("owner entry_point is required")
        if not session_id:
            raise ValueError("owner session_id is required")
        object.__setattr__(self, "entry_point", entry_point)
        object.__setattr__(self, "session_id", session_id)
        object.__setattr__(self, "room_id", str(self.room_id or "").strip() or None)
        object.__setattr__(
            self, "a2a_task_id", str(self.a2a_task_id or "").strip() or None
        )


class SubAgentJobCancelled(Exception):
    """Raised by a cooperative worker after its job has been cancelled."""


class SubAgentJobDeadlineExceeded(TimeoutError):
    """Raised by a cooperative worker after its absolute job deadline."""


class SubAgentConfirmationUnavailable(RuntimeError):
    """Raised when a background Job cannot safely obtain human confirmation."""


@dataclass(frozen=True)
class SubAgentJobExecutionContext:
    job_id: str
    agent_name: str
    owner: SubAgentJobOwner
    job_root: Path
    cancel_event: threading.Event
    deadline_at: float | None
    shutdown_deadline: "_ShutdownDeadline"
    event_sink: Callable[[str, str], None]
    confirmation_handler: (
        Callable[["SubAgentJobExecutionContext", str, bool], str] | None
    )
    waiting_sink: Callable[[bool], None]
    initial_messages: deque[dict[str, Any]]
    message_sink: Callable[[], list[dict[str, Any]]]
    handoff_dispatch: SubAgentDispatch | None = None
    handoff_result_sink: Callable[[SubAgentDispatch, str], None] | None = None

    @property
    def effective_deadline_at(self) -> float | None:
        shutdown_deadline = self.shutdown_deadline.get()
        candidates = [
            value
            for value in (self.deadline_at, shutdown_deadline)
            if value is not None
        ]
        return min(candidates) if candidates else None

    @property
    def remaining(self) -> float | None:
        deadline_at = self.effective_deadline_at
        if deadline_at is None:
            return None
        return max(0.0, deadline_at - time.monotonic())

    def raise_if_cancelled(self) -> None:
        if self.cancel_event.is_set():
            raise SubAgentJobCancelled(f"Sub-Agent job {self.job_id} cancelled")
        deadline_at = self.effective_deadline_at
        if deadline_at is not None and time.monotonic() >= deadline_at:
            raise SubAgentJobDeadlineExceeded(
                f"Sub-Agent job {self.job_id} deadline exceeded"
            )

    def record_handoff_result(self, dispatch: SubAgentDispatch, result: str) -> None:
        """Persist the result while the manager serializes Job termination."""
        if dispatch is not self.handoff_dispatch or self.handoff_result_sink is None:
            raise RuntimeError("structured result is not owned by this Job")
        self.handoff_result_sink(dispatch, result)

    def log(self, kind: str, message: str) -> None:
        """Append a bounded, secret-masked event to this Job's private log."""
        self.event_sink(str(kind), str(message))

    def ask_user(self, message: str, *, is_password: bool = False) -> str:
        self.raise_if_cancelled()
        if self.confirmation_handler is None:
            raise SubAgentConfirmationUnavailable(
                "No Job-aware confirmation broker is configured"
            )
        return self.confirmation_handler(self, str(message), bool(is_password))

    def set_waiting_for_user(self, waiting: bool) -> None:
        self.waiting_sink(bool(waiting))

    def drain_messages(self) -> list[dict[str, Any]]:
        messages = list(self.initial_messages)
        self.initial_messages.clear()
        return messages + self.message_sink()


class _ShutdownDeadline:
    """Mutable deadline cell shared with running worker contexts."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._deadline_at: float | None = None

    def set(self, deadline_at: float) -> None:
        with self._lock:
            if self._deadline_at is None or deadline_at < self._deadline_at:
                self._deadline_at = deadline_at

    def get(self) -> float | None:
        with self._lock:
            return self._deadline_at


def get_current_sub_agent_job() -> SubAgentJobExecutionContext | None:
    """Return the cooperative job context, if executing in a background job."""
    return _CURRENT_SUB_AGENT_JOB_EXECUTION.get()


def current_sub_agent_job_id() -> str | None:
    return CURRENT_SUB_AGENT_JOB_ID.get()


def current_sub_agent_job_mode() -> str | None:
    return CURRENT_SUB_AGENT_JOB_MODE.get()


def current_sub_agent_job_root() -> Path | None:
    value = CURRENT_SUB_AGENT_JOB_ROOT.get()
    return Path(value) if value else None


@dataclass(frozen=True)
class SubAgentJobSettings:
    workers: int = 4
    queue_limit: int = 16
    owner_limit: int = 8
    completed_limit: int = 100
    result_ttl_sec: float = 3600.0
    event_limit: int = 1000
    log_max_bytes: int = 1_048_576
    result_max_bytes: int = 1_048_576
    task_max_bytes: int = 65_536
    inbox_limit: int = 100
    inbox_max_bytes: int = 65_536
    message_max_bytes: int = 16_384
    message_round_limit: int = 16
    shared_store_limit: int = 100
    shared_store_max_bytes: int = 16_777_216
    shutdown_timeout_sec: float = 5.0

    def __post_init__(self) -> None:
        for name in (
            "workers",
            "owner_limit",
            "completed_limit",
            "event_limit",
            "shared_store_limit",
        ):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be at least 1")
        if self.queue_limit < 0:
            raise ValueError("queue_limit must be non-negative")
        for name in ("result_ttl_sec", "shutdown_timeout_sec"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        for name in (
            "log_max_bytes",
            "result_max_bytes",
            "task_max_bytes",
            "inbox_limit",
            "inbox_max_bytes",
            "message_max_bytes",
            "message_round_limit",
            "shared_store_max_bytes",
        ):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be at least 1")

    @classmethod
    def from_env(cls) -> "SubAgentJobSettings":
        """Read runtime limits from UAGENT_SUB_AGENT_JOB_* environment variables."""

        def integer(name: str, default: int) -> int:
            try:
                return int(os.environ.get(name, default))
            except (TypeError, ValueError):
                return default

        def seconds(name: str, default: float) -> float:
            try:
                return max(0.0, float(os.environ.get(name, default)))
            except (TypeError, ValueError):
                return default

        return cls(
            workers=max(1, integer("UAGENT_SUB_AGENT_JOB_WORKERS", 4)),
            queue_limit=max(0, integer("UAGENT_SUB_AGENT_JOB_QUEUE_LIMIT", 16)),
            owner_limit=max(1, integer("UAGENT_SUB_AGENT_JOB_OWNER_LIMIT", 8)),
            completed_limit=max(
                1, integer("UAGENT_SUB_AGENT_JOB_COMPLETED_LIMIT", 100)
            ),
            result_ttl_sec=seconds("UAGENT_SUB_AGENT_JOB_RESULT_TTL_SEC", 3600),
            event_limit=max(1, integer("UAGENT_SUB_AGENT_JOB_EVENT_LIMIT", 1000)),
            log_max_bytes=max(
                1, integer("UAGENT_SUB_AGENT_JOB_LOG_MAX_BYTES", 1_048_576)
            ),
            result_max_bytes=max(
                1, integer("UAGENT_SUB_AGENT_JOB_RESULT_MAX_BYTES", 1_048_576)
            ),
            task_max_bytes=max(
                1, integer("UAGENT_SUB_AGENT_JOB_TASK_MAX_BYTES", 65_536)
            ),
            inbox_limit=max(1, integer("UAGENT_SUB_AGENT_JOB_INBOX_LIMIT", 100)),
            inbox_max_bytes=max(
                1, integer("UAGENT_SUB_AGENT_JOB_INBOX_MAX_BYTES", 65_536)
            ),
            message_max_bytes=max(
                1, integer("UAGENT_SUB_AGENT_JOB_MESSAGE_MAX_BYTES", 16_384)
            ),
            message_round_limit=max(
                1, integer("UAGENT_SUB_AGENT_JOB_MESSAGE_ROUND_LIMIT", 16)
            ),
            shared_store_limit=max(
                1, integer("UAGENT_SUB_AGENT_JOB_SHARED_STORE_LIMIT", 100)
            ),
            shared_store_max_bytes=max(
                1, integer("UAGENT_SUB_AGENT_JOB_SHARED_STORE_MAX_BYTES", 16_777_216)
            ),
            shutdown_timeout_sec=seconds("UAGENT_SUB_AGENT_JOB_SHUTDOWN_TIMEOUT", 5),
        )


@dataclass
class _JobEvent:
    sequence: int
    created_at: str
    kind: str
    message: str


@dataclass
class _SubAgentJob:
    job_id: str
    agent_name: str
    task: str
    owner: SubAgentJobOwner
    job_root: Path
    worker: Callable[[SubAgentJobExecutionContext], Any]
    context: Context
    state: SubAgentJobState
    created_monotonic: float
    created_at: str
    deadline_at: float | None
    shutdown_deadline: _ShutdownDeadline = field(default_factory=_ShutdownDeadline)
    cancel_event: threading.Event = field(default_factory=threading.Event)
    started_monotonic: float | None = None
    started_at: str | None = None
    completed_monotonic: float | None = None
    completed_at: str | None = None
    result: str | None = None
    error: str | None = None
    reason: str | None = None
    truncated: bool = False
    orphaned_on_shutdown: bool = False
    events: deque[_JobEvent] = field(default_factory=deque)
    event_bytes: int = 0
    next_event_sequence: int = 1
    inbox: deque[dict[str, Any]] = field(default_factory=deque)
    inbox_bytes: int = 0
    next_message_sequence: int = 1
    continuation_count: int = 0
    store_key: str | None = None
    handoff_dispatch: SubAgentDispatch | None = None
    handoff_result_persisted: bool = False


class SubAgentJobManager:
    """Own a bounded queue and fixed daemon workers for Sub-Agent jobs."""

    def __init__(
        self,
        settings: SubAgentJobSettings | None = None,
        *,
        notice_callback: Callable[[dict[str, Any]], None] | None = None,
        confirmation_handler: (
            Callable[[SubAgentJobExecutionContext, str, bool], str] | None
        ) = None,
        handoff_dispatch_policy: (
            Callable[[SubAgentJobOwner, str, str], SubAgentDispatch] | None
        ) = None,
    ) -> None:
        self.settings = settings or SubAgentJobSettings.from_env()
        self._notice_callback = notice_callback
        self._confirmation_handler = confirmation_handler
        if handoff_dispatch_policy is not None and not callable(
            handoff_dispatch_policy
        ):
            raise TypeError("handoff_dispatch_policy must be callable")
        self._handoff_dispatch_policy = handoff_dispatch_policy
        self._condition = threading.Condition(threading.RLock())
        self._jobs: OrderedDict[str, _SubAgentJob] = OrderedDict()
        self._queue: deque[str] = deque()
        self._closing = False
        self._closed = False
        self._workers: list[threading.Thread] = []
        self._active_worker_jobs: set[str] = set()
        self._active_worker_owners: dict[str, SubAgentJobOwner] = {}
        self._paused_owners: set[SubAgentJobOwner] = set()
        self._shared_store: dict[SubAgentJobOwner, OrderedDict[str, str]] = {}
        self._shared_store_bytes: dict[SubAgentJobOwner, int] = {}
        self._store_reservations: dict[tuple[SubAgentJobOwner, str], str] = {}
        self._maintenance_thread = threading.Thread(
            target=self._maintenance_loop,
            name="uagent-sub-agent-job-maintenance",
            daemon=True,
        )
        for index in range(self.settings.workers):
            thread = threading.Thread(
                target=self._worker_loop,
                name=f"uagent-sub-agent-job-worker-{index + 1}",
                daemon=True,
            )
            self._workers.append(thread)
            thread.start()
        self._maintenance_thread.start()

    @property
    def structured_handoff_enabled(self) -> bool:
        """Whether this host installed a trusted structured handoff policy."""
        return self._handoff_dispatch_policy is not None

    def spawn(
        self,
        *,
        owner: SubAgentJobOwner,
        agent_name: str,
        task: str,
        worker: Callable[[SubAgentJobExecutionContext], Any],
        job_root: str | os.PathLike[str] | None = None,
        timeout: float | None = None,
        store_key: str | None = None,
    ) -> dict[str, Any]:
        """Admit a job, returning immediately or a structured rejection."""
        if not isinstance(owner, SubAgentJobOwner):
            raise TypeError("owner must be a trusted SubAgentJobOwner")
        if not callable(worker):
            raise TypeError("worker must be callable")
        if timeout is not None:
            timeout = float(timeout)
            if not math.isfinite(timeout) or timeout <= 0:
                return {"status": "rejected", "reason": "invalid_timeout"}
        agent_name = str(agent_name or "").strip()
        if not agent_name:
            return {"status": "rejected", "reason": "invalid_agent_name"}
        task_text = _mask_inline_secrets(str(task or ""))
        if (
            len(task_text.encode("utf-8", errors="replace"))
            > self.settings.task_max_bytes
        ):
            return {"status": "rejected", "reason": "task_too_large"}
        normalized_store_key = str(store_key or "").strip() or None
        if (
            normalized_store_key
            and len(normalized_store_key.encode("utf-8", errors="replace")) > 256
        ):
            return {"status": "rejected", "reason": "store_key_too_large"}
        try:
            resolved_job_root = Path(job_root if job_root is not None else os.getcwd())
            resolved_job_root = resolved_job_root.expanduser().resolve(strict=False)
        except (OSError, RuntimeError, TypeError, ValueError):
            return {"status": "rejected", "reason": "invalid_job_root"}

        job_id = "sa_" + uuid.uuid4().hex
        context = copy_context()
        created_at = _utc_now()
        with self._condition:
            self._evict_completed_locked(time.monotonic())
            if self._closing:
                return {"status": "rejected", "reason": "shutting_down"}
            if owner in self._paused_owners:
                return {"status": "rejected", "reason": "owner_transition"}
            if normalized_store_key:
                owner_store = self._shared_store.get(owner, {})
                reservation_key = (owner, normalized_store_key)
                if (
                    normalized_store_key in owner_store
                    or reservation_key in self._store_reservations
                ):
                    return {"status": "rejected", "reason": "store_key_conflict"}
            owner_jobs = [
                job
                for job in self._jobs.values()
                if job.owner == owner and not job.state.terminal
            ]
            if len(owner_jobs) >= self.settings.owner_limit:
                return {"status": "rejected", "reason": "owner_limit"}
            if len(self._queue) >= self.settings.queue_limit:
                return {"status": "rejected", "reason": "queue_full"}
            handoff_dispatch = None
            if self._handoff_dispatch_policy is not None:
                if normalized_store_key:
                    return {
                        "status": "rejected",
                        "reason": "structured_handoff_shared_store_disabled",
                    }
                try:
                    # The host policy must only capture a local, bounded
                    # SessionStore snapshot while the queue lock is held.
                    handoff_dispatch = self._handoff_dispatch_policy(
                        owner, agent_name, str(task or "")
                    )
                except Exception:
                    return {
                        "status": "rejected",
                        "reason": "structured_handoff_capture_failed",
                    }
                if not isinstance(handoff_dispatch, SubAgentDispatch):
                    return {
                        "status": "rejected",
                        "reason": "structured_handoff_capture_failed",
                    }
                if (
                    handoff_dispatch.objective != str(task or "")
                    or handoff_dispatch.bounds.receiving_session_id != owner.session_id
                ):
                    return {
                        "status": "rejected",
                        "reason": "structured_handoff_scope_mismatch",
                    }
                # One captured dispatch belongs to exactly one Job. The
                # check includes terminal Jobs still retained by the manager.
                # The indexed-output check also rejects reuse after eviction,
                # or if a different manager already persisted an output.
                key = (
                    handoff_dispatch.source_session_id,
                    handoff_dispatch.dispatch_id,
                )
                if any(
                    existing.handoff_dispatch is not None
                    and (
                        existing.handoff_dispatch.source_session_id,
                        existing.handoff_dispatch.dispatch_id,
                    )
                    == key
                    for existing in self._jobs.values()
                ):
                    return {
                        "status": "rejected",
                        "reason": "structured_handoff_dispatch_conflict",
                    }
                if isinstance(handoff_dispatch._store, SessionStore):
                    try:
                        previously_saved = handoff_dispatch._result_source(
                            check_owner=False
                        )
                    except Exception:
                        return {
                            "status": "rejected",
                            "reason": "structured_handoff_capture_failed",
                        }
                    if previously_saved is not None:
                        return {
                            "status": "rejected",
                            "reason": "structured_handoff_dispatch_conflict",
                        }
            now = time.monotonic()
            deadline_at = now + timeout if timeout is not None else None
            job = _SubAgentJob(
                job_id=job_id,
                agent_name=agent_name,
                task=task_text,
                owner=owner,
                job_root=resolved_job_root,
                worker=worker,
                context=context,
                state=SubAgentJobState.QUEUED,
                created_monotonic=now,
                created_at=created_at,
                deadline_at=deadline_at,
                store_key=normalized_store_key,
                handoff_dispatch=handoff_dispatch,
            )
            self._jobs[job_id] = job
            self._queue.append(job_id)
            if normalized_store_key:
                self._store_reservations[(owner, normalized_store_key)] = job_id
            self._append_event_locked(job, "accepted", "Job accepted")
            self._condition.notify_all()
        return {"status": "accepted", "job_id": job_id, "agent_name": agent_name}

    def get(self, *, owner: SubAgentJobOwner, job_id: str) -> dict[str, Any]:
        with self._condition:
            self._evict_completed_locked(time.monotonic())
            job = self._authorized_job_locked(owner, job_id)
            if job is None:
                return _not_found()
            return self._snapshot_locked(job)

    def get_compact_handoff_return(
        self,
        *,
        owner: SubAgentJobOwner,
        job_id: str,
        source_access_check: SourceAccessCheck,
        max_bytes: int = 32_000,
    ) -> str | None:
        """Let the trusted host read a finished, indexed Sub-Agent return.

        This read-only API is not a model/tool action. Missing, unauthorized,
        unfinished, legacy and unpersisted jobs all return None. The caller
        must supply a current source-access check; a successful read does not
        deliver or apply a state delta to Main. Results are not consumed, so
        an eventual receiver must deduplicate root handoff IDs durably.
        """
        with self._condition:
            self._evict_completed_locked(time.monotonic())
            job = self._authorized_job_locked(owner, job_id)
            if (
                job is None
                or not job.state.terminal
                or not job.handoff_result_persisted
                or job.handoff_dispatch is None
            ):
                return None
            dispatch = job.handoff_dispatch
            role = job.agent_name

        # No Job-manager lock during SQLite access or host authorization.
        # Terminal persistence and cancellation were serialized at publication.
        return build_compact_sub_agent_return(
            dispatch,
            agent_role=role,
            source_access_check=source_access_check,
            max_bytes=max_bytes,
        )

    def deliver_compact_handoff_to_main(
        self,
        *,
        owner: SubAgentJobOwner,
        job_id: str,
        source_access_check: SourceAccessCheck,
        max_bytes: int = 32_000,
    ) -> dict[str, Any] | None:
        """Host-only delivery of a finished Job's evidence to Main's receipt log.

        Owner checks happen before source inspection. Only the same Job's
        persisted child output can be delivered; a plain, unfinished,
        cancelled, unpersisted or unknown Job returns None. The receiving
        transaction rechecks scope, revision and source grants, and rejects
        stale or forged returns. Delivery never changes Main AgentState,
        Memory, or Goal completion, nor acknowledges the Job notification.
        """
        with self._condition:
            self._evict_completed_locked(time.monotonic())
            job = self._authorized_job_locked(owner, job_id)
            if (
                job is None
                or not job.state.terminal
                or not job.handoff_result_persisted
                or job.handoff_dispatch is None
            ):
                return None
            dispatch = job.handoff_dispatch
            role = job.agent_name
            trusted_job_id = job.job_id

        # Do not keep the Job lock while invoking SQLite or host permissions.
        # This separate check prevents a Job from adopting an output produced
        # by another Job, including one using the same dispatch elsewhere.
        if dispatch._result_source(job_id=trusted_job_id) is None:
            raise CompactionValidationError(
                "persisted Sub-Agent Job output is unavailable"
            )
        return receive_compact_sub_agent_return(
            dispatch,
            agent_role=role,
            source_access_check=source_access_check,
            max_bytes=max_bytes,
            expected_job_id=trusted_job_id,
        )

    def record_event(
        self, *, owner: SubAgentJobOwner, job_id: str, kind: str, message: str
    ) -> bool:
        """Append an event to the authorized, non-terminal Job's bounded log."""
        with self._condition:
            job = self._authorized_job_locked(owner, job_id)
            if job is None or job.state.terminal:
                return False
            self._append_event_locked(job, kind, message)
            return True

    def send_message(
        self, *, owner: SubAgentJobOwner, job_id: str, message: str
    ) -> dict[str, Any]:
        text = str(message or "")
        if not text.strip():
            return {"status": "rejected", "reason": "empty_message"}
        message_bytes = len(text.encode("utf-8", errors="replace"))
        if message_bytes > self.settings.message_max_bytes:
            return {"status": "rejected", "reason": "message_too_large"}
        with self._condition:
            job = self._authorized_job_locked(owner, job_id)
            if job is None:
                return _not_found()
            if job.state not in {
                SubAgentJobState.RUNNING,
                SubAgentJobState.WAITING_FOR_USER,
            }:
                return {"status": "rejected", "reason": "job_not_running"}
            if job.handoff_dispatch is not None:
                return {
                    "status": "rejected",
                    "reason": "structured_handoff_requires_new_dispatch",
                }
            if job.continuation_count >= self.settings.message_round_limit:
                return {"status": "rejected", "reason": "message_round_limit"}
            if len(job.inbox) >= self.settings.inbox_limit:
                return {"status": "rejected", "reason": "inbox_full"}
            if job.inbox_bytes + message_bytes > self.settings.inbox_max_bytes:
                return {"status": "rejected", "reason": "inbox_full"}
            sequence = job.next_message_sequence
            job.next_message_sequence += 1
            job.inbox.append({"sequence": sequence, "message": text})
            job.inbox_bytes += message_bytes
            self._append_event_locked(
                job,
                "message_accepted",
                f"Main Agent message accepted (sequence {sequence})",
            )
            self._condition.notify_all()
            return {"status": "accepted", "job_id": job_id, "sequence": sequence}

    def _drain_messages(self, job_id: str) -> list[dict[str, Any]]:
        with self._condition:
            job = self._jobs.get(job_id)
            if job is None or job.state.terminal:
                return []
            messages = list(job.inbox)
            job.inbox.clear()
            if messages:
                job.inbox_bytes = max(
                    0,
                    job.inbox_bytes
                    - sum(
                        len(item["message"].encode("utf-8", errors="replace"))
                        for item in messages
                    ),
                )
                job.continuation_count += 1
                self._append_event_locked(
                    job,
                    "message_delivered",
                    f"Delivered {len(messages)} Main Agent message(s) to the worker",
                )
            return messages

    def load_shared_results(
        self, *, owner: SubAgentJobOwner, keys: list[str]
    ) -> tuple[dict[str, str], list[str]]:
        """Load only completed shared results belonging to one immutable owner."""
        with self._condition:
            store = self._shared_store.get(owner, OrderedDict())
            found: dict[str, str] = {}
            missing: list[str] = []
            for key in keys:
                normalized = str(key or "").strip()
                if not normalized or normalized not in store:
                    missing.append(normalized)
                    continue
                found[normalized] = store[normalized]
                store.move_to_end(normalized)
            return found, missing

    def _set_waiting_for_user(self, job_id: str, waiting: bool) -> None:
        with self._condition:
            job = self._jobs.get(job_id)
            if job is None or job.state.terminal:
                return
            if waiting and job.state == SubAgentJobState.RUNNING:
                job.state = SubAgentJobState.WAITING_FOR_USER
            elif not waiting and job.state == SubAgentJobState.WAITING_FOR_USER:
                job.state = SubAgentJobState.RUNNING
            else:
                return
            self._append_event_locked(
                job, "waiting_for_user" if waiting else "resumed", "User confirmation"
            )
            self._condition.notify_all()

    def wait(
        self,
        *,
        owner: SubAgentJobOwner,
        job_id: str,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        wait_deadline = None if timeout is None else time.monotonic() + max(0, timeout)
        with self._condition:
            self._evict_completed_locked(time.monotonic())
            job = self._authorized_job_locked(owner, job_id)
            if job is None:
                return _not_found()
            while not job.state.terminal:
                self._evict_completed_locked(time.monotonic())
                if job.state.terminal:
                    break
                if wait_deadline is None:
                    self._condition.wait()
                else:
                    remaining = wait_deadline - time.monotonic()
                    if remaining <= 0:
                        snapshot = self._snapshot_locked(job)
                        snapshot["wait_timed_out"] = True
                        return snapshot
                    self._condition.wait(remaining)
            return self._snapshot_locked(job)

    def cancel(
        self, *, owner: SubAgentJobOwner, job_id: str, reason: str = "cancelled"
    ) -> dict[str, Any]:
        notice = None
        with self._condition:
            self._evict_completed_locked(time.monotonic())
            job = self._authorized_job_locked(owner, job_id)
            if job is None:
                return _not_found()
            if job.state.terminal:
                snapshot = self._snapshot_locked(job)
                snapshot["cancel_noop"] = True
                return snapshot
            job.cancel_event.set()
            job.reason = _bounded_text(_mask_inline_secrets(reason), 1024)
            if job.state == SubAgentJobState.QUEUED:
                self._remove_queued_locked(job_id)
                self._finish_locked(job, SubAgentJobState.CANCELLED)
            else:
                job.state = SubAgentJobState.CANCELLED
                self._finish_locked(job, SubAgentJobState.CANCELLED)
            self._append_event_locked(job, "cancelled", job.reason)
            notice = self._notice_locked(job, "finished")
            self._condition.notify_all()
            snapshot = self._snapshot_locked(job)
        self._dispatch_notice(notice)
        return snapshot

    def get_events(
        self, *, owner: SubAgentJobOwner, job_id: str, after: int = 0
    ) -> dict[str, Any]:
        with self._condition:
            self._evict_completed_locked(time.monotonic())
            job = self._authorized_job_locked(owner, job_id)
            if job is None:
                return _not_found()
            return {
                "job_id": job_id,
                "events": [
                    {
                        "sequence": event.sequence,
                        "created_at": event.created_at,
                        "kind": event.kind,
                        "message": event.message,
                    }
                    for event in job.events
                    if event.sequence > max(0, after)
                ],
                "truncated": job.truncated,
            }

    def running_count(self, *, owner: SubAgentJobOwner) -> int:
        with self._condition:
            self._evict_completed_locked(time.monotonic())
            return sum(
                job.state
                in {
                    SubAgentJobState.QUEUED,
                    SubAgentJobState.RUNNING,
                    SubAgentJobState.WAITING_FOR_USER,
                }
                and job.owner == owner
                for job in self._jobs.values()
            )

    def pause_owner(self, owner: SubAgentJobOwner) -> None:
        """Atomically prevent new admissions for one lifecycle owner."""
        with self._condition:
            self._paused_owners.add(owner)
            self._condition.notify_all()

    def resume_owner(self, owner: SubAgentJobOwner) -> None:
        with self._condition:
            self._paused_owners.discard(owner)
            self._condition.notify_all()

    def wait_owner_workers(
        self, owner: SubAgentJobOwner, timeout: float | None = None
    ) -> bool:
        """Wait until callbacks owned by ``owner`` have actually exited."""
        deadline = None if timeout is None else time.monotonic() + max(0.0, timeout)
        with self._condition:
            while owner in self._active_worker_owners.values():
                if deadline is None:
                    self._condition.wait()
                    continue
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(remaining)
            return True

    def active_job_ids(self, owner: SubAgentJobOwner) -> list[str]:
        with self._condition:
            return [
                job_id
                for job_id, job_owner in self._active_worker_owners.items()
                if job_owner == owner
            ]

    def summary(self, *, owner: SubAgentJobOwner) -> list[dict[str, Any]]:
        with self._condition:
            self._evict_completed_locked(time.monotonic())
            return [
                {
                    "job_id": job.job_id,
                    "agent_name": job.agent_name,
                    "state": job.state.value,
                    "created_at": job.created_at,
                    "updated_at": job.completed_at or job.started_at or job.created_at,
                }
                for job in self._jobs.values()
                if job.owner == owner
            ]

    def cancel_all(
        self, *, owner: SubAgentJobOwner | None = None, reason: str = "shutdown"
    ) -> int:
        cancelled = 0
        notices: list[dict[str, Any]] = []
        with self._condition:
            for job in tuple(self._jobs.values()):
                if job.state.terminal or (owner is not None and job.owner != owner):
                    continue
                job.cancel_event.set()
                job.reason = _bounded_text(_mask_inline_secrets(reason), 1024)
                if job.state == SubAgentJobState.QUEUED:
                    self._remove_queued_locked(job.job_id)
                self._finish_locked(job, SubAgentJobState.CANCELLED)
                self._append_event_locked(job, "cancelled", job.reason)
                notices.append(self._notice_locked(job, "finished"))
                cancelled += 1
            self._condition.notify_all()
        for notice in notices:
            self._dispatch_notice(notice)
        return cancelled

    def shutdown(self, timeout: float | None = None) -> list[str]:
        """Stop admission, cancel work, and boundedly join daemon workers.

        Returns job IDs whose worker callbacks did not exit before the deadline.
        """
        grace = (
            self.settings.shutdown_timeout_sec
            if timeout is None
            else max(0.0, float(timeout))
        )
        with self._condition:
            if self._closed:
                return []
            self._closing = True
            shutdown_deadline = time.monotonic() + grace
            for job in self._jobs.values():
                if job.state == SubAgentJobState.RUNNING:
                    job.shutdown_deadline.set(shutdown_deadline)
            self.cancel_all(reason="runtime shutdown")
            self._condition.notify_all()
        deadline = time.monotonic() + grace
        for thread in self._workers:
            thread.join(max(0.0, deadline - time.monotonic()))
        self._maintenance_thread.join(max(0.0, deadline - time.monotonic()))
        with self._condition:
            self._closed = True
            lingering = sorted(self._active_worker_jobs)
            for job_id in lingering:
                job = self._jobs.get(job_id)
                if job is not None:
                    self._append_event_locked(
                        job,
                        "orphaned_on_shutdown",
                        "Worker exceeded shutdown grace period",
                    )
                    job.orphaned_on_shutdown = True
            self._condition.notify_all()
        return lingering

    def _worker_loop(self) -> None:
        while True:
            notice: dict[str, Any] | None = None
            with self._condition:
                job: _SubAgentJob | None = None
                while job is None:
                    if self._closing and not self._queue:
                        return
                    if self._queue:
                        job_id = self._queue.popleft()
                        candidate = self._jobs.get(job_id)
                        if (
                            candidate is None
                            or candidate.state != SubAgentJobState.QUEUED
                        ):
                            continue
                        if (
                            candidate.deadline_at is not None
                            and time.monotonic() >= candidate.deadline_at
                        ):
                            candidate.cancel_event.set()
                            candidate.reason = "deadline exceeded while queued"
                            self._finish_locked(candidate, SubAgentJobState.TIMED_OUT)
                            self._append_event_locked(
                                candidate, "timed_out", candidate.reason
                            )
                            notice = self._notice_locked(candidate, "finished")
                            self._condition.notify_all()
                            break
                        job = candidate
                        job.state = SubAgentJobState.RUNNING
                        job.started_monotonic = time.monotonic()
                        job.started_at = _utc_now()
                        self._active_worker_jobs.add(job.job_id)
                        self._active_worker_owners[job.job_id] = job.owner
                        self._append_event_locked(job, "started", "Job started")
                        notice = self._notice_locked(job, "started")
                        self._condition.notify_all()
                        break
                    self._condition.wait()
            if notice is not None:
                self._dispatch_notice(notice)
            if job is None:
                continue
            try:
                self._execute_job(job)
            finally:
                with self._condition:
                    self._active_worker_jobs.discard(job.job_id)
                    self._active_worker_owners.pop(job.job_id, None)
                    self._condition.notify_all()

    def _execute_job(self, job: _SubAgentJob) -> None:
        while True:
            with self._condition:
                if job.state.terminal:
                    return
                if job.cancel_event.is_set():
                    terminal = (
                        SubAgentJobState.TIMED_OUT
                        if job.deadline_at is not None
                        and time.monotonic() >= job.deadline_at
                        else SubAgentJobState.CANCELLED
                    )
                    job.reason = (
                        "deadline exceeded"
                        if terminal == SubAgentJobState.TIMED_OUT
                        else "cancelled"
                    )
                    self._finish_locked(job, terminal)
                    self._append_event_locked(job, terminal.value, job.reason)
                    notice = self._notice_locked(job, "finished")
                    self._condition.notify_all()
                    initial_messages: list[dict[str, Any]] = []
                    already_terminal = True
                else:
                    initial_messages = list(job.inbox)
                    job.inbox.clear()
                    job.inbox_bytes = 0
                    if initial_messages:
                        self._append_event_locked(
                            job,
                            "message_delivered",
                            f"Worker received {len(initial_messages)} Main Agent message(s)",
                        )
                    already_terminal = False
                    execution = SubAgentJobExecutionContext(
                        job_id=job.job_id,
                        agent_name=job.agent_name,
                        owner=job.owner,
                        job_root=job.job_root,
                        cancel_event=job.cancel_event,
                        deadline_at=job.deadline_at,
                        shutdown_deadline=job.shutdown_deadline,
                        event_sink=lambda kind, message: self.record_event(
                            owner=job.owner,
                            job_id=job.job_id,
                            kind=kind,
                            message=message,
                        ),
                        confirmation_handler=self._confirmation_handler,
                        waiting_sink=lambda waiting: self._set_waiting_for_user(
                            job.job_id, waiting
                        ),
                        message_sink=lambda: self._drain_messages(job.job_id),
                        initial_messages=deque(initial_messages),
                        handoff_dispatch=job.handoff_dispatch,
                        handoff_result_sink=lambda dispatch, result: self._record_handoff_result(
                            job, dispatch, result
                        ),
                    )

            if already_terminal:
                self._dispatch_notice(notice)
                return

            def invoke() -> Any:
                id_token = CURRENT_SUB_AGENT_JOB_ID.set(job.job_id)
                mode_token = CURRENT_SUB_AGENT_JOB_MODE.set("background")
                root_token = CURRENT_SUB_AGENT_JOB_ROOT.set(str(job.job_root))
                execution_token = _CURRENT_SUB_AGENT_JOB_EXECUTION.set(execution)
                try:
                    execution.raise_if_cancelled()
                    return job.worker(execution)
                finally:
                    _CURRENT_SUB_AGENT_JOB_EXECUTION.reset(execution_token)
                    CURRENT_SUB_AGENT_JOB_ROOT.reset(root_token)
                    CURRENT_SUB_AGENT_JOB_MODE.reset(mode_token)
                    CURRENT_SUB_AGENT_JOB_ID.reset(id_token)

            try:
                raw_result = job.context.run(invoke)
                result_text = (
                    raw_result
                    if isinstance(raw_result, str)
                    else json.dumps(raw_result, ensure_ascii=False, default=str)
                )
                inferred_state = _infer_terminal_state(result_text)
            except SubAgentJobDeadlineExceeded as exc:
                self._finish_from_exception(job, SubAgentJobState.TIMED_OUT, exc)
                return
            except SubAgentJobCancelled as exc:
                self._finish_from_exception(job, SubAgentJobState.CANCELLED, exc)
                return
            except BaseException as exc:  # Keep a worker failure from killing the pool.
                self._finish_from_exception(job, SubAgentJobState.FAILED, exc)
                return

            with self._condition:
                if job.state.terminal:
                    return
                if job.cancel_event.is_set():
                    terminal = (
                        SubAgentJobState.TIMED_OUT
                        if execution.effective_deadline_at is not None
                        and time.monotonic() >= execution.effective_deadline_at
                        else SubAgentJobState.CANCELLED
                    )
                    job.reason = (
                        "deadline exceeded"
                        if terminal == SubAgentJobState.TIMED_OUT
                        else "cancelled"
                    )
                    self._finish_locked(job, terminal)
                    self._append_event_locked(job, terminal.value, job.reason)
                    should_continue = False
                elif job.inbox:
                    if job.continuation_count >= self.settings.message_round_limit:
                        job.reason = "Main Agent message round limit reached"
                        job.result = json.dumps(
                            {"status": "blocked", "reason": "message_round_limit"},
                            ensure_ascii=False,
                        )
                        self._finish_locked(job, SubAgentJobState.BLOCKED)
                        self._append_event_locked(
                            job, "blocked", "Main Agent message round limit reached"
                        )
                        should_continue = False
                    else:
                        job.continuation_count += 1
                        self._append_event_locked(
                            job,
                            "message_continue",
                            f"Continuing for Main Agent messages (round {job.continuation_count})",
                        )
                        should_continue = True
                else:
                    job.result, was_truncated = _bounded_result(
                        _mask_inline_secrets(result_text),
                        self.settings.result_max_bytes,
                    )
                    job.truncated = job.truncated or was_truncated
                    if inferred_state == SubAgentJobState.COMPLETED and job.store_key:
                        store_error = self._publish_shared_result_locked(
                            job, _mask_inline_secrets(result_text)
                        )
                        if store_error:
                            job.reason = store_error
                            inferred_state = SubAgentJobState.BLOCKED
                    self._finish_locked(job, inferred_state)
                    self._append_event_locked(job, job.state.value, "Job finished")
                    should_continue = False
                self._condition.notify_all()
                notice = (
                    None if should_continue else self._notice_locked(job, "finished")
                )

            if should_continue:
                continue
            self._dispatch_notice(notice)
            return

    def _record_handoff_result(
        self, job: _SubAgentJob, dispatch: SubAgentDispatch, result: str
    ) -> None:
        """Persist and finish a structured Job atomically against cancellation."""
        with self._condition:
            if job.handoff_dispatch is not dispatch:
                raise RuntimeError("structured result is not owned by this Job")
            deadline_candidates = [
                value
                for value in (job.deadline_at, job.shutdown_deadline.get())
                if value is not None
            ]
            deadline_at = min(deadline_candidates) if deadline_candidates else None
            now = time.monotonic()
            if job.state.terminal or job.cancel_event.is_set():
                if deadline_at is not None and now >= deadline_at:
                    raise SubAgentJobDeadlineExceeded(
                        f"Sub-Agent job {job.job_id} deadline exceeded"
                    )
                raise SubAgentJobCancelled(f"Sub-Agent job {job.job_id} cancelled")
            if deadline_at is not None and now >= deadline_at:
                raise SubAgentJobDeadlineExceeded(
                    f"Sub-Agent job {job.job_id} deadline exceeded"
                )

            # Cancellation and timeout transitions use the same condition.
            # Holding it through persistence makes either termination or
            # successful result publication win as one serialized operation.
            dispatch.record_result(result, job_id=job.job_id)
            job.handoff_result_persisted = True
            job.result, was_truncated = _bounded_result(
                _mask_inline_secrets(result), self.settings.result_max_bytes
            )
            job.truncated = job.truncated or was_truncated
            state = _infer_terminal_state(result)
            self._finish_locked(job, state)
            self._append_event_locked(job, job.state.value, "Job finished")
            self._condition.notify_all()
            notice = self._notice_locked(job, "finished")
        self._dispatch_notice(notice)

    def _finish_from_exception(
        self, job: _SubAgentJob, state: SubAgentJobState, exc: BaseException
    ) -> None:
        with self._condition:
            if job.state.terminal:
                return
            job.error, was_truncated = _bounded_result(
                _mask_inline_secrets(f"{type(exc).__name__}: {exc}"),
                self.settings.result_max_bytes,
            )
            job.truncated = job.truncated or was_truncated
            self._finish_locked(job, state)
            self._append_event_locked(job, state.value, job.error or "Job failed")
            notice = self._notice_locked(job, "finished")
            self._condition.notify_all()
        self._dispatch_notice(notice)

    def _maintenance_loop(self) -> None:
        while True:
            notices: list[dict[str, Any]] = []
            with self._condition:
                if self._closing:
                    return
                now = time.monotonic()
                self._evict_completed_locked(now)
                for job in tuple(self._jobs.values()):
                    if job.state.terminal or job.deadline_at is None:
                        continue
                    if now < job.deadline_at:
                        continue
                    job.cancel_event.set()
                    job.reason = "absolute job deadline exceeded"
                    if job.state == SubAgentJobState.QUEUED:
                        self._remove_queued_locked(job.job_id)
                    self._finish_locked(job, SubAgentJobState.TIMED_OUT)
                    self._append_event_locked(job, "timed_out", job.reason)
                    notices.append(self._notice_locked(job, "finished"))
                self._condition.notify_all()
                self._condition.wait(0.05)
            for notice in notices:
                self._dispatch_notice(notice)

    def _authorized_job_locked(
        self, owner: SubAgentJobOwner, job_id: str
    ) -> _SubAgentJob | None:
        job = self._jobs.get(str(job_id))
        if job is None or job.owner != owner:
            return None
        return job

    def _notice_locked(self, job: _SubAgentJob, event: str) -> dict[str, Any]:
        elapsed = None
        if job.started_monotonic is not None:
            ended = job.completed_monotonic or time.monotonic()
            elapsed = max(0.0, ended - job.started_monotonic)
        return {
            "event": event,
            "job_id": job.job_id,
            "agent_name": job.agent_name,
            "state": job.state.value,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "elapsed_sec": elapsed,
            "reason": job.reason,
            "owner": {
                "entry_point": job.owner.entry_point,
                "session_id": job.owner.session_id,
                "room_id": job.owner.room_id,
                "a2a_task_id": job.owner.a2a_task_id,
            },
        }

    def _dispatch_notice(self, notice: dict[str, Any] | None) -> None:
        callback = self._notice_callback
        if callback is None or notice is None:
            return
        try:
            callback(dict(notice))
        except Exception:
            pass

    def _snapshot_locked(self, job: _SubAgentJob) -> dict[str, Any]:
        result: dict[str, Any] = {
            "job_id": job.job_id,
            "state": job.state.value,
            "agent_name": job.agent_name,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "truncated": job.truncated,
            "orphaned_on_shutdown": job.orphaned_on_shutdown,
        }
        if job.result is not None:
            result["result"] = job.result
        if job.error is not None:
            result["error"] = job.error
        if job.reason is not None:
            result["reason"] = job.reason
        if job.deadline_at is not None:
            result["remaining"] = max(0.0, job.deadline_at - time.monotonic())
        return result

    def _append_event_locked(self, job: _SubAgentJob, kind: str, message: str) -> None:
        text, truncated = _bounded_result(
            _mask_inline_secrets(str(message)), self.settings.log_max_bytes
        )
        job.truncated = job.truncated or truncated
        event = _JobEvent(
            sequence=job.next_event_sequence,
            created_at=_utc_now(),
            kind=str(kind)[:64],
            message=text,
        )
        job.next_event_sequence += 1
        job.events.append(event)
        job.event_bytes += len(text.encode("utf-8"))
        while (
            len(job.events) > self.settings.event_limit
            or job.event_bytes > self.settings.log_max_bytes
        ):
            dropped = job.events.popleft()
            job.event_bytes -= len(dropped.message.encode("utf-8"))
            job.truncated = True

    def _release_store_reservation_locked(self, job: _SubAgentJob) -> None:
        if job.store_key:
            self._store_reservations.pop((job.owner, job.store_key), None)

    def _publish_shared_result_locked(
        self, job: _SubAgentJob, result: str
    ) -> str | None:
        if not job.store_key:
            return None
        encoded_size = len(result.encode("utf-8", errors="replace"))
        if encoded_size > self.settings.shared_store_max_bytes:
            return "shared_store_result_too_large"
        store = self._shared_store.setdefault(job.owner, OrderedDict())
        if job.store_key in store:
            return "store_key_conflict"
        total_bytes = self._shared_store_bytes.get(job.owner, 0)
        while store and (
            len(store) >= self.settings.shared_store_limit
            or total_bytes + encoded_size > self.settings.shared_store_max_bytes
        ):
            _old_key, old_value = store.popitem(last=False)
            total_bytes -= len(old_value.encode("utf-8", errors="replace"))
        if total_bytes + encoded_size > self.settings.shared_store_max_bytes:
            return "shared_store_full"
        store[job.store_key] = result
        self._shared_store_bytes[job.owner] = total_bytes + encoded_size
        self._release_store_reservation_locked(job)
        return None

    def _finish_locked(self, job: _SubAgentJob, state: SubAgentJobState) -> None:
        if job.state.terminal:
            return
        job.state = state
        job.completed_monotonic = time.monotonic()
        job.completed_at = _utc_now()
        self._jobs.move_to_end(job.job_id)
        self._release_store_reservation_locked(job)
        self._evict_completed_locked(job.completed_monotonic)

    def _remove_queued_locked(self, job_id: str) -> None:
        if not self._queue:
            return
        self._queue = deque(item for item in self._queue if item != job_id)

    def _evict_completed_locked(self, now: float) -> None:
        terminal = [job for job in self._jobs.values() if job.state.terminal]
        ttl = self.settings.result_ttl_sec
        if ttl > 0:
            for job in terminal:
                if (
                    job.completed_monotonic is not None
                    and now - job.completed_monotonic >= ttl
                ):
                    self._jobs.pop(job.job_id, None)
        terminal = [job for job in self._jobs.values() if job.state.terminal]
        excess = len(terminal) - self.settings.completed_limit
        for job in terminal[: max(0, excess)]:
            self._jobs.pop(job.job_id, None)


def _infer_terminal_state(result: str) -> SubAgentJobState:
    try:
        parsed = json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return SubAgentJobState.COMPLETED
    if not isinstance(parsed, dict):
        return SubAgentJobState.COMPLETED
    status = str(parsed.get("status", "")).strip().lower()
    if status == "blocked":
        return SubAgentJobState.BLOCKED
    if status == "error":
        return SubAgentJobState.FAILED
    return SubAgentJobState.COMPLETED


def _bounded_result(value: str, max_bytes: int) -> tuple[str, bool]:
    encoded = str(value).encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return str(value), False
    marker = "\n[truncated]"
    marker_bytes = marker.encode("utf-8")
    clipped = encoded[: max(0, max_bytes - len(marker_bytes))]
    while clipped:
        try:
            text = clipped.decode("utf-8")
            break
        except UnicodeDecodeError as exc:
            clipped = clipped[: exc.start]
    else:
        text = ""
    if max_bytes < len(marker_bytes):
        return marker[:max_bytes], True
    return text + marker, True


def _bounded_text(value: str, max_bytes: int) -> str:
    return _bounded_result(value, max_bytes)[0]


def _not_found() -> dict[str, Any]:
    # Same response for unknown IDs and owner mismatches prevents enumeration.
    return {"status": "error", "reason": "not_found"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "CURRENT_SUB_AGENT_JOB_ID",
    "CURRENT_SUB_AGENT_JOB_MODE",
    "CURRENT_SUB_AGENT_JOB_ROOT",
    "SubAgentJobCancelled",
    "SubAgentConfirmationUnavailable",
    "SubAgentJobDeadlineExceeded",
    "SubAgentJobExecutionContext",
    "SubAgentJobManager",
    "SubAgentJobOwner",
    "SubAgentJobSettings",
    "SubAgentJobState",
    "current_sub_agent_job_id",
    "current_sub_agent_job_mode",
    "current_sub_agent_job_root",
    "get_current_sub_agent_job",
]
