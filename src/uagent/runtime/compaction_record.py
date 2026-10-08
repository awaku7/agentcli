"""Provider-neutral Structured Compaction record models.

This module defines and validates the in-memory schema only. It does not call
providers, mutate AgentState, or persist records; those behaviors are added by
later runtime layers.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Literal, Mapping, TypeVar

ApplicationStatus = Literal["applied", "comparison_only"]
GoalAssociation = Literal["existing", "new", "ambiguous"]
DecisionStatus = Literal["active", "superseded", "reverted", "tentative"]
ConstraintStatus = Literal["active", "superseded", "revoked", "tentative"]
SourceKind = Literal[
    "message",
    "event",
    "tool_call",
    "tool_result",
    "execution",
    "artifact",
    "checkpoint",
    "handoff",
    "subagent",
    "pending_operation",
]
TrackingDimension = Literal[
    "file_reads", "file_writes", "commands", "tests", "artifacts"
]
TrackingStatus = Literal["complete", "partial", "unavailable"]
TRACKING_DIMENSIONS = ("file_reads", "file_writes", "commands", "tests", "artifacts")

SCHEMA_VERSION = 1
MAX_ITEMS_PER_SECTION = 50
MAX_TEXT_CHARS = 16_000
MAX_RECORD_JSON_BYTES = 1_000_000


class CompactionValidationError(ValueError):
    """Raised when a Structured Compaction payload violates its schema."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any, name: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise CompactionValidationError(f"{name} must be a string")
    if len(value) > MAX_TEXT_CHARS:
        raise CompactionValidationError(f"{name} exceeds {MAX_TEXT_CHARS} characters")
    if not value.strip() and not optional:
        raise CompactionValidationError(f"{name} must not be empty")
    return value


def _choice(value: Any, name: str, choices: set[str]) -> str:
    if not isinstance(value, str) or value not in choices:
        raise CompactionValidationError(f"invalid {name}")
    return value


def _nonnegative_int(value: Any, name: str, *, optional: bool = False) -> int | None:
    if value is None and optional:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CompactionValidationError(f"{name} must be a non-negative integer")
    return value


def _text_tuple(
    value: Any,
    name: str,
    *,
    allow_empty_items: bool = False,
    require_one: bool = False,
) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)):
        raise CompactionValidationError(f"{name} must be a list or tuple")
    if len(value) > MAX_ITEMS_PER_SECTION:
        raise CompactionValidationError(f"{name} exceeds {MAX_ITEMS_PER_SECTION} items")
    items = tuple(
        _text(item, f"{name}[{index}]", optional=allow_empty_items)
        for index, item in enumerate(value)
    )
    # Preserve source order while removing repeated references/paths.
    unique_items = tuple(dict.fromkeys(items))
    if require_one and not unique_items:
        raise CompactionValidationError(f"{name} must contain at least one item")
    return unique_items  # type: ignore[return-value]


def _object_tuple(value: Any, name: str, expected_type: type) -> tuple[Any, ...]:
    if not isinstance(value, (tuple, list)):
        raise CompactionValidationError(f"{name} must be a list or tuple")
    if len(value) > MAX_ITEMS_PER_SECTION:
        raise CompactionValidationError(f"{name} exceeds {MAX_ITEMS_PER_SECTION} items")
    if any(not isinstance(item, expected_type) for item in value):
        raise CompactionValidationError(
            f"every item in {name} must be {expected_type.__name__}"
        )
    return tuple(value)


def _source_ref_tuple(
    value: Any, name: str, *, require_one: bool = False
) -> tuple[SourceRef, ...]:
    refs = _object_tuple(value, name, SourceRef)
    if require_one and not refs:
        raise CompactionValidationError(f"{name} must contain at least one SourceRef")
    return refs


def _freeze_json(value: Any, name: str) -> Any:
    """Copy JSON values into immutable containers and reject non-JSON values."""
    if value is None or isinstance(value, (str, bool, int)):
        if isinstance(value, str) and len(value) > MAX_TEXT_CHARS:
            raise CompactionValidationError(f"{name} contains an oversized string")
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CompactionValidationError(f"{name} contains a non-finite number")
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise CompactionValidationError(f"{name} keys must be strings")
            frozen[key] = _freeze_json(item, f"{name}.{key}")
        return MappingProxyType(frozen)
    if isinstance(value, (tuple, list)):
        if len(value) > MAX_ITEMS_PER_SECTION:
            raise CompactionValidationError(
                f"{name} exceeds {MAX_ITEMS_PER_SECTION} items"
            )
        return tuple(
            _freeze_json(item, f"{name}[{index}]") for index, item in enumerate(value)
        )
    raise CompactionValidationError(f"{name} must contain JSON-compatible values")


