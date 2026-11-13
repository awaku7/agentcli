from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

MemoryScope = Literal["personal", "profile", "session"]


@dataclass(frozen=True)
class MemoryItem:
    scope: str
    note: str
    timestamp: Any = None

    def as_dict(self) -> dict[str, Any]:
        return {"scope": self.scope, "note": self.note, "ts": self.timestamp}


class MemoryManager:
    """Unified facade over the existing personal memory store."""

    def __init__(
        self,
        *,
        personal: Any = None,
        profile: Any = None,
        session_store: Any = None,
        session_id: str | None = None,
    ) -> None:
        if personal is None:
            from ..tools import long_memory as personal
        if profile is None:
            from .. import profile_manager as profile
        self.personal = personal
        self.profile = profile
        self.session_store = session_store
        self.session_id = session_id

    def remember(self, note: str, *, scope: MemoryScope = "personal") -> None:
        text = str(note or "").strip()
        if not text:
            raise ValueError("note must not be empty")
        if scope == "personal":
            self.personal.append_long_memory(text)
        elif scope in ("profile", "session"):
            raise RuntimeError(f"{scope} memory is read-only through MemoryManager")
        else:
            raise ValueError(f"unknown memory scope: {scope}")

    def list(self, *, scope: MemoryScope | None = None) -> list[MemoryItem]:
        if scope not in (None, "personal", "profile", "session"):
            raise ValueError(f"unknown memory scope: {scope}")
        items: list[MemoryItem] = []
        if scope in (None, "personal"):
            items.extend(
                MemoryItem("personal", str(r.get("note", "")), r.get("ts"))
                for r in self.personal.load_long_memory_records()
            )
        if scope in (None, "profile"):
            snapshot = self.profile.load_profile()
            for key in ("preferences", "constraints"):
                for note in (
                    snapshot.get(key, []) if isinstance(snapshot.get(key), list) else []
                ):
                    items.append(MemoryItem("profile", str(note)))
        # The "session" scope used to list pending marker candidates.
        # Marked notes are now saved to long-term memory at write time by
        # the session store, so the scope intentionally yields nothing.
        return [item for item in items if item.note]

    def records_for_prompt(
        self, *, scope: MemoryScope | None = None
    ) -> list[dict[str, Any]]:
        return [item.as_dict() for item in self.list(scope=scope)]


__all__ = ["MemoryItem", "MemoryManager", "MemoryScope"]
