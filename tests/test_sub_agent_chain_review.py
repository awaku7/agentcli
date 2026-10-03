from __future__ import annotations

import json

from uagent.tools import sub_agent_chain_tool, sub_agent_tool


def _worker_result(label: str) -> str:
    return json.dumps(
        {
            "status": "completed",
            "role": "general",
            "summary": label,
        }
    )


def _review_result(verdict: str, feedback: str = "") -> str:
    return json.dumps(
        {
            "status": "completed",
            "verdict": verdict,
            "feedback": feedback,
        }
    )


def test_review_gate_approves_first_worker_attempt(monkeypatch):
    calls = []

    def fake_run(args):
        calls.append(args)
        if args["agent_name"] == "reviewer":
            return _review_result("approve")
        return _worker_result("candidate-v1")

    monkeypatch.setattr(sub_agent_tool, "run_tool", fake_run)

    raw = sub_agent_chain_tool.run_tool(
        {
            "chain": [
                {
                    "agent_name": "general",
                    "task": "produce result",
                    "review": {"agent_name": "reviewer"},
                }
            ]
        }
    )

    result = json.loads(raw)
    step = result["steps"][0]
    assert result["status"] == "completed"
    assert step["status"] == "completed"
    assert step["attempts"] == 1
    assert step["reviews"][0]["verdict"] == "approve"
    assert json.loads(step["result"])["summary"] == "candidate-v1"
    assert [call["agent_name"] for call in calls] == ["general", "reviewer"]


def test_review_gate_retries_worker_with_feedback_then_approves(monkeypatch):
    calls = []
    worker_count = 0
    review_count = 0

    def fake_run(args):
        nonlocal worker_count, review_count
        calls.append(args)
        if args["agent_name"] == "reviewer":
            review_count += 1
            if review_count == 1:
                return _review_result("retry", "Add validation evidence.")
            return _review_result("approve")

        worker_count += 1
        return _worker_result(f"candidate-v{worker_count}")

    monkeypatch.setattr(sub_agent_tool, "run_tool", fake_run)

    raw = sub_agent_chain_tool.run_tool(
        {
            "chain": [
                {
                    "agent_name": "general",
                    "task": "produce and validate result",
                    "review": {
                        "agent_name": "reviewer",
                        "max_retries": 2,
                    },
                }
            ]
        }
    )

    result = json.loads(raw)
    step = result["steps"][0]
    assert result["status"] == "completed"
    assert step["status"] == "completed"
    assert step["attempts"] == 2
    assert [review["verdict"] for review in step["reviews"]] == [
        "retry",
        "approve",
    ]
    assert json.loads(step["result"])["summary"] == "candidate-v2"

    worker_calls = [call for call in calls if call["agent_name"] == "general"]
    assert len(worker_calls) == 2
    assert worker_calls[0]["task"] == "produce and validate result"
    assert "Add validation evidence." in worker_calls[1]["task"]
    assert "produce and validate result" in worker_calls[1]["task"]


def test_review_gate_retry_exhaustion_blocks_chain(monkeypatch):
    calls = []
    worker_count = 0

    def fake_run(args):
        nonlocal worker_count
        calls.append(args)
        if args["agent_name"] == "reviewer":
            return _review_result("retry", "Still incomplete.")
        worker_count += 1
        return _worker_result(f"candidate-v{worker_count}")

    monkeypatch.setattr(sub_agent_tool, "run_tool", fake_run)

    raw = sub_agent_chain_tool.run_tool(
        {
            "chain": [
                {
                    "agent_name": "general",
                    "task": "first",
                    "review": {"max_retries": 1},
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
    step = result["steps"][0]
    assert result["status"] == "error"
    assert result["total_steps"] == 1
    assert step["status"] == "blocked"
    assert step["attempts"] == 2
    assert len(step["reviews"]) == 2
    assert "exhausted worker retries" in step["error"]
    assert all(call["task"] != "must not run" for call in calls)


def test_review_gate_blocks_when_reviewer_itself_is_blocked(monkeypatch):
    def fake_run(args):
        if args["agent_name"] == "reviewer":
            return json.dumps(
                {
                    "status": "blocked",
                    "reason": "max_rounds",
                    "message": "reviewer did not finish",
                }
            )
        return _worker_result("candidate")

    monkeypatch.setattr(sub_agent_tool, "run_tool", fake_run)

    raw = sub_agent_chain_tool.run_tool(
        {
            "chain": [
                {
                    "agent_name": "general",
                    "task": "produce result",
                    "review": {},
                }
            ]
        }
    )

    result = json.loads(raw)
    step = result["steps"][0]
    assert result["status"] == "error"
    assert step["status"] == "blocked"
    assert "Review gate failed" in step["error"]
    assert "reviewer did not finish" in step["error"]


def test_chain_without_review_keeps_single_worker_execution(monkeypatch):
    calls = []

    def fake_run(args):
        calls.append(args)
        return _worker_result("single")

    monkeypatch.setattr(sub_agent_tool, "run_tool", fake_run)

    raw = sub_agent_chain_tool.run_tool(
        {
            "chain": [
                {
                    "agent_name": "general",
                    "task": "plain step",
                }
            ]
        }
    )

    result = json.loads(raw)
    step = result["steps"][0]
    assert result["status"] == "completed"
    assert step["status"] == "completed"
    assert "attempts" not in step
    assert "reviews" not in step
    assert len(calls) == 1
