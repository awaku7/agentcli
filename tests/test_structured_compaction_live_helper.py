"""Offline tests for the live real-LLM verification helper.

No provider/API traffic and no changes to the user's real session databases.
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "structured_compaction_live_test.py"
)
SPEC = importlib.util.spec_from_file_location("structured_compaction_live_test", SCRIPT)
assert SPEC and SPEC.loader
live = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(live)


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    run = tmp_path / "isolated"
    run.mkdir()
    state = run / "state"
    db = state / "sessions" / "sessions.sqlite3"
    db.parent.mkdir(parents=True)
    config = {
        "state_dir": str(state),
        "session_db": str(db),
        "project_dir": str(tmp_path),
    }
    (run / "test-config.json").write_text(json.dumps(config), encoding="utf-8")
    with sqlite3.connect(db) as con:
        con.executescript("""
            CREATE TABLE messages (
                session_id TEXT, message_id INTEGER, role TEXT, content TEXT
            );
            CREATE TABLE checkpoints (
                session_id TEXT, application_status TEXT,
                source_start_seq INTEGER, source_end_seq INTEGER,
                result_revision INTEGER
            );
            CREATE TABLE tool_calls (session_id TEXT, call_id TEXT);
            """)
        con.executemany(
            "INSERT INTO messages VALUES ('s1', ?, 'user', ?)",
            [(i + 1, fact) for i, fact in enumerate(live.SEED_FACTS)],
        )
    return run


def test_baseline_and_pending_report(run_dir: Path) -> None:
    assert live.capture_baseline(run_dir) == 4
    report = live.inspect(run_dir)
    assert report["checks"] == {
        "initial_checkpoint": "PENDING",
        "continued_checkpoint": "PENDING",
        "raw_history": "PASS",
        "tool_calls_recorded": "PENDING",
    }
    assert (run_dir / "result.md").exists()
    with pytest.raises(ValueError, match="already exists"):
        live.capture_baseline(run_dir)


def test_checkpoints_and_raw_history_regression(run_dir: Path) -> None:
    live.capture_baseline(run_dir)
    db = Path(live._config(run_dir)["session_db"])
    with sqlite3.connect(db) as con:
        con.executemany(
            "INSERT INTO checkpoints VALUES ('s1', 'applied', ?, ?, ?)",
            [(1, 4, 1), (5, 8, 2)],
        )
        con.executemany("INSERT INTO tool_calls VALUES ('s1', ?)", [("one",), ("two",)])
    report = live.inspect(run_dir)
    assert all(value == "PASS" for value in report["checks"].values())
    assert not report["lost_or_modified_ids"]

    with sqlite3.connect(db) as con:
        con.execute("UPDATE messages SET content = 'rewritten' WHERE message_id = 3")
        con.execute("INSERT INTO checkpoints VALUES ('s1', 'applied', 8, 12, 3)")
    report = live.inspect(run_dir)
    assert report["checks"]["raw_history"] == "FAIL"
    assert report["checks"]["continued_checkpoint"] == "FAIL"
    assert report["lost_or_modified_ids"] == [3]


def test_out_of_order_checkpoint_revisions_are_rejected(run_dir: Path) -> None:
    live.capture_baseline(run_dir)
    db = Path(live._config(run_dir)["session_db"])
    with sqlite3.connect(db) as con:
        con.executemany(
            "INSERT INTO checkpoints VALUES ('s1', 'applied', ?, ?, ?)",
            [(5, 8, 1), (1, 4, 2)],
        )
    report = live.inspect(run_dir)
    assert report["checks"]["continued_checkpoint"] == "FAIL"


def test_baseline_rejects_existing_checkpoint(run_dir: Path) -> None:
    db = Path(live._config(run_dir)["session_db"])
    with sqlite3.connect(db) as con:
        con.execute("INSERT INTO checkpoints VALUES ('s1', 'applied', 1, 4, 1)")
    with pytest.raises(ValueError, match="Checkpoint already exists"):
        live.capture_baseline(run_dir)
    assert not (run_dir / "raw-baseline.json").exists()


def test_test_env_overrides_live_memory_configuration(
    run_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UAGENT_MEMORY_DB", "other-memory.sqlite3")
    monkeypatch.setenv("UAGENT_SESSION_STORE_PATH", "other-sessions.sqlite3")
    monkeypatch.setenv("UAGENT_SHARED_MEMORY_FILE", "old-shared.jsonl")
    config = live._config(run_dir)
    env = live._test_env(config)
    assert env["UAGENT_SESSION_STORE_PATH"] == config["session_db"]
    assert env["UAGENT_MEMORY_DB"] != "other-memory.sqlite3"
    assert env["UAGENT_SHARED_MEMORY_FILE"] == ""
    assert env["UAGENT_ENABLE_PROFILING"] == "0"


def test_missing_database_never_creates_empty_store(run_dir: Path) -> None:
    config = live._config(run_dir)
    db = Path(config["session_db"])
    db.unlink()
    with pytest.raises(ValueError, match="does not exist"):
        live.capture_baseline(run_dir)
    assert not db.exists()
