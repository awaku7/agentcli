from __future__ import annotations

import os
import threading
import time

from fastapi.testclient import TestClient

from uagent.a2a import server
from uagent.a2a.task_store import InMemoryTaskStore
from uagent.runtime.turn_context_runtime import resolved_turn_context
from uagent.runtime.sub_agent_job_access import get_job_runtime_context
from uagent.runtime.sub_agent_jobs import SubAgentJobOwner


async def _allow_auth():
    return {"subject": "test"}


def _task_id(response) -> str:
    return str(response.json()["task"]["id"])


def test_a2a_task_waits_for_child_jobs_and_returns_results(monkeypatch):
    monkeypatch.setattr(server, "require_bearer_auth", _allow_auth)
    monkeypatch.setattr(server, "_build_task_store", InMemoryTaskStore)

    def fake_run_once(*, user_text: str, task_id: str):
        with resolved_turn_context(entry_point="a2a", project_path=os.getcwd()):
            runtime = get_job_runtime_context()
            assert runtime is not None
            manager, owner = runtime
            assert owner.a2a_task_id == task_id
            manager.spawn(
                owner=owner,
                agent_name="planner",
                task="child task",
                worker=lambda _context: "child result",
                timeout=3,
            )
        return {"role": "assistant", "content": "parent result"}, None

    monkeypatch.setattr(server, "run_once", fake_run_once)
    app = server.build_app(credential_store=object())
    with TestClient(app) as client:
        response = client.post(
            "/message:send",
            json={
                "message": {"role": "user", "content": "delegate"},
                "returnImmediately": True,
            },
        )
        assert response.status_code == 200
        task_id = _task_id(response)
        deadline = time.monotonic() + 5
        task = response.json()["task"]
        while task["status"] == "IN_PROGRESS" and time.monotonic() < deadline:
            time.sleep(0.03)
            task = client.get(f"/tasks/{task_id}").json()["task"]
        assert task["status"] == "SUCCEEDED"
        reports = task["outputMessage"]["background_jobs"]
        assert len(reports) == 1
        assert reports[0]["state"] == "completed"
        assert reports[0]["result"] == "child result"


def test_a2a_task_cancel_cancels_jobs_owned_by_that_task(monkeypatch):
    monkeypatch.setattr(server, "require_bearer_auth", _allow_auth)
    monkeypatch.setattr(server, "_build_task_store", InMemoryTaskStore)
    child_started = threading.Event()
    cancellation_seen = threading.Event()

    def fake_run_once(*, user_text: str, task_id: str):
        with resolved_turn_context(entry_point="a2a", project_path=os.getcwd()):
            runtime = get_job_runtime_context()
            assert runtime is not None
            manager, owner = runtime

            def child(context):
                child_started.set()
                while not context.cancel_event.wait(0.01):
                    context.raise_if_cancelled()
                try:
                    context.raise_if_cancelled()
                except Exception:
                    cancellation_seen.set()
                    raise

            manager.spawn(
                owner=owner,
                agent_name="reviewer",
                task="child task",
                worker=child,
                timeout=10,
            )
        return {"role": "assistant", "content": "parent result"}, None

    monkeypatch.setattr(server, "run_once", fake_run_once)
    app = server.build_app(credential_store=object())
    with TestClient(app) as client:
        response = client.post(
            "/message:send",
            json={
                "message": {"role": "user", "content": "delegate then cancel"},
                "returnImmediately": True,
            },
        )
        task_id = _task_id(response)
        assert child_started.wait(3)
        manager = app.state.sub_agent_job_manager
        owner = SubAgentJobOwner(
            entry_point="a2a", session_id=task_id, a2a_task_id=task_id
        )
        child_jobs = manager.summary(owner=owner)
        assert len(child_jobs) == 1
        cancelled = client.post(f"/tasks/{task_id}:cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["task"]["status"] == "CANCELLED"
        assert (
            manager.get(owner=owner, job_id=child_jobs[0]["job_id"])["state"]
            == "cancelled"
        )
        assert cancellation_seen.wait(2)
        assert manager.spawn(
            owner=owner,
            agent_name="late-child",
            task="should not be admitted",
            worker=lambda _context: "unreachable",
        ) == {"status": "rejected", "reason": "owner_transition"}


def test_a2a_stream_route_registers_runtime_and_completes(monkeypatch):
    monkeypatch.setattr(server, "require_bearer_auth", _allow_auth)
    monkeypatch.setattr(server, "_build_task_store", InMemoryTaskStore)

    def fake_run_once(*, user_text: str, task_id: str):
        return {"role": "assistant", "content": "stream result"}, None

    monkeypatch.setattr(server, "run_once", fake_run_once)
    app = server.build_app(credential_store=object())
    with TestClient(app) as client:
        response = client.post(
            "/message:stream",
            json={"message": {"role": "user", "content": "stream"}},
        )
        assert response.status_code == 200
        assert "SUCCEEDED" in response.text
        assert "stream result" in response.text
