"""Immutable, provider-neutral handoff evidence (no state application).

Delivery IDs and the receiving session/revision are supplied by the trusted
dispatcher, not inferred by a model. Source authorization belongs to projection.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .compaction_record import (
    MAX_RECORD_JSON_BYTES,
    SCHEMA_VERSION,
    TRACKING_DIMENSIONS,
    CompactionValidationError,
    DecisionRecord,
    ExecutionRecord,
    ProvenancedObservation,
    SourceRef,
    TrackingCoverage,
    _RecordMixin,
    _decode_dataclass,
    _default_tracking_coverage,
    _nonnegative_int,
    _object_tuple,
    _source_ref_tuple,
    _text,
    _text_tuple,
)


def _bounded_json(value: dict[str, Any], max_bytes: int) -> str:
    _nonnegative_int(max_bytes, "max_bytes")
    if not 0 < max_bytes <= MAX_RECORD_JSON_BYTES:
        raise CompactionValidationError("invalid handoff byte budget")

    def check_text(item: Any) -> None:
        if isinstance(item, str):
            if any(ord(char) < 32 and char not in "\n\r\t" for char in item):
                raise CompactionValidationError("handoff contains control characters")
        elif isinstance(item, dict):
            for nested in item.values():
                check_text(nested)
        elif isinstance(item, list):
            for nested in item:
                check_text(nested)

    check_text(value)
    try:
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True)
        size = len(payload.encode("utf-8"))
    except (TypeError, ValueError, UnicodeError) as exc:
        raise CompactionValidationError("invalid handoff JSON") from exc
    if size > max_bytes:
        raise CompactionValidationError("handoff exceeds byte budget")
    return payload


@dataclass(frozen=True)
class ProvenancedHandoffItem(ProvenancedObservation):
    """One compact report item with its own durable source references."""


@dataclass(frozen=True)
class ProvenancedDeterministicItem(_RecordMixin):
    value: str
    source_refs: tuple[SourceRef, ...]

    def __post_init__(self) -> None:
        _text(self.value, "value")
        object.__setattr__(
            self,
            "source_refs",
            _source_ref_tuple(self.source_refs, "source_refs", require_one=True),
        )

    @classmethod
    def from_dict(cls, value: Any) -> "ProvenancedDeterministicItem":
        return _decode_dataclass(cls, value, nested={"source_refs": SourceRef})


@dataclass(frozen=True)
class ProvenancedExecutionRecord(_RecordMixin):
    execution: ExecutionRecord
    source_refs: tuple[SourceRef, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.execution, ExecutionRecord):
            raise CompactionValidationError("execution must be an ExecutionRecord")
        object.__setattr__(
            self,
            "source_refs",
            _source_ref_tuple(self.source_refs, "source_refs", require_one=True),
        )

    @classmethod
    def from_dict(cls, value: Any) -> "ProvenancedExecutionRecord":
        return _decode_dataclass(
            cls,
            value,
            nested={"execution": ExecutionRecord, "source_refs": SourceRef},
        )


@dataclass(frozen=True)
class ProvenancedDeterministicDelta(_RecordMixin):
    read_files: tuple[ProvenancedDeterministicItem, ...] = ()
    modified_files: tuple[ProvenancedDeterministicItem, ...] = ()
    created_files: tuple[ProvenancedDeterministicItem, ...] = ()
    deleted_files: tuple[ProvenancedDeterministicItem, ...] = ()
    artifact_refs: tuple[ProvenancedDeterministicItem, ...] = ()
    tool_call_refs: tuple[ProvenancedDeterministicItem, ...] = ()
    subagent_refs: tuple[ProvenancedDeterministicItem, ...] = ()
    executed_checks: tuple[ProvenancedExecutionRecord, ...] = ()
    pending_operation_events: tuple[ProvenancedDeterministicItem, ...] = ()
    tracking_coverage: tuple[TrackingCoverage, ...] = field(
        default_factory=_default_tracking_coverage
    )

    def __post_init__(self) -> None:
        for name in self._item_fields():
            object.__setattr__(
                self,
                name,
                _object_tuple(getattr(self, name), name, ProvenancedDeterministicItem),
            )
        object.__setattr__(
            self,
            "executed_checks",
            _object_tuple(
                self.executed_checks, "executed_checks", ProvenancedExecutionRecord
            ),
        )
        coverage = _object_tuple(
            self.tracking_coverage, "tracking_coverage", TrackingCoverage
        )
        dimensions = [item.dimension for item in coverage]
        if len(dimensions) != len(TRACKING_DIMENSIONS) or set(dimensions) != set(
            TRACKING_DIMENSIONS
        ):
            raise CompactionValidationError(
                "tracking_coverage must specify each dimension once"
            )
        object.__setattr__(self, "tracking_coverage", coverage)

    @staticmethod
    def _item_fields() -> tuple[str, ...]:
        return (
            "read_files",
            "modified_files",
            "created_files",
            "deleted_files",
            "artifact_refs",
            "tool_call_refs",
            "subagent_refs",
            "pending_operation_events",
        )

    @classmethod
    def from_dict(cls, value: Any) -> "ProvenancedDeterministicDelta":
        return _decode_dataclass(
            cls,
            value,
            nested={
                **dict.fromkeys(cls._item_fields(), ProvenancedDeterministicItem),
                "executed_checks": ProvenancedExecutionRecord,
                "tracking_coverage": TrackingCoverage,
            },
        )


@dataclass(frozen=True)
class HandoffRecord(_RecordMixin):
    handoff_id: str
    root_handoff_id: str
    receiving_session_id: str
    receiving_base_revision: int
    application_base_revision: int
    agent_id: str
    role: str
    goal_ids: tuple[str, ...]
    objective: str
    work_done: tuple[ProvenancedHandoffItem, ...] = ()
    findings: tuple[ProvenancedHandoffItem, ...] = ()
    decisions: tuple[DecisionRecord, ...] = ()
    unresolved: tuple[ProvenancedHandoffItem, ...] = ()
    recommended_next_steps: tuple[ProvenancedHandoffItem, ...] = ()
    state_delta: ProvenancedDeterministicDelta = field(
        default_factory=ProvenancedDeterministicDelta
    )
    artifact_refs: tuple[SourceRef, ...] = ()
    source_checkpoint_id: str | None = None
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if (
            type(self.schema_version) is not int
            or self.schema_version != SCHEMA_VERSION
        ):
            raise CompactionValidationError("unsupported handoff schema_version")
        for name in (
            "handoff_id",
            "root_handoff_id",
            "receiving_session_id",
            "agent_id",
            "role",
            "objective",
        ):
            _text(getattr(self, name), name)
        _text(self.source_checkpoint_id, "source_checkpoint_id", optional=True)
        for name in ("receiving_base_revision", "application_base_revision"):
            _nonnegative_int(getattr(self, name), name)
        if self.application_base_revision < self.receiving_base_revision:
            raise CompactionValidationError("application revision precedes dispatch")
        if (
            self.handoff_id == self.root_handoff_id
            and self.application_base_revision != self.receiving_base_revision
        ):
            raise CompactionValidationError(
                "initial handoff must use dispatch revision"
            )
        object.__setattr__(self, "goal_ids", _text_tuple(self.goal_ids, "goal_ids"))
        for name in ("work_done", "findings", "unresolved", "recommended_next_steps"):
            object.__setattr__(
                self,
                name,
                _object_tuple(getattr(self, name), name, ProvenancedHandoffItem),
            )
        object.__setattr__(
            self,
            "decisions",
            _object_tuple(self.decisions, "decisions", DecisionRecord),
        )
        if not isinstance(self.state_delta, ProvenancedDeterministicDelta):
            raise CompactionValidationError("invalid handoff state_delta")
        refs = _source_ref_tuple(self.artifact_refs, "artifact_refs")
        if any(ref.kind != "artifact" for ref in refs):
            raise CompactionValidationError("artifact_refs must reference artifacts")
        object.__setattr__(self, "artifact_refs", refs)
        self.to_json()

    def to_json(self) -> str:
        return _bounded_json(self.to_dict(), MAX_RECORD_JSON_BYTES)

    @classmethod
    def from_dict(cls, value: Any) -> "HandoffRecord":
        return _decode_dataclass(
            cls,
            value,
            nested={
                **dict.fromkeys(
                    ("work_done", "findings", "unresolved", "recommended_next_steps"),
                    ProvenancedHandoffItem,
                ),
                "decisions": DecisionRecord,
                "state_delta": ProvenancedDeterministicDelta,
                "artifact_refs": SourceRef,
            },
        )