def _to_json_value(value: Any) -> Any:
    if is_dataclass(value):
        return {
            item.name: _to_json_value(getattr(value, item.name))
            for item in fields(value)
        }
    if isinstance(value, Mapping):
        return {key: _to_json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_to_json_value(item) for item in value]
    return value


T = TypeVar("T")


def _decode_nested(nested_type: type, value: Any) -> Any:
    if isinstance(value, nested_type):
        return value
    decoder = getattr(nested_type, "from_dict", None)
    if callable(decoder):
        return decoder(value)
    return _decode_dataclass(nested_type, value)


def _decode_dataclass(
    record_type: type[T],
    value: Any,
    *,
    nested: Mapping[str, type] | None = None,
) -> T:
    if not isinstance(value, dict):
        raise CompactionValidationError(f"{record_type.__name__} must be an object")
    known_fields = {item.name for item in fields(record_type)}
    unknown_fields = set(value) - known_fields
    if unknown_fields:
        raise CompactionValidationError(
            f"unknown {record_type.__name__} fields: {sorted(unknown_fields)}"
        )

    kwargs = dict(value)
    for name, nested_type in (nested or {}).items():
        if name not in kwargs:
            continue
        raw_value = kwargs[name]
        if isinstance(raw_value, nested_type):
            continue
        if isinstance(raw_value, dict):
            kwargs[name] = _decode_nested(nested_type, raw_value)
            continue
        if not isinstance(raw_value, (tuple, list)):
            raise CompactionValidationError(f"{name} must be an object, list, or tuple")
        if len(raw_value) > MAX_ITEMS_PER_SECTION:
            raise CompactionValidationError(
                f"{name} exceeds {MAX_ITEMS_PER_SECTION} items"
            )
        kwargs[name] = tuple(_decode_nested(nested_type, item) for item in raw_value)
    try:
        return record_type(**kwargs)
    except TypeError as exc:
        raise CompactionValidationError(
            f"invalid {record_type.__name__} fields: {exc}"
        ) from exc


class _RecordMixin:
    def to_dict(self) -> dict[str, Any]:
        return _to_json_value(self)


@dataclass(frozen=True)
class SourceRef(_RecordMixin):
    """Opaque, scope-bound reference to a durable source item."""

    kind: SourceKind
    ref_id: str
    scope_id: str
    session_seq: int | None = None

    def __post_init__(self) -> None:
        _choice(
            self.kind,
            "SourceRef kind",
            {
                "message",
                "event",
                "tool_call",
                "tool_result",
                "execution",
                "artifact",
                "checkpoint",
                "handoff",
                "subagent",
                "pending_operation",
            },
        )
        _text(self.ref_id, "SourceRef.ref_id")
        _text(self.scope_id, "SourceRef.scope_id")
        sequence = _nonnegative_int(
            self.session_seq, "SourceRef.session_seq", optional=True
        )
        if self.kind != "artifact" and sequence is None:
            raise CompactionValidationError(
                "session-scoped SourceRef requires session_seq"
            )
        if sequence == 0:
            raise CompactionValidationError("SourceRef.session_seq must be positive")

    @classmethod
    def from_dict(cls, value: Any) -> "SourceRef":
        return _decode_dataclass(cls, value)


@dataclass(frozen=True)
class ProvenancedObservation(_RecordMixin):
    text: str
    source_refs: tuple[SourceRef, ...]

    def __post_init__(self) -> None:
        _text(self.text, "text")
        refs = _source_ref_tuple(self.source_refs, "source_refs", require_one=True)
        object.__setattr__(self, "source_refs", refs)

    @classmethod
    def from_dict(cls, value: Any) -> "ProvenancedObservation":
        return _decode_dataclass(cls, value, nested={"source_refs": SourceRef})


