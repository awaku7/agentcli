from __future__ import annotations

import threading
from queue import Queue
from types import SimpleNamespace

from uagent.runtime.identity_context import TurnContext, bind_turn_context
from uagent.runtime.sub_agent_job_access import get_job_runtime_context
from uagent.runtime.sub_agent_jobs import (
    CURRENT_SUB_AGENT_JOB_MODE,
    SubAgentJobManager,
    SubAgentJobOwner,
    SubAgentJobSettings,
)


def _turn(entry: str, session: str, room: str = "") -> TurnContext:
    return TurnContext(
        principal_id="local",
        room_id=room,
        project_id="",
        session_id=session,
        entry_point=entry,
        authenticated=True,
        authn_kind="local",
    )


def _manager(**overrides) -> SubAgentJobManager:
    settings = {
        "workers": 1,
        "queue_limit": 4,
        "owner_limit": 8,
        "completed_limit": 10,
        "result_ttl_sec": 60,
        "event_limit": 20,
        "log_max_bytes": 4096,
        "result_max_bytes": 4096,
        "shutdown_timeout_sec": 0.2,
    }
    notice_callback = overrides.pop("notice_callback", None)
    confirmation_handler = overrides.pop("confirmation_handler", None)
    settings.update(overrides)
    return SubAgentJobManager(
        SubAgentJobSettings(**settings),
        notice_callback=notice_callback,
        confirmation_handler=confirmation_handler,
    )


def test_web_job_runtime_is_bound_to_the_authenticated_room(monkeypatch):
    from uagent.web_impl.rooms import (
        WebRoom,
        set_context_web_room,
        reset_context_web_room,
    )
    from uagent.web_impl.rooms import web_manager

    room = WebRoom("room-a")
    room.session_id = "private-session-a"
    manager = object()
    monkeypatch.setattr(web_manager, "sub_agent_job_manager", manager, raising=False)
    token = set_context_web_room(room)
    try:
        with bind_turn_context(_turn("web", "private-session-a", "room-a")):
            assert get_job_runtime_context() == (
                manager,
                SubAgentJobOwner(
                    entry_point="web",
                    session_id="private-session-a",
                    room_id="room-a",
                    principal_id="local",
                ),
            )
            from uagent import tools

            assert tools._sub_agent_job_tools_visible() is True
        with bind_turn_context(_turn("web", "other-session", "room-a")):
            assert get_job_runtime_context() is None
        with bind_turn_context(_turn("web", "private-session-a", "room-b")):
            assert get_job_runtime_context() is None
    finally:
        reset_context_web_room(token)


def test_gui_job_runtime_requires_the_current_gui_session(monkeypatch):
    import uagent.core as core

    manager = object()
    owner = SubAgentJobOwner(entry_point="gui", session_id="gui-session")
    monkeypatch.setattr(core, "_sub_agent_job_manager", manager, raising=False)
    monkeypatch.setattr(core, "_sub_agent_job_owner", owner, raising=False)
    with bind_turn_context(_turn("gui", "gui-session")):
        assert get_job_runtime_context() == (manager, owner)
        from uagent import tools

        assert tools._sub_agent_job_tools_visible() is True
    with bind_turn_context(_turn("gui", "other-session")):
        assert get_job_runtime_context() is None
    with bind_turn_context(_turn("cli", "gui-session")):
        assert get_job_runtime_context() is None


def test_gui_job_confirmation_broker_routes_reply_and_cancellation():
    from uagent.scheckgui_impl.sub_agent_jobs import GUIJobConfirmationBroker

    requests: Queue = Queue()
    cancellations = []
    broker = GUIJobConfirmationBroker(requests.put, cancellations.append)
    manager = _manager(
        confirmation_handler=lambda context, message, password: (
            context.set_waiting_for_user(True),
            broker.ask(context, message, password),
            context.set_waiting_for_user(False),
        )[1]
    )
    owner = SubAgentJobOwner(entry_point="gui", session_id="gui-session")
    try:
        accepted = manager.spawn(
            owner=owner,
            agent_name="reviewer",
            task="confirm",
            worker=lambda context: context.ask_user("Approve patch?"),
        )
        request = requests.get(timeout=2)
        assert request.job_id == accepted["job_id"]
        assert request.agent_name == "reviewer"
        assert (
            manager.get(owner=owner, job_id=accepted["job_id"])["state"]
            == "waiting_for_user"
        )
        request.respond("approved")
        result = manager.wait(owner=owner, job_id=accepted["job_id"], timeout=2)
        assert result["state"] == "completed"
        assert result["result"] == "approved"

        second = manager.spawn(
            owner=owner,
            agent_name="planner",
            task="cancel confirmation",
            worker=lambda context: context.ask_user("Continue?"),
        )
        second_request = requests.get(timeout=2)
        assert (
            manager.cancel(owner=owner, job_id=second["job_id"])["state"] == "cancelled"
        )
        assert (
            manager.wait(owner=owner, job_id=second["job_id"], timeout=2)["state"]
            == "cancelled"
        )
        assert second_request.completed.wait(1)
        assert second["job_id"] in cancellations
    finally:
        manager.shutdown()


