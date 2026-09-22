from __future__ import annotations

from pathlib import Path


def test_call_with_resolved_turn_context_binds_and_restores(
    tmp_path, monkeypatch
) -> None:
    from uagent.runtime.identity_context import (
        get_current_identity_context,
        get_current_turn_context,
    )
    from uagent.runtime.turn_context_runtime import call_with_resolved_turn_context

    monkeypatch.setenv("UAGENT_IDENTITY_MODE", "local")

    def capture():
        return get_current_identity_context(), get_current_turn_context()

    identity, turn = call_with_resolved_turn_context(
        capture,
        entry_point="cli",
        project_path=str(tmp_path),
        session_id="session-1",
    )

    assert identity is not None
    assert turn is not None
    assert identity.principal_id == "local"
    assert turn.principal_id == "local"
    assert turn.entry_point == "cli"
    assert turn.project_id == tmp_path.name
    assert turn.session_id == "session-1"
    assert get_current_identity_context() is None
    assert get_current_turn_context() is None


def test_web_coordinates_remain_distinct(tmp_path, monkeypatch) -> None:
    from uagent.runtime.identity_context import get_current_turn_context
    from uagent.runtime.turn_context_runtime import call_with_resolved_turn_context

    monkeypatch.setenv("UAGENT_IDENTITY_MODE", "local")

    turn = call_with_resolved_turn_context(
        get_current_turn_context,
        entry_point="web",
        room_id="room-X",
        project_path=str(tmp_path),
        session_id="session-X",
    )

    assert turn is not None
    assert turn.principal_id == "local"
    assert turn.room_id == "room-X"
    assert turn.project_id == tmp_path.name
    assert turn.session_id == "session-X"
    assert len({turn.principal_id, turn.room_id, turn.project_id, turn.session_id}) == 4


def test_parallel_tool_workers_receive_current_turn_context(
    tmp_path, monkeypatch
) -> None:
    from uagent import tools
    from uagent.runtime.identity_context import get_current_turn_context
    from uagent.runtime.turn_context_runtime import call_with_resolved_turn_context

    monkeypatch.setenv("UAGENT_IDENTITY_MODE", "local")
    monkeypatch.setattr(tools, "_ensure_loaded", lambda: None)

    def fake_run_tool(name, args):
        del args
        turn = get_current_turn_context()
        return f"{name}:{turn.principal_id}:{turn.entry_point}" if turn else "missing"

    monkeypatch.setattr(tools, "run_tool", fake_run_tool)

    results = call_with_resolved_turn_context(
        tools.run_tools_parallel,
        [("one", {}), ("two", {})],
        entry_point="gui",
        project_path=str(tmp_path),
        session_id="session-gui",
    )

    assert [item[2] for item in results] == ["one:local:gui", "two:local:gui"]


def test_host_adapters_use_resolved_turn_context_helper() -> None:
    root = Path(__file__).resolve().parents[1]
    expected = {
        "src/uagent/cli_impl/main.py": 'entry_point="cli"',
        "src/uagent/cli_startup.py": 'entry_point="cli"',
        "src/uagent/scheckgui_impl/worker.py": 'entry_point="gui"',
        "src/uagent/web_impl/agent_worker.py": 'entry_point="web"',
        "src/uagent/a2a/engine.py": 'entry_point="a2a"',
    }
    for relative, marker in expected.items():
        source = (root / relative).read_text(encoding="utf-8")
        assert "call_with_resolved_turn_context" in source
        assert marker in source


def test_scheduled_direct_tools_use_turn_context() -> None:
    root = Path(__file__).resolve().parents[1]
    cli = (root / "src/uagent/cli_impl/main.py").read_text(encoding="utf-8")
    gui = (root / "src/uagent/scheckgui_impl/worker.py").read_text(encoding="utf-8")
    assert "execute_direct_tool, target_tool, target_args" in cli
    assert "execute_direct_tool, target_tool, target_args" in gui
    assert "_run_cli_turn(" in cli
    assert "self._run_gui_turn(" in gui


def test_llm_call_thread_receives_current_turn_context(tmp_path, monkeypatch) -> None:
    from uagent.llm_helpers import _call_maybe_thread
    from uagent.runtime.identity_context import get_current_turn_context
    from uagent.runtime.turn_context_runtime import call_with_resolved_turn_context

    monkeypatch.setenv("UAGENT_IDENTITY_MODE", "local")

    turn = call_with_resolved_turn_context(
        lambda: _call_maybe_thread(get_current_turn_context, use_llm_thread=True),
        entry_point="cli",
        project_path=str(tmp_path),
        session_id="session-thread",
    )

    assert turn is not None
    assert turn.principal_id == "local"
    assert turn.entry_point == "cli"
    assert turn.session_id == "session-thread"


def test_web_turn_uses_active_core_session_id() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/uagent/web_impl/agent_worker.py").read_text(encoding="utf-8")
    assert 'session_id=str(getattr(core, "session_id", "") or ""),' in source
    assert 'session_id=str(getattr(room, "session_id", "") or ""),' not in source


def test_gui_image_preprocessing_uses_turn_context() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/uagent/scheckgui_impl/worker.py").read_text(encoding="utf-8")
    expected = (
        "res = self._run_gui_turn(\n"
        "                                        self.tools.run_tool,\n"
        '                                        "analyze_image",\n'
        '                                        {"image_path": p},\n'
        "                                    )"
    )
    assert expected in source


def test_cli_image_confirmation_uses_turn_context() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/uagent/cli_impl/main.py").read_text(encoding="utf-8")
    assert (
        "res_json = _run_cli_turn(\n"
        "                                    tools.run_tool,\n"
        '                                    "human_ask",\n'
    ) in source
