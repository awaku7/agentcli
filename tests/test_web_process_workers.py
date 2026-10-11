from __future__ import annotations

import json
import os
import threading
import time
from multiprocessing.process import BaseProcess
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
        from uagent.decision.settings import get_decision_settings
        from uagent.util_mode import get_display_reasoning

        result = run_tool(
            {
                "code": "import os\nfrom pathlib import Path\nPath('worker-marker.txt').write_text(os.getcwd(), encoding='utf-8')\nprint('tool-ok')"
            }
        )
        assert "tool-ok" in result
        observation = {
            "pid": os.getpid(),
            "decision_provider": get_decision_settings().provider,
            "display_reasoning": get_display_reasoning(),
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


def _state_child(connection, payload):
    from uagent import core
    from uagent.runtime import runtime_plugins
    from uagent.web_impl import agent_worker
    from uagent.web_impl.process_workers import _child_turn

    runtime_plugins.load_plugins_status_at_startup = lambda **kwargs: ([], "")

    def run_worker(room, user_input, attachments=None, **kwargs):
        manager = core.agent_state_manager
        observed = {
            "responses_state": dict(core.responses_state),
            "tool_context": dict(core.tool_context),
            "agent_goal": manager.state.goal,
            "mcp_request_generation": core.mcp_request_generation,
        }
        room.add_message(
            {
                "role": "assistant",
                "content": "STATE:" + json.dumps(observed, sort_keys=True),
            }
        )
        core.responses_state["previous_response_id"] = "resp-" + user_input
        core.tool_context["marker"] = "tool-" + user_input
        manager.update(goal="goal-" + user_input)
        core.mcp_request_generation += 1

    agent_worker.run_agent_worker = run_worker
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


def _interruptible_child(connection, payload):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if connection.poll(0.1):
            request = connection.recv()
            if request.get("type") == "interrupt":
                connection.send({"state": payload["room"]})
                return
    connection.send({"state": payload["room"]})


def _crashing_child(connection, payload):
    for role, content in (("user", payload["input"]), ("assistant", "partial output")):
        connection.send(
            {
                "event": {
                    "type": "message",
                    "message": {"role": role, "content": content},
                }
            }
        )
    connection.close()
    os._exit(7)


def _stream_crashing_child(connection, payload):
    connection.send(
        {
            "event": {
                "type": "message",
                "message": {"role": "user", "content": payload["input"]},
            }
        }
    )
    connection.send({"event": {"type": "assistant_stream_start", "id": "stream-1"}})
    connection.send(
        {
            "event": {
                "type": "assistant_stream_delta",
                "id": "stream-1",
                "delta": "partial ",
            }
        }
    )
    connection.send(
        {
            "event": {
                "type": "assistant_stream_delta",
                "id": "stream-1",
                "delta": "reply",
            }
        }
    )
    connection.close()
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

    from uagent.decision import settings

    monkeypatch.setattr(settings, "_current_settings", settings.DecisionSettings())
    from uagent import util_mode

    monkeypatch.setattr(util_mode, "_DISPLAY_REASONING", private_session)
    expected_decision = "typesafe" if private_session else "openai"
    settings.configure_decision_settings(
        cli_provider="typesafe" if private_session else None,
        environ={"UAGENT_PROVIDER": "openai"},
    )
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
                assert item["decision_provider"] == expected_decision
                assert item["display_reasoning"] is private_session
                assert room._process_turn_active
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
            from uagent.i18n import _

            pool.run(rooms[0], "duplicate")
            assert (
                _(
                    "[WARN] Another task is already running in this room. Please retry after it completes."
                )
                == rooms[0].messages[-1]["content"]
            )
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
                assert room._process_stale_history is None
                assert not room._process_turn_active
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
    room.history = [{"role": "assistant", "content": "previous"}]
    room.messages = list(room.history)
    room.welcome_shown = True
    room.private_session = True
    room.base_dir = str(tmp_path)
    pool = RoomWorkerPool(1, target=_crashing_child)
    pool.run(room, "first")
    assert "[ERROR] Room worker" in room.messages[-1]["content"]
    assert not room._process_turn_active
    assert room._process_stale_history is room.history
    assert _reconnect_messages(room, monkeypatch) == room.messages
    assert any(m["content"] == "first" for m in room.messages)
    assert any(m["content"] == "partial output" for m in room.messages)
    room.history = [{"role": "assistant", "content": "explicitly loaded"}]
    assert [m["content"] for m in _reconnect_messages(room, monkeypatch)] == [
        "explicitly loaded"
    ]
    assert not pool.busy
    assert not room.worker_lock.locked()
    pool.run(room, "second")
    assert not room.worker_lock.locked()
    assert room.status["label"] == "IDLE"
    pool.shutdown()


def test_stop_is_not_exposed_until_child_is_interruptible(monkeypatch, tmp_path):
    from uagent import core
    from uagent.tools import _genre_control_util

    monkeypatch.setattr(core, "session_store", None, raising=False)
    monkeypatch.setattr(_genre_control_util, "get_enabled_tool_names", lambda: [])
    spawn_entered = threading.Event()
    allow_spawn = threading.Event()
    busy_exposed = threading.Event()
    original_start = BaseProcess.start

    def gated_start(process, *args, **kwargs):
        spawn_entered.set()
        assert allow_spawn.wait(10)
        return original_start(process, *args, **kwargs)

    monkeypatch.setattr(BaseProcess, "start", gated_start)
    pool = RoomWorkerPool(1, target=_interruptible_child)
    room = WebRoom("stop-startup")
    room.base_dir = str(tmp_path)
    original_set_status = room.set_status

    def track_busy(busy, label=""):
        if busy and label == "BUSY":
            with pool._lock:
                assert room.room_id in pool._running
            busy_exposed.set()
        original_set_status(busy, label)

    monkeypatch.setattr(room, "set_status", track_busy)
    thread = threading.Thread(target=pool.run, args=(room, "interrupt me"))
    thread.start()
    try:
        assert spawn_entered.wait(20)
        assert not busy_exposed.is_set()
        assert room.status["busy"]
        assert room.status["label"] == "QUEUED"

        allow_spawn.set()
        assert busy_exposed.wait(10), (
            f"worker_thread_alive={thread.is_alive()}, "
            f"status={room.status}, pool_busy={pool.busy}, "
            f"messages={room.messages}"
        )
        assert pool.interrupt(room)
        thread.join(10)
        assert not thread.is_alive()
        assert not pool.busy
        assert not room.worker_lock.locked()
    finally:
        allow_spawn.set()
        pool.shutdown()
        thread.join(10)


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


def test_worker_count_defaults_to_five(monkeypatch):
    from uagent.web_impl.process_workers import room_worker_count

    monkeypatch.delenv("UAGENT_WEB_ROOM_WORKERS", raising=False)
    assert room_worker_count() == 5
    assert room_worker_count(1) == 1


@pytest.mark.parametrize("active", [True, False])
def test_reconnect_uses_live_messages_only_during_process_turn(monkeypatch, active):
    room = WebRoom("reconnect")
    room.private_session = True
    room.welcome_shown = True
    room.history = [{"role": "assistant", "content": "previous"}]
    room.messages = [
        {"role": "assistant", "content": "previous"},
        {"role": "user", "content": "current input"},
    ]
    room._process_turn_active = active
    RoomWorkerPool._relay(
        room,
        {
            "type": "message",
            "message": {"role": "assistant", "content": "current output"},
        },
    )

    messages = _reconnect_messages(room, monkeypatch)
    assert [m["content"] for m in messages] == (
        ["previous", "current input", "current output"] if active else ["previous"]
    )


def test_reconnect_buffers_worker_messages_during_history_conversion(monkeypatch):
    import asyncio

    from uagent.web_impl import rooms as rooms_module

    room = WebRoom("reconnect-history-race")
    room.private_session = True
    room.welcome_shown = True
    room.history = [{"role": "assistant", "content": "previous"}]
    room.messages = list(room.history)
    original_enrich = rooms_module._enrich_message_attachments
    injected = False

    def inject_worker_message(message):
        nonlocal injected
        if not injected and message.get("content") == "previous":
            injected = True
            with room._lifecycle_lock:
                room._process_turn_active = True
            RoomWorkerPool._relay(
                room,
                {
                    "type": "message",
                    "message": {"role": "user", "content": "new turn input"},
                },
            )
        return original_enrich(message)

    monkeypatch.setattr(
        rooms_module, "_enrich_message_attachments", inject_worker_message
    )

    async def validate(*args):
        pass

    monkeypatch.setattr(room, "_validate_connection_context", validate)

    class Socket:
        def __init__(self):
            self.events = []

        async def accept(self):
            pass

        async def send_json(self, event):
            self.events.append(event)

    socket = Socket()
    asyncio.run(room.connect(socket))

    assert socket.events[0]["messages"][0]["content"] == "previous"
    assert [event["message"]["content"] for event in socket.events[1:]] == [
        "new turn input"
    ]


def _reconnect_messages(room, monkeypatch):
    async def validate(*args):
        pass

    monkeypatch.setattr(room, "_validate_connection_context", validate)

    class Socket:
        async def accept(self):
            pass

        async def send_json(self, event):
            if event["type"] == "init":
                self.initial = event

    socket = Socket()
    import asyncio

    asyncio.run(room.connect(socket))
    return socket.initial["messages"]


def test_crashed_stream_preserves_partial_reply_on_reconnect(monkeypatch, tmp_path):
    from uagent import core
    from uagent.tools import _genre_control_util

    monkeypatch.setattr(core, "session_store", None, raising=False)
    monkeypatch.setattr(_genre_control_util, "get_enabled_tool_names", lambda: [])
    room = WebRoom("stream-crash")
    room.history = [{"role": "assistant", "content": "previous"}]
    room.messages = list(room.history)
    room.welcome_shown = True
    room.private_session = True
    room.base_dir = str(tmp_path)
    pool = RoomWorkerPool(1, target=_stream_crashing_child)
    try:
        pool.run(room, "question")
        contents = [m["content"] for m in _reconnect_messages(room, monkeypatch)]
        assert contents == [
            "previous",
            "question",
            "partial reply",
            "[ERROR] Room worker exited before returning its state.",
        ]
        assert not room.worker_lock.locked()
        assert not pool.busy
    finally:
        pool.shutdown()


def test_reconnect_replays_live_stream_events(monkeypatch):
    room = WebRoom("stream-reconnect")
    room.private_session = True
    room.welcome_shown = True
    room._process_turn_active = True
    room._partial_streams = {"stream-1": "partial reply"}
    room.messages = [{"role": "user", "content": "question"}]

    async def validate(*args):
        pass

    monkeypatch.setattr(room, "_validate_connection_context", validate)

    class Socket:
        def __init__(self):
            self.events = []

        async def accept(self):
            pass

        async def send_json(self, event):
            self.events.append(event)

    import asyncio

    socket = Socket()
    asyncio.run(room.connect(socket))
    assert [event["type"] for event in socket.events[:3]] == [
        "init",
        "assistant_stream_start",
        "assistant_stream_replace",
    ]
    assert socket.events[2]["content"] == "partial reply"


def test_reconnect_snapshot_and_queued_delta_do_not_duplicate(monkeypatch):
    room = WebRoom("snapshot-boundary")
    room.private_session = True
    room.welcome_shown = True
    room._process_turn_active = True
    room._partial_streams = {"stream-1": "before"}
    room.messages = [{"role": "user", "content": "question"}]

    async def validate(*args):
        pass

    monkeypatch.setattr(room, "_validate_connection_context", validate)

    class Socket:
        def __init__(self):
            self.events = []

        async def accept(self):
            pass

        async def send_json(self, event):
            self.events.append(event)
            if event["type"] == "init":
                RoomWorkerPool._relay(
                    room,
                    {
                        "type": "assistant_stream_delta",
                        "id": "stream-1",
                        "delta": "after",
                    },
                )

    import asyncio

    socket = Socket()
    asyncio.run(room.connect(socket))
    assert [event["type"] for event in socket.events[:4]] == [
        "init",
        "assistant_stream_start",
        "assistant_stream_replace",
        "assistant_stream_delta",
    ]
    assert socket.events[2]["content"] == "before"
    assert socket.events[3]["delta"] == "after"
    assert room._partial_streams["stream-1"] == "beforeafter"


def test_reconnect_replays_retained_stream_end(monkeypatch):
    room = WebRoom("ended-reconnect")
    room.private_session = True
    room.welcome_shown = True
    room._process_turn_active = True
    room.messages = [{"role": "user", "content": "question"}]
    room._partial_streams = {"stream-1": "completed"}
    room._ended_streams.add("stream-1")

    async def validate(*args):
        pass

    monkeypatch.setattr(room, "_validate_connection_context", validate)

    class Socket:
        def __init__(self):
            self.events = []

        async def accept(self):
            pass

        async def send_json(self, event):
            self.events.append(event)

    import asyncio

    socket = Socket()
    asyncio.run(room.connect(socket))
    assert [event["type"] for event in socket.events[:4]] == [
        "init",
        "assistant_stream_start",
        "assistant_stream_replace",
        "assistant_stream_end",
    ]


def test_add_message_during_reconnect_is_replayed_once(monkeypatch):
    room = WebRoom("error-reconnect")
    room.private_session = True
    room.welcome_shown = True
    room._process_turn_active = True

    async def validate(*args):
        pass

    monkeypatch.setattr(room, "_validate_connection_context", validate)

    class Socket:
        def __init__(self):
            self.events = []

        async def accept(self):
            pass

        async def send_json(self, event):
            self.events.append(event)
            if event["type"] == "init":
                room.add_message({"role": "assistant", "content": "worker failed"})

    import asyncio

    socket = Socket()
    asyncio.run(room.connect(socket))
    assert socket.events[0]["messages"] == []
    assert [event["type"] for event in socket.events].count("message") == 1
    assert socket.events[-1]["message"]["content"] == "worker failed"


def test_ended_stream_survives_until_state_or_matching_message():
    room = WebRoom("stream-end")
    room._partial_streams = {}
    RoomWorkerPool._relay(room, {"type": "assistant_stream_start", "id": "stream-1"})
    RoomWorkerPool._relay(
        room,
        {"type": "assistant_stream_delta", "id": "stream-1", "delta": "complete"},
    )
    RoomWorkerPool._relay(room, {"type": "assistant_stream_end", "id": "stream-1"})
    assert room._partial_streams == {"stream-1": "complete"}
    RoomWorkerPool._relay(
        room,
        {"type": "message", "message": {"role": "assistant", "content": "complete"}},
    )
    assert room._partial_streams == {}


def test_public_room_without_session_store_keeps_turn_state(monkeypatch, tmp_path):
    from uagent import core
    from uagent.runtime.agent_state import AgentStateManager

    monkeypatch.setattr(core, "session_store", None, raising=False)
    monkeypatch.setattr(core, "auto_pilot_active", False, raising=False)
    room = WebRoom("public-no-store")
    room.base_dir = str(tmp_path)
    room.history_initialized = True
    room.history = [{"role": "system", "content": "offline"}]
    room.responses_state = {}
    room.tool_context = {}
    room.agent_state_manager = AgentStateManager()
    room.mcp_request_generation = 0
    pool = RoomWorkerPool(1, target=_state_child)
    try:
        pool.run(room, "turn-1")
        pool.run(room, "turn-2")

        observations = [
            json.loads(message["content"][len("STATE:") :])
            for message in room.messages
            if message.get("content", "").startswith("STATE:")
        ]
        assert observations == [
            {
                "responses_state": {},
                "tool_context": {},
                "agent_goal": "",
                "mcp_request_generation": 0,
            },
            {
                "responses_state": {"previous_response_id": "resp-turn-1"},
                "tool_context": {"marker": "tool-turn-1"},
                "agent_goal": "goal-turn-1",
                "mcp_request_generation": 1,
            },
        ]
        assert room.responses_state["previous_response_id"] == "resp-turn-2"
        assert room.tool_context["marker"] == "tool-turn-2"
        assert room.agent_state_manager.state.goal == "goal-turn-2"
        assert room.mcp_request_generation == 2
    finally:
        pool.shutdown()


def test_crash_recovery_is_atomic_with_reconnect_snapshot(monkeypatch):
    import asyncio

    room = WebRoom("atomic-crash-reconnect")
    room.private_session = True
    room.welcome_shown = True
    room._process_turn_active = True
    room._partial_streams = {"stream-1": "partial reply"}
    room.messages = [{"role": "user", "content": "question"}]
    snapshot_sent = threading.Event()
    allow_connect_to_continue = threading.Event()

    async def validate(*args):
        pass

    monkeypatch.setattr(room, "_validate_connection_context", validate)

    class Socket:
        def __init__(self):
            self.events = []

        async def accept(self):
            pass

        async def send_json(self, event):
            self.events.append(event)
            if event["type"] == "init":
                snapshot_sent.set()
                assert allow_connect_to_continue.wait(5)

    socket = Socket()
    connect_thread = threading.Thread(target=lambda: asyncio.run(room.connect(socket)))
    connect_thread.start()
    try:
        assert snapshot_sent.wait(5)
        room.recover_partial_streams("[ERROR] worker exited")
    finally:
        allow_connect_to_continue.set()
        connect_thread.join(5)

    assert not connect_thread.is_alive()
    assert [event["type"] for event in socket.events] == [
        "init",
        "assistant_stream_start",
        "assistant_stream_replace",
        "assistant_stream_end",
        "message",
    ]
    assert socket.events[2]["content"] == "partial reply"
    assert socket.events[-1]["message"]["content"] == "[ERROR] worker exited"
    assert [message["content"] for message in room.messages] == [
        "question",
        "partial reply",
        "[ERROR] worker exited",
    ]
    assert room._partial_streams == {}
