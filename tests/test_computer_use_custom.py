from uagent.computer_use.adapters.custom import CustomComputerAdapter
from uagent.computer_use.results import ComputerActionResult, Screenshot


def test_custom_adapter_parses_function_call():
    actions = CustomComputerAdapter().parse_actions(
        {
            "tool_calls": [
                {
                    "id": "fn1",
                    "function": {"name": "click", "arguments": {"x": 1, "y": 2}},
                }
            ]
        },
        turn_id="t1",
    )
    assert len(actions) == 1
    assert actions[0].action_id == "fn1"
    assert actions[0].coordinate == (1, 2)


def test_custom_adapter_builds_function_result():
    adapter = CustomComputerAdapter()
    action = adapter.parse_actions(
        {
            "tool_calls": [
                {"id": "fn2", "function": {"name": "screenshot", "arguments": {}}}
            ]
        },
        turn_id="t2",
    )[0]
    result = adapter.build_tool_result(
        action,
        ComputerActionResult(
            action_id="fn2", success=True, screenshot=Screenshot(b"x")
        ),
    )
    assert result["tool_call_id"] == "fn2"
    assert result["content"]
