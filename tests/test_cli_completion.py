from __future__ import annotations

from prompt_toolkit.document import Document
import pytest


def test_command_completer_tool_create(monkeypatch: pytest.MonkeyPatch) -> None:
    import uagent.cli as cli
    import uagent.tools as tools_mod

    class MockEvent:
        pass

    # Ensure dynamic commands "tool" and "tools" are registered
    tools_mod.register_dynamic_command(
        command="tool",
        subcommand="create",
        handler=lambda args: "",
        overwrite=True,
    )
    tools_mod.register_dynamic_command(
        command="tools",
        subcommand="list",
        handler=lambda args: "",
        overwrite=True,
    )

    # Call _get_prompt_session with mocked PromptSession constructor
    monkeypatch.setattr(cli, "_PROMPT_SESSION", None)

    created_completers = []

    def mock_prompt_session(*args, **kwargs):
        completer = kwargs.get("completer")
        created_completers.append(completer)
        return completer

    monkeypatch.setattr("prompt_toolkit.PromptSession", mock_prompt_session)

    res = cli._get_prompt_session()
    assert res is not None
    completer = created_completers[0]

    # Test ":tool c" completion -> should yield "create"
    doc = Document(text=":tool c", cursor_position=len(":tool c"))
    completions = list(completer.get_completions(doc, MockEvent()))
    completion_texts = [c.text for c in completions]
    assert "create" in completion_texts

    # Test ":tools l" completion -> should yield "list"
    doc_tools = Document(text=":tools l", cursor_position=len(":tools l"))
    completions_tools = list(completer.get_completions(doc_tools, MockEvent()))
    completion_texts_tools = [c.text for c in completions_tools]
    assert "list" in completion_texts_tools

    # Built-in :response options must be completed before generic dynamic
    # command completion handles commands containing a space.
    doc_response = Document(text=":response c", cursor_position=len(":response c"))
    completions_response = list(completer.get_completions(doc_response, MockEvent()))
    completion_texts_response = [c.text for c in completions_response]
    assert "cancel" in completion_texts_response

    def completed(text: str) -> list[str]:
        doc = Document(text=text, cursor_position=len(text))
        return [c.text for c in completer.get_completions(doc, MockEvent())]

    assert "status" in completed(":response ")
    assert "auto" in completed(":r ")
    assert "high" in completed(":verbosity ")
    assert "response" in completed(":help res")
    assert ":reload" in completed(":")
    assert "list" in completed(":tools l")
    assert "active" in completed(":skills a")


def test_dynamic_map_block_false_never_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    """block=False の get_dynamic_commands_map はプラグインロードをブロックしない."""
    import uagent.tools as tools_mod

    calls: list[int] = []

    def boom() -> None:
        calls.append(1)
        raise AssertionError("block=False must not call _ensure_loaded")

    monkeypatch.setattr(tools_mod, "_ensure_loaded", boom)
    m = tools_mod.get_dynamic_commands_map(block=False)
    assert isinstance(m, dict)
    assert not calls


def test_dynamic_map_cache_invalidation() -> None:
    """register/unregister 後に get_dynamic_commands_map のキャッシュが更新される."""
    from uagent.tools import (
        get_dynamic_commands_map,
        register_dynamic_command,
        unregister_dynamic_commands_by_source,
    )

    register_dynamic_command(
        command="zzztest",
        subcommand="abc",
        handler=lambda args: "",
        source="test_cache",
        overwrite=True,
    )
    try:
        m = get_dynamic_commands_map()
        assert "zzztest" in m
        assert m["zzztest"] == ["abc"]
    finally:
        unregister_dynamic_commands_by_source("test_cache")
    m2 = get_dynamic_commands_map()
    assert "zzztest" not in m2


def test_get_dynamic_subcommands() -> None:
    """get_dynamic_subcommands が1コマンド分のサブコマンド一覧を返す."""
    from uagent.tools import (
        get_dynamic_subcommands,
        register_dynamic_command,
        unregister_dynamic_commands_by_source,
    )

    register_dynamic_command(
        command="subtest",
        subcommand="alpha",
        handler=lambda args: "",
        source="test_sub",
        overwrite=True,
    )
    register_dynamic_command(
        command="subtest",
        subcommand="beta",
        handler=lambda args: "",
        source="test_sub",
        overwrite=True,
    )
    try:
        subs = get_dynamic_subcommands(":subtest")
        assert subs == ["alpha", "beta"]
        assert get_dynamic_subcommands("unknown_cmd") == []
    finally:
        unregister_dynamic_commands_by_source("test_sub")


def test_arrow_keys_navigate_completion_menu() -> None:
    import uagent.cli as cli

    kb = cli._make_prompt_key_bindings()
    handlers = {tuple(binding.keys): binding.handler for binding in kb.bindings}

    class Buffer:
        complete_state = object()
        document = type("Document", (), {"cursor_position_row": 0, "line_count": 1})()

        def __init__(self) -> None:
            self.calls: list[str] = []

        def complete_previous(self) -> None:
            self.calls.append("previous")

        def complete_next(self) -> None:
            self.calls.append("next")

        def history_backward(self) -> None:
            self.calls.append("history_backward")

        def history_forward(self) -> None:
            self.calls.append("history_forward")

        def cursor_up(self) -> None:
            self.calls.append("cursor_up")

        def cursor_down(self) -> None:
            self.calls.append("cursor_down")

    buffer = Buffer()
    event = type("Event", (), {"current_buffer": buffer})()
    handlers[("up",)](event)
    handlers[("down",)](event)

    assert buffer.calls == ["previous", "next"]


def test_skills_completion_covers_dynamic_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import uagent.cli as cli

    class MockEvent:
        pass

    monkeypatch.setattr(cli, "_PROMPT_SESSION", None)

    def mock_prompt_session(*args, **kwargs):
        return kwargs["completer"]

    monkeypatch.setattr("prompt_toolkit.PromptSession", mock_prompt_session)
    completer = cli._get_prompt_session()

    def completed(text: str) -> list[str]:
        doc = Document(text=text, cursor_position=len(text))
        return [c.text for c in completer.get_completions(doc, MockEvent())]

    assert "review" in completed(":skills r")
    assert "enable" in completed(":skills e")
    assert "--yes" in completed(":skills enable my-skill --y")
    assert "--sort" in completed(":skills mp_search query ")
    assert "recent" in completed(":skills mp_search query --sort ")
    assert "clawhub" in completed(":skills mp_search query --source ")


def test_skills_dynamic_help_includes_lifecycle_commands() -> None:
    from uagent import tools

    detail = tools.get_dynamic_command_detail("skills") or ""
    assert ":skills review" in detail
    assert ":skills enable" in detail
