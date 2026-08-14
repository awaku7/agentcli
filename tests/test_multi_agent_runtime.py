import asyncio

import pytest

from uagent.runtime.multi_agent import AgentTask, run_agents


def test_multi_agent_runs_concurrently_and_collects_results() -> None:
    async def scenario() -> None:
        result = await run_agents(
            [
                AgentTask("one", lambda _: "1"),
                AgentTask("two", lambda _: "2"),
            ]
        )
        assert result == {"one": "1", "two": "2"}

    asyncio.run(scenario())


def test_multi_agent_non_fail_fast_collects_exceptions() -> None:
    async def bad(_: dict) -> None:
        raise RuntimeError("failed")

    async def scenario() -> None:
        result = await run_agents([AgentTask("bad", bad)], fail_fast=False)
        assert isinstance(result["bad"], RuntimeError)
        with pytest.raises(ValueError):
            await run_agents(
                [AgentTask("same", lambda _: 1), AgentTask("same", lambda _: 2)]
            )

    asyncio.run(scenario())


def test_remote_runtime_wait_and_cancel(monkeypatch) -> None:
    from uagent.runtime.remote_agent import RemoteAgentRuntime

    runtime = RemoteAgentRuntime(base_url="https://agent.example")
    statuses = iter(["IN_PROGRESS", "SUCCEEDED"])
    runtime.client.get_task = lambda _task_id: {"task": {"status": next(statuses)}}
    runtime.client.cancel_task = lambda task_id: {
        "task": {"id": task_id, "status": "CANCELLED"}
    }
    result = runtime.wait("task-1", timeout=1, interval=0)
    assert result["task"]["status"] == "SUCCEEDED"
    assert runtime.cancel("task-1")["task"]["status"] == "CANCELLED"
    runtime.close()
