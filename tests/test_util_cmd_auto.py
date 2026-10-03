from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from uagent.decision import DecisionAnswer, DecisionResult, DecisionSettings
from uagent import util_cmd_auto
from uagent.util_cmd_auto import (
    _ask_auto_pilot_decision,
    _build_auto_pilot_decision_state,
    _build_judgment_messages,
    _handle_cmd_auto,
    _parse_auto_goal_options,
    _sentinel_judgment,
)


def _core() -> SimpleNamespace:
    return SimpleNamespace(
        auto_pilot_active=False,
        auto_pilot_exit_requested=False,
        auto_pilot_goal="",
        auto_pilot_max_rounds=10,
        auto_pilot_round=0,
    )


def test_auto_parser_preserves_goal_text_and_apostrophes() -> None:
    goal = 'Do not change "quoted" text. Don\'t collapse lines.\nSecond line.'

    parsed_goal, rounds, infinite, error = _parse_auto_goal_options(
        goal + " --max-rounds 3"
    )

    assert parsed_goal == goal
    assert rounds == 3
    assert infinite is False
    assert error is None


def test_auto_parser_rejects_unbalanced_round_option_without_shlex() -> None:
    goal = "Don't do this --max-rounds 2"
    parsed_goal, rounds, infinite, error = _parse_auto_goal_options(goal)

    assert parsed_goal == "Don't do this"
    assert rounds == 2
    assert infinite is False
    assert error is None


def test_auto_infinite_prefix_sets_unbounded_mode() -> None:
    core = _core()

    result = _handle_cmd_auto(
        "INFINITE inspect the repository",
        [],
        None,
        "",
        core=core,
        tr=lambda text, **kwargs: text,
    )

    assert result.run_llm is True
    assert result.prompt == "inspect the repository"
    assert core.auto_pilot_max_rounds is None
    assert core.auto_pilot_active is True


def test_auto_infinite_flag_sets_unbounded_mode() -> None:
    core = _core()

    result = _handle_cmd_auto(
        "inspect the repository --infinite",
        [],
        None,
        "",
        core=core,
        tr=lambda text, **kwargs: text,
    )

    assert result.run_llm is True
    assert result.prompt == "inspect the repository"
    assert core.auto_pilot_max_rounds is None


def test_auto_max_rounds_infinite_alias_sets_unbounded_mode() -> None:
    core = _core()

    _handle_cmd_auto(
        "inspect the repository --max-rounds INFINITE",
        [],
        None,
        "",
        core=core,
        tr=lambda text, **kwargs: text,
    )

    assert core.auto_pilot_max_rounds is None


def test_auto_rejects_non_positive_max_rounds() -> None:
    core = _core()

    result = _handle_cmd_auto(
        "inspect the repository --max-rounds 0",
        [],
        None,
        "",
        core=core,
        tr=lambda text, **kwargs: text,
    )

    assert result.run_llm is False
    assert core.auto_pilot_active is False


def test_auto_keeps_numeric_max_rounds() -> None:
    core = _core()

    _handle_cmd_auto(
        "inspect the repository --max-rounds 25",
        [],
        None,
        "",
        core=core,
        tr=lambda text, **kwargs: text,
    )

    assert core.auto_pilot_max_rounds == 25


def test_auto_off_stops_infinite_mode() -> None:
    core = _core()
    core.auto_pilot_active = True
    core.auto_pilot_max_rounds = None

    result = _handle_cmd_auto(
        "off",
        [],
        None,
        "",
        core=core,
        tr=lambda text, **kwargs: text,
    )

    assert result.run_llm is False
    assert core.auto_pilot_active is False
    assert core.auto_pilot_exit_requested is False


def test_reviewer_judgment_includes_masked_tool_result_summaries() -> None:
    messages = [
        {"role": "user", "content": "inspect the result"},
        {
            "role": "tool",
            "name": "demo",
            "tool_call_id": "call-1",
            "content": '{"ok": true, "result": {"text": "token: secret-value"}}',
        },
    ]

    judgment = _build_judgment_messages(messages, "inspect the result")
    summary_messages = [
        item
        for item in judgment
        if item.get("role") == "user"
        and "Recent tool results" in str(item.get("content"))
    ]
    assert len(summary_messages) == 1
    content = str(summary_messages[0]["content"])
    assert "[TOOL-RESULT] tool=demo status=success call_id=call-1" in content
    assert "secret-value" not in content
    assert "********" in content