@dataclass(frozen=True)
class DecisionRecord(_RecordMixin):
    decision_id: str
    decision: str
    rationale: str | None = None
    status: DecisionStatus = "active"
    supersedes: tuple[str, ...] = ()
    source_refs: tuple[SourceRef, ...] = ()

    def __post_init__(self) -> None:
        _text(self.decision_id, "decision_id")
        _text(self.decision, "decision")
        _text(self.rationale, "rationale", optional=True)
        _choice(
            self.status,
            "decision status",
            {"active", "superseded", "reverted", "tentative"},
        )
        object.__setattr__(
            self, "supersedes", _text_tuple(self.supersedes, "supersedes")
        )
        object.__setattr__(
            self,
            "source_refs",
            _source_ref_tuple(self.source_refs, "source_refs", require_one=True),
        )

    @classmethod
    def from_dict(cls, value: Any) -> "DecisionRecord":
        return _decode_dataclass(cls, value, nested={"source_refs": SourceRef})


@dataclass(frozen=True)
class ConstraintRecord(_RecordMixin):
    constraint_id: str
    constraint: str
    status: ConstraintStatus = "active"
    supersedes: tuple[str, ...] = ()
    source_refs: tuple[SourceRef, ...] = ()

    def __post_init__(self) -> None:
        _text(self.constraint_id, "constraint_id")
        _text(self.constraint, "constraint")
        _choice(
            self.status,
            "constraint status",
            {"active", "superseded", "revoked", "tentative"},
        )
        object.__setattr__(
            self, "supersedes", _text_tuple(self.supersedes, "supersedes")
        )
        object.__setattr__(
            self,
            "source_refs",
            _source_ref_tuple(self.source_refs, "source_refs", require_one=True),
        )

    @classmethod
    def from_dict(cls, value: Any) -> "ConstraintRecord":
        return _decode_dataclass(cls, value, nested={"source_refs": SourceRef})


@dataclass(frozen=True)
class FactRecord(_RecordMixin):
    fact_id: str
    fact: str
    source_refs: tuple[SourceRef, ...] = ()

    def __post_init__(self) -> None:
        _text(self.fact_id, "fact_id")
        _text(self.fact, "fact")
        object.__setattr__(
            self,
            "source_refs",
            _source_ref_tuple(self.source_refs, "source_refs", require_one=True),
        )

    @classmethod
    def from_dict(cls, value: Any) -> "FactRecord":
        return _decode_dataclass(cls, value, nested={"source_refs": SourceRef})


@dataclass(frozen=True)
class GoalDelta(_RecordMixin):
    goal_delta_id: str
    association: GoalAssociation
    goal_id: str | None = None
    candidate_goal_ids: tuple[str, ...] = ()
    title_hint: str | None = None
    status_observations: tuple[ProvenancedObservation, ...] = ()
    progress_events: tuple[ProvenancedObservation, ...] = ()
    decisions: tuple[DecisionRecord, ...] = ()
    constraints: tuple[ConstraintRecord, ...] = ()
    facts: tuple[FactRecord, ...] = ()
    next_action_observations: tuple[ProvenancedObservation, ...] = ()
    resolves_ambiguous_delta_ids: tuple[str, ...] = ()
    source_refs: tuple[SourceRef, ...] = ()

    def __post_init__(self) -> None:
        _text(self.goal_delta_id, "goal_delta_id")
        _choice(
            self.association,
            "goal association",
            {"existing", "new", "ambiguous"},
        )
        _text(self.goal_id, "goal_id", optional=True)
        _text(self.title_hint, "title_hint", optional=True)
        if self.association == "existing" and not self.goal_id:
            raise CompactionValidationError("existing GoalDelta requires goal_id")
        if self.association == "new" and self.goal_id is not None:
            raise CompactionValidationError("new GoalDelta must not assign goal_id")
        if self.association == "new" and not (self.title_hint or "").strip():
            raise CompactionValidationError("new GoalDelta requires title_hint")
        if self.association == "ambiguous" and self.goal_id is not None:
            raise CompactionValidationError(
                "ambiguous GoalDelta must not assign goal_id"
            )

        for name in ("candidate_goal_ids", "resolves_ambiguous_delta_ids"):
            object.__setattr__(self, name, _text_tuple(getattr(self, name), name))
        object.__setattr__(
            self,
            "source_refs",
            _source_ref_tuple(self.source_refs, "source_refs", require_one=True),
        )
        for name, expected in (
            ("status_observations", ProvenancedObservation),
            ("progress_events", ProvenancedObservation),
            ("decisions", DecisionRecord),
            ("constraints", ConstraintRecord),
            ("facts", FactRecord),
            ("next_action_observations", ProvenancedObservation),
        ):
            object.__setattr__(
                self, name, _object_tuple(getattr(self, name), name, expected)
            )

    @classmethod
    def from_dict(cls, value: Any) -> "GoalDelta":
        return _decode_dataclass(
            cls,
            value,
            nested={
                "status_observations": ProvenancedObservation,
                "progress_events": ProvenancedObservation,
                "decisions": DecisionRecord,
                "constraints": ConstraintRecord,
                "facts": FactRecord,
                "next_action_observations": ProvenancedObservation,
                "source_refs": SourceRef,
            },
        )


