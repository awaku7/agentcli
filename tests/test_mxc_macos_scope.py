"""macOS process-tree accounting invariants, runnable on every CI OS."""

from __future__ import annotations

import threading
from types import SimpleNamespace

from uagent.runtime import mxc_backend, mxc_macos_scope


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
    before = {
        100: _process(100, 1, 100, 0.1, "root"),
        101: _process(101, 100, 100, 1.0, "original"),
    }
    mxc_macos_scope._summarize(100, 100, known, ledger, before)
    # The genuine root is still alive, so a replacement group member is
    # provably within the original sandbox despite recycling its numeric PID.
    after = {
        100: _process(100, 1, 100, 0.2, "root"),
        101: _process(101, 100, 100, 0.0, "replacement"),
    }
    count, _, cpu = mxc_macos_scope._summarize(100, 100, known, ledger, after)
    assert count == 2
    assert known[101] == "replacement"
    assert cpu == 1.2

    # The verified replacement stays tracked after detachment and root exit.
    detached = {101: _process(101, 1, 900, 0.4, "replacement")}
    count, _, cpu = mxc_macos_scope._summarize(100, 100, known, ledger, detached)
    assert count == 1
    assert cpu == 1.6


def test_macos_recycled_helper_group_is_not_adopted_or_signaled(monkeypatch):
    """The numeric PGID may be reused by an unrelated process after exit."""
    known = {100: "original-helper", 101: "detached-child"}
    ledger = {}
    unrelated = {
        100: _process(100, 1, 100, 0.1, "unrelated-leader"),
        102: _process(102, 100, 100, 0.2, "unrelated-child"),
    }
    count, rss, cpu = mxc_macos_scope._summarize(100, 100, known, ledger, unrelated)
    assert (count, rss, cpu) == (0, 0, 0.0)
    assert known[100] == "original-helper"
    assert 102 not in known

    supervisor = mxc_macos_scope.MacosProcessGroup.__new__(
        mxc_macos_scope.MacosProcessGroup
    )
    supervisor.process = SimpleNamespace(pid=100, poll=lambda: 0)
    supervisor.pgid = 100
    supervisor._known = known
    supervisor._cpu_ledger = ledger
    supervisor._tracking_lock = threading.RLock()
    monkeypatch.setattr(mxc_macos_scope, "_process_table", lambda: unrelated)
    signaled = []
    monkeypatch.setattr(
        mxc_macos_scope.os,
        "killpg",
        lambda gid, sig: signaled.append(("group", gid)),
    )
    monkeypatch.setattr(
        mxc_macos_scope.os,
        "kill",
        lambda pid, sig: signaled.append(("pid", pid)),
    )
    supervisor._terminate_observed()
    assert signaled == []
    assert known[100] == "original-helper"


def test_macos_only_kills_verified_live_original_helper_group(monkeypatch):
    """Retain group teardown when the genuine helper owns the current PGID."""
    supervisor = mxc_macos_scope.MacosProcessGroup.__new__(
        mxc_macos_scope.MacosProcessGroup
    )
    supervisor.process = SimpleNamespace(pid=100, poll=lambda: None)
    supervisor.pgid = 100
    supervisor._known = {100: "original-helper"}
    supervisor._cpu_ledger = {}
    supervisor._tracking_lock = threading.RLock()
    own = {100: _process(100, 1, 100, 0.1, "original-helper")}
    monkeypatch.setattr(mxc_macos_scope, "_process_table", lambda: own)
    killed = []
    monkeypatch.setattr(
        mxc_macos_scope.os,
        "killpg",
        lambda gid, sig: killed.append(("group", gid)),
    )
    monkeypatch.setattr(
        mxc_macos_scope.os,
        "kill",
        lambda pid, sig: killed.append(("pid", pid)),
    )
    supervisor._terminate_observed()
    assert ("group", 100) in killed
    assert ("pid", 100) not in killed


def test_macos_poll_reaped_helper_never_gets_stale_pid_signal(monkeypatch):
    """Popen.poll() can reap the helper after ps but before os.kill(pid)."""
    supervisor = mxc_macos_scope.MacosProcessGroup.__new__(
        mxc_macos_scope.MacosProcessGroup
    )
    supervisor.process = SimpleNamespace(pid=100, poll=lambda: 0)
    supervisor.pgid = 100
    supervisor._known = {100: "original-helper", 102: "detached-owned"}
    supervisor._cpu_ledger = {}
    supervisor._tracking_lock = threading.RLock()
    table = {
        100: _process(100, 1, 100, 0.1, "original-helper"),
        102: _process(102, 1, 900, 0.2, "detached-owned"),
    }
    monkeypatch.setattr(mxc_macos_scope, "_process_table", lambda: table)
    signaled = []
    monkeypatch.setattr(
        mxc_macos_scope.os,
        "killpg",
        lambda gid, sig: signaled.append(("group", gid)),
    )
    monkeypatch.setattr(
        mxc_macos_scope.os,
        "kill",
        lambda pid, sig: signaled.append(("pid", pid)),
    )
    supervisor._terminate_observed()
    assert ("group", 100) not in signaled
    assert ("pid", 100) not in signaled
    assert ("pid", 102) in signaled


