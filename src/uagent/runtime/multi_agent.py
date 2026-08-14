"""Small multi-agent orchestration primitives built on the DAG runtime."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass(frozen=True)
class AgentTask:
    name: str
    run: Callable[[dict[str, Any]], Awaitable[Any] | Any]


async def run_agents(tasks: list[AgentTask], *, fail_fast: bool = True) -> dict[str, Any]:
    """Run independent agents concurrently and collect results by name."""
    names = [task.name for task in tasks]
    if len(set(names)) != len(names):
        raise ValueError("duplicate agent task name")

    async def invoke(task: AgentTask) -> tuple[str, Any]:
        value = task.run({})
        if asyncio.iscoroutine(value):
            value = await value
        return task.name, value

    if fail_fast:
        pairs = await asyncio.gather(*(invoke(task) for task in tasks))
        return dict(pairs)

    results: dict[str, Any] = {}
    outcomes = await asyncio.gather(*(invoke(task) for task in tasks), return_exceptions=True)
    for task, outcome in zip(tasks, outcomes):
        results[task.name] = outcome
    return results


__all__ = ["AgentTask", "run_agents"]