@dataclass(frozen=True)
class ExecutionRecord(_RecordMixin):
    command_class: str
    status: str
    target: str | None = None
    exit_code: int | None = None
    artifact_ref: SourceRef | None = None

    def __post_init__(self) -> None:
        _text(self.command_class, "command_class")
        _text(self.status, "status")
        _text(self.target, "target", optional=True)
        if self.artifact_ref is not None and not isinstance(
            self.artifact_ref, SourceRef
        ):
            raise CompactionValidationError("artifact_ref must be a SourceRef or None")
        if self.exit_code is not None and (
            isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int)
        ):
            raise CompactionValidationError("exit_code must be an integer or None")

    @classmethod
    def from_dict(cls, value: Any) -> "ExecutionRecord":
        return _decode_dataclass(
            cls,
            value,
            nested={"artifact_ref": SourceRef},
        )


@dataclass(frozen=True)
class TrackingCoverage(_RecordMixin):
    dimension: TrackingDimension
    status: TrackingStatus
    observed_by: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _choice(self.dimension, "tracking dimension", set(TRACKING_DIMENSIONS))
        _choice(self.status, "tracking status", {"complete", "partial", "unavailable"})
        object.__setattr__(
            self, "observed_by", _text_tuple(self.observed_by, "observed_by")
        )
        if self.status != "unavailable" and not self.observed_by:
            raise CompactionValidationError(
                "complete/partial tracking coverage requires observed_by"
            )

    @classmethod
    def from_dict(cls, value: Any) -> "TrackingCoverage":
        return _decode_dataclass(cls, value)


def _default_tracking_coverage() -> tuple[TrackingCoverage, ...]:
    return tuple(
        TrackingCoverage(dimension=dimension, status="unavailable")
        for dimension in TRACKING_DIMENSIONS
    )


@dataclass(frozen=True)
class DeterministicDelta(_RecordMixin):
    read_files: tuple[str, ...] = ()
    modified_files: tuple[str, ...] = ()
    created_files: tuple[str, ...] = ()
    deleted_files: tuple[str, ...] = ()
    artifact_refs: tuple[SourceRef, ...] = ()
    tool_call_refs: tuple[SourceRef, ...] = ()
    subagent_refs: tuple[SourceRef, ...] = ()
    executed_checks: tuple[ExecutionRecord, ...] = ()
    pending_operation_events: tuple[SourceRef, ...] = ()
    tracking_coverage: tuple[TrackingCoverage, ...] = field(
        default_factory=_default_tracking_coverage
    )

    def __post_init__(self) -> None:
        for name in (
            "read_files",
            "modified_files",
            "created_files",
            "deleted_files",
        ):
            object.__setattr__(self, name, _text_tuple(getattr(self, name), name))
        for name in (
            "artifact_refs",
            "tool_call_refs",
            "subagent_refs",
            "pending_operation_events",
        ):
            object.__setattr__(self, name, _source_ref_tuple(getattr(self, name), name))
        object.__setattr__(
            self,
            "executed_checks",
            _object_tuple(self.executed_checks, "executed_checks", ExecutionRecord),
        )
        coverage = _object_tuple(
            self.tracking_coverage, "tracking_coverage", TrackingCoverage
        )
        dimensions = tuple(item.dimension for item in coverage)
        if len(dimensions) != len(TRACKING_DIMENSIONS) or set(dimensions) != set(
            TRACKING_DIMENSIONS
        ):
            raise CompactionValidationError(
                "tracking_coverage must specify each tracking dimension exactly once"
            )
        object.__setattr__(self, "tracking_coverage", coverage)

    @classmethod
    def from_dict(cls, value: Any) -> "DeterministicDelta":
        return _decode_dataclass(
            cls,
            value,
            nested={
                "artifact_refs": SourceRef,
                "tool_call_refs": SourceRef,
                "subagent_refs": SourceRef,
                "executed_checks": ExecutionRecord,
                "pending_operation_events": SourceRef,
                "tracking_coverage": TrackingCoverage,
            },
        )


