from uagent.runtime.chat_tool_policy import (
    initial_chat_completion_tools,
    limit_chat_completion_tools,
)


def _spec(name: str) -> dict:
    return {"type": "function", "function": {"name": name}}


def test_limit_chat_completion_tools_preserves_management_helpers():
    specs = [
        _spec("tool_catalog"),
        _spec("tool_load"),
        _spec("unload_tool"),
        _spec("human_ask"),
    ]
    specs.extend(_spec(f"tool_{index}") for index in range(140))

    result = limit_chat_completion_tools(
        specs, [{"role": "user", "content": "find a tool"}]
    )

    assert len(result) == 128
    names = {item["function"]["name"] for item in result}
    assert {"tool_catalog", "tool_load", "unload_tool", "human_ask"} <= names


def test_initial_chat_completion_tools_returns_discovery_tools_only():
    specs = [_spec("tool_load"), _spec("ordinary_tool"), _spec("tool_catalog")]

    result = initial_chat_completion_tools(specs)

    assert [item["function"]["name"] for item in result] == [
        "tool_load",
        "tool_catalog",
    ]
