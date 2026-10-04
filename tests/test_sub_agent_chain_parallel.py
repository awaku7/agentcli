from __future__ import annotations

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor

from uagent.runtime.identity_context import submit_with_current_context
from uagent.tools import sub_agent_chain_tool, sub_agent_tool


def _worker_result(label: str) -> str:
    return json.dumps(
        {
            "status": "completed",
            "role": "general",
            "summary": label,
        }
    )


def test_parallel_group_runs_concurrently_and_preserves_input_order(monkeypatch):
    barrier = threading.Barrier(2)
    second_finished = threading.Event()

    def fake_run(args):
        task = args["task"]
        if task == "first":
            barrier.wait(timeout=5)
            assert second_finished.wait(timeout=5)
            return _worker_result("first")
        if task == "second":
            barrier.wait(timeout=5)
            second_finished.set()
            return _worker_result("second")
        raise AssertionError(f"unexpected task: {task}")

    monkeypatch.setattr(sub_agent_tool, "run_tool", fake_run)

    raw = sub_agent_chain_tool.run_tool(
        {
            "chain": [
                {
                    "agent_name": "general",
                    "task": "first",
                    "parallel_group": "research",
                },
                {
                    "agent_name": "general",
                    "task": "second",
                    "parallel_group": "research",
                },
            ]
        }
    )

    result = json.loads(raw)
    assert result["status"] == "completed"
    assert [step["step"] for step in result["steps"]] == [1, 2]
    assert [json.loads(step["result"])["summary"] for step in result["steps"]] == [
        "first",
        "second",
    ]
    assert [step["parallel_group"] for step in result["steps"]] == [
        "research",
        "research",
    ]


def test_parallel_group_defers_store_publication_until_group_finishes(monkeypatch):
    published = []
    worker_store_keys = []

    def fake_run(args):
        worker_store_keys.append(args.get("store_key"))
        assert published == []
        return _worker_result(args["task"])

    monkeypatch.setattr(sub_agent_tool, "run_tool", fake_run)
    monkeypatch.setattr(
        sub_agent_tool,
        "publish_shared_result",
        lambda key, result: published.append((key, result)),
    )

    raw = sub_agent_chain_tool.run_tool(
        {
            "chain": [
                {
                    "agent_name": "general",
                    "task": "alpha",
                    "parallel_group": "pair",
                    "store_key": "alpha_result",
                },
                {
                    "agent_name": "general",
                    "task": "beta",
                    "parallel_group": "pair",
                    "store_key": "beta_result",
                },
            ]
        }
    )

    result = json.loads(raw)
    assert result["status"] == "completed"
    assert worker_store_keys == [None, None]
    assert published == [
        ("alpha_result", _worker_result("alpha")),
        ("beta_result", _worker_result("beta")),
    ]


def test_parallel_group_rejects_sibling_store_dependency(monkeypatch):
    calls = []

    def fake_run(args):
        calls.append(args)
        return _worker_result(args["task"])

    monkeypatch.setattr(sub_agent_tool, "run_tool", fake_run)

    raw = sub_agent_chain_tool.run_tool(
        {
            "chain": [
                {
                    "agent_name": "general",
                    "task": "producer",
                    "parallel_group": "pair",
                    "store_key": "producer_result",
                },
                {
                    "agent_name": "general",
                    "task": "consumer",
                    "parallel_group": "pair",
                    "load_keys": ["producer_result"],
                },
            ]
        }
    )

    result = json.loads(raw)
    assert result["status"] == "error"
    assert result["total_steps"] == 0
    assert "intra-group dependency" in result["message"]
    assert calls == []


def test_parallel_group_rejects_duplicate_store_keys(monkeypatch):
    calls = []

    def fake_run(args):
        calls.append(args)
        return _worker_result(args["task"])

    monkeypatch.setattr(sub_agent_tool, "run_tool", fake_run)

    raw = sub_agent_chain_tool.run_tool(
        {
            "chain": [
                {
                    "agent_name": "general",
                    "task": "one",
                    "parallel_group": "pair",
                    "store_key": "same",
                },
                {
                    "agent_name": "general",
                    "task": "two",
                    "parallel_group": "pair",
                    "store_key": "same",
                },
            ]
        }
    )

    result = json.loads(raw)
    assert result["status"] == "error"
    assert result["total_steps"] == 0
    assert "duplicate store_key" in result["message"]
    assert calls == []


