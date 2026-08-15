import json

from uagent.computer_use.integration import make_computer_use_handler
from uagent.computer_use.policy import ComputerUsePolicy
from uagent.computer_use.runtimes.mock import MockComputerRuntime


def test_handler_factory_executes_normalized_computer_call():
    policy = ComputerUsePolicy(
        enabled=True,
        environment="desktop",
        require_confirmation=False,
        allowed_actions=frozenset({"screenshot"}),
        allowed_domains=frozenset(),
        max_actions=10,
        max_turns=3,
        timeout=30.0,
    )
    runtime = MockComputerRuntime()
    handler = make_computer_use_handler(
        provider="openrouter",
        model="custom-model",
        policy=policy,
        runtime=runtime,
    )

    result = handler(
        tool_call={"id": "c1"},
        action={"action": "screenshot"},
        messages=[],
        core=None,
    )
    payload = json.loads(result)
    assert payload["success"] is True
    assert runtime.executed[0].action_id == "c1"
