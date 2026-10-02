"""Provider-neutral request and result models for decision providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DecisionKind(str, Enum):
    BOOLEAN = "boolean"
    CHOICE = "choice"
    SCORE = "score"


@dataclass(frozen=True)
class DecisionQuestion:
    id: str
    kind: DecisionKind
    instruction: str
    choices: tuple[Any, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", DecisionKind(self.kind))
        object.__setattr__(self, "choices", tuple(self.choices or ()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "instruction": self.instruction,
            "choices": list(self.choices),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DecisionRequest:
    state: Any
    questions: tuple[DecisionQuestion, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "questions", tuple(self.questions or ()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "questions": [question.to_dict() for question in self.questions],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DecisionAnswer:
    value: Any
    confidence: float | None = None
    calibrated: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "confidence": self.confidence,
            "calibrated": self.calibrated,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DecisionResult:
    provider: str
    model: str | None
    answers: dict[str, DecisionAnswer] = field(default_factory=dict)
    latency_ms: float = 0.0
    skipped: bool = False
    raw: Any = None

    def to_dict(self, *, include_raw: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "provider": self.provider,
            "model": self.model,
            "answers": {key: answer.to_dict() for key, answer in self.answers.items()},
            "latency_ms": self.latency_ms,
            "skipped": self.skipped,
        }
        if include_raw:
            payload["raw"] = self.raw
        return payload
