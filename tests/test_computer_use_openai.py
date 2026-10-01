from types import SimpleNamespace

from uagent.computer_use.adapters.openai import OpenAIComputerAdapter
from uagent.computer_use.results import ComputerActionResult, Screenshot


class Capability:
    supported = True
    native = True
    tool_type = "computer"


def test_openai_builds_computer_tool():
    tool = OpenAIComputerAdapter().build_tool(Capability())
    assert tool == {"type": "computer"}


def test_openai_parses_computer_call_actions():
    response = {
        "output": [
            {
                "type": "computer_call",
                "call_id": "call_1",
                "actions": [
                    {"type": "click", "x": 10, "y": 20, "button": "left"},
                    {"type": "type", "text": "hello"},
                ],
            }
        ]
    }
    actions = OpenAIComputerAdapter().parse_actions(response)
    assert [action.action_id for action in actions] == ["call_1:0", "call_1:1"]
    assert actions[0].coordinate == (10, 20)
    assert actions[1].text == "hello"


def test_openai_parses_native_action_shapes_and_rejects_nonstandard_actions():
    adapter = OpenAIComputerAdapter()
    actions = adapter.parse_actions(
        {
            "output": [
                {
                    "type": "computer_call",
                    "call_id": "call_shapes",
                    "actions": [
                        {"type": "keypress", "keys": ["CTRL", "A"]},
                        {"type": "scroll", "x": 10, "y": 20, "scroll_y": 100},
                        {
                            "type": "drag",
                            "path": [{"x": 1, "y": 2}, {"x": 3, "y": 4}],
                        },
                    ],
                }
            ]
        }
    )

    assert actions[0].keys == ("CTRL", "A")
    assert actions[1].coordinate == (10, 20)
    assert actions[1].scroll_y == 100
    assert actions[2].path == ((1, 2), (3, 4))

    import pytest

    with pytest.raises(ValueError, match="unsupported OpenAI Computer Use action"):
        adapter.parse_actions(
            {
                "output": [
                    {
                        "type": "computer_call",
                        "call_id": "call_extra",
                        "actions": [{"type": "zoom"}],
                    }
                ]
            }
        )


def test_openai_parses_drag_path_with_sdk_model_points():
    actions = OpenAIComputerAdapter().parse_actions(
        {
            "output": [
                {
                    "type": "computer_call",
                    "call_id": "call_sdk_path",
                    "actions": [
                        {
                            "type": "drag",
                            "path": [
                                SimpleNamespace(x=1, y=2),
                                SimpleNamespace(x=3, y=4),
                            ],
                        }
                    ],
                }
            ]
        }
    )

    assert actions[0].path == ((1, 2), (3, 4))


def test_openai_builds_computer_call_output():
    adapter = OpenAIComputerAdapter()
    action = adapter.parse_actions(
        {
            "output": [
                {
                    "type": "computer_call",
                    "call_id": "call_2",
                    "actions": [{"type": "screenshot"}],
                }
            ]
        }
    )[0]
    result = ComputerActionResult(
        action_id=action.action_id,
        success=True,
        screenshot=Screenshot(data=b"png"),
    )
    output = adapter.build_tool_result(action, result)
    assert output["type"] == "computer_call_output"
    assert output["call_id"] == "call_2"
    assert output["output"]["type"] == "computer_screenshot"
    assert output["output"]["detail"] == "original"


class PreviewCapability:
    supported = True
    native = True
    tool_type = "computer_use_preview"


def test_openai_builds_preview_computer_tool():
    tool = OpenAIComputerAdapter().build_tool(PreviewCapability())
    assert tool == {"type": "computer_use_preview"}
