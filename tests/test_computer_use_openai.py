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
