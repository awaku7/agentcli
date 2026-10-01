import base64
import json

from uagent.computer_use.adapters.anthropic import AnthropicComputerAdapter
from uagent.computer_use.capability import ComputerUseCapabilityError
from uagent.computer_use.results import ComputerActionResult, Screenshot


class Capability:
    supported = True
    native = True
    tool_type = "computer_20251124"
    tool_version = "2025-11-24"
    beta_header = "computer-use-2025-11-24"
    enable_zoom = True


def test_anthropic_builds_native_computer_tool():
    adapter = AnthropicComputerAdapter()
    tool = adapter.build_tool(Capability(), width=1280, height=720, display_number=1)

    assert tool == {
        "type": "computer_20251124",
        "name": "computer",
        "display_width_px": 1280,
        "display_height_px": 720,
        "display_number": 1,
        "enable_zoom": True,
    }
    assert adapter.beta_headers(Capability()) == ["computer-use-2025-11-24"]


def test_anthropic_parses_tool_use_into_normalized_actions():
    response = {
        "content": [
            {
                "type": "tool_use",
                "id": "toolu_1",
                "name": "computer",
                "input": {"action": "left_click", "coordinate": [10, 20]},
            }
        ]
    }

    actions = AnthropicComputerAdapter().parse_actions(response)

    assert len(actions) == 1
    assert actions[0].action_id == "toolu_1"
    assert actions[0].action == "click"
    assert actions[0].coordinate == (10, 20)


def test_anthropic_builds_tool_result_with_screenshot():
    action = AnthropicComputerAdapter().parse_actions(
        {
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_2",
                    "name": "computer",
                    "input": {"action": "screenshot"},
                }
            ]
        }
    )[0]
    result = ComputerActionResult(
        action_id="toolu_2",
        success=True,
        screenshot=Screenshot(data=b"png", media_type="image/png"),
    )

    tool_result = AnthropicComputerAdapter().build_tool_result(action, result)

    image = tool_result["content"][0]
    assert tool_result["type"] == "tool_result"
    assert tool_result["tool_use_id"] == "toolu_2"
    assert image["type"] == "image"
    assert image["source"]["data"] == base64.b64encode(b"png").decode("ascii")


def test_anthropic_rejects_non_native_capability():
    class CustomCapability(Capability):
        native = False

    try:
        AnthropicComputerAdapter().build_tool(CustomCapability(), width=1, height=1)
    except ComputerUseCapabilityError:
        pass
    else:
        raise AssertionError("expected ComputerUseCapabilityError")


class ToolsetCapability(Capability):
    tool_type = "computer_toolset_20260801"
    beta_header = None


def test_anthropic_builds_toolset_without_legacy_fields_or_beta_header():
    adapter = AnthropicComputerAdapter()
    tool = adapter.build_tool(ToolsetCapability(), width=1280, height=720)

    assert tool == {
        "type": "computer_toolset_20260801",
        "configs": {
            "cursor_position": {"enabled": False},
            "hold_key": {"enabled": False},
            "left_mouse_down": {"enabled": False},
            "left_mouse_up": {"enabled": False},
            "zoom": {"enabled": False},
        },
    }
    assert adapter.beta_headers(ToolsetCapability()) == []


def test_anthropic_parses_toolset_member_shapes():
    adapter = AnthropicComputerAdapter()
    actions = adapter.parse_actions(
        {
            "content": [
                {
                    "type": "tool_use",
                    "id": "click-1",
                    "name": "left_click",
                    "toolset_name": "computer",
                    "input": {
                        "coordinate": [10, 20],
                        "text": "ctrl+shift",
                    },
                },
                {
                    "type": "tool_use",
                    "id": "drag-1",
                    "name": "left_click_drag",
                    "toolset_name": "computer",
                    "input": {
                        "start_coordinate": [1, 2],
                        "coordinate": [3, 4],
                    },
                },
                {
                    "type": "tool_use",
                    "id": "scroll-1",
                    "name": "scroll",
                    "toolset_name": "computer",
                    "input": {"scroll_direction": "down", "scroll_amount": 3},
                },
                {
                    "type": "tool_use",
                    "id": "key-1",
                    "name": "key",
                    "toolset_name": "computer",
                    "input": {"text": "ctrl+s", "repeat": 2},
                },
                {
                    "type": "tool_use",
                    "id": "wait-1",
                    "name": "wait",
                    "toolset_name": "computer",
                    "input": {"duration": 2},
                },
            ]
        }
    )

    assert [action.action for action in actions] == [
        "click",
        "drag",
        "scroll",
        "keypress",
        "wait",
    ]
    assert actions[0].coordinate == (10, 20)
    assert actions[0].keys == ("ctrl", "shift")
    assert actions[1].path == ((1, 2), (3, 4))
    assert actions[2].scroll_y == 300
    assert actions[3].keys == ("ctrl", "s")
    assert actions[3].repeat == 2
    assert actions[4].text == "2"


def test_anthropic_rejects_disabled_toolset_members():
    import pytest

    with pytest.raises(ValueError, match="unsupported Anthropic computer toolset"):
        AnthropicComputerAdapter().parse_actions(
            {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "zoom-1",
                        "name": "zoom",
                        "toolset_name": "computer",
                        "input": {"region": [0, 0, 10, 10]},
                    }
                ]
            }
        )