def test_background_and_synchronous_subagents_cannot_use_host_job_runtime(
    monkeypatch,
):
    from uagent.tools.context import reset_active_sub_agent, set_active_sub_agent
    import uagent.core as core

    manager = object()
    owner = SubAgentJobOwner(entry_point="gui", session_id="gui-session")
    monkeypatch.setattr(core, "_sub_agent_job_manager", manager, raising=False)
    monkeypatch.setattr(core, "_sub_agent_job_owner", owner, raising=False)
    with bind_turn_context(_turn("gui", "gui-session")):
        mode_token = CURRENT_SUB_AGENT_JOB_MODE.set("background")
        try:
            assert get_job_runtime_context() is None
        finally:
            CURRENT_SUB_AGENT_JOB_MODE.reset(mode_token)
        active_token = set_active_sub_agent("planner")
        try:
            assert get_job_runtime_context() is None
        finally:
            reset_active_sub_agent(active_token)


def test_web_job_confirmation_is_room_owned_and_cancel_wakes_waiter(monkeypatch):
    from uagent.web_impl.rooms import WebRoom, web_manager
    from uagent.web_impl.sub_agent_jobs import _web_confirmation_handler

    room = WebRoom("room-web")
    room.session_id = "session-web"
    room.active_connections.append(object())
    monkeypatch.setattr(web_manager, "get_room", lambda _room_id: room)
    owner = SubAgentJobOwner(
        entry_point="web",
        session_id="session-web",
        room_id="room-web",
        principal_id="alice",
    )
    manager = _manager(confirmation_handler=_web_confirmation_handler)
    try:
        accepted = manager.spawn(
            owner=owner,
            agent_name="reviewer",
            task="ask the Web user",
            worker=lambda context: context.ask_user("Approve this patch?"),
        )
        state = ""
        for _ in range(100):
            state = manager.get(owner=owner, job_id=accepted["job_id"])["state"]
            if state == "waiting_for_user":
                break
            threading.Event().wait(0.02)
        assert state == "waiting_for_user"
        assert room.human_ask_pending is True
        assert "Background Job" in room.human_ask_message
        manager.cancel(owner=owner, job_id=accepted["job_id"], reason="test cancel")
        result = manager.wait(owner=owner, job_id=accepted["job_id"], timeout=2)
        assert result["state"] == "cancelled"
        for _ in range(100):
            if not room.human_ask_pending:
                break
            threading.Event().wait(0.02)
        assert room.human_ask_pending is False
    finally:
        manager.shutdown()


def test_gui_job_runtime_initialization_binds_owner_and_shuts_down():
    from uagent.scheckgui_impl.sub_agent_jobs import (
        initialize_gui_job_runtime,
        shutdown_gui_job_runtime,
    )

    class Signal:
        def emit(self, _value):
            pass

    core = SimpleNamespace(session_id="gui-host-session")
    worker = SimpleNamespace(
        sig_job_notice=Signal(),
        sig_job_confirmation_request=Signal(),
        sig_job_confirmation_cancel=Signal(),
    )
    manager = initialize_gui_job_runtime(core, worker)
    try:
        assert core._sub_agent_job_manager is manager
        assert core._sub_agent_job_owner == SubAgentJobOwner(
            entry_point="gui", session_id="gui-host-session"
        )
    finally:
        shutdown_gui_job_runtime(core)
    assert not hasattr(core, "_sub_agent_job_manager")


