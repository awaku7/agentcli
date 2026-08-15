import base64

from uagent.computer_use.adapters.gemini import GeminiComputerAdapter
from uagent.computer_use.results import ComputerActionResult, Screenshot


class Capability:
    supported = True
    native = True
    tool_type = "computer_use"


def test_gemini_builds_computer_use_tool_for_browser():
    tool = GeminiComputerAdapter().build_tool(
        Capability(), environment="browser", prompt_injection_detection=True
    )
    assert tool == {
        "computer_use": {
            "environment": "ENVIRONMENT_BROWSER",
            "enable_prompt_injection_detection": True,
        }
    }


def test_gemini_parses_function_call_parts():
    response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "function_call": {
                                "name": "click",
                                "args": {"x": 450, "y": 120, "intent": "search"},
                            }
                        }
                    ]
                }
            }
        ]
    }
    actions = GeminiComputerAdapter().parse_actions(response, turn_id="turn-1")
    assert len(actions) == 1
    assert actions[0].action_id == "turn-1:0"
    assert actions[0].action == "click"
    assert actions[0].coordinate == (450, 120)


def test_gemini_builds_function_response_with_screenshot():
    adapter = GeminiComputerAdapter()
    action = adapter.parse_actions(
        {
            "function_call": {
                "name": "take_screenshot",
                "args": {},
            }
        },
        turn_id="turn-2",
    )[0]
    result = ComputerActionResult(
        action_id=action.action_id,
        success=True,
        screenshot=Screenshot(data=b"png"),
    )
    output = adapter.build_tool_result(action, result)
    assert output["function_response"]["name"] == "screenshot"
    part = output["function_response"]["response"]["parts"][0]
    assert part["inline_data"]["data"] == base64.b64encode(b"png").decode("ascii")