def test_macos_zombie_snapshot_is_not_a_kill_target(monkeypatch):
    """A zombie still visible in ps is not evidence of a live group owner."""
    supervisor = mxc_macos_scope.MacosProcessGroup.__new__(
        mxc_macos_scope.MacosProcessGroup
    )
    supervisor.process = SimpleNamespace(pid=100, poll=lambda: None)
    supervisor.pgid = 100
    supervisor._known = {100: "original-helper"}
    supervisor._cpu_ledger = {}
    supervisor._tracking_lock = threading.RLock()
    zombie = mxc_macos_scope._Process(
        pid=100,
        ppid=1,
        pgid=100,
        rss_kib=0,
        cpu_seconds=0.1,
        state="Z",
        started="original-helper",
    )
    monkeypatch.setattr(mxc_macos_scope, "_process_table", lambda: {100: zombie})
    signaled = []
    monkeypatch.setattr(
        mxc_macos_scope.os,
        "killpg",
        lambda gid, sig: signaled.append(("group", gid)),
    )
    monkeypatch.setattr(
        mxc_macos_scope.os,
        "kill",
        lambda pid, sig: signaled.append(("pid", pid)),
    )
    supervisor._terminate_observed()
    assert signaled == []


def test_macos_manager_prune_cannot_trigger_duplicate_helper_pid_kill(monkeypatch):
    """Manager polling/reaping during group SIGKILL must not permit stale PID kill."""

    class ReapedProcess:
        pid = 100
        reaped = False

        def poll(self):
            return 0 if self.reaped else None

    process = ReapedProcess()

    class FakeSession:
        _closed = False
        _scope = None
        _proc = process

        def close(self):
            self._closed = True

    manager = mxc_backend.MxcSessionManager.__new__(mxc_backend.MxcSessionManager)
    manager._sessions = {"existing": FakeSession()}
    manager._session_last_used = {"existing": 0}
    manager._active_web_scopes = set()
    manager._dormant_web_scopes = {}

    supervisor = mxc_macos_scope.MacosProcessGroup.__new__(
        mxc_macos_scope.MacosProcessGroup
    )
    supervisor.process = process
    supervisor.pgid = 100
    supervisor._known = {100: "genuine-helper", 102: "verified-child"}
    supervisor._cpu_ledger = {}
    supervisor._tracking_lock = threading.RLock()
    table = {
        100: _process(100, 1, 100, 0.1, "genuine-helper"),
        102: _process(102, 100, 100, 0.1, "verified-child"),
    }
    monkeypatch.setattr(mxc_macos_scope, "_process_table", lambda: table)
    signaled = []

    def kill_group(group_id, _sig):
        signaled.append(("group", group_id))
        process.reaped = True
        # The manager sees exit and reaps the PID while the watcher still
        # holds its prior (valid) process-table snapshot.
        manager._prune_inactive_sessions()

    monkeypatch.setattr(mxc_macos_scope.os, "killpg", kill_group)
    monkeypatch.setattr(
        mxc_macos_scope.os,
        "kill",
        lambda pid, _sig: signaled.append(("pid", pid)),
    )
    supervisor._terminate_observed()
    assert ("group", 100) in signaled
    assert ("pid", 100) not in signaled
    assert ("pid", 102) in signaled
    assert manager._sessions == {}