def test_parallel_group_finishes_started_siblings_before_stop_on_error(monkeypatch):
    calls = []
    published = []
    barrier = threading.Barrier(2)

    def fake_run(args):
        calls.append(args["task"])
        if args["task"] in {"blocked", "successful"}:
            barrier.wait(timeout=5)
        if args["task"] == "blocked":
            return json.dumps(
                {
                    "status": "blocked",
                    "message": "worker incomplete",
                }
            )
        return _worker_result(args["task"])

    monkeypatch.setattr(sub_agent_tool, "run_tool", fake_run)
    monkeypatch.setattr(
        sub_agent_tool,
        "publish_shared_result",
        lambda key, result: published.append((key, result)),
    )

    raw = sub_agent_chain_tool.run_tool(
        {
            "chain": [
                {
                    "agent_name": "general",
                    "task": "blocked",
                    "parallel_group": "pair",
                },
                {
                    "agent_name": "general",
                    "task": "successful",
                    "parallel_group": "pair",
                    "store_key": "successful_result",
                },
                {
                    "agent_name": "general",
                    "task": "must not run",
                },
            ],
            "stop_on_error": True,
        }
    )

    result = json.loads(raw)
    assert result["status"] == "error"
    assert result["total_steps"] == 2
    assert [step["status"] for step in result["steps"]] == [
        "blocked",
        "completed",
    ]
    assert published == []
    assert "must not run" not in calls


def test_parallel_group_continues_and_publishes_successes_when_configured(monkeypatch):
    published = []

    def fake_run(args):
        if args["task"] == "blocked":
            return json.dumps(
                {
                    "status": "blocked",
                    "message": "worker incomplete",
                }
            )
        if args["task"] == "after":
            assert published == [("successful_result", _worker_result("successful"))]
        return _worker_result(args["task"])

    monkeypatch.setattr(sub_agent_tool, "run_tool", fake_run)
    monkeypatch.setattr(
        sub_agent_tool,
        "publish_shared_result",
        lambda key, result: published.append((key, result)),
    )

    raw = sub_agent_chain_tool.run_tool(
        {
            "chain": [
                {
                    "agent_name": "general",
                    "task": "blocked",
                    "parallel_group": "pair",
                },
                {
                    "agent_name": "general",
                    "task": "successful",
                    "parallel_group": "pair",
                    "store_key": "successful_result",
                },
                {
                    "agent_name": "general",
                    "task": "after",
                },
            ],
            "stop_on_error": False,
        }
    )

    result = json.loads(raw)
    assert result["status"] == "completed"
    assert [step["status"] for step in result["steps"]] == [
        "blocked",
        "completed",
        "completed",
    ]
    assert published == [("successful_result", _worker_result("successful"))]


def test_sub_agent_call_chain_is_context_local_across_parallel_workers(monkeypatch):
    runner = sub_agent_tool.SubAgentRunner()
    barrier = threading.Barrier(2)

    monkeypatch.setattr(runner, "_write_log", lambda *args, **kwargs: None)

    def fake_run_llm(**kwargs):
        barrier.wait(timeout=5)
        return _worker_result(kwargs["task"].task), {}, 0

    monkeypatch.setattr(runner, "_run_llm", fake_run_llm)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = submit_with_current_context(
            executor,
            runner.run,
            "general",
            "parallel task one",
        )
        second = submit_with_current_context(
            executor,
            runner.run,
            "general",
            "parallel task two",
        )
        results = [first.result(timeout=10), second.result(timeout=10)]

    decoded = [json.loads(result) for result in results]
    assert [item["status"] for item in decoded] == ["completed", "completed"]


def test_default_sub_agent_client_creation_uses_environment_lock(monkeypatch):
    class CountingLock:
        def __init__(self):
            self._lock = threading.Lock()
            self.entries = 0

        def __enter__(self):
            self._lock.acquire()
            self.entries += 1
            return self

        def __exit__(self, exc_type, exc, tb):
            self._lock.release()

    runner = sub_agent_tool.SubAgentRunner()
    lock = CountingLock()

    monkeypatch.setattr(sub_agent_tool, "_SUB_AGENT_ENV_LOCK", lock)
    monkeypatch.setattr(runner, "_write_log", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        sub_agent_tool,
        "make_client",
        lambda cb: (_ for _ in ()).throw(RuntimeError("stop after client setup")),
    )

    result = json.loads(runner.run("general", "default provider task"))

    assert result["status"] == "error"
    assert "Failed to create client" in result["message"]
    assert lock.entries == 2


