import base64

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
