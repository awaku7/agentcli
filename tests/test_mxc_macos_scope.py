"""macOS process-tree accounting invariants, runnable on every CI OS."""

from __future__ import annotations

from types import SimpleNamespace

from uagent.runtime import mxc_macos_scope


def _process(pid, ppid, pgid, cpu, started):
    return mxc_macos_scope._Process(
        pid=pid,
        ppid=ppid,
        pgid=pgid,
        rss_kib=10,
        cpu_seconds=cpu,
        state="S",
        started=started,
    )


def test_macos_cpu_ledger_retains_exited_children():
    known: dict[int, str] = {}
    ledger: dict[tuple[int, str], float] = {}
    first = {
        100: _process(100, 1, 100, 0.2, "root"),
        101: _process(101, 100, 100, 0.8, "child-a"),
    }
    count, rss, cpu = mxc_macos_scope._summarize(100, 100, known, ledger, first)
    assert (count, rss) == (2, 20)
    assert cpu == 1.0

    second = {
        100: _process(100, 1, 100, 0.4, "root"),
        102: _process(102, 100, 100, 0.9, "child-b"),
    }
    count, rss, cpu = mxc_macos_scope._summarize(100, 100, known, ledger, second)
    assert (count, rss) == (2, 20)
    assert cpu > 2.0
    # Neither short-lived child reached this illustrative 1.5-second budget,
    # but the observed aggregate of both completed children does.
    assert cpu > 1.5


def test_macos_tracks_descendants_after_setsid_and_parent_exit():
    known: dict[int, str] = {}
    ledger: dict[tuple[int, str], float] = {}
    before = {
        100: _process(100, 1, 100, 0.2, "root"),
        101: _process(101, 100, 900, 0.1, "detached"),
    }
    count, _, _ = mxc_macos_scope._summarize(100, 100, known, ledger, before)
    assert count == 2
    assert known[101] == "detached"

    after = {
        101: _process(101, 1, 900, 0.5, "detached"),
    }
    count, _, cpu = mxc_macos_scope._summarize(100, 100, known, ledger, after)
    assert count == 1
    assert cpu >= 0.7


def test_macos_pid_reuse_cannot_inherit_previous_cpu_identity():
    known: dict[int, str] = {}
    ledger: dict[tuple[int, str], float] = {}
    before = {100: _process(100, 1, 100, 1.0, "original")}
    mxc_macos_scope._summarize(100, 100, known, ledger, before)
    after = {100: _process(100, 1, 100, 0.0, "replacement")}
    count, _, cpu = mxc_macos_scope._summarize(100, 100, known, ledger, after)
    assert count == 1
    assert known[100] == "replacement"
    assert cpu == 1.0

    # A recycled sandbox PID that later changes group must remain tracked.
    detached = {100: _process(100, 1, 900, 0.4, "replacement")}
    count, _, cpu = mxc_macos_scope._summarize(100, 100, known, ledger, detached)
    assert count == 1
    assert cpu == 1.4


def test_reap_uses_same_snapshot_to_register_new_detached_grandchild(monkeypatch):
    """A detached parent can fork between two ps snapshots during cleanup."""
    scope = mxc_macos_scope.MacosProcessGroup.__new__(
        mxc_macos_scope.MacosProcessGroup
    )
    scope.process = SimpleNamespace(pid=100)
    scope.pgid = 100
    scope._known = {100: "root", 101: "parent"}
    scope._cpu_ledger = {}

    root = _process(100, 1, 100, 0.1, "root")
    parent = _process(101, 1, 900, 0.1, "parent")
    child = _process(102, 101, 901, 0.1, "child")
    reparented = _process(102, 1, 901, 0.2, "child")
    observations = iter(
        [
            {100: root, 101: parent},
            {100: root, 101: parent, 102: child},
            {100: root, 102: reparented},
            {100: root},
        ]
    )
    monkeypatch.setattr(
        mxc_macos_scope,
        "_process_table",
        lambda: next(observations, {100: root}),
    )
    killed = []
    monkeypatch.setattr(mxc_macos_scope.os, "kill", lambda pid, _sig: killed.append(pid))
    monkeypatch.setattr(mxc_macos_scope.time, "sleep", lambda _seconds: None)
    scope.reap_since(frozenset({(100, "root")}))
    assert 101 in killed
    assert 102 in killed
    assert scope._known[102] == "child"
