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
