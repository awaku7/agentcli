"""Provider adapter-driven Computer Use agent loops."""

from __future__ import annotations

from typing import Any, Callable

from .policy import ComputerUsePolicy
from .runtime import ComputerRuntime, execute_action


def _content(response: Any) -> Any:
    if isinstance(response, dict):
        return response.get("content", [])
    return getattr(response, "content", [])


def run_anthropic_computer_loop(
    *,
    messages: list[dict[str, Any]],
    request: Callable[[list[dict[str, Any]]], Any],
    adapter: Any,
    policy: ComputerUsePolicy,
    runtime: ComputerRuntime,
    max_turns: int | None = None,
    domain: str | None = None,
) -> tuple[Any, list[dict[str, Any]]]:
    """Run an Anthropic-style tool-use loop with injected request/runtime.

    The callback boundary keeps provider transport separate from the loop and
    makes the loop deterministic in tests. Production integration can pass a
    callback around the existing Claude client call.
    """
    history = list(messages)
    turn_limit = max_turns if max_turns is not None else policy.max_turns
    if turn_limit <= 0:
        raise ValueError("max_turns must be positive")

    response: Any = None
    for _ in range(turn_limit):
        response = request(history)
        actions = adapter.parse_actions(response)
        if not actions:
            return response, history

        history.append({"role": "assistant", "content": _content(response)})
        tool_results = []
        for action in actions:
            result = execute_action(
                action,
                policy=policy,
                runtime=runtime,
                domain=domain,
            )
            tool_results.append(adapter.build_tool_result(action, result))
        history.append({"role": "user", "content": tool_results})

    return response, history
