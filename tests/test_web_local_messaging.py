from __future__ import annotations

import queue
import threading
from types import SimpleNamespace

import psutil
import pytest

from uagent.runtime.local_messaging import LocalMessageRuntime, LocalMessageStore
from uagent.web_impl.local_messaging import (
    WebLocalMessagingAdapter,
    start_web_local_messaging,
    stop_web_local_messaging,
)


class _Connection:
    room_id = "private-room"
    project_id = "project-a"
    identity = SimpleNamespace(principal_id="alice", authenticated=True)

    def validate_authentication_configuration(self) -> None:
        return None

    def validate_room_access(self, *, touch_activity: bool = True) -> None:
        del touch_activity
        return None


def test_web_messaging_requires_private_room_and_honors_opt_out(monkeypatch, tmp_path):
    public_room = SimpleNamespace(
        room_id="public-room", private_session=False, project_id="project-a"
    )
    with pytest.raises(RuntimeError, match="private Web room"):
        start_web_local_messaging(public_room, _Connection())

    private_room = SimpleNamespace(
        room_id="private-room", private_session=True, project_id="project-a"
    )
    monkeypatch.setenv("UAGENT_LOCAL_MESSAGING", "off")
    with pytest.raises(RuntimeError, match="must be enabled"):
        start_web_local_messaging(private_room, _Connection())
    assert not hasattr(private_room, "_local_messaging_runtime")


def test_web_endpoint_is_scoped_to_authenticated_private_room(monkeypatch, tmp_path):
    monkeypatch.setenv("UAGENT_STATE_DIR", str(tmp_path))
    monkeypatch.delenv("UAGENT_LOCAL_MESSAGING", raising=False)
    room = SimpleNamespace(
        room_id="private-room",
        private_session=True,
        project_id="project-a",
    )
    adapter, peers = start_web_local_messaging(room, _Connection())
    assert peers == []
    try:
        runtime = adapter.runtime
        assert runtime is not None
        endpoint = runtime.store.active_endpoint(runtime.endpoint_id)
        assert endpoint is not None
        assert endpoint["entrypoint"] == "web"
        assert endpoint["principal_id"] == "alice"
        assert endpoint["room_id"] == "private-room"
        assert endpoint["project_id"] == "project-a"

        process = psutil.Process()
        runtime.store.register_endpoint(
            "same-scope",
            entrypoint="web",
            pid=process.pid,
            create_time=process.create_time(),
            principal_id="alice",
            room_id="private-room",
            project_id="project-a",
        )
        runtime.store.register_endpoint(
            "other-principal",
            entrypoint="web",
            pid=process.pid,
            create_time=process.create_time(),
            principal_id="bob",
            room_id="private-room",
            project_id="project-a",
        )
        runtime.store.register_endpoint(
            "other-project",
            entrypoint="web",
            pid=process.pid,
            create_time=process.create_time(),
            principal_id="alice",
            room_id="private-room",
            project_id="project-b",
        )
        listed = runtime.list_peers()
        assert [peer["endpoint_id"] for peer in listed] == ["same-scope"]
    finally:
        stop_web_local_messaging(room)
        # These test-only peers share the test process and are explicitly removed.
        store = LocalMessageStore(tmp_path / "local_messaging" / "messages.sqlite3")
        for endpoint_id in ("same-scope", "other-principal", "other-project"):
            store.unregister_endpoint(endpoint_id)
        store.close()


def test_web_inbox_turn_is_bound_to_confirmed_private_room(monkeypatch, tmp_path):
    identity = SimpleNamespace(principal_id="alice", authenticated=True)
    connection = _Connection()
    connection.identity = identity
    room = SimpleNamespace(
        room_id="private-room",
        private_session=True,
        project_id="project-a",
        base_dir=str(tmp_path),
        session_id="session-a",
        worker_lock=threading.Lock(),
        _lifecycle_lock=threading.Lock(),
        active_connections=[object()],
        _connection_contexts={1: connection},
    )
    connection.make_turn = lambda **_kwargs: SimpleNamespace(project_id="project-a")
    connection.revalidate_identity = lambda: identity
    connection.validate_room_access = lambda **_kwargs: None
    connection.validate_authentication_configuration = lambda: None
    store = LocalMessageStore(tmp_path / "messages.sqlite3")
    runtime = LocalMessageRuntime(
        queue.Queue(),
        entrypoint="web",
        endpoint_id="web:target",
        principal_id="alice",
        room_id="private-room",
        project_id="project-a",
        store=store,
        receive_messages=False,
        announce_peers=False,
    )
    runtime.start()
    adapter = WebLocalMessagingAdapter(room, "alice", "project-a")
    adapter.runtime = runtime
    runtime.approve_sender_for_lifetime("web:sender")
    sender_process = psutil.Process()
    store.register_endpoint(
        "web:sender",
        entrypoint="web",
        pid=sender_process.pid,
        create_time=sender_process.create_time(),
        principal_id="alice",
        room_id="private-room",
        project_id="project-a",
    )
    message_id = store.send_message("web:sender", runtime.endpoint_id, "approved")
    message = store.claim_messages(runtime.endpoint_id)[0]
    assert message["message_id"] == message_id
    calls = []
    monkeypatch.setattr(
        "uagent.web_impl.agent_worker.run_agent_worker",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    try:
        adapter._handle_event({"kind": "local_message_received", "message": message})
        assert len(calls) == 1
        assert calls[0][0][1].startswith("Message from local UAG endpoint web:sender.")
        assert calls[0][1]["turn_context"].project_id == "project-a"
        assert calls[0][1]["identity_context"] is identity
    finally:
        runtime.stop()
        store.unregister_endpoint("web:sender")
