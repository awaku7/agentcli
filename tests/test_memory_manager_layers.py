from __future__ import annotations

from uagent.runtime.memory_manager import MemoryManager


class Profile:
    def load_profile(self):
        return {"preferences": ["concise"], "constraints": ["no secrets"]}


class Sessions:
    def list_memory_candidates(self, session_id):
        assert session_id == "s1"
        return ["use project style"]


def test_memory_manager_reads_profile_and_session_layers():
    manager = MemoryManager(
        personal=type("P", (), {"load_long_memory_records": lambda _: []})(),
        shared=type("S", (), {"load_shared_memory_records": lambda _: []})(),
        profile=Profile(),
        session_store=Sessions(),
        session_id="s1",
    )
    items = manager.list()
    assert [(item.scope, item.note) for item in items] == [
        ("profile", "concise"),
        ("profile", "no secrets"),
        ("session", "use project style"),
    ]
