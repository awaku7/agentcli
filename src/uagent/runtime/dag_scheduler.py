"""Dependency-aware scheduler for independent Tool steps."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


@dataclass(frozen=True)
class DagNode:
    id: str
    run: Callable[[dict[str, Any]], Awaitable[Any] | Any]
    depends_on: tuple[str, ...] = field(default_factory=tuple)


class DagCycleError(ValueError):
    """Raised when a DAG contains a missing dependency or cycle."""


async def run_dag(nodes: list[DagNode]) -> dict[str, Any]:
    """Run dependency-ready nodes concurrently and return results by node ID."""
    by_id = {node.id: node for node in nodes}
    if len(by_id) != len(nodes):
        raise DagCycleError("duplicate DAG node id")
    for node in nodes:
        missing = set(node.depends_on) - by_id.keys()
        if missing:
            raise DagCycleError(f"missing DAG dependency: {sorted(missing)!r}")

    results: dict[str, Any] = {}
    pending = set(by_id)
    while pending:
        ready = [
            by_id[node_id]
            for node_id in sorted(pending)
            if set(by_id[node_id].depends_on).issubset(results)
        ]
        if not ready:
            raise DagCycleError("DAG contains a cycle")

        async def invoke(node: DagNode) -> tuple[str, Any]:
            value = node.run({dep: results[dep] for dep in node.depends_on})
            if asyncio.iscoroutine(value) or isinstance(value, Awaitable):
                value = await value
            return node.id, value

        completed = await asyncio.gather(*(invoke(node) for node in ready))
        results.update(completed)
        pending.difference_update(node.id for node in ready)
    return results


__all__ = ["DagCycleError", "DagNode", "run_dag"]
