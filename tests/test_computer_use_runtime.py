from uagent.computer_use.actions import ComputerAction
from uagent.computer_use.policy import ComputerUsePolicy
from uagent.computer_use.runtime import execute_action
from uagent.computer_use.runtimes.mock import MockComputerRuntime


def _policy(*actions):
    return ComputerUsePolicy(
        enabled=True,
        environment="desktop",
        require_confirmation=False,
        allowed_actions=frozenset(actions),
        allowed_domains=frozenset(),
        max_actions=10,
        max_turns=3,
        timeout=30.0,
    )


def test_mock_runtime_records_click_and_returns_success():
    runtime = MockComputerRuntime()
    action = ComputerAction(
        action_id="a1",
        action="click",
        coordinate=(10, 20),
        button="left",
    )

    result = execute_action(action, policy=_policy("click"), runtime=runtime)

    assert result.success is True
    assert result.action_id == "a1"
    assert runtime.executed == [action]


def test_mock_runtime_returns_screenshot_result():
    runtime = MockComputerRuntime()
    action = ComputerAction(action_id="a2", action="screenshot")

    result = execute_action(
        action,
        policy=_policy("screenshot"),
        runtime=runtime,
    )

    assert result.success is True
    assert result.screenshot is not None
    assert result.screenshot.media_type == "image/png"


def test_policy_rejection_does_not_reach_runtime():
    runtime = MockComputerRuntime()
    action = ComputerAction(action_id="a3", action="click")

    result = execute_action(
        action,
        policy=_policy("screenshot"),
        runtime=runtime,
    )

    assert result.success is False
    assert result.error
    assert runtime.executed == []


def test_runtime_error_is_returned_as_failed_result():
    runtime = MockComputerRuntime(fail_action="type")
    action = ComputerAction(action_id="a4", action="type", text="secret")

    result = execute_action(action, policy=_policy("type"), runtime=runtime)

    assert result.success is False
    assert result.action_id == "a4"
    assert "mock runtime failure" in result.error