def test_web_private_room_is_retained_while_owned_background_job_runs():
    from uagent.web_impl.rooms import WebManager

    manager = WebManager()
    room, _ = manager.get_or_create_room("private-room")
    room.private_session = True
    room.session_id = "private-session"
    room.last_activity = 1.0

    class ActiveJobManager:
        active = True

        def running_count_for_room(self, room_id):
            assert room_id == "private-room"
            return 1 if self.active else 0

    jobs = ActiveJobManager()
    manager.sub_agent_job_manager = jobs
    assert manager.evict_idle_rooms(idle_ttl_seconds=0, now=10.0) == []
    jobs.active = False
    assert manager.evict_idle_rooms(idle_ttl_seconds=0, now=10.0) == ["private-room"]


def test_gui_mainwindow_job_controls_import_when_qt_is_available():
    import pytest

    pytest.importorskip("PySide6")
    from uagent.scheckgui_impl.mainwindow import MainWindow

    assert callable(MainWindow._show_sub_agent_jobs)
    assert callable(MainWindow._on_job_confirmation_request)


def test_web_job_runtime_lifecycle_creates_and_stops_manager():
    from uagent.web_impl.rooms import web_manager
    from uagent.web_impl.sub_agent_jobs import (
        initialize_web_job_runtime,
        shutdown_web_job_runtime,
    )

    manager = initialize_web_job_runtime()
    try:
        assert web_manager.sub_agent_job_manager is manager
        assert (
            manager.running_count(
                owner=SubAgentJobOwner(
                    entry_point="web", session_id="session", room_id="room"
                )
            )
            == 0
        )
    finally:
        shutdown_web_job_runtime()
    assert web_manager.sub_agent_job_manager is None


def test_a2a_job_runtime_is_scoped_to_the_bound_task():
    from uagent.runtime.sub_agent_job_access import bind_a2a_job_runtime_context

    manager = object()
    owner = SubAgentJobOwner(
        entry_point="a2a", session_id="task-a", a2a_task_id="task-a"
    )
    cancel_event = threading.Event()
    with bind_turn_context(_turn("a2a", "session-store-id")):
        assert get_job_runtime_context() is None
        with bind_a2a_job_runtime_context(manager, owner, cancel_event):
            assert get_job_runtime_context() == (manager, owner)
            cancel_event.set()
            assert get_job_runtime_context() is None


def test_gui_session_owner_refresh_aborts_when_previous_workers_linger():
    import pytest

    from uagent.scheckgui_impl.sub_agent_jobs import refresh_gui_job_owner

    previous = SubAgentJobOwner(entry_point="gui", session_id="old-session")
    calls = []

    class Manager:
        def pause_owner(self, owner):
            calls.append(("pause", owner))

        def cancel_all(self, *, owner, reason):
            calls.append(("cancel", owner, reason))

        def wait_owner_workers(self, *, owner, timeout):
            calls.append(("wait", owner, timeout))
            return False

        def active_job_ids(self, owner):
            calls.append(("active", owner))
            return ["lingering-job"]

        def resume_owner(self, owner):
            calls.append(("resume", owner))

    core = SimpleNamespace(
        session_id="new-session",
        _sub_agent_job_owner=previous,
        _sub_agent_job_manager=Manager(),
    )

    with pytest.raises(RuntimeError, match="lingering-job"):
        refresh_gui_job_owner(core, core.session_id)

    assert core._sub_agent_job_owner == previous
    assert calls == [
        ("pause", previous),
        ("cancel", previous, "GUI session changed"),
        ("wait", previous, 5.0),
        ("active", previous),
    ]


def test_gui_turn_does_not_activate_scope_when_owner_refresh_fails(monkeypatch):
    import pytest

    pytest.importorskip("PySide6")
    from uagent.runtime import mxc_backend
    from uagent.scheckgui_impl import sub_agent_jobs as gui_jobs
    from uagent.scheckgui_impl import worker as gui_worker

    core = SimpleNamespace(session_id="new-session", _sandbox_enabled=True)
    monkeypatch.setattr(gui_worker, "core", core)
    monkeypatch.setattr(
        gui_jobs,
        "refresh_gui_job_owner",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("transition refused")),
    )
    activations = []
    manager = SimpleNamespace(activate_scope=lambda scope: activations.append(scope))
    monkeypatch.setattr(mxc_backend, "current_session_manager", lambda: manager)
    monkeypatch.setattr(
        mxc_backend,
        "startup_scope",
        lambda **_kwargs: SimpleNamespace(scope_id="new-scope"),
    )
    executed = []
    monkeypatch.setattr(
        gui_worker,
        "call_with_resolved_turn_context",
        lambda fn, *args, **kwargs: fn(*args, **kwargs),
    )

    with pytest.raises(RuntimeError, match="transition refused"):
        gui_worker.ScheckWorker._run_gui_turn(object(), lambda: executed.append("ran"))

    assert activations == []
    assert executed == []


