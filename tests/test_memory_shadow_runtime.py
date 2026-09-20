from __future__ import annotations

import copy
import json
from types import SimpleNamespace


def test_runtime_shadow_observation_is_opt_in_and_does_not_change_messages(
    tmp_path, monkeypatch
) -> None:
    from uagent.runtime.memory_retrieval import observe_memory_shadow_retrieval
    from uagent.tools import long_memory, shared_memory

    monkeypatch.setenv("UAGENT_MEMORY_SHADOW_RETRIEVAL", "1")
    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "jsonl")
    monkeypatch.setenv("UAGENT_MEMORY_FILE", str(tmp_path / "personal.jsonl"))
    monkeypatch.setenv("UAGENT_SHARED_MEMORY_FILE", str(tmp_path / "shared.jsonl"))
    assert long_memory.append_long_memory("database rule") is True
    shared_memory.append_shared_memory("team database rule")

    logged: list[dict] = []
    core = SimpleNamespace(workdir=str(tmp_path), log_message=logged.append)
    messages = [{"role": "user", "content": "find the database rule"}]
    before = copy.deepcopy(messages)

    observation = observe_memory_shadow_retrieval(messages, core)

    assert messages == before
    assert observation is not None
    assert observation["type"] == "memory_shadow_retrieval"
    assert observation["personal"]["candidate_count"] == 1
    assert observation["shared"]["candidate_count"] == 1
    assert core.memory_shadow_last_observation == observation
    assert len(core.memory_shadow_observations) == 1
    assert logged == [observation]
    assert "database rule" not in json.dumps(observation, ensure_ascii=False)


def test_runtime_shadow_observation_is_disabled_by_default(monkeypatch) -> None:
    from uagent.runtime.memory_retrieval import observe_memory_shadow_retrieval

    monkeypatch.delenv("UAGENT_MEMORY_SHADOW_RETRIEVAL", raising=False)
    core = SimpleNamespace(log_message=lambda _event: None)

    assert (
        observe_memory_shadow_retrieval([{"role": "user", "content": "database"}], core)
        is None
    )
    assert not hasattr(core, "memory_shadow_last_observation")
