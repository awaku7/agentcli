from __future__ import annotations

import json
import os
import threading
import time
from types import SimpleNamespace

import pytest

from uagent.runtime.session_store import SessionStore, attach_opt_in_session_store
from uagent.web_impl.process_workers import RoomWorkerPool
from uagent.web_impl.rooms import WebRoom


def _offline_child(connection, payload):
    """Exercise the actual child/worker pipeline with an offline provider."""
    from uagent import core
    from uagent.llm_helpers import LLMWaitInterrupted
    from uagent.runtime import runtime_plugins
    from uagent.web_impl import agent_worker
    from uagent.web_impl.process_workers import _child_turn

    runtime_plugins.load_plugins_status_at_startup = lambda **kwargs: ([], "")
    agent_worker.providers.make_client = lambda bound_core: ("openai", None, "offline")

    def run_rounds(provider, client, model, history, **kwargs):
        from uagent.tools.python_exec_tool import run_tool

        result = run_tool(
            {
                "code": "import os\nfrom pathlib import Path\nPath('worker-marker.txt').write_text(os.getcwd(), encoding='utf-8')\nprint('tool-ok')"
            }
        )
        assert "tool-ok" in result
        observation = {
            "pid": os.getpid(),
            "cwd": os.getcwd(),
            "session": core.session_id,
            "response": core.responses_state.get("previous_response_id"),
        }
        message = {"role": "assistant", "content": json.dumps(observation)}
        core.log_message(message)
        history.append(message)
        # Make the live child observable before stopping its blocked request.
        from uagent.web_impl.rooms import web_manager

        web_manager.worker_room.add_message(message)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            with core.interrupt_lock:
                if core.interrupt_requested:
                    core.responses_state["previous_response_id"] = (
                        "updated-" + payload["room"]["room_id"]
                    )
                    raise LLMWaitInterrupted()
            time.sleep(0.02)
        raise RuntimeError("offline worker timed out")

    agent_worker.llm_util.run_llm_rounds = run_rounds
    _child_turn(connection, payload)


def _asking_child(connection, payload):
    from uagent.runtime import runtime_plugins
    from uagent.web_impl import agent_worker
    from uagent.web_impl.io import web_human_ask
    from uagent.web_impl.process_workers import _child_turn
    from uagent.web_impl.rooms import web_manager

    runtime_plugins.load_plugins_status_at_startup = lambda **kwargs: ([], "")
    agent_worker.providers.make_client = lambda bound_core: ("openai", None, "offline")

    def run_rounds(provider, client, model, history, **kwargs):
        room = web_manager.worker_room
        reply = web_human_ask(room, {"message": "Question for " + room.room_id})
        message = {"role": "assistant", "content": reply}
        kwargs["core"].log_message(message)
        history.append(message)

    agent_worker.llm_util.run_llm_rounds = run_rounds
    _child_turn(connection, payload)


def _crashing_child(connection, payload):
    os._exit(7)


