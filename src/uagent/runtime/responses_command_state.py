"""Provider-neutral state view for ``:response`` command operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ResponsesCommandState:
    """Read-only view of the Responses continuation state held by a host."""

    provider: str = ""
    active_response_id: str = ""
    previous_response_id: str = ""

    @classmethod
    def from_core(cls, core: Any) -> "ResponsesCommandState":
        state = getattr(core, "responses_state", {})
        if not isinstance(state, dict):
            state = {}
        provider = str(
            state.get("provider") or getattr(core, "_responses_provider", "") or ""
        ).strip().lower()
        if not provider:
            provider = str(getattr(core, "provider", "") or "").strip().lower()
        return cls(
            provider=provider,
            active_response_id=str(state.get("active_response_id") or ""),
            previous_response_id=str(state.get("previous_response_id") or ""),
        )

    def resolve_id(self, explicit: str = "") -> str:
        """Resolve an explicit response ID or the current continuation ID."""
        if explicit.strip():
            return explicit.strip()
        return self.active_response_id or self.previous_response_id

    def is_current(self, response_id: str) -> bool:
        """Return whether a response ID is the current continuation target."""
        return bool(response_id) and response_id == self.resolve_id()


__all__ = ["ResponsesCommandState"]
