"""Compact, room-scoped Web tool activity without extra UI or tool arguments."""

from pathlib import Path

from uagent.web_impl.rooms import WebRoom

ROOT = Path(__file__).resolve().parents[1]


def test_parallel_tools_keep_one_current_name_and_clear_on_idle():
    room = WebRoom("tool-room")
    first = room.begin_tool("read_file")
    second = room.begin_tool("search_code")
    assert room.current_tool == "search_code"

    room.end_tool(first)
    assert room.current_tool == "search_code"
    room.end_tool(second)
    assert room.current_tool == ""

    room.end_tool(second)  # Duplicate completion does not alter the state.
    room.begin_tool("slow_task")
    room.set_status(False, "IDLE")
    assert room.current_tool == ""
    assert room._active_tool_calls == {}


def test_tool_activity_is_forwarded_across_worker_processes(monkeypatch):
    from uagent.web_impl import process_workers

    room = WebRoom("relay-room")
    room.loop = object()
    forwarded = []

    def fake_submit(coro, loop):
        coro.close()
        forwarded.append(loop)

    monkeypatch.setattr(
        process_workers.asyncio, "run_coroutine_threadsafe", fake_submit
    )
    process_workers.RoomWorkerPool._relay(
        room, {"type": "tool_activity", "name": "search_code"}
    )
    assert room.current_tool == "search_code"
    assert len(forwarded) == 1

    process_workers.RoomWorkerPool._relay(
        room, {"type": "status", "status": {"busy": False, "label": "IDLE"}}
    )
    assert room.current_tool == ""


def test_header_shows_only_one_compact_tool_badge():
    header = (ROOT / "frontend/src/lib/components/Header.svelte").read_text(
        encoding="utf-8"
    )
    bundle = (ROOT / "src/uagent/static/assets/index.js").read_text(encoding="utf-8")
    store = (ROOT / "frontend/src/lib/stores.svelte.js").read_text(encoding="utf-8")
    assert "getCurrentTool()" in header
    assert "status.busy && status.label !== 'WAIT' && currentTool" in header
    assert 'a(r).label!=="WAIT"&&a(activeTool)' in bundle
    assert header.count("status-idle={!status.busy}") == 1
    assert "{#if status.busy}" not in header
    assert "tool_activity" in store
    assert 'case"tool_activity":M.currentTool=e.name||""' in bundle
    assert "activeTool=le(()=>M.currentTool)" in bundle
    assert "current_tool" in store
    assert "animation:uag-pulse" not in bundle


def test_server_tool_activity_payload_does_not_include_arguments():
    source = (ROOT / "src/uagent/web_impl/rooms.py").read_text(encoding="utf-8")
    init = (ROOT / "src/uagent/web_impl/init.py").read_text(encoding="utf-8")

    assert '{"type": "tool_activity", "name": name}' in source
    assert "room.begin_tool(name)" in init
    assert "room.end_tool(tool_call_id)" in init
    assert 'name != "human_ask"' in init


def test_confirmation_wait_takes_priority_over_active_tool_badge():
    room = WebRoom("waiting-room")
    call_id = room.begin_tool("delete_path")
    room.set_status(True, "WAIT")
    assert room.current_tool == "delete_path"
    assert room.status["label"] == "WAIT"

    # The client must show WAIT, not the still-running outer tool.
    header = (ROOT / "frontend/src/lib/components/Header.svelte").read_text(
        encoding="utf-8"
    )
    bundle = (ROOT / "src/uagent/static/assets/index.js").read_text(encoding="utf-8")
    assert "status.label !== 'WAIT'" in header
    assert 'a(r).label!=="WAIT"' in bundle
    room.end_tool(call_id)
    assert room.current_tool == ""
