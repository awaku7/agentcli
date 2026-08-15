from uagent.computer_use.adapters.anthropic import AnthropicComputerAdapter
from uagent.computer_use.loop import run_anthropic_computer_loop
from uagent.computer_use.policy import ComputerUsePolicy
from uagent.computer_use.runtimes.mock import MockComputerRuntime


def test_anthropic_loop_executes_tool_and_returns_result_to_model():
    responses = iter(
        [
            {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "computer",
                        "input": {"action": "screenshot"},
                    }
                ]
            },
            {"content": [{"type": "text", "text": "done"}]},
        ]
    )
    requests = []

    def request(messages):
        requests.append(messages)
        return next(responses)

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

    final_response, history = run_anthropic_computer_loop(
        messages=[{"role": "user", "content": "inspect"}],
        request=request,
        adapter=AnthropicComputerAdapter(),
        policy=policy,
        runtime=runtime,
    )

    assert final_response["content"][0]["text"] == "done"
    assert runtime.executed[0].action_id == "toolu_1"
    assert len(requests) == 2
    assert history[-1]["role"] == "user"
    assert history[-1]["content"][0]["tool_use_id"] == "toolu_1"


def test_anthropic_loop_stops_at_max_turns():
    def request(messages):
        return {
            "content": [
                {
                    "type": "tool_use",
                    "id": "repeat",
                    "name": "computer",
                    "input": {"action": "screenshot"},
                }
            ]
        }

    policy = ComputerUsePolicy(
        enabled=True,
        environment="desktop",
        require_confirmation=False,
        allowed_actions=frozenset({"screenshot"}),
        allowed_domains=frozenset(),
        max_actions=10,
        max_turns=1,
        timeout=30.0,
    )
    runtime = MockComputerRuntime()

    _, history = run_anthropic_computer_loop(
        messages=[],
        request=request,
        adapter=AnthropicComputerAdapter(),
        policy=policy,
        runtime=runtime,
        max_turns=1,
    )

    assert len(runtime.executed) == 1
    assert history[-1]["content"][0]["tool_use_id"] == "repeat"
