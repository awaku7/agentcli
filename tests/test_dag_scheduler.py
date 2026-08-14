import asyncio

import pytest

from uagent.runtime.dag_scheduler import DagCycleError, DagNode, run_dag


def test_dag_runs_dependencies_and_parallel_ready_nodes() -> None:
    async def scenario() -> None:
        results = await run_dag(
            [
                DagNode("a", lambda _deps: "A"),
                DagNode("b", lambda deps: deps["a"] + "B", ("a",)),
                DagNode("c", lambda deps: deps["a"] + "C", ("a",)),
            ]
        )
        assert results == {"a": "A", "b": "AB", "c": "AC"}

    asyncio.run(scenario())


def test_dag_rejects_cycle_and_missing_dependency() -> None:
    async def scenario() -> None:
        with pytest.raises(DagCycleError):
            await run_dag([DagNode("a", lambda _: None, ("missing",))])
        with pytest.raises(DagCycleError):
            await run_dag([
                DagNode("a", lambda _: None, ("b",)),
                DagNode("b", lambda _: None, ("a",)),
            ])

    asyncio.run(scenario())