def test_macos_prune_poll_waits_for_identity_checked_group_signal(monkeypatch):
    """Manager cannot reap and recycle the helper PGID before killpg runs."""

    class FakeProcess:
        pid = 100
        reaped = False

        def poll(self):
            return 0 if self.reaped else None

    process = FakeProcess()
    supervisor = mxc_macos_scope.MacosProcessGroup.__new__(
        mxc_macos_scope.MacosProcessGroup
    )
    supervisor.process = process
    supervisor.pgid = 100
    supervisor._known = {100: "original-helper"}
    supervisor._cpu_ledger = {}
    supervisor._tracking_lock = threading.RLock()

    class FakeSession:
        _closed = False
        _scope = None
        _proc = process
        _mac_scope = supervisor

        def close(self):
            self._closed = True

    manager = mxc_backend.MxcSessionManager.__new__(mxc_backend.MxcSessionManager)
    manager._sessions = {"session": FakeSession()}
    manager._session_last_used = {"session": 0}
    manager._active_web_scopes = set()
    manager._dormant_web_scopes = {}

    own = {100: _process(100, 1, 100, 0.1, "original-helper")}
    monkeypatch.setattr(mxc_macos_scope, "_process_table", lambda: own)
    signals = []
    prune_started = threading.Event()
    prune_finished = threading.Event()
    pruning = []

    def prune():
        prune_started.set()
        manager._prune_inactive_sessions()
        prune_finished.set()

    def kill_group(group_id, _sig):
        signals.append(("group", group_id))
        thread = threading.Thread(target=prune, name="concurrent-pruner")
        pruning.append(thread)
        thread.start()
        assert prune_started.wait(timeout=5)
        # _terminate_observed() still owns the tracker lock during signal
        # delivery; the concurrent manager poll must remain blocked.
        assert not prune_finished.wait(timeout=0.05)
        process.reaped = True

    monkeypatch.setattr(mxc_macos_scope.os, "killpg", kill_group)
    monkeypatch.setattr(
        mxc_macos_scope.os,
        "kill",
        lambda pid, _sig: signals.append(("pid", pid)),
    )
    supervisor._terminate_observed()
    assert len(pruning) == 1
    pruning[0].join(timeout=5)
    assert prune_finished.is_set()
    assert ("group", 100) in signals
    assert ("pid", 100) not in signals
    assert manager._sessions == {}


def test_reap_uses_same_snapshot_to_register_new_detached_grandchild(monkeypatch):
    """A detached parent can fork between two ps snapshots during cleanup."""
    scope = mxc_macos_scope.MacosProcessGroup.__new__(mxc_macos_scope.MacosProcessGroup)
    scope.process = SimpleNamespace(pid=100)
    scope.pgid = 100
    scope._known = {100: "root", 101: "parent"}
    scope._cpu_ledger = {}
    scope._tracking_lock = threading.RLock()

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
    monkeypatch.setattr(
        mxc_macos_scope.os, "kill", lambda pid, _sig: killed.append(pid)
    )
    monkeypatch.setattr(mxc_macos_scope.time, "sleep", lambda _seconds: None)
    scope.reap_since(frozenset({(100, "root")}))
    assert 101 in killed
    assert 102 in killed
    assert scope._known[102] == "child"


def test_macos_watchdog_cannot_overwrite_newer_reap_identity(monkeypatch):
    """The watcher may observe a stale PID before a replacement exists."""
    scope = mxc_macos_scope.MacosProcessGroup.__new__(mxc_macos_scope.MacosProcessGroup)
    scope.process = SimpleNamespace(pid=100)
    scope.pgid = 100
    scope._known = {100: "root", 101: "old"}
    scope._cpu_ledger = {}
    scope._tracking_lock = threading.RLock()
    root = _process(100, 1, 100, 0.1, "root")
    old = _process(101, 100, 100, 0.1, "old")
    replacement = _process(101, 100, 100, 0.2, "new")
    watcher_inside_ps = threading.Event()
    allow_old_ps = threading.Event()
    killed = []
    observations = [0]

    def fake_ps():
        if threading.current_thread().name == "stale-watcher":
            watcher_inside_ps.set()
            assert allow_old_ps.wait(timeout=5)
            return {100: root, 101: old}
        observations[0] += 1
        return {100: root, 101: replacement} if observations[0] == 1 else {100: root}

    monkeypatch.setattr(mxc_macos_scope, "_process_table", fake_ps)
    monkeypatch.setattr(
        mxc_macos_scope.os, "kill", lambda pid, _sig: killed.append(pid)
    )
    monkeypatch.setattr(mxc_macos_scope.time, "sleep", lambda _seconds: None)

    watcher = threading.Thread(target=scope._inspect, name="stale-watcher")
    watcher.start()
    assert watcher_inside_ps.wait(timeout=5)
    result = []

    def reap():
        scope.reap_since(frozenset({(100, "root")}))
        result.append("complete")

    reaper = threading.Thread(target=reap, name="one-shot-reaper")
    reaper.start()
    allow_old_ps.set()
    watcher.join(timeout=5)
    reaper.join(timeout=5)
    assert not watcher.is_alive() and not reaper.is_alive()
    assert result == ["complete"]
    assert scope._known[101] == "new"
    assert 101 in killed
