from uagent.runtime.active_context import ContextCandidate
from uagent.runtime.context_benchmark import run_context_benchmark
from uagent.runtime.context_budget import ContextBudget
from uagent.runtime.context_manager import ContextManager


def test_context_benchmark_compares_baseline_and_runtime_metrics():
    manager = ContextManager(
        budget=ContextBudget(
            total_chars=30,
            system_chars=0,
            tool_definition_chars=0,
            agent_state_chars=0,
            history_chars=0,
            tool_result_chars=30,
            artifact_chars=0,
            memory_chars=0,
        )
    )
    result = run_context_benchmark(
        [
            {
                "id": "one",
                "task": "task",
                "candidates": [
                    ContextCandidate(
                        "result",
                        "tool_result",
                        "tool_results",
                        "x" * 100,
                        relevance=0.9,
                    )
                ],
                "success": True,
            }
        ],
        manager=manager,
    )

    sample = result["samples"][0]
    assert result["success_rate"] == 1.0
    assert sample["baseline"]["active_chars"] > sample["runtime"]["active_chars"]
    assert sample["runtime"]["compaction_count"] == 1
