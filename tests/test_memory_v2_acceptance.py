from __future__ import annotations

import json
from pathlib import Path

import pytest

from uagent.runtime.memory_evaluation_runner import run_evaluation


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "memory_evaluation_cases.json"


@pytest.mark.parametrize(
    ("host", "relative_path", "required_text"),
    [
        ("cli", "src/uagent/cli_impl/main.py", "llm_util.run_llm_rounds"),
        ("gui", "src/uagent/scheckgui_impl/worker.py", "util_run_llm_rounds"),
        ("web", "src/uagent/web_impl/agent_worker.py", "llm_util.run_llm_rounds"),
        ("a2a", "src/uagent/a2a/engine.py", "llm_util.run_llm_rounds"),
    ],
)
def test_v2_hosts_route_through_shared_llm_round(
    host: str, relative_path: str, required_text: str
) -> None:
    source_path = ROOT / relative_path
    source = source_path.read_text(encoding="utf-8")

    assert required_text in source, (
        f"{host} no longer routes through the shared LLM round path; "
        "Memory V2 projection acceptance must be reviewed for this host."
    )


def test_v2_shared_round_owns_memory_projection_boundary() -> None:
    source = (ROOT / "src/uagent/uagent_llm.py").read_text(encoding="utf-8")

    # Host adapters should not each implement their own retrieval/projection logic.
    # The shared round is the single turn boundary for Memory V2.
    assert "prepare_memory_projection(" in source
    assert "apply_memory_projection(" in source
    assert "memory_projection_snapshot" in source


def _load_cases() -> list[dict[str, object]]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return payload["retrieval_cases"]


def test_v2_strict_scope_acceptance_gate_passes_without_llm() -> None:
    report = run_evaluation(
        _load_cases(),
        iterations=1,
        gate_mode="strict_scope",
    )

    strict = report["modes"]["strict_scope"]
    baseline = report["modes"]["baseline"]

    assert report["overall_gate_passed"] is True
    assert baseline["gate_passed"] is None
    assert strict["gate_passed"] is True
    assert strict["recall"] == 1.0
    assert strict["irrelevant_injection_rate"] == 0.0
    assert strict["scope_violation_count"] == 0
    assert strict["legacy_unknown_selected_count"] == 0
    assert strict["forget_reappearance_count"] == 0
    assert strict["provider_continuation_cleared"] is True


def test_v2_projection_acceptance_gate_passes_without_llm() -> None:
    report = run_evaluation(
        _load_cases(),
        iterations=1,
        gate_mode="projection",
    )

    projection = report["modes"]["projection"]

    assert report["overall_gate_passed"] is True
    assert projection["gate_passed"] is True
    assert projection["recall"] == 1.0
    assert projection["irrelevant_injection_rate"] == 0.0
    assert projection["scope_violation_count"] == 0
    assert projection["forget_reappearance_count"] == 0
    assert projection["provider_continuation_cleared"] is True
