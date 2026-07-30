from __future__ import annotations

from typing import Any
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
