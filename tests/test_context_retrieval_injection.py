from __future__ import annotations

from types import SimpleNamespace

from uagent.uagent_llm import _inject_retrieved_tool_context


def test_retrieved_context_is_injected_into_latest_user_turn(monkeypatch) -> None:
    monkeypatch.delenv("UAGENT_AUTO_RETRIEVE_TOOL_RESULTS", raising=False)
    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "find the configuration"},
    ]
    core = SimpleNamespace(
        retrieve_tool_context=lambda query, limit, max_chars: (
            "[retrieved tool results]\nresult_id=result-1"
            if "configuration" in query and limit == 5 and max_chars == 8000
            else ""
        )
    )

    assert _inject_retrieved_tool_context(messages, core) is True
    assert messages[-1]["content"].startswith("[retrieved tool results]")
    assert messages[-1]["content"].endswith("find the configuration")


def test_retrieval_is_not_injected_twice() -> None:
    messages = [
        {
            "role": "user",
            "content": "[retrieved tool results]\nold\n\nfind the configuration",
        }
    ]
    core = SimpleNamespace(retrieve_tool_context=lambda *args, **kwargs: "new")

    assert _inject_retrieved_tool_context(messages, core) is False
    assert messages[0]["content"].count("[retrieved tool results]") == 1


def test_retrieval_can_be_disabled(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_AUTO_RETRIEVE_TOOL_RESULTS", "0")
    messages = [{"role": "user", "content": "find the configuration"}]
    core = SimpleNamespace(retrieve_tool_context=lambda *args, **kwargs: "context")

    assert _inject_retrieved_tool_context(messages, core) is False
    assert messages[0]["content"] == "find the configuration"
