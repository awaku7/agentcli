from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

from uagent import util_tools as ut


def test_count_user_turns_ignores_non_user():
    msgs = [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a"},
        {"role": "tool", "content": "t"},
        {"role": "user", "content": "u2"},
    ]
    assert ut._count_user_turns(msgs) == 2
    assert ut._count_user_turns([]) == 0
    assert ut._count_user_turns(None) == 0


def test_default_clean_threshold_env(monkeypatch):
    monkeypatch.delenv("UAGENT_CLEAN_THRESHOLD", raising=False)
    with mock.patch.object(
        ut, "env_get", side_effect=lambda k, d="": os.environ.get(k, d)
    ):
        assert ut._default_clean_threshold() == 5
        monkeypatch.setenv("UAGENT_CLEAN_THRESHOLD", "3")
        assert ut._default_clean_threshold() == 3
        monkeypatch.setenv("UAGENT_CLEAN_THRESHOLD", "0")
        assert ut._default_clean_threshold() == 0
        monkeypatch.setenv("UAGENT_CLEAN_THRESHOLD", "nope")
        assert ut._default_clean_threshold() == 5


def test_maybe_discard_short_session_log(tmp_path, monkeypatch):
    log = tmp_path / "scheck_log_test.jsonl"
    log.write_text("{}\n", encoding="utf-8")

    class Core:
        LOG_FILE = str(log)

    monkeypatch.setattr(ut, "_default_clean_threshold", lambda: 5)

    # short: delete
    ut._maybe_discard_short_session_log(
        core=Core(),
        messages_ref=[{"role": "system"}, {"role": "user", "content": "hi"}],
        tr=lambda s: s,
    )
    assert not log.exists()

    # long: keep
    log.write_text("{}\n", encoding="utf-8")
    msgs = [{"role": "user", "content": f"u{i}"} for i in range(6)]
    ut._maybe_discard_short_session_log(
        core=Core(),
        messages_ref=msgs,
        tr=lambda s: s,
    )
    assert log.exists()


def test_collect_clean_targets_by_user_turns(tmp_path):
    short = str(tmp_path / "short.jsonl")
    long = str(tmp_path / "long.jsonl")
    Path(short).write_text("x\n", encoding="utf-8")
    Path(long).write_text("y\n", encoding="utf-8")

    def load(p):
        if p.endswith("short.jsonl"):
            return [{"role": "system"}, {"role": "user"}, {"role": "assistant"}]
        return [{"role": "user"} for _ in range(8)]

    class Core:
        BASE_LOG_DIR = str(tmp_path)

        @staticmethod
        def find_log_files(exclude_current=False):
            return [short, long]

        @staticmethod
        def load_conversation_from_log(p):
            return load(p)

    ok, targets, counts = ut._collect_clean_targets(
        core=Core(), threshold=5, tr=lambda s: s
    )
    assert ok is True
    assert targets == [short]
    assert counts[short] == 1
    assert counts[long] == 8


def test_sweep_short_session_logs_deletes_short_only(tmp_path, monkeypatch, capsys):
    short = str(tmp_path / "short.jsonl")
    long = str(tmp_path / "long.jsonl")
    Path(short).write_text("x\n", encoding="utf-8")
    Path(long).write_text("y\n", encoding="utf-8")

    seen = {}

    def load(p):
        if p.endswith("short.jsonl"):
            return [{"role": "user", "content": "hi"}]
        return [{"role": "user", "content": f"u{i}"} for i in range(8)]

    class Core:
        BASE_LOG_DIR = str(tmp_path)

        @staticmethod
        def find_log_files(exclude_current=False):
            seen["exclude_current"] = exclude_current
            return [short, long]

        @staticmethod
        def load_conversation_from_log(p):
            return load(p)

    monkeypatch.setattr(ut, "_default_clean_threshold", lambda: 5)

    deleted, failed = ut._sweep_short_session_logs(
        core=Core(),
        tr=lambda s: s,
        exclude_current=True,
        quiet=False,
    )
    assert seen["exclude_current"] is True
    assert deleted == 1
    assert failed == 0
    assert not Path(short).exists()
    assert Path(long).exists()
    out = capsys.readouterr().out
    assert "Startup sweep" in out
    assert "deleted=1" in out


def test_sweep_short_session_logs_quiet_no_output(tmp_path, monkeypatch, capsys):
    short = str(tmp_path / "short.jsonl")
    Path(short).write_text("x\n", encoding="utf-8")

    class Core:
        BASE_LOG_DIR = str(tmp_path)

        @staticmethod
        def find_log_files(exclude_current=False):
            return [short]

        @staticmethod
        def load_conversation_from_log(p):
            return [{"role": "user"}]

    monkeypatch.setattr(ut, "_default_clean_threshold", lambda: 5)

    deleted, failed = ut._sweep_short_session_logs(
        core=Core(),
        tr=lambda s: s,
        quiet=True,
    )
    assert deleted == 1
    assert failed == 0
    assert not Path(short).exists()
    assert capsys.readouterr().out == ""


def test_sweep_short_session_logs_none(tmp_path, monkeypatch):
    long = str(tmp_path / "long.jsonl")
    Path(long).write_text("y\n", encoding="utf-8")

    class Core:
        BASE_LOG_DIR = str(tmp_path)

        @staticmethod
        def find_log_files(exclude_current=False):
            return [long]

        @staticmethod
        def load_conversation_from_log(p):
            return [{"role": "user"} for _ in range(9)]

    monkeypatch.setattr(ut, "_default_clean_threshold", lambda: 5)

    deleted, failed = ut._sweep_short_session_logs(core=Core(), tr=lambda s: s)
    assert deleted == 0
    assert failed == 0
    assert Path(long).exists()


def test_parse_clean_threshold(monkeypatch):
    monkeypatch.setattr(ut, "_default_clean_threshold", lambda: 5)
    assert ut._parse_clean_threshold("", tr=lambda s: s) == 5
    assert ut._parse_clean_threshold("2", tr=lambda s: s) == 2
    assert ut._parse_clean_threshold("x", tr=lambda s: s) is None
