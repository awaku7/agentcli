from __future__ import annotations

import json
import os
import re
from pathlib import Path

from uagent import core as ucore
from uagent import util_tools as ut


def _write_log(path: Path, lines: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(o, ensure_ascii=False) + "\n" for o in lines),
        encoding="utf-8",
    )


def _cwd_content(path: str) -> str:
    return "[CWD] " + json.dumps({"event": "startup", "path": path})


def _setup(tmp_path: Path, monkeypatch, cwd_dir: str | None) -> Path:
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setattr(ucore, "BASE_LOG_DIR", str(log_dir))
    monkeypatch.setattr(ucore, "LOG_FILE", str(log_dir / "current_session.jsonl"))

    lines: list[dict] = [
        {"role": "system", "content": "plain instruction (dropped by :load)"},
        {"role": "system", "content": "[SKILL] name=demo"},
        {"role": "user", "content": "hello"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "c1", "type": "function", "function": {}}],
        },
        {"role": "tool", "tool_call_id": "c1", "name": "demo", "content": "ok"},
        {"role": "assistant", "content": "done"},
    ]
    if cwd_dir is not None:
        lines.insert(1, {"role": "system", "content": _cwd_content(cwd_dir)})
    log = log_dir / "scheck_log_20260101_000000.jsonl"
    _write_log(log, lines)
    return log


def _parse_msgs_from_logs_output(capsys) -> int:
    # Locale-independent: "[0] <mtime> | <N> ... | first: ... | last: ..."
    out = capsys.readouterr().out
    m = re.search(r"\| *(\d+) *[^|\n]*\|", out)
    assert m, f"no msgs count found in output: {out!r}"
    return int(m.group(1))


def test_logs_count_matches_load_without_cwd(tmp_path, monkeypatch, capsys):
    log = _setup(tmp_path, monkeypatch, cwd_dir=None)

    ucore.list_logs(limit=10, show_all=True)
    shown = _parse_msgs_from_logs_output(capsys)

    loaded = ucore.load_conversation_from_log(str(log))
    # user=1, assistant=2, tool=1, [SKILL] preserved=1 -> loaded=1+1+1+2+1=6
    assert len(loaded) == 6
    assert shown == len(loaded)


def test_logs_count_includes_existing_cwd_marker(tmp_path, monkeypatch, capsys):
    workdir = tmp_path / "workdir_a"
    workdir.mkdir()
    log = _setup(tmp_path, monkeypatch, cwd_dir=str(workdir))

    ucore.list_logs(limit=10, show_all=True)
    shown = _parse_msgs_from_logs_output(capsys)

    loaded = ucore.load_conversation_from_log(str(log))
    # [CWD] exists on disk -> :load would insert an extra system message
    assert shown == len(loaded) + 1


def test_logs_count_skips_missing_cwd_marker(tmp_path, monkeypatch, capsys):
    gone = tmp_path / "gone"
    log = _setup(tmp_path, monkeypatch, cwd_dir=str(gone))

    ucore.list_logs(limit=10, show_all=True)
    shown = _parse_msgs_from_logs_output(capsys)

    loaded = ucore.load_conversation_from_log(str(log))
    assert shown == len(loaded)


def test_load_restores_cwd_from_raw_log_lines(tmp_path):
    workdir = tmp_path / "wd"
    workdir.mkdir()
    log = tmp_path / "scheck_log_x.jsonl"
    _write_log(
        log,
        [
            {"role": "system", "content": "plain"},
            {"role": "system", "content": _cwd_content(str(workdir))},
            {"role": "user", "content": "hi"},
        ],
    )
    raw = ut._read_raw_log_messages(str(log))
    assert ut._extract_last_cwd_from_messages(raw) == str(workdir)
    # Normalized/loaded messages no longer contain the [CWD] marker.
    loaded = ucore.load_conversation_from_log(str(log))
    assert ut._extract_last_cwd_from_messages(loaded) is None


