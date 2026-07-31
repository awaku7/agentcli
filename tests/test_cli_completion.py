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
