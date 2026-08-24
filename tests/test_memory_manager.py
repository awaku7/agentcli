from __future__ import annotations

import pytest

from uagent.runtime.memory_manager import MemoryManager


class FakePersonal:
    def __init__(self):
        self.records = []

    def append_long_memory(self, note):
        self.records.append({"note": note, "ts": 1})

    def load_long_memory_records(self):
        return list(self.records)


class FakeShared:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.records = []

    def is_enabled(self):
        return self.enabled

    def append_shared_memory(self, note):
        self.records.append({"note": note, "ts": 2})

    def load_shared_memory_records(self):
        return list(self.records)


def test_memory_manager_routes_and_lists_scopes():
    personal, shared = FakePersonal(), FakeShared()
    manager = MemoryManager(
        personal=personal,
        shared=shared,
        profile=type("Profile", (), {"load_profile": lambda _: {}})(),
    )

    manager.remember("private")
    manager.remember("team", scope="shared")

    assert [item.scope for item in manager.list()] == ["personal", "shared"]
    assert manager.records_for_prompt(scope="shared")[0]["note"] == "team"


def test_memory_manager_rejects_disabled_shared_and_empty_notes():
    manager = MemoryManager(personal=FakePersonal(), shared=FakeShared(False))
    with pytest.raises(ValueError):
        manager.remember(" ")
    with pytest.raises(RuntimeError):
        manager.remember("team", scope="shared")
    with pytest.raises(ValueError):
        manager.list(scope="unknown")
