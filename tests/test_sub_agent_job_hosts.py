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
        entry_point="web", session_id="session-web", room_id="room-web"
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

        def running_count(self, *, owner):
            assert owner == SubAgentJobOwner(
                entry_point="web", session_id="private-session", room_id="private-room"
            )
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
