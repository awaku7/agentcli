"""Common decision-provider protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import DecisionRequest, DecisionResult


@runtime_checkable
class DecisionProvider(Protocol):
    @property
    def name(self) -> str: ...

    def decide(self, request: DecisionRequest) -> DecisionResult: ...

    def close(self) -> None: ...