def _fake_anthropic_module(monkeypatch):
    import sys
    from types import ModuleType

    module = ModuleType("anthropic")
    module.Anthropic = object
    monkeypatch.setitem(sys.modules, "anthropic", module)


def test_claude_turn_parser_routes_computer_toolset_members_to_shared_handler(
    monkeypatch,
):
    from types import SimpleNamespace

    from uagent.providers.llm_claude import claude_chat_with_tools

    _fake_anthropic_module(monkeypatch)
    response = SimpleNamespace(
        id="resp-batch",
        content=[
            SimpleNamespace(
                type="tool_use",
                id="toolu-click",
                name="left_click",
                toolset_name="computer",
                input={"coordinate": [5, 7]},
            ),
            SimpleNamespace(
                type="tool_use",
                id="toolu-type",
                name="type",
                toolset_name="computer",
                input={"text": "hello"},
            ),
        ],
    )

    class Client:
        class Messages:
            def create(self, **kwargs):
                return response

        messages = Messages()

    _, calls = claude_chat_with_tools(
        Client(), "claude-sonnet-5-5", [], send_tools=False
    )

    assert [call["function"]["name"] for call in calls] == ["computer", "computer"]
    assert [call["computer_member_tool"] for call in calls] == ["left_click", "type"]
    assert [call["computer_batch_index"] for call in calls] == [0, 1]
    assert all(call["computer_batch_size"] == 2 for call in calls)
    assert json.loads(calls[0]["function"]["arguments"]) == {
        "coordinate": [5, 7],
        "action": "left_click",
    }


def test_claude_history_serializes_toolset_markers_and_final_screenshot(monkeypatch):
    import json
    from types import SimpleNamespace

    from uagent.providers.llm_claude import claude_chat_with_tools

    _fake_anthropic_module(monkeypatch)
    response = SimpleNamespace(content=[])

    class Messages:
        kwargs = None

        def create(self, **kwargs):
            self.kwargs = kwargs
            return response

    messages_api = Messages()
    client = SimpleNamespace(messages=messages_api)
    function_args = json.dumps({"action": "left_click", "coordinate": [5, 7]})
    tool_output = json.dumps(
        {
            "success": True,
            "screenshot_data": "cG5n",
            "screenshot_media_type": "image/png",
        }
    )
    claude_chat_with_tools(
        client,
        "claude-sonnet-5-5",
        [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "toolu-click",
                        "type": "function",
                        "function": {"name": "computer", "arguments": function_args},
                        "computer_toolset_name": "computer",
                        "computer_member_tool": "left_click",
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "toolu-click",
                "name": "computer",
                "content": tool_output,
                "computer_toolset_name": "computer",
                "computer_member_tool": "left_click",
                "computer_batch_index": 0,
                "computer_batch_size": 1,
            },
        ],
        send_tools=False,
    )

    sent = messages_api.kwargs["messages"]
    use_block = sent[0]["content"][0]
    result_block = sent[1]["content"][0]
    assert use_block == {
        "type": "tool_use",
        "id": "toolu-click",
        "name": "left_click",
        "toolset_name": "computer",
        "input": {"coordinate": [5, 7]},
    }
    assert result_block["toolset_name"] == "computer"
    assert result_block["is_error"] is False
    assert result_block["content"][0] == {"type": "text", "text": "OK"}
    assert result_block["content"][1]["type"] == "image"


def test_prepare_native_anthropic_toolset_allows_guarded_runtime(monkeypatch):
    from types import SimpleNamespace

    from uagent.computer_use.native import prepare_native_computer_use

    class Capability:
        supported = True
        native = True
        tool_type = "computer_toolset_20260801"

    monkeypatch.setattr(
        "uagent.computer_use.capability.get_computer_use_capability",
        lambda model, provider: Capability(),
    )
    core = SimpleNamespace(computer_use_runtime=object())

    assert prepare_native_computer_use(
        core=core, provider="claude", model="sonnet-test"
    )
    assert core.computer_use_native_tool["type"] == "computer_toolset_20260801"
    assert core.computer_use_native_headers == []


def test_claude_requests_native_toolset_alongside_guarded_runtime(monkeypatch):
    from types import SimpleNamespace

    from uagent.providers.llm_claude import claude_chat_with_tools

    _fake_anthropic_module(monkeypatch)
    response = SimpleNamespace(content=[])

    class Messages:
        kwargs = None

        def create(self, **kwargs):
            self.kwargs = kwargs
            return response

    messages_api = Messages()
    client = SimpleNamespace(messages=messages_api)
    core = SimpleNamespace(
        computer_use_runtime=object(),
        computer_use_native_tool={
            "type": "computer_toolset_20260801",
            "configs": {"zoom": {"enabled": False}},
        },
        context_tool_specs=[],
    )

    claude_chat_with_tools(client, "claude-sonnet-5-5", [], core=core)

    sent_tools = messages_api.kwargs["tools"]
    assert sent_tools == [
        {"type": "computer_toolset_20260801", "configs": {"zoom": {"enabled": False}}}
    ]
    assert "extra_headers" not in messages_api.kwargs
