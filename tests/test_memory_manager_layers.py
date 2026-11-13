from __future__ import annotations

from uagent.runtime.memory_manager import MemoryManager


class Profile:
    def load_profile(self):
        return {"preferences": ["concise"], "constraints": ["no secrets"]}


def test_memory_manager_reads_profile_layer():
    manager = MemoryManager(
        personal=type("P", (), {"load_long_memory_records": lambda _: []})(),
        profile=Profile(),
        session_store=None,
        session_id="s1",
    )
    items = manager.list()
    assert [(item.scope, item.note) for item in items] == [
        ("profile", "concise"),
        ("profile", "no secrets"),
    ]
    # The session scope no longer surfaces pending marker candidates:
    # marked notes are saved to long-term memory at write time.
    assert manager.list(scope="session") == []