def test_parallel_provider_credentials_do_not_leak_between_workers(monkeypatch):
    class ContendedLock:
        def __init__(self):
            self._lock = threading.Lock()
            self._meta_lock = threading.Lock()
            self.waiter_entered = threading.Event()

        def __enter__(self):
            with self._meta_lock:
                if self._lock.locked():
                    self.waiter_entered.set()
            self._lock.acquire()
            return self

        def __exit__(self, exc_type, exc, tb):
            self._lock.release()

    runner = sub_agent_tool.SubAgentRunner()
    lock = ContendedLock()
    planner_in_client = threading.Event()
    observed_api_keys = []

    monkeypatch.setattr(sub_agent_tool, "_SUB_AGENT_ENV_LOCK", lock)
    monkeypatch.setattr(runner, "_write_log", lambda *args, **kwargs: None)
    monkeypatch.setenv("UAGENT_OPENAI_API_KEY", "KEY_B")
    monkeypatch.setenv("UAGENT_SUB_AGENT_PLANNER_API_KEY", "KEY_A")
    monkeypatch.delenv("UAGENT_SUB_AGENT_REVIEWER_API_KEY", raising=False)
    monkeypatch.delenv("UAGENT_SUB_AGENT_API_KEY", raising=False)

    def fake_make_client(cb):
        api_key = os.environ.get("UAGENT_OPENAI_API_KEY")
        observed_api_keys.append(api_key)
        if api_key == "KEY_A":
            planner_in_client.set()
            assert lock.waiter_entered.wait(timeout=5)
        raise RuntimeError("stop after client setup")

    monkeypatch.setattr(sub_agent_tool, "make_client", fake_make_client)

    with ThreadPoolExecutor(max_workers=2) as executor:
        planner = submit_with_current_context(
            executor,
            runner.run,
            "planner",
            "planner credential task",
            provider="openai",
        )
        assert planner_in_client.wait(timeout=5)

        reviewer = submit_with_current_context(
            executor,
            runner.run,
            "reviewer",
            "reviewer credential task",
            provider="openai",
        )

        planner_result = json.loads(planner.result(timeout=10))
        reviewer_result = json.loads(reviewer.result(timeout=10))

    assert planner_result["status"] == "error"
    assert reviewer_result["status"] == "error"
    assert observed_api_keys == ["KEY_A", "KEY_B"]


def test_parallel_group_does_not_start_queued_steps_after_failure(monkeypatch):
    monkeypatch.setattr(sub_agent_chain_tool, "_MAX_PARALLEL_GROUP_WORKERS", 1)

    calls = []

    def fake_run(args):
        task = args["task"]
        calls.append(task)
        if task == "blocked":
            return json.dumps(
                {
                    "status": "blocked",
                    "message": "worker incomplete",
                }
            )
        return _worker_result(task)

    monkeypatch.setattr(sub_agent_tool, "run_tool", fake_run)

    raw = sub_agent_chain_tool.run_tool(
        {
            "chain": [
                {
                    "agent_name": "general",
                    "task": "blocked",
                    "parallel_group": "wide",
                },
                {
                    "agent_name": "general",
                    "task": "queued-1",
                    "parallel_group": "wide",
                },
                {
                    "agent_name": "general",
                    "task": "queued-2",
                    "parallel_group": "wide",
                },
            ],
            "stop_on_error": True,
        }
    )

    result = json.loads(raw)
    assert result["status"] == "error"
    assert calls == ["blocked"]
    assert result["total_steps"] == 1


def test_parallel_sub_agents_keep_status_busy_until_last_worker_finishes(monkeypatch):
    both_started = threading.Barrier(2)
    release_second = threading.Event()
    false_status_seen = threading.Event()
    status_events = []
    status_lock = threading.Lock()

    class Callbacks:
        def set_status(self, busy, label=""):
            with status_lock:
                status_events.append((busy, label))
            if not busy:
                false_status_seen.set()

    def fake_runner_run(agent_name, task, **kwargs):
        both_started.wait(timeout=5)
        if task == "second":
            assert release_second.wait(timeout=5)
        return _worker_result(task)

    monkeypatch.setattr(sub_agent_tool, "get_callbacks", lambda: Callbacks())
    monkeypatch.setattr(sub_agent_tool._runner, "run", fake_runner_run)
    with sub_agent_tool._SUB_AGENT_STATUS_LOCK:
        sub_agent_tool._SUB_AGENT_ACTIVE_RUNS = 0

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(
            sub_agent_tool.run_tool,
            {"agent_name": "general", "task": "first"},
        )
        second = executor.submit(
            sub_agent_tool.run_tool,
            {"agent_name": "general", "task": "second"},
        )

        assert json.loads(first.result(timeout=10))["status"] == "completed"
        assert not false_status_seen.is_set()

        release_second.set()
        assert json.loads(second.result(timeout=10))["status"] == "completed"

    assert [event for event in status_events if event[0] is False] == [(False, "")]