def _wait(predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    pytest.fail("timed out waiting for worker")


def _observations(room):
    return [
        json.loads(m["content"])
        for m in room.messages
        if m["content"].startswith('{"pid"')
    ]


@pytest.mark.parametrize("private_session", [False, True])
def test_parallel_rooms_respect_cap_and_isolate_cwd_stop_and_persistence(
    monkeypatch, tmp_path, private_session
):
    from uagent import core
    from uagent.tools import _genre_control_util

    monkeypatch.setenv("UAGENT_PROVIDER", "offline-test")
    monkeypatch.setenv("UAGENT_IDENTITY_MODE", "local")
    monkeypatch.setattr(_genre_control_util, "get_enabled_tool_names", lambda: [])
    pool = RoomWorkerPool(2, target=_offline_child)
    initial_cwd = os.getcwd()
    rooms = [WebRoom(name) for name in ("a", "b", "c")]
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        monkeypatch.setattr(core, "session_store", store, raising=False)
        monkeypatch.setattr(core, "auto_pilot_active", False)
        for room in rooms:
            directory = tmp_path / room.room_id
            directory.mkdir()
            room.base_dir = str(directory)
            room.history_initialized = True
            room.history = [{"role": "system", "content": "offline"}]
            session = store.create_session(project=room.room_id, entry_point="web")
            room.session_id = session.session_id
            room.responses_state = {"previous_response_id": "saved-" + room.room_id}
            room.private_session = private_session
        from uagent.runtime.identity_context import IdentityContext, TurnContext
        from uagent.runtime.session_store import project_id_from_path

        identity = IdentityContext("alice", True, "local")
        turns = [
            TurnContext.from_identity(
                identity,
                entry_point="web",
                room_id=room.room_id,
                session_id=room.session_id,
                project_id=project_id_from_path(room.base_dir),
                private_session=private_session,
            )
            for room in rooms
        ]
        threads = [
            threading.Thread(
                target=pool.run,
                args=(room, "input-" + room.room_id),
                kwargs={
                    "turn_context": turn,
                    "identity_context": identity,
                    "project_path": room.base_dir,
                },
            )
            for room, turn in zip(rooms, turns)
        ]
        try:
            for thread in threads[:2]:
                thread.start()
            _wait(lambda: all(_observations(room) for room in rooms[:2]))
            observed = [_observations(room)[0] for room in rooms[:2]]
            assert observed[0]["pid"] != observed[1]["pid"]
            assert all(item["pid"] != os.getpid() for item in observed)
            for room, item in zip(rooms, observed):
                assert item["cwd"] == room.base_dir
                from pathlib import Path

                assert (Path(room.base_dir) / "worker-marker.txt").read_text(
                    encoding="utf-8"
                ) == room.base_dir
                assert item["session"] == room.session_id
                assert item["response"] == "saved-" + room.room_id
            assert os.getcwd() == initial_cwd
            threads[2].start()
            _wait(lambda: rooms[2].status["label"] == "QUEUED")
            assert not _observations(rooms[2])
            assert not pool.interrupt(rooms[2])
            pool.run(rooms[0], "duplicate")
            assert "Another task" in rooms[0].messages[-1]["content"]
            assert pool.interrupt(rooms[0])
            threads[0].join(10)
            assert not threads[0].is_alive()
            _wait(lambda: bool(_observations(rooms[2])))
            assert threads[1].is_alive()
            assert rooms[0].responses_state["previous_response_id"] == "updated-a"
            assert rooms[1].responses_state["previous_response_id"] == "saved-b"
            for room in rooms[1:]:
                assert pool.interrupt(room)
            for thread in threads:
                thread.join(10)
            assert all(not thread.is_alive() for thread in threads)
            assert not pool.busy
            assert os.getcwd() == initial_cwd
            for room in rooms:
                assert not room.worker_lock.locked()
                assert room.status["label"] == "IDLE"
                messages = store.list_messages(room.session_id)
                assert any(m["content"] == "input-" + room.room_id for m in messages)
                assert not any(m["content"] == "duplicate" for m in messages)
                assert len(store.list_sessions()) == 3
        finally:
            pool.shutdown()
            for thread in threads:
                if thread.ident is not None:
                    thread.join(10)


def test_attach_worker_reuses_session_without_creating_an_empty_startup_session(
    monkeypatch, tmp_path
):
    path = tmp_path / "reuse.sqlite3"
    monkeypatch.setenv("UAGENT_SESSION_STORE", "1")
    monkeypatch.setenv("UAGENT_SESSION_STORE_PATH", str(path))
    with SessionStore(path) as store:
        session = store.create_session(project="original", entry_point="web")
    core = SimpleNamespace(log_message=lambda message: None)
    attached, session_id = attach_opt_in_session_store(
        core,
        project_path=tmp_path,
        entry_point="web",
        existing_session_id=session.session_id,
    )
    try:
        assert session_id == session.session_id
        core.log_message({"role": "user", "content": "worker turn"})
        assert len(attached.list_sessions()) == 1
        assert attached.list_messages(session_id)[0]["content"] == "worker turn"
    finally:
        attached.close()


@pytest.mark.parametrize("value", [0, -1])
def test_worker_capacity_must_be_positive(value):
    with pytest.raises(ValueError, match="at least 1"):
        RoomWorkerPool(value)


def test_confirmation_responses_reach_only_their_own_process(monkeypatch, tmp_path):
    from uagent import core
    from uagent.tools import _genre_control_util

    monkeypatch.setenv("UAGENT_PROVIDER", "offline-test")
    monkeypatch.setenv("UAGENT_IDENTITY_MODE", "local")
    monkeypatch.setattr(core, "session_store", None, raising=False)
    monkeypatch.setattr(core, "auto_pilot_active", False)
    monkeypatch.setattr(_genre_control_util, "get_enabled_tool_names", lambda: [])
    pool = RoomWorkerPool(2, target=_asking_child)
    rooms = [WebRoom(name) for name in ("ask-a", "ask-b")]
    threads = []
    for room in rooms:
        room.base_dir = str(tmp_path)
        room.history_initialized = True
        room.history = [{"role": "system", "content": "offline"}]
        room.active_connections = [True]
        threads.append(threading.Thread(target=pool.run, args=(room, "ask")))
    try:
        for thread in threads:
            thread.start()
        _wait(lambda: all(room.human_ask_pending for room in rooms))
        assert pool.answer(rooms[0], "answer-a")
        threads[0].join(10)
        assert not threads[0].is_alive()
        assert threads[1].is_alive()
        assert rooms[1].human_ask_pending
        assert pool.answer(rooms[1], "answer-b")
        threads[1].join(10)
        assert not threads[1].is_alive()
        for room, answer in zip(rooms, ("answer-a", "answer-b")):
            assert json.loads(room.history[-1]["content"])["user_reply"] == answer
            assert not room.human_ask_pending
    finally:
        pool.shutdown()
        for thread in threads:
            thread.join(10)


def test_crashed_worker_releases_room_and_capacity(monkeypatch, tmp_path):
    from uagent import core
    from uagent.tools import _genre_control_util

    monkeypatch.setattr(core, "session_store", None, raising=False)
    monkeypatch.setattr(_genre_control_util, "get_enabled_tool_names", lambda: [])
    room = WebRoom("crash")
    room.base_dir = str(tmp_path)
    pool = RoomWorkerPool(1, target=_crashing_child)
    pool.run(room, "first")
    assert "exited" in room.messages[-1]["content"]
    assert not pool.busy
    assert not room.worker_lock.locked()
    pool.run(room, "second")
    assert not room.worker_lock.locked()
    assert room.status["label"] == "IDLE"
    pool.shutdown()


def test_worker_count_cli_overrides_environment(monkeypatch):
    from uagent.web_impl.process_workers import room_worker_count

    monkeypatch.setenv("UAGENT_WEB_ROOM_WORKERS", "3")
    assert room_worker_count() == 3
    assert room_worker_count(2) == 2
    monkeypatch.setenv("UAGENT_WEB_ROOM_WORKERS", "bad")
    assert room_worker_count(4) == 4
    with pytest.raises(ValueError, match="positive integer"):
        room_worker_count()


def test_auto_goals_stay_on_their_room(monkeypatch):
    from uagent import core
    from uagent.web_impl.process_workers import AUTO_PILOT_FIELDS, bind_room_auto_pilot

    for name in AUTO_PILOT_FIELDS:
        monkeypatch.setattr(
            core, name, False if name.endswith("active") else None, raising=False
        )
    a, b = WebRoom("a"), WebRoom("b")
    with bind_room_auto_pilot(a, enabled=True):
        core.auto_pilot_active = True
        core.auto_pilot_goal = "goal-a"
    assert core.auto_pilot_active is False
    with bind_room_auto_pilot(b, enabled=True):
        assert core.auto_pilot_goal is None
        core.auto_pilot_goal = "goal-b"
    with bind_room_auto_pilot(a, enabled=True):
        assert core.auto_pilot_goal == "goal-a"
        assert core.auto_pilot_active is True
    assert b._worker_auto_pilot["auto_pilot_goal"] == "goal-b"
    assert core.auto_pilot_goal is None
