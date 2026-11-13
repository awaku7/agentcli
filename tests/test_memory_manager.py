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


def test_memory_manager_routes_and_lists_scopes():
    personal = FakePersonal()
    manager = MemoryManager(
        personal=personal,
        profile=type("Profile", (), {"load_profile": lambda _: {}})(),
    )

    manager.remember("private")

    assert [item.scope for item in manager.list()] == ["personal"]
    assert manager.records_for_prompt(scope="personal")[0]["note"] == "private"


def test_memory_manager_rejects_unknown_scope_and_empty_notes():
    manager = MemoryManager(personal=FakePersonal())
    with pytest.raises(ValueError):
        manager.remember(" ")
    with pytest.raises(ValueError):
        manager.remember("team", scope="shared")
    with pytest.raises(ValueError):
        manager.list(scope="unknown")