def test_reviewer_judgment_includes_failed_tool_status() -> None:
    judgment = _build_judgment_messages(
        [
            {
                "role": "tool",
                "name": "demo",
                "tool_call_id": "call-2",
                "content": '{"ok": false, "error": {"code": "NOPE", "message": "failed"}}',
            }
        ],
        "inspect",
    )
    content = "\n".join(str(item.get("content")) for item in judgment)
    assert "tool=demo status=failed call_id=call-2" in content
    assert "failed" in content


def test_sentinel_judgment_accepts_case_and_optional_brackets() -> None:
    assert (
        _sentinel_judgment([{"role": "assistant", "content": " Auto_complete "}])
        == "COMPLETE"
    )
    assert (
        _sentinel_judgment([{"role": "assistant", "content": "AUTO_CONTINUE"}])
        == "CONTINUE"
    )


def test_sentinel_judgment_rejects_extra_text() -> None:
    assert (
        _sentinel_judgment([{"role": "assistant", "content": "AUTO_COMPLETE now"}])
        is None
    )


def test_sentinel_judgment_continues_for_tool_call_only_response() -> None:
    assert (
        _sentinel_judgment(
            [
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"id": "call-1", "type": "function"}],
                }
            ]
        )
        == "CONTINUE"
    )


def test_sentinel_judgment_does_not_use_older_marker_after_tool_call() -> None:
    assert (
        _sentinel_judgment(
            [
                {"role": "assistant", "content": "<AUTO_COMPLETE>"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{"id": "call-1"}],
                },
            ]
        )
        == "CONTINUE"
    )


