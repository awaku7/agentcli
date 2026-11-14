from __future__ import annotations

from pathlib import Path

import pytest


def _use_jsonl(monkeypatch: pytest.MonkeyPatch, tmp: Path) -> None:
    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "jsonl")
    monkeypatch.setenv("UAGENT_MEMORY_FILE", str(tmp / "mem.jsonl"))


def _use_sqlite(monkeypatch: pytest.MonkeyPatch, tmp: Path) -> None:
    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "sqlite")
    monkeypatch.setenv("UAGENT_MEMORY_DB", str(tmp / "memory.sqlite3"))


def _setup(backend: str, monkeypatch: pytest.MonkeyPatch, tmp: Path) -> None:
    if backend == "jsonl":
        _use_jsonl(monkeypatch, tmp)
    else:
        _use_sqlite(monkeypatch, tmp)


@pytest.mark.parametrize("backend", ["jsonl", "sqlite"])
def test_aliases_saved_on_record(
    backend: str, repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.tools import long_memory

    _setup(backend, monkeypatch, repo_tmp_path)

    result = long_memory.save_long_memory(
        "車を買い替えた",
        source="tool",
        aliases=["自動車を購入した", "マイカーを新しくした"],
    )
    assert result["saved"] is True

    records = long_memory.load_long_memory_records()
    assert len(records) == 1
    assert records[0]["aliases"] == ["自動車を購入した", "マイカーを新しくした"]


@pytest.mark.parametrize("backend", ["jsonl", "sqlite"])
def test_aliases_cleaned_on_save(
    backend: str, repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.tools import long_memory

    _setup(backend, monkeypatch, repo_tmp_path)

    result = long_memory.save_long_memory(
        "車を買い替えた",
        source="tool",
        aliases=[
            "車を買い替えた",  # the note itself
            "自動車を購入した",
            "自動車を購入した",  # duplicate
            "   ",
            "api_key: abcdefghij123456",  # credential-shaped
        ],
    )
    assert result["saved"] is True

    records = long_memory.load_long_memory_records()
    assert records[0]["aliases"] == ["自動車を購入した"]


def test_aliases_capped() -> None:
    from uagent.tools import long_memory

    cleaned = long_memory._clean_aliases(
        "本題のメモ", [f"別表現{i}" for i in range(12)]
    )
    assert cleaned == [f"別表現{i}" for i in range(long_memory.MAX_ALIASES)]


def test_retrieval_matches_alias_only() -> None:
    from uagent.runtime.memory_retrieval import shadow_retrieve_memories

    # The query shares no character bigram with the note, so only the
    # alias can match it.
    records = [{"note": "マイカーを新調した", "aliases": ["自動車の購入"]}]
    result = shadow_retrieve_memories(records, query="自動車の購入", scope="personal")
    assert len(result.candidates) == 1
    # The evidence text is the note itself, never the alias.
    assert result.candidates[0].content == "マイカーを新調した"


def test_retrieval_without_alias_misses_paraphrase() -> None:
    from uagent.runtime.memory_retrieval import shadow_retrieve_memories

    records = [{"note": "マイカーを新調した"}]
    result = shadow_retrieve_memories(records, query="自動車の購入", scope="personal")
    assert result.candidates == []


def test_alias_match_survives_discriminative_filter() -> None:
    from uagent.runtime.memory_retrieval import shadow_retrieve_memories

    # The query is not a substring of the alias, so no phrase match
    # applies and the discriminative filter runs. It must score the
    # alias text too, or the strongest alias match is dropped in favor
    # of an incidental note match.
    records = [
        {"note": "マイカーを新調した", "aliases": ["自動車の購入"]},
        {"note": "購入した本は小説です"},
    ]
    result = shadow_retrieve_memories(
        records, query="自動車の購入について", scope="personal"
    )
    assert [c.content for c in result.candidates] == ["マイカーを新調した"]


def test_retrieval_accepts_json_string_aliases() -> None:
    from uagent.runtime.memory_retrieval import shadow_retrieve_memories

    records = [{"note": "マイカーを新調した", "aliases": '["自動車の購入"]'}]
    result = shadow_retrieve_memories(records, query="自動車の購入", scope="personal")
    assert len(result.candidates) == 1


@pytest.mark.parametrize("backend", ["jsonl", "sqlite"])
def test_saved_aliases_reach_retrieval(
    backend: str, repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.runtime.memory_retrieval import shadow_retrieve_memories
    from uagent.tools import long_memory

    _setup(backend, monkeypatch, repo_tmp_path)

    saved = long_memory.save_long_memory(
        "マイカーを新調した", source="tool", aliases=["自動車の購入"]
    )
    assert saved["saved"] is True

    result = shadow_retrieve_memories(
        long_memory.load_long_memory_records(),
        query="自動車の購入",
        scope="personal",
    )
    assert [c.content for c in result.candidates] == ["マイカーを新調した"]


def test_tool_saves_aliases(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.tools import add_long_memory_tool, long_memory

    _use_sqlite(monkeypatch, repo_tmp_path)

    output = add_long_memory_tool.run_tool(
        {"note": "車を買い替えた", "aliases": ["自動車を購入した"]}
    )
    assert "saved" in output

    records = long_memory.load_long_memory_records()
    assert records[0]["aliases"] == ["自動車を購入した"]