@dataclass(frozen=True)
class ProvenancedNarrativeItem(_RecordMixin):
    text: str
    source_refs: tuple[SourceRef, ...]

    def __post_init__(self) -> None:
        _text(self.text, "text")
        object.__setattr__(
            self,
            "source_refs",
            _source_ref_tuple(self.source_refs, "source_refs", require_one=True),
        )

    @classmethod
    def from_dict(cls, value: Any) -> "ProvenancedNarrativeItem":
        return _decode_dataclass(cls, value, nested={"source_refs": SourceRef})


@dataclass(frozen=True)
class CompactionRecord(_RecordMixin):
    record_id: str
    operation_id: str
    application_status: ApplicationStatus
    session_id: str
    actor_kind: str
    actor_id: str
    created_at: str = field(default_factory=_utc_now)
    tenant_id: str | None = None
    principal_id: str | None = None
    workspace_id: str | None = None
    client_instance_id: str | None = None
    agent_id: str | None = None
    source_start_id: str | None = None
    source_end_id: str | None = None
    source_start_seq: int | None = None
    source_end_seq: int | None = None
    source_message_count: int = 0
    source_tokens: int | None = None
    source_chars: int = 0
    goal_deltas: tuple[GoalDelta, ...] = ()
    shared_constraints: tuple[ConstraintRecord, ...] = ()
    shared_facts: tuple[FactRecord, ...] = ()
    critical_context: tuple[FactRecord, ...] = ()
    deterministic_delta: DeterministicDelta = field(default_factory=DeterministicDelta)
    narrative_continuation: tuple[ProvenancedNarrativeItem, ...] = ()
    first_kept_message_id: str | None = None
    split_turn: bool = False
    previous_compaction_id: str | None = None
    parent_checkpoint_id: str | None = None
    base_revision: int | None = None
    committed_revision: int | None = None
    summarizer_provider: str | None = None
    summarizer_model: str | None = None
    summarizer_usage: Mapping[str, Any] | None = None
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "record_id",
            "operation_id",
            "session_id",
            "actor_kind",
            "actor_id",
            "created_at",
        ):
            _text(getattr(self, name), name)
        for name in (
            "tenant_id",
            "principal_id",
            "workspace_id",
            "client_instance_id",
            "agent_id",
            "source_start_id",
            "source_end_id",
            "first_kept_message_id",
            "previous_compaction_id",
            "parent_checkpoint_id",
            "summarizer_provider",
            "summarizer_model",
        ):
            _text(getattr(self, name), name, optional=True)
        _choice(
            self.application_status,
            "application_status",
            {"applied", "comparison_only"},
        )
        if (
            isinstance(self.schema_version, bool)
            or not isinstance(self.schema_version, int)
            or self.schema_version != SCHEMA_VERSION
        ):
            raise CompactionValidationError(
                f"unsupported CompactionRecord schema_version: {self.schema_version}"
            )
        if not isinstance(self.split_turn, bool):
            raise CompactionValidationError("split_turn must be a boolean")
        if self.split_turn and not self.first_kept_message_id:
            raise CompactionValidationError("split_turn requires first_kept_message_id")
        for name in ("source_message_count", "source_chars"):
            _nonnegative_int(getattr(self, name), name)
        _nonnegative_int(self.source_tokens, "source_tokens", optional=True)
        source_start_seq = _nonnegative_int(
            self.source_start_seq, "source_start_seq", optional=True
        )
        source_end_seq = _nonnegative_int(
            self.source_end_seq, "source_end_seq", optional=True
        )
        if source_start_seq is None or source_end_seq is None:
            raise CompactionValidationError("record requires a source sequence range")
        if source_start_seq == 0:
            raise CompactionValidationError("source_start_seq must be positive")
        if source_end_seq < source_start_seq:
            raise CompactionValidationError(
                "source_end_seq must not precede source_start_seq"
            )
        base_revision = _nonnegative_int(
            self.base_revision, "base_revision", optional=True
        )
        committed_revision = _nonnegative_int(
            self.committed_revision, "committed_revision", optional=True
        )
        if base_revision is None:
            raise CompactionValidationError("record requires base_revision")
        if self.application_status == "applied":
            if (
                committed_revision is not None
                and committed_revision != base_revision + 1
            ):
                raise CompactionValidationError(
                    "committed_revision must equal base_revision + 1"
                )
        elif committed_revision is not None:
            raise CompactionValidationError(
                "comparison_only record must not have committed_revision"
            )
        if (self.source_start_id is None) != (self.source_end_id is None):
            raise CompactionValidationError(
                "source_start_id and source_end_id must be set together"
            )
        for name, expected in (
            ("goal_deltas", GoalDelta),
            ("shared_constraints", ConstraintRecord),
            ("shared_facts", FactRecord),
            ("critical_context", FactRecord),
            ("narrative_continuation", ProvenancedNarrativeItem),
        ):
            object.__setattr__(
                self, name, _object_tuple(getattr(self, name), name, expected)
            )
        if not isinstance(self.deterministic_delta, DeterministicDelta):
            raise CompactionValidationError(
                "deterministic_delta must be a DeterministicDelta"
            )
        if self.summarizer_usage is not None:
            frozen_usage = _freeze_json(self.summarizer_usage, "summarizer_usage")
            if not isinstance(frozen_usage, Mapping):
                raise CompactionValidationError("summarizer_usage must be an object")
            object.__setattr__(self, "summarizer_usage", frozen_usage)

    def to_json(self) -> str:
        try:
            encoded = json.dumps(
                self.to_dict(), ensure_ascii=False, sort_keys=True, allow_nan=False
            )
        except (TypeError, ValueError) as exc:
            raise CompactionValidationError("record is not JSON serializable") from exc
        if len(encoded.encode("utf-8")) > MAX_RECORD_JSON_BYTES:
            raise CompactionValidationError(
                f"record exceeds {MAX_RECORD_JSON_BYTES} serialized bytes"
            )
        return encoded

    @classmethod
    def from_json(cls, value: str) -> "CompactionRecord":
        if not isinstance(value, str):
            raise CompactionValidationError("CompactionRecord JSON must be a string")
        if len(value.encode("utf-8")) > MAX_RECORD_JSON_BYTES:
            raise CompactionValidationError(
                f"record exceeds {MAX_RECORD_JSON_BYTES} serialized bytes"
            )
        try:
            payload = json.loads(value)
        except (TypeError, ValueError) as exc:
            raise CompactionValidationError("invalid CompactionRecord JSON") from exc
        return cls.from_dict(payload)

    @classmethod
    def from_dict(cls, value: Any) -> "CompactionRecord":
        if not isinstance(value, dict):
            raise CompactionValidationError("CompactionRecord must be an object")
        version = value.get("schema_version")
        if isinstance(version, bool) or not isinstance(version, int):
            raise CompactionValidationError(
                "CompactionRecord schema_version is required"
            )
        if version != SCHEMA_VERSION:
            raise CompactionValidationError(
                f"unsupported CompactionRecord schema_version: {version}"
            )
        record = _decode_dataclass(
            cls,
            value,
            nested={
                "goal_deltas": GoalDelta,
                "shared_constraints": ConstraintRecord,
                "shared_facts": FactRecord,
                "critical_context": FactRecord,
                "narrative_continuation": ProvenancedNarrativeItem,
                "deterministic_delta": DeterministicDelta,
            },
        )
        record.to_json()
        return record


__all__ = [
    "ApplicationStatus",
    "CompactionRecord",
    "CompactionValidationError",
    "ConstraintRecord",
    "DecisionRecord",
    "DeterministicDelta",
    "ExecutionRecord",
    "FactRecord",
    "GoalAssociation",
    "GoalDelta",
    "ProvenancedNarrativeItem",
    "ProvenancedObservation",
    "SCHEMA_VERSION",
    "SourceKind",
    "SourceRef",
    "TrackingCoverage",
    "TrackingDimension",
    "TrackingStatus",
]