def test_list_logs_filters_by_workdir(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setattr(ucore, "BASE_LOG_DIR", str(log_dir))
    monkeypatch.setattr(ucore, "LOG_FILE", str(log_dir / "current_session.jsonl"))

    base = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "yo"},
    ]
    fa = log_dir / "scheck_log_20260102_000000.jsonl"
    _write_log(fa, [{"role": "system", "content": _cwd_content("/work/a")}] + base)
    fb = log_dir / "scheck_log_20260101_000000.jsonl"
    _write_log(fb, [{"role": "system", "content": _cwd_content("/work/b")}] + base)
    fmeta = log_dir / "scheck_log_20251231_000000.jsonl"
    _write_log(fmeta, [{"type": "session_metadata", "project_path": "/work/a"}] + base)
    fnone = log_dir / "scheck_log_20251230_000000.jsonl"
    _write_log(fnone, base)
    for index, path in enumerate([fnone, fmeta, fb, fa]):
        stamp = 1_700_000_000 + index * 100
        os.utime(path, (stamp, stamp))

    view = ucore.list_logs(limit=10, show_all=True, workdir="/work/a")
    assert view == [str(fa), str(fmeta)]
    # The displayed view is what :load indices resolve against.
    assert ucore.last_log_view() == view

    assert ucore.list_logs(limit=10, show_all=True, workdir="/work/b") == [str(fb)]
    # Unknown-workdir logs appear only in the unfiltered listing.
    assert len(ucore.list_logs(limit=10, show_all=True)) == 4


def test_list_logs_workdir_marker_wins_over_metadata(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setattr(ucore, "BASE_LOG_DIR", str(log_dir))
    monkeypatch.setattr(ucore, "LOG_FILE", str(log_dir / "current_session.jsonl"))

    base = [{"role": "user", "content": "hi"}]
    moved = log_dir / "scheck_log_20260102_000000.jsonl"
    _write_log(
        moved,
        [{"type": "session_metadata", "project_path": "/work/a"}]
        + [{"role": "system", "content": _cwd_content("/work/b")}]
        + base,
    )

    assert ucore.list_logs(limit=10, show_all=True, workdir="/work/a") == []
    assert ucore.list_logs(limit=10, show_all=True, workdir="/work/b") == [str(moved)]


def test_load_index_preserves_empty_displayed_view(tmp_path, monkeypatch, capsys):
    from types import SimpleNamespace

    from uagent.util_cmd_session import _handle_cmd_load

    monkeypatch.setenv("UAGENT_SESSION_BACKEND", "jsonl")
    unrelated = tmp_path / "scheck_log_20260101_000000.jsonl"
    unrelated.write_text("{}\n", encoding="utf-8")
    loaded: list[str] = []
    core = SimpleNamespace(
        session_store=None,
        last_log_view=lambda: [],
        find_log_files=lambda exclude_current=True: [str(unrelated)],
        load_conversation_from_log=lambda path: loaded.append(path) or [],
    )
    messages: list = []
    assert _handle_cmd_load("0", messages, core=core, tr=lambda text, **_: text)
    # The empty displayed view is a real listing: index 0 is out of
    # range, and the unrelated log is never loaded.
    assert loaded == []
    assert "out of range" in capsys.readouterr().out


def test_load_index_ignores_displayed_view_when_opted_out(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from uagent.util_cmd_session import _handle_cmd_load

    monkeypatch.setenv("UAGENT_SESSION_BACKEND", "jsonl")
    newest = tmp_path / "scheck_log_20260102_000000.jsonl"
    newest.write_text("{}\n", encoding="utf-8")
    older = tmp_path / "scheck_log_20260101_000000.jsonl"
    older.write_text("{}\n", encoding="utf-8")
    loaded: list[str] = []
    core = SimpleNamespace(
        session_store=None,
        last_log_view=lambda: [str(older)],
        find_log_files=lambda exclude_current=True: [str(newest), str(older)],
        load_conversation_from_log=lambda path: loaded.append(path)
        or [{"role": "user", "content": "hi"}],
    )
    messages: list = []
    # :cont passes use_last_displayed_view=False: index 0 is the newest
    # log overall, not the first row of the displayed listing.
    assert _handle_cmd_load(
        "0",
        messages,
        core=core,
        tr=lambda text, **_: text,
        use_last_displayed_view=False,
    )
    assert loaded == [str(newest)]
