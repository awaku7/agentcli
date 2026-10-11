from __future__ import annotations

from types import SimpleNamespace

import pytest

from uagent.runtime.session_store import SessionStore
from uagent.util_cmd_session import (
    RoomSessionBusyError,
    _handle_cmd_load,
    bind_room_session_runtime,
    bind_session_selection_context,
    guard_room_session_command,
)
from uagent.web_impl import agent_worker
from uagent.web_impl.rooms import WebRoom


def test_loaded_room_worker_binds_persistence_and_continuation_then_restores(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("UAGENT_PROVIDER", "offline-test")
    monkeypatch.setattr(agent_worker, "resolve_identity_mode", lambda: "local")
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        startup = store.create_session(project="startup", entry_point="cli")
        core = SimpleNamespace(
            session_store=store,
            session_id=startup.session_id,
            _session_store_active_id=startup.session_id,
            responses_state={"previous_response_id": "startup-response"},
            tool_context={"startup": {}},
        )

        def persist(message):
            store.append_message(
                core._session_store_active_id, message["role"], message["content"]
            )

        core.log_message = persist
        monkeypatch.setattr(agent_worker, "core", core)
        calls = []
        original_responses = core.responses_state
        original_tools = core.tool_context
        for name in ("first", "second"):
            session = store.create_session(project=name, entry_point="cli")
            store.append_message(session.session_id, "user", f"{name}-seed")
            store.record_response_state(
                session.session_id,
                provider="openai",
                model="test",
                response_id=f"{name}-saved",
                status="completed",
            )
            store.record_tool_context(
                session.session_id, tool_name="test_tool", context={"room": name}
            )
            room = WebRoom(name)
            room.base_dir = str(tmp_path)
            with bind_session_selection_context(room):
                assert _handle_cmd_load(
                    session.session_id, room.history, core=core, tr=lambda text: text
                )
            assert core.session_id == startup.session_id

            def provider_setup(bound_core):
                calls.append(bound_core.session_id)
                assert bound_core.session_id == session.session_id
                assert (
                    bound_core.responses_state["previous_response_id"]
                    == f"{name}-saved"
                )
                assert bound_core.tool_context == {"test_tool": {"room": name}}
                for role in ("user", "assistant", "tool"):
                    bound_core.log_message({"role": role, "content": f"{name}-{role}"})
                bound_core.responses_state["previous_response_id"] = f"{name}-next"
                # Exercise worker cleanup on an error as well as normal state setup.
                raise RuntimeError("offline stop after runtime verification")

            monkeypatch.setattr(agent_worker.providers, "make_client", provider_setup)
            agent_worker.run_agent_worker(room, "follow-up")
            assert calls[-1] == session.session_id
            assert [
                message["content"]
                for message in store.list_messages(session.session_id)
            ] == [f"{name}-seed", f"{name}-user", f"{name}-assistant", f"{name}-tool"]
            assert room.responses_state["previous_response_id"] == f"{name}-next"
            assert core.session_id == startup.session_id
            assert core._session_store_active_id == startup.session_id
            assert core.responses_state is original_responses
            assert core.tool_context is original_tools
        assert store.list_messages(startup.session_id) == []


def test_room_session_switch_is_blocked_while_worker_owns_lock():
    room = WebRoom("busy-room")
    room.worker_lock.acquire()
    try:
        for command in ("load", "cont", "sessions"):
            with pytest.raises(RoomSessionBusyError, match="turn is running"):
                with guard_room_session_command(room, command):
                    pytest.fail("busy room must never run session-changing commands")
    finally:
        room.worker_lock.release()

    with guard_room_session_command(room, "load"):
        assert room.worker_lock.locked()
    assert not room.worker_lock.locked()


def test_room_runtime_cleanup_never_overwrites_another_loaded_session(tmp_path):
    with SessionStore(tmp_path / "switched.sqlite3") as store:
        first = store.create_session(project="first", entry_point="cli")
        second = store.create_session(project="second", entry_point="cli")
        core = SimpleNamespace(
            session_store=store,
            session_id="startup",
            responses_state={"previous_response_id": "startup"},
            tool_context={"startup": {}},
        )
        room = WebRoom("room")
        room.session_id = first.session_id
        room.responses_state = {"previous_response_id": "first"}
        room.tool_context = {"first": {}}

        with bind_room_session_runtime(core, room):
            core.responses_state["previous_response_id"] = "first-next"
            # Simulate an unexpected external load while this worker is active.
            room.session_id = second.session_id
            room.responses_state = {"previous_response_id": "second-restored"}
            room.tool_context = {"second": {}}

        assert room.session_id == second.session_id
        assert room.responses_state == {"previous_response_id": "second-restored"}
        assert room.tool_context == {"second": {}}
        assert core.responses_state == {"previous_response_id": "startup"}


@pytest.mark.parametrize("mapping", [{}, {0: "shown"}])
def test_displayed_view_is_authoritative_for_missing_indices(mapping):
    from uagent.runtime.session_command_service import SessionCommandService

    result = SessionCommandService.resolve_load_target(
        "1",
        [{"session_id": "unseen-0"}, {"session_id": "unseen-1"}],
        search_results=mapping,
    )
    assert result.error == "index_out_of_range"
    assert result.target is None


def test_other_room_queues_without_changing_active_worker_state(monkeypatch, tmp_path):
    import os
    import threading

    from uagent.web_impl.rooms import WebManager

    manager = WebManager()
    monkeypatch.setattr(agent_worker, "web_manager", manager)
    monkeypatch.setattr(agent_worker, "resolve_identity_mode", lambda: "local")
    monkeypatch.setenv("UAGENT_PROVIDER", "offline-test")

    def original_log(message):
        pass

    core = SimpleNamespace(log_message=original_log, status_busy=False)
    monkeypatch.setattr(agent_worker, "core", core)
    rooms = [WebRoom("room-a"), WebRoom("room-b")]
    for room in rooms:
        directory = tmp_path / room.room_id
        directory.mkdir()
        room.base_dir = str(directory)
    initial_cwd = os.getcwd()
    entered = threading.Event()
    queued = threading.Event()
    release = threading.Event()
    observations = []
    errors = []
    active_log = []
    original_set_status = rooms[1].set_status

    def observe_status(busy, label=""):
        original_set_status(busy, label)
        if label == "QUEUED":
            queued.set()

    monkeypatch.setattr(rooms[1], "set_status", observe_status)

    def provider_setup(bound_core):
        room = manager.active_room
        observations.append((room.room_id, os.getcwd()))
        if room is rooms[0]:
            active_log.append(bound_core.log_message)
            entered.set()
            if not release.wait(10):
                errors.append("first worker timed out")
        raise RuntimeError("offline provider stop")

    monkeypatch.setattr(agent_worker.providers, "make_client", provider_setup)
    workers = [
        threading.Thread(target=agent_worker.run_agent_worker, args=(room, "input"))
        for room in rooms
    ]
    workers[0].start()
    try:
        assert entered.wait(10)
        workers[1].start()
        assert queued.wait(10)
        assert rooms[0].status["busy"]
        assert rooms[1].status["busy"]
        assert rooms[1].status["label"] == "QUEUED"
        assert rooms[1].worker_lock.locked()
        assert manager.active_room is rooms[0]
        assert manager.worker_room is rooms[0]
        assert os.getcwd() == rooms[0].base_dir
        assert core.log_message is active_log[0]
        assert core.status_busy
        assert not rooms[1].messages
        # Only a second submission to the already reserved B room is rejected.
        agent_worker.run_agent_worker(rooms[1], "duplicate")
        assert "Another task" in rooms[1].messages[-1]["content"]
        assert rooms[1].status["label"] == "QUEUED"
        assert manager.active_room is rooms[0]
        assert manager.worker_room is rooms[0]
        assert core.log_message is active_log[0]
    finally:
        release.set()
        for worker in workers:
            if worker.ident is not None:
                worker.join(10)
    assert not errors
    assert all(not worker.is_alive() for worker in workers)
    assert observations == [(room.room_id, room.base_dir) for room in rooms]
    assert os.getcwd() == initial_cwd
    assert core.log_message is original_log
    assert not core.status_busy
    assert manager.active_room is None
    assert manager.worker_room is None
    for room in rooms:
        assert room.status["label"] == "IDLE"
        assert not room.worker_lock.locked()


@pytest.mark.parametrize("label", ["QUEUED", "IDLE"])
def test_non_active_room_cannot_interrupt_other_room(monkeypatch, label):
    import threading

    from uagent.web_impl import routes_ws
    from uagent.web_impl.rooms import WebManager

    manager = WebManager()
    active = WebRoom("active")
    other = WebRoom("other")
    manager.active_room = active
    manager.worker_room = active
    other.set_status(label == "QUEUED", label)
    # Even stale/pending confirmation state must not bypass room ownership.
    other.human_ask_pending = True
    other.human_ask_cancelled = False
    other.human_ask_result = "keep"
    core = SimpleNamespace(
        status_busy=True, interrupt_lock=threading.Lock(), interrupt_requested=False
    )
    monkeypatch.setattr(routes_ws, "web_manager", manager)
    monkeypatch.setattr(routes_ws, "core", core)
    assert not routes_ws._request_room_interrupt(other)
    assert not core.interrupt_requested
    assert not other.human_ask_cancelled
    assert other.human_ask_result == "keep"
    assert not other.human_ask_sync_event.is_set()
    assert routes_ws._request_room_interrupt(active)
    assert core.interrupt_requested


def test_active_room_interrupt_unblocks_confirmation_with_busy_cleared(monkeypatch):
    import threading

    from uagent.web_impl import routes_ws
    from uagent.web_impl.rooms import WebManager

    manager = WebManager()
    room = WebRoom("active")
    room.human_ask_pending = True
    room.human_ask_result = "pending"
    manager.active_room = room
    manager.worker_room = room
    core = SimpleNamespace(
        status_busy=False, interrupt_lock=threading.Lock(), interrupt_requested=False
    )
    monkeypatch.setattr(routes_ws, "web_manager", manager)
    monkeypatch.setattr(routes_ws, "core", core)
    assert routes_ws._request_room_interrupt(room)
    assert room.human_ask_cancelled
    assert room.human_ask_result == ""
    assert room.human_ask_sync_event.is_set()
    assert core.interrupt_requested
    manager.active_room = None
    manager.worker_room = None
    core.interrupt_requested = False
    assert not routes_ws._request_room_interrupt(room)
    assert not core.interrupt_requested


def test_bootstrap_display_room_cannot_take_worker_interrupt_ownership(
    monkeypatch, tmp_path
):
    import threading

    from uagent.web_impl import history, routes_ws
    from uagent.web_impl.rooms import WebManager

    manager = WebManager()
    active = WebRoom("executing-a")
    bootstrap = WebRoom("connecting-b")
    bootstrap.base_dir = str(tmp_path)
    manager.active_room = active
    manager.worker_room = active
    core = SimpleNamespace(
        status_busy=True, interrupt_lock=threading.Lock(), interrupt_requested=False
    )
    monkeypatch.setattr(routes_ws, "web_manager", manager)
    monkeypatch.setattr(routes_ws, "core", core)
    monkeypatch.setattr(history, "web_manager", manager)
    observed = []

    def build_initial_messages(**kwargs):
        assert manager.active_room is bootstrap
        assert bootstrap.status["label"] == "INIT"
        assert manager.worker_room is active
        assert not routes_ws._request_room_interrupt(bootstrap)
        assert not core.interrupt_requested
        assert routes_ws._request_room_interrupt(active)
        assert core.interrupt_requested
        observed.append(True)
        return []

    monkeypatch.setattr(
        history.tools_util, "build_initial_messages", build_initial_messages
    )
    history._ensure_room_history_initialized(bootstrap)
    assert observed == [True]
    assert manager.worker_room is active
    assert manager.active_room is active
