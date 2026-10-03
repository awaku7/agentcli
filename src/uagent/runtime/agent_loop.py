"""Reusable goal-driven agent loop control.

This module contains only the control-flow contract shared by autonomous agent
runtimes. It deliberately does not know about providers, messages, tools,
Decision Providers, CLI state, or UI rendering.

The caller owns one unit of work (for example an Auto-pilot main-agent round or
a Sub-Agent round) and supplies callbacks for completion judgment and follow-up
execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class AgentLoopJudgment:
    """One completion judgment produced after evaluating accumulated work."""

    complete: bool
    feedback: str = ""
    source: str = ""


@dataclass(frozen=True)
class AgentLoopOutcome:
    """Terminal state returned by run_agent_loop()."""

    reason: str
    followup_rounds: int
    judgment_source: str = ""
    max_rounds_reached: bool = False


def run_agent_loop(
    *,
    is_active: Callable[[], bool],
    consume_exit_request: Callable[[], bool],
    deterministic_completion: Callable[[], Optional[str]],
    judge: Callable[[], AgentLoopJudgment],
    advance_round: Callable[[], int],
    get_max_rounds: Callable[[], Optional[int]],
    run_followup: Callable[[str, int, Optional[int]], None],
) -> AgentLoopOutcome:
    """Run a goal-driven autonomous loop until one terminal condition is met.

    The initial unit of work is assumed to have already completed before this
    function starts. Therefore judgment always happens before the first
    follow-up round. This matches UAG Auto-pilot semantics and is also suitable
    for Sub-Agents whose initial answer should be reviewed before more work is
    scheduled.

    deterministic_completion may return a caller-defined terminal reason such
    as "completion_regex". Returning None means that model-based judgment
    should proceed.

    advance_round returns the newly selected follow-up round number.
    run_followup is never called after the configured maximum is exceeded.
    """

    last_judgment_source = ""
    followup_rounds = 0

    while True:
        if not is_active():
            return AgentLoopOutcome(
                reason="stopped",
                followup_rounds=followup_rounds,
                judgment_source=last_judgment_source,
            )

        if consume_exit_request():
            return AgentLoopOutcome(
                reason="user_exit",
                followup_rounds=followup_rounds,
                judgment_source=last_judgment_source,
            )

        deterministic_reason = deterministic_completion()
        if deterministic_reason:
            return AgentLoopOutcome(
                reason=str(deterministic_reason),
                followup_rounds=followup_rounds,
                judgment_source=last_judgment_source,
            )

        judgment = judge()
        last_judgment_source = str(judgment.source or "")
        if judgment.complete:
            return AgentLoopOutcome(
                reason="complete",
                followup_rounds=followup_rounds,
                judgment_source=last_judgment_source,
            )

        round_number = int(advance_round())
        max_rounds = get_max_rounds()
        if max_rounds is not None and round_number > max_rounds:
            return AgentLoopOutcome(
                reason="max_rounds",
                followup_rounds=followup_rounds,
                judgment_source=last_judgment_source,
                max_rounds_reached=True,
            )

        run_followup(judgment.feedback, round_number, max_rounds)
        followup_rounds += 1