def test_reviewer_prompt_uses_configured_feedback_language(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_AUTO_REVIEW_LANGUAGE", "ja")

    judgment = _build_judgment_messages([], "inspect")
    system = str(judgment[0]["content"])

    assert "requested review language: ja" in system
    assert "Keep COMPLETE/CONTINUE unchanged" in system


def _loop_core(*, max_rounds=10) -> SimpleNamespace:
    return SimpleNamespace(
        auto_pilot_active=True,
        auto_pilot_exit_requested=False,
        auto_pilot_exit_lock=threading.Lock(),
        auto_pilot_complete_regex=None,
        auto_pilot_goal="finish the task",
        auto_pilot_max_rounds=max_rounds,
        auto_pilot_round=0,
        interrupt_lock=threading.Lock(),
        interrupt_requested=False,
        _last_completion_reason=None,
        _last_round_outcome=None,
        set_status=lambda *_args, **_kwargs: None,
        log_message=lambda *_args, **_kwargs: None,
    )


class _FakeDecisionProvider:
    name = "typesafe"
    model = "jev-latest"

    def __init__(self, *, value="COMPLETE", error=None):
        self.value = value
        self.error = error
        self.requests = []
        self.closed = False

    def decide(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return DecisionResult(
            provider=self.name,
            model=self.model,
            answers={
                "goal_satisfied": DecisionAnswer(
                    value=self.value == "COMPLETE", confidence=0.8
                ),
                "material_work_remaining": DecisionAnswer(
                    value=self.value != "COMPLETE",
                    confidence=0.8,
                    calibrated=True,
                ),
            },
            latency_ms=2.5,
        )

    def close(self):
        self.closed = True


class _SequencedLayaDecisionProvider:
    name = "laya"
    model = "laya-multilingual"

    def __init__(self, values):
        self.values = list(values)
        self.requests = []
        self.closed = False

    def decide(self, request):
        self.requests.append(request)
        value = self.values[len(self.requests) - 1]
        return DecisionResult(
            provider=self.name,
            model=self.model,
            answers={
                "auto_pilot_goal_status": DecisionAnswer(
                    value=value,
                    confidence=0.7,
                    calibrated=False,
                )
            },
            latency_ms=2.0,
        )

    def close(self):
        self.closed = True


def test_auto_pilot_decision_state_is_bounded_and_masked() -> None:
    messages = []
    for index in range(8):
        messages.append(
            {
                "role": "assistant" if index % 2 else "user",
                "content": f"message {index} token: secret-{index} " + ("x" * 700),
            }
        )
    for index in range(5):
        messages.append(
            {
                "role": "tool",
                "name": f"tool-{index}",
                "tool_call_id": f"call-{index}",
                "content": (
                    '{"ok": true, "result": {"text": '
                    f'"tool result {index} token: tool-secret-{index}"}}'
                ),
            }
        )
    core = _loop_core()
    core.auto_pilot_goal = "goal token: goal-secret"

    state = _build_auto_pilot_decision_state(messages, core)

    assert set(state) == {"goal", "latest_answer", "evidence"}
    tools = [item for item in state["evidence"] if "tool" in item]
    prior_results = [
        item for item in state["evidence"] if item.get("source") == "assistant"
    ]
    assert len(tools) == 4
    assert len(prior_results) == 3
    assert len(state["latest_answer"]) <= 12000
    assert all(len(item["summary"]) <= 400 for item in tools)
    assert all(len(item["summary"]) <= 2000 for item in prior_results)
    assert all("call_id" not in item for item in state["evidence"])
    serialized = str(state)
    assert "goal-secret" not in serialized
    assert "tool-secret" not in serialized
    assert "secret-" not in serialized
    assert "********" in serialized


@pytest.mark.parametrize("judgment", ["COMPLETE", "CONTINUE"])
def test_auto_pilot_decision_uses_atomic_booleans_and_empty_feedback(judgment) -> None:
    provider = _FakeDecisionProvider(value=judgment)
    core = _loop_core()

    result = _ask_auto_pilot_decision(
        [{"role": "assistant", "content": "work result"}],
        core,
        decision_provider=provider,
    )

    assert result == (judgment, "")
    assert len(provider.requests) == 1
    request = provider.requests[0]
    assert request.metadata["site"] == "auto_pilot_review"
    assert [question.id for question in request.questions] == [
        "goal_satisfied",
        "material_work_remaining",
    ]
    assert all(question.kind.value == "boolean" for question in request.questions)
    assert all(not question.choices for question in request.questions)


def test_laya_auto_pilot_decision_requires_order_consistency(capsys) -> None:
    provider = _SequencedLayaDecisionProvider(["COMPLETE", "COMPLETE"])
    core = _loop_core()

    result = _ask_auto_pilot_decision(
        [{"role": "assistant", "content": "work result"}],
        core,
        decision_provider=provider,
    )

    assert result == ("COMPLETE", "")
    assert len(provider.requests) == 2
    primary = provider.requests[0].questions[0]
    reversed_question = provider.requests[1].questions[0]
    assert primary.choices == ("COMPLETE", "CONTINUE")
    assert reversed_question.choices == ("CONTINUE", "COMPLETE")
    assert list(primary.metadata["criteria"]) == ["COMPLETE", "CONTINUE"]
    assert list(reversed_question.metadata["criteria"]) == ["CONTINUE", "COMPLETE"]
    output = capsys.readouterr().out
    assert "order_consistent=true" in output


def test_laya_auto_pilot_order_inconsistency_requests_legacy_fallback(
    capsys,
) -> None:
    provider = _SequencedLayaDecisionProvider(["CONTINUE", "COMPLETE"])

    result = _ask_auto_pilot_decision(
        [],
        _loop_core(),
        decision_provider=provider,
    )

    assert result is None
    assert len(provider.requests) == 2
    output = capsys.readouterr().out
    assert "order_inconsistent" in output
    assert "primary=CONTINUE" in output
    assert "reversed=COMPLETE" in output
    assert "falling back to LLM reviewer" in output


def test_auto_pilot_decision_failure_requests_legacy_fallback(capsys) -> None:
    provider = _FakeDecisionProvider(
        error=RuntimeError("download failed token: secret-value\nsecond line")
    )

    result = _ask_auto_pilot_decision(
        [],
        _loop_core(),
        decision_provider=provider,
    )

    assert result is None
    output = capsys.readouterr().out
    assert "failed=RuntimeError" in output
    assert "download failed" in output
    assert "second line" in output
    assert "secret-value" not in output
    assert "********" in output


def test_auto_loop_none_uses_legacy_reviewer_without_factory(monkeypatch) -> None:
    core = _loop_core()
    reviewer_calls = []

    monkeypatch.setattr(
        util_cmd_auto,
        "get_decision_settings",
        lambda: DecisionSettings(provider="none", source="default"),
    )

    def fail_factory(*_args, **_kwargs):
        raise AssertionError("decision provider factory must not run for none")

    monkeypatch.setattr(util_cmd_auto, "create_decision_provider", fail_factory)

    def reviewer(*_args, **_kwargs):
        reviewer_calls.append(True)
        return "COMPLETE", ""

    monkeypatch.setattr(util_cmd_auto, "_ask_reviewer_judgment", reviewer)

    util_cmd_auto._run_auto_pilot_loop(
        "openai",
        object(),
        "model",
        [{"role": "assistant", "content": "done"}],
        core,
        lambda _core: ("openai", object(), "model"),
        lambda *_args, **_kwargs: None,
        lambda *_args, **_kwargs: None,
    )

    assert reviewer_calls == [True]
    assert core.auto_pilot_active is False


def test_auto_loop_decision_complete_skips_legacy_reviewer(monkeypatch) -> None:
    core = _loop_core()
    decision_provider = _FakeDecisionProvider(value="COMPLETE")

    monkeypatch.setattr(
        util_cmd_auto,
        "get_decision_settings",
        lambda: DecisionSettings(provider="typesafe", source="env"),
    )
    monkeypatch.setattr(
        util_cmd_auto,
        "create_decision_provider",
        lambda _settings: decision_provider,
    )
    monkeypatch.setattr(
        util_cmd_auto,
        "_decision_provider_supports_questions",
        lambda _provider: True,
    )

    def fail_reviewer(*_args, **_kwargs):
        raise AssertionError("legacy reviewer must not run on valid decision")

    monkeypatch.setattr(util_cmd_auto, "_ask_reviewer_judgment", fail_reviewer)

    util_cmd_auto._run_auto_pilot_loop(
        "openai",
        object(),
        "model",
        [{"role": "assistant", "content": "done"}],
        core,
        lambda _core: ("openai", object(), "model"),
        lambda *_args, **_kwargs: None,
        lambda *_args, **_kwargs: None,
    )

    assert len(decision_provider.requests) == 1
    assert decision_provider.closed is True
    assert core.auto_pilot_active is False


def test_auto_loop_decision_failure_falls_back_to_legacy_reviewer(monkeypatch) -> None:
    core = _loop_core()
    decision_provider = _FakeDecisionProvider(error=RuntimeError("offline"))
    reviewer_calls = []

    monkeypatch.setattr(
        util_cmd_auto,
        "get_decision_settings",
        lambda: DecisionSettings(provider="typesafe", source="env"),
    )
    monkeypatch.setattr(
        util_cmd_auto,
        "create_decision_provider",
        lambda _settings: decision_provider,
    )
    monkeypatch.setattr(
        util_cmd_auto,
        "_decision_provider_supports_questions",
        lambda _provider: True,
    )

    def reviewer(*_args, **_kwargs):
        reviewer_calls.append(True)
        return "COMPLETE", ""

    monkeypatch.setattr(util_cmd_auto, "_ask_reviewer_judgment", reviewer)

    util_cmd_auto._run_auto_pilot_loop(
        "openai",
        object(),
        "model",
        [{"role": "assistant", "content": "done"}],
        core,
        lambda _core: ("openai", object(), "model"),
        lambda *_args, **_kwargs: None,
        lambda *_args, **_kwargs: None,
    )

    assert reviewer_calls == [True]
    assert decision_provider.closed is True


def test_auto_loop_laya_order_inconsistency_falls_back_and_closes(
    monkeypatch,
) -> None:
    core = _loop_core()
    decision_provider = _SequencedLayaDecisionProvider(["CONTINUE", "COMPLETE"])
    reviewer_calls = []

    monkeypatch.setattr(
        util_cmd_auto,
        "get_decision_settings",
        lambda: DecisionSettings(provider="laya", source="env"),
    )
    monkeypatch.setattr(
        util_cmd_auto,
        "create_decision_provider",
        lambda _settings: decision_provider,
    )
    monkeypatch.setattr(
        util_cmd_auto,
        "_decision_provider_supports_questions",
        lambda _provider: True,
    )

    def reviewer(*_args, **_kwargs):
        reviewer_calls.append(True)
        return "COMPLETE", ""

    monkeypatch.setattr(util_cmd_auto, "_ask_reviewer_judgment", reviewer)

    util_cmd_auto._run_auto_pilot_loop(
        "openai",
        object(),
        "model",
        [{"role": "assistant", "content": "done"}],
        core,
        lambda _core: ("openai", object(), "model"),
        lambda *_args, **_kwargs: None,
        lambda *_args, **_kwargs: None,
    )

    assert len(decision_provider.requests) == 2
    assert reviewer_calls == [True]
    assert decision_provider.closed is True
    assert core.auto_pilot_active is False


def test_auto_loop_unsupported_choice_falls_back_without_deciding(monkeypatch) -> None:
    core = _loop_core()
    decision_provider = _FakeDecisionProvider()
    reviewer_calls = []

    monkeypatch.setattr(
        util_cmd_auto,
        "get_decision_settings",
        lambda: DecisionSettings(provider="typesafe", source="env"),
    )
    monkeypatch.setattr(
        util_cmd_auto,
        "create_decision_provider",
        lambda _settings: decision_provider,
    )
    monkeypatch.setattr(
        util_cmd_auto,
        "_decision_provider_supports_questions",
        lambda _provider: False,
    )

    def reviewer(*_args, **_kwargs):
        reviewer_calls.append(True)
        return "COMPLETE", ""

    monkeypatch.setattr(util_cmd_auto, "_ask_reviewer_judgment", reviewer)

    util_cmd_auto._run_auto_pilot_loop(
        "openai",
        object(),
        "model",
        [{"role": "assistant", "content": "done"}],
        core,
        lambda _core: ("openai", object(), "model"),
        lambda *_args, **_kwargs: None,
        lambda *_args, **_kwargs: None,
    )

    assert decision_provider.requests == []
    assert decision_provider.closed is True
    assert reviewer_calls == [True]


def test_auto_loop_sentinel_precedes_decision_provider(monkeypatch) -> None:
    core = _loop_core()
    monkeypatch.setattr(util_cmd_auto, "_sentinel_mode_enabled", lambda: True)

    def fail_settings():
        raise AssertionError("decision settings must not be read in sentinel mode")

    monkeypatch.setattr(util_cmd_auto, "get_decision_settings", fail_settings)

    util_cmd_auto._run_auto_pilot_loop(
        "openai",
        object(),
        "model",
        [{"role": "assistant", "content": "<AUTO_COMPLETE>"}],
        core,
        lambda _core: ("openai", object(), "model"),
        lambda *_args, **_kwargs: None,
        lambda *_args, **_kwargs: None,
    )

    assert core.auto_pilot_active is False


def test_auto_loop_completion_regex_precedes_decision_provider(monkeypatch) -> None:
    core = _loop_core()
    core.auto_pilot_complete_regex = r"DONE$"

    def fail_settings():
        raise AssertionError(
            "decision settings must not be read after regex completion"
        )

    monkeypatch.setattr(util_cmd_auto, "get_decision_settings", fail_settings)

    util_cmd_auto._run_auto_pilot_loop(
        "openai",
        object(),
        "model",
        [{"role": "assistant", "content": "DONE"}],
        core,
        lambda _core: ("openai", object(), "model"),
        lambda *_args, **_kwargs: None,
        lambda *_args, **_kwargs: None,
    )

    assert core.auto_pilot_active is False


def test_auto_loop_disables_failed_decision_provider_for_remaining_rounds(monkeypatch):
    from uagent import uagent_llm

    core = _loop_core(max_rounds=3)
    decision_provider = _FakeDecisionProvider(error=RuntimeError("offline"))
    reviewer_answers = iter([("CONTINUE", ""), ("COMPLETE", "")])
    reviewer_calls = []

    monkeypatch.setattr(
        util_cmd_auto,
        "get_decision_settings",
        lambda: DecisionSettings(provider="typesafe", source="env"),
    )
    monkeypatch.setattr(
        util_cmd_auto,
        "create_decision_provider",
        lambda _settings: decision_provider,
    )
    monkeypatch.setattr(
        util_cmd_auto,
        "_decision_provider_supports_questions",
        lambda _provider: True,
    )

    def reviewer(*_args, **_kwargs):
        reviewer_calls.append(True)
        return next(reviewer_answers)

    monkeypatch.setattr(util_cmd_auto, "_ask_reviewer_judgment", reviewer)
    monkeypatch.setattr(
        uagent_llm,
        "run_llm_rounds",
        lambda *_args, **_kwargs: "",
    )

    util_cmd_auto._run_auto_pilot_loop(
        "openai",
        object(),
        "model",
        [{"role": "assistant", "content": "initial"}],
        core,
        lambda _core: ("openai", object(), "model"),
        lambda *_args, **_kwargs: None,
        lambda *_args, **_kwargs: None,
    )

    assert len(decision_provider.requests) == 1
    assert reviewer_calls == [True, True]
    assert decision_provider.closed is True


@pytest.mark.parametrize("provider_name", ["typesafe", "openrouter"])
def test_weather_answer_completion_ignores_round_budget(provider_name):
    provider = _FakeDecisionProvider()
    provider.name = provider_name
    core = _loop_core()
    core.auto_pilot_goal = "Find today's weather and last year's weather on this date"
    answer = "Today: sunny, 24.5 C. Last year: rain, 25.3/18.7 C, 2.3 mm (estimate)."
    messages = [
        {"role": "user", "content": "irrelevant old conversation"},
        {
            "role": "tool",
            "name": "weather",
            "tool_call_id": "call-123",
            "content": '{"ok": true, "data": "today sunny; last year rain"}',
        },
        {"role": "assistant", "content": answer},
    ]
    assert _ask_auto_pilot_decision(messages, core, decision_provider=provider) == (
        "COMPLETE",
        "",
    )
    state = provider.requests[0].state
    assert state["latest_answer"] == answer
    assert set(state) == {"goal", "latest_answer", "evidence"}
    assert "call-123" not in str(state)
    core.auto_pilot_round = 9
    core.auto_pilot_max_rounds = None
    assert util_cmd_auto._build_auto_pilot_decision_state(messages, core) == state


@pytest.mark.parametrize(
    "satisfied,remaining,expected",
    [
        (True, False, "COMPLETE"),
        (True, True, "CONTINUE"),
        (False, False, "CONTINUE"),
        (False, True, "CONTINUE"),
        ("true", False, None),
        (True, None, None),
    ],
)
def test_atomic_completion_requires_valid_consistent_booleans(
    satisfied, remaining, expected
):
    provider = _FakeDecisionProvider()
    provider.decide = lambda request: DecisionResult(
        provider="typesafe",
        model="jev-latest",
        answers={
            "goal_satisfied": DecisionAnswer(satisfied),
            "material_work_remaining": DecisionAnswer(remaining),
        },
    )
    result = _ask_auto_pilot_decision([], _loop_core(), decision_provider=provider)
    assert result == ((expected, "") if expected else None)


@pytest.mark.parametrize(
    "name,kinds,expected",
    [
        ("typesafe", ["boolean"], True),
        ("openrouter", ["noul"], True),
        ("typesafe", ["choice"], False),
        ("laya", ["choice"], True),
        ("laya", ["boolean"], False),
    ],
)
def test_decision_capability_checks_required_question_kind(
    monkeypatch, name, kinds, expected
):
    import sys

    capability = SimpleNamespace(
        supports=lambda _: True, decision=SimpleNamespace(question_kinds=kinds)
    )
    monkeypatch.setitem(
        sys.modules, "llmcapa", SimpleNamespace(get=lambda *a, **kw: capability)
    )
    provider = SimpleNamespace(name=name, model="test")
    assert util_cmd_auto._decision_provider_supports_questions(provider) is expected


@pytest.mark.parametrize("name", ["typesafe", "openrouter", "laya"])
def test_multi_round_completion_preserves_prior_results(name):
    core = _loop_core()
    core.auto_pilot_goal = "Complete A and B"
    messages = [
        {"role": "assistant", "content": "Unrelated old result"},
        {"role": "user", "content": core.auto_pilot_goal},
        {"role": "assistant", "content": "A is complete"},
        {"role": "user", "content": "Continue. Goal: Complete A and B"},
        {"role": "assistant", "content": "B is complete"},
    ]
    requests = []

    def decide(request):
        requests.append(request)
        state = request.state
        assert state["latest_answer"] == "B is complete"
        assert state["evidence"] == [
            {"source": "assistant", "status": "reported", "summary": "A is complete"}
        ]
        if name == "laya":
            answers = {"auto_pilot_goal_status": DecisionAnswer("COMPLETE")}
        else:
            answers = {
                "goal_satisfied": DecisionAnswer(True),
                "material_work_remaining": DecisionAnswer(False),
            }
        return DecisionResult(provider=name, model="test", answers=answers)

    provider = SimpleNamespace(name=name, model="test", decide=decide)
    assert _ask_auto_pilot_decision(messages, core, decision_provider=provider) == (
        "COMPLETE",
        "",
    )
    assert len(requests) == (2 if name == "laya" else 1)


def test_prior_result_evidence_is_bounded_masked_and_skips_tool_calls():
    core = _loop_core()
    messages = [{"role": "user", "content": core.auto_pilot_goal}]
    for index in range(8):
        messages.append(
            {
                "role": "assistant",
                "content": f"result {index} token: hidden-value " + "x" * 3000,
            }
        )
    messages.extend(
        [
            {
                "role": "assistant",
                "content": "tool planning",
                "tool_calls": [{"id": "call-x"}],
            },
            {"role": "assistant", "content": None},
        ]
    )
    state = _build_auto_pilot_decision_state(messages, core)
    assert state["latest_answer"] == ""
    assert len(state["evidence"]) == 4
    assert all(len(item["summary"]) <= 2000 for item in state["evidence"])
    assert "hidden-value" not in str(state)
    assert "call-x" not in str(state)
    assert "tool planning" not in str(state)
    assert state["evidence"][0]["summary"].startswith("result 4")
    assert state["evidence"][-1]["summary"].startswith("result 7")


def test_sentinel_goal_boundary_excludes_previous_run_evidence():
    core = _loop_core()
    messages = [
        {"role": "assistant", "content": "old run completed"},
        {
            "role": "user",
            "content": core.auto_pilot_goal + util_cmd_auto._SENTINEL_INSTRUCTION,
        },
        {"role": "assistant", "content": "current result"},
    ]
    assert _build_auto_pilot_decision_state(messages, core)["evidence"] == []


def test_auto_loop_max_rounds_does_not_run_extra_followup(monkeypatch) -> None:
    from uagent import uagent_llm

    core = _loop_core(max_rounds=1)
    reviewer_calls = []
    followup_calls = []

    monkeypatch.setattr(
        util_cmd_auto,
        "get_decision_settings",
        lambda: DecisionSettings(provider="none", source="default"),
    )

    def reviewer(*_args, **_kwargs):
        reviewer_calls.append(True)
        return "CONTINUE", "more work remains"

    monkeypatch.setattr(util_cmd_auto, "_ask_reviewer_judgment", reviewer)
    monkeypatch.setattr(
        uagent_llm,
        "run_llm_rounds",
        lambda *_args, **_kwargs: followup_calls.append(True) or "",
    )

    util_cmd_auto._run_auto_pilot_loop(
        "openai",
        object(),
        "model",
        [{"role": "assistant", "content": "initial"}],
        core,
        lambda _core: ("openai", object(), "model"),
        lambda *_args, **_kwargs: None,
        lambda *_args, **_kwargs: None,
    )

    assert reviewer_calls == [True, True]
    assert followup_calls == [True]
    assert core.auto_pilot_round == 2
    assert core._last_round_outcome == {
        "status": "failed",
        "reason": "max_rounds",
    }
    assert core.auto_pilot_active is False
