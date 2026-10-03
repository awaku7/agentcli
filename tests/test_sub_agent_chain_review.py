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
    published = []
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
                    "task": "produce and validate result",
                    "store_key": "reviewed_result",
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
    assert all(call.get("store_key") is None for call in worker_calls)
    assert worker_calls[0]["task"] == "produce and validate result"
    assert "Add validation evidence." in worker_calls[1]["task"]
    assert "produce and validate result" in worker_calls[1]["task"]
    assert published == [("reviewed_result", _worker_result("candidate-v2"))]


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


def test_reviewed_store_key_is_published_only_after_approval(monkeypatch):
    worker_args = []
    published = []
    candidate = _worker_result("approved candidate")

    def fake_run(args):
        if args["agent_name"] == "reviewer":
            return _review_result("approve")
        worker_args.append(args)
        return candidate

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
                    "task": "produce result",
                    "store_key": "approved_result",
                    "review": {},
                }
            ]
        }
    )

    result = json.loads(raw)
    assert result["status"] == "completed"
    assert worker_args[0].get("store_key") is None
    assert published == [("approved_result", candidate)]


def test_reviewed_store_key_is_not_published_when_gate_blocks(monkeypatch):
    worker_args = []
    published = []

    def fake_run(args):
        if args["agent_name"] == "reviewer":
            return _review_result("retry", "still incomplete")
        worker_args.append(args)
        return _worker_result("rejected candidate")

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
                    "task": "produce result",
                    "store_key": "must_not_publish",
                    "review": {"max_retries": 0},
                }
            ]
        }
    )

    result = json.loads(raw)
    assert result["status"] == "error"
    assert result["steps"][0]["status"] == "blocked"
    assert worker_args[0].get("store_key") is None
    assert published == []


def test_review_gate_segments_long_candidate_and_covers_suffix(monkeypatch):
    reviewer_tasks = []
    candidate = "A" * sub_agent_chain_tool._REVIEW_SEGMENT_CHARS + "SUFFIX_DEFECT"

    def fake_run(args):
        if args["agent_name"] == "reviewer":
            reviewer_tasks.append(args["task"])
            if "SUFFIX_DEFECT" in args["task"]:
                return _review_result("retry", "suffix defect found")
            return _review_result("approve")
        return candidate

    monkeypatch.setattr(sub_agent_tool, "run_tool", fake_run)

    raw = sub_agent_chain_tool.run_tool(
        {
            "chain": [
                {
                    "agent_name": "general",
                    "task": "produce a complete long result",
                    "response_mode": "text",
                    "review": {"max_retries": 0},
                }
            ]
        }
    )

    result = json.loads(raw)
    step = result["steps"][0]
    assert result["status"] == "error"
    assert step["status"] == "blocked"
    assert len(reviewer_tasks) == 2
    assert "segment 1 of 2" in reviewer_tasks[0]
    assert "segment 2 of 2" in reviewer_tasks[1]
    assert "SUFFIX_DEFECT" in reviewer_tasks[1]
    assert [review["segment"] for review in step["reviews"]] == [1, 2]