def test_gui_session_owner_refresh_resumes_the_new_owner_after_workers_exit():
    from uagent.scheckgui_impl.sub_agent_jobs import refresh_gui_job_owner

    previous = SubAgentJobOwner(entry_point="gui", session_id="old-session")
    expected = SubAgentJobOwner(entry_point="gui", session_id="new-session")
    calls = []

    class Manager:
        def pause_owner(self, owner):
            calls.append(("pause", owner))

        def cancel_all(self, *, owner, reason):
            calls.append(("cancel", owner, reason))

        def wait_owner_workers(self, *, owner, timeout):
            calls.append(("wait", owner, timeout))
            return True

        def resume_owner(self, owner):
            calls.append(("resume", owner))

    core = SimpleNamespace(
        session_id="new-session",
        _sub_agent_job_owner=previous,
        _sub_agent_job_manager=Manager(),
    )

    assert refresh_gui_job_owner(core, core.session_id) == expected
    assert core._sub_agent_job_owner == expected
    assert calls == [
        ("pause", previous),
        ("cancel", previous, "GUI session changed"),
        ("wait", previous, 5.0),
        ("resume", expected),
    ]


def test_gui_session_command_drains_old_owner_before_dispatch():
    from uagent.scheckgui_impl.sub_agent_jobs import (
        run_gui_command_with_session_transition_guard,
    )

    old_owner = SubAgentJobOwner(entry_point="gui", session_id="old-session")
    new_owner = SubAgentJobOwner(entry_point="gui", session_id="new-session")
    events = []

    class Manager:
        def pause_owner(self, owner):
            events.append(("pause", owner.session_id))

        def cancel_all(self, *, owner, reason):
            events.append(("cancel", owner.session_id, reason))

        def wait_owner_workers(self, owner, timeout):
            events.append(("wait", owner.session_id, timeout))
            return True

        def active_job_ids(self, owner):
            return []

        def resume_owner(self, owner):
            events.append(("resume", owner.session_id))

    core = SimpleNamespace(
        session_id="old-session",
        _sub_agent_job_owner=old_owner,
        _sub_agent_job_manager=Manager(),
    )

    def dispatch():
        events.append(("dispatch",))
        core.session_id = new_owner.session_id
        return "loaded"

    executed, result, lingering = run_gui_command_with_session_transition_guard(
        core, ":sessions load new-session", dispatch, timeout=2.5
    )

    assert executed is True
    assert result == "loaded"
    assert lingering == []
    assert events.index(("wait", "old-session", 2.5)) < events.index(("dispatch",))
    assert events.index(("dispatch",)) < events.index(("resume", "new-session"))
    assert core._sub_agent_job_owner == new_owner


def test_gui_session_command_is_not_dispatched_when_old_jobs_linger():
    from uagent.scheckgui_impl.sub_agent_jobs import (
        run_gui_command_with_session_transition_guard,
    )

    owner = SubAgentJobOwner(entry_point="gui", session_id="old-session")
    calls = []

    class Manager:
        def pause_owner(self, _owner):
            calls.append("pause")

        def cancel_all(self, *, owner, reason):
            calls.append(("cancel", owner, reason))

        def wait_owner_workers(self, _owner, timeout):
            calls.append(("wait", timeout))
            return False

        def active_job_ids(self, _owner):
            return ["job-still-running"]

        def resume_owner(self, _owner):
            calls.append("resume")

    core = SimpleNamespace(
        session_id="old-session",
        _sub_agent_job_owner=owner,
        _sub_agent_job_manager=Manager(),
    )
    dispatched = []
    executed, result, lingering = run_gui_command_with_session_transition_guard(
        core,
        ":load session-2",
        lambda: dispatched.append(True),
        timeout=0.25,
    )

    assert executed is False
    assert result is None
    assert lingering == ["job-still-running"]
    assert dispatched == []
    assert "resume" in calls
