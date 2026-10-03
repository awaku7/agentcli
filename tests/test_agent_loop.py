from __future__ import annotations

from uagent.runtime.agent_loop import AgentLoopJudgment, run_agent_loop


def _counter():
    state = {"round": 0}

    def advance():
        state["round"] += 1
        return state["round"]

    return state, advance


def test_agent_loop_completes_before_first_followup():
    state, advance = _counter()
    followups = []

    outcome = run_agent_loop(
        is_active=lambda: True,
        consume_exit_request=lambda: False,
        deterministic_completion=lambda: None,
        judge=lambda: AgentLoopJudgment(True, source="decision_provider"),
        advance_round=advance,
        get_max_rounds=lambda: 10,
        run_followup=lambda *args: followups.append(args),
    )

    assert outcome.reason == "complete"
    assert outcome.followup_rounds == 0
    assert outcome.judgment_source == "decision_provider"
    assert state["round"] == 0
    assert followups == []


def test_agent_loop_runs_followups_until_complete():
    state, advance = _counter()
    answers = iter(
        [
            AgentLoopJudgment(False, "missing A", "reviewer"),
            AgentLoopJudgment(False, "missing B", "reviewer"),
            AgentLoopJudgment(True, "", "reviewer"),
        ]
    )
    followups = []

    outcome = run_agent_loop(
        is_active=lambda: True,
        consume_exit_request=lambda: False,
        deterministic_completion=lambda: None,
        judge=lambda: next(answers),
        advance_round=advance,
        get_max_rounds=lambda: 5,
        run_followup=lambda feedback, round_number, max_rounds: followups.append(
            (feedback, round_number, max_rounds)
        ),
    )

    assert outcome.reason == "complete"
    assert outcome.followup_rounds == 2
    assert outcome.judgment_source == "reviewer"
    assert state["round"] == 2
    assert followups == [
        ("missing A", 1, 5),
        ("missing B", 2, 5),
    ]


def test_agent_loop_stops_before_followup_beyond_max_rounds():
    state, advance = _counter()
    followups = []

    outcome = run_agent_loop(
        is_active=lambda: True,
        consume_exit_request=lambda: False,
        deterministic_completion=lambda: None,
        judge=lambda: AgentLoopJudgment(False, "keep going", "reviewer"),
        advance_round=advance,
        get_max_rounds=lambda: 2,
        run_followup=lambda feedback, round_number, max_rounds: followups.append(
            (feedback, round_number, max_rounds)
        ),
    )

    assert outcome.reason == "max_rounds"
    assert outcome.max_rounds_reached is True
    assert outcome.followup_rounds == 2
    assert state["round"] == 3
    assert followups == [
        ("keep going", 1, 2),
        ("keep going", 2, 2),
    ]


def test_agent_loop_deterministic_completion_precedes_judgment():
    state, advance = _counter()
    calls = []

    outcome = run_agent_loop(
        is_active=lambda: True,
        consume_exit_request=lambda: False,
        deterministic_completion=lambda: "completion_regex",
        judge=lambda: calls.append("judge") or AgentLoopJudgment(True),
        advance_round=advance,
        get_max_rounds=lambda: 10,
        run_followup=lambda *args: calls.append(("followup", args)),
    )

    assert outcome.reason == "completion_regex"
    assert outcome.followup_rounds == 0
    assert calls == []
    assert state["round"] == 0


def test_agent_loop_stops_when_inactive_before_other_work():
    state, advance = _counter()
    calls = []

    outcome = run_agent_loop(
        is_active=lambda: False,
        consume_exit_request=lambda: calls.append("exit") or False,
        deterministic_completion=lambda: calls.append("deterministic") or None,
        judge=lambda: calls.append("judge") or AgentLoopJudgment(True),
        advance_round=advance,
        get_max_rounds=lambda: 10,
        run_followup=lambda *args: calls.append(("followup", args)),
    )

    assert outcome.reason == "stopped"
    assert outcome.followup_rounds == 0
    assert calls == []
    assert state["round"] == 0


def test_agent_loop_honors_explicit_exit_before_completion_checks():
    state, advance = _counter()
    calls = []

    outcome = run_agent_loop(
        is_active=lambda: True,
        consume_exit_request=lambda: True,
        deterministic_completion=lambda: calls.append("deterministic") or None,
        judge=lambda: calls.append("judge") or AgentLoopJudgment(True),
        advance_round=advance,
        get_max_rounds=lambda: 10,
        run_followup=lambda *args: calls.append(("followup", args)),
    )

    assert outcome.reason == "user_exit"
    assert outcome.followup_rounds == 0
    assert calls == []
    assert state["round"] == 0


def test_agent_loop_supports_judgment_terminal_reason():
    state, advance = _counter()
    calls = []

    outcome = run_agent_loop(
        is_active=lambda: True,
        consume_exit_request=lambda: False,
        deterministic_completion=lambda: None,
        judge=lambda: AgentLoopJudgment(
            False,
            source="sentinel",
            terminal_reason="sentinel_invalid",
        ),
        advance_round=advance,
        get_max_rounds=lambda: 10,
        run_followup=lambda *args: calls.append(("followup", args)),
    )

    assert outcome.reason == "sentinel_invalid"
    assert outcome.judgment_source == "sentinel"
    assert outcome.followup_rounds == 0
    assert calls == []
    assert state["round"] == 0
