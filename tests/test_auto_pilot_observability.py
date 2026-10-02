from __future__ import annotations

import threading
from types import SimpleNamespace

from uagent import util_cmd_auto
from uagent.decision import DecisionAnswer, DecisionResult
from uagent.runtime.observability import auto_pilot as auto_observability


class _Backend:
    enabled = True

    def __init__(self):
        self.events = []
        self.counters = []
        self.histograms = []

    def record_event(self, name, attributes=None):
        self.events.append((name, dict(attributes or {})))

    def record_counter(self, name, value=1, attributes=None):
        self.counters.append((name, value, dict(attributes or {})))

    def record_histogram(self, name, value, attributes=None):
        self.histograms.append((name, value, dict(attributes or {})))


class _DecisionProvider:
    name = "typesafe"
    model = "jev-latest"

    def __init__(self, value="COMPLETE", error=None):
        self.value = value
        self.error = error

    def decide(self, _request):
        if self.error is not None:
            raise self.error
        return DecisionResult(
            provider=self.name,
            model=self.model,
            answers={
                "auto_pilot_goal_status": DecisionAnswer(
                    value=self.value,
                    confidence=0.82,
                    calibrated=True,
                )
            },
            latency_ms=3.5,
        )


def _loop_core(*, max_rounds=10):
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


def test_auto_observability_records_metadata_only_judgment(monkeypatch):
    backend = _Backend()
    monkeypatch.setattr(
        auto_observability,
        "get_observability_backend",
        lambda: backend,
    )

    auto_observability.record_auto_pilot_judgment(
        source="decision_provider",
        round_number=2,
        answer="COMPLETE",
        provider="typesafe",
        model="jev-latest",
        confidence=0.82,
        latency_ms=3.5,
        additional_call=True,
    )

    name, attributes = backend.events[-1]
    assert name == "uag.auto.judgment"
    assert attributes["uag.decision.site"] == "auto_pilot_review"
    assert attributes["uag.auto.judgment.source"] == "decision_provider"
    assert attributes["uag.auto.judgment.answer"] == "COMPLETE"
    assert attributes["uag.auto.judgment.round"] == 2
    assert attributes["uag.auto.judgment.provider"] == "typesafe"
    assert attributes["uag.auto.judgment.model"] == "jev-latest"
    assert attributes["uag.auto.judgment.confidence"] == 0.82
    assert attributes["uag.auto.judgment.additional_call"] is True
    serialized = repr(attributes).lower()
    assert "goal" not in serialized
    assert "prompt" not in serialized
    assert "response" not in serialized

    counter_names = [item[0] for item in backend.counters]
    assert "uag.auto.judgment.attempts" in counter_names
    assert "uag.auto.judgments" in counter_names
    assert "uag.auto.judgment.failures" not in counter_names
    assert backend.histograms[-1][0] == "uag.auto.judgment.latency_ms"


def test_auto_observability_distinguishes_failed_attempt(monkeypatch):
    backend = _Backend()
    monkeypatch.setattr(
        auto_observability,
        "get_observability_backend",
        lambda: backend,
    )

    auto_observability.record_auto_pilot_judgment(
        source="decision_provider",
        round_number=0,
        provider="laya",
        error_type="RuntimeError",
        latency_ms=12.0,
    )

    attributes = backend.events[-1][1]
    assert attributes["uag.auto.judgment.status"] == "error"
    assert attributes["uag.auto.judgment.error_type"] == "RuntimeError"
    counter_names = [item[0] for item in backend.counters]
    assert "uag.auto.judgment.attempts" in counter_names
    assert "uag.auto.judgment.failures" in counter_names
    assert "uag.auto.judgments" not in counter_names


def test_auto_observability_records_run_outcome(monkeypatch):
    backend = _Backend()
    monkeypatch.setattr(
        auto_observability,
        "get_observability_backend",
        lambda: backend,
    )

    auto_observability.record_auto_pilot_run_finished(
        reason="max_rounds",
        rounds=10,
        judgment_source="sentinel",
        max_rounds_reached=True,
    )

    name, attributes = backend.events[-1]
    assert name == "uag.auto.run.finished"
    assert attributes["uag.auto.run.reason"] == "max_rounds"
    assert attributes["uag.auto.run.followup_rounds"] == 10
    assert attributes["uag.auto.run.judgment_source"] == "sentinel"
    assert attributes["uag.auto.run.max_rounds_reached"] is True
    assert backend.histograms[-1][0] == "uag.auto.followup_rounds"


def test_llm_reviewer_records_source_and_fallback(monkeypatch):
    from uagent import uagent_llm

    recorded = []
    monkeypatch.setattr(
        uagent_llm,
        "run_llm_rounds",
        lambda **_kwargs: "COMPLETE",
    )
    monkeypatch.setattr(
        util_cmd_auto,
        "record_auto_pilot_judgment",
        lambda **kwargs: recorded.append(kwargs),
    )
    core = SimpleNamespace(
        auto_pilot_goal="finish",
        auto_pilot_round=3,
        set_status=lambda *_args, **_kwargs: None,
    )

    result = util_cmd_auto._ask_reviewer_judgment(
        "openai",
        object(),
        "gpt-test",
        [],
        core,
        make_client_fn=lambda _core: ("openai", object(), "gpt-test"),
        fallback=True,
    )

    assert result == ("COMPLETE", "")
    assert recorded[-1]["source"] == "llm_reviewer"
    assert recorded[-1]["answer"] == "COMPLETE"
    assert recorded[-1]["fallback"] is True
    assert recorded[-1]["provider"] == "openai"
    assert recorded[-1]["model"] == "gpt-test"
    assert recorded[-1]["additional_call"] is True


def test_decision_provider_records_success_and_failure(monkeypatch):
    recorded = []
    monkeypatch.setattr(
        util_cmd_auto,
        "record_auto_pilot_judgment",
        lambda **kwargs: recorded.append(kwargs),
    )
    core = _loop_core()

    result = util_cmd_auto._ask_auto_pilot_decision(
        [],
        core,
        decision_provider=_DecisionProvider(value="CONTINUE"),
    )

    assert result == ("CONTINUE", "")
    assert recorded[-1]["source"] == "decision_provider"
    assert recorded[-1]["answer"] == "CONTINUE"
    assert recorded[-1]["provider"] == "typesafe"
    assert recorded[-1]["confidence"] == 0.82

    result = util_cmd_auto._ask_auto_pilot_decision(
        [],
        core,
        decision_provider=_DecisionProvider(error=RuntimeError("offline")),
    )

    assert result is None
    assert recorded[-1]["source"] == "decision_provider"
    assert recorded[-1]["error_type"] == "RuntimeError"


def test_laya_order_guard_records_both_decision_attempts(monkeypatch):
    recorded = []

    class LayaProvider(_DecisionProvider):
        name = "laya"
        model = "laya-multilingual"

        def __init__(self):
            super().__init__(value="COMPLETE")
            self.calls = []

        def decide(self, request):
            self.calls.append(request.questions[0].choices)
            return super().decide(request)

    provider = LayaProvider()
    monkeypatch.setattr(
        util_cmd_auto,
        "record_auto_pilot_judgment",
        lambda **kwargs: recorded.append(kwargs),
    )

    result = util_cmd_auto._ask_auto_pilot_decision(
        [],
        _loop_core(),
        decision_provider=provider,
    )

    assert result == ("COMPLETE", "")
    assert provider.calls == [
        ("COMPLETE", "CONTINUE"),
        ("CONTINUE", "COMPLETE"),
    ]
    assert len(recorded) == 2
    assert [item["answer"] for item in recorded] == ["COMPLETE", "COMPLETE"]
    assert all(item["provider"] == "laya" for item in recorded)
    assert all(item["additional_call"] is True for item in recorded)


def test_sentinel_records_no_additional_judgment_call(monkeypatch):
    judgments = []
    outcomes = []
    core = _loop_core()

    monkeypatch.setattr(util_cmd_auto, "_sentinel_mode_enabled", lambda: True)
    monkeypatch.setattr(
        util_cmd_auto,
        "record_auto_pilot_judgment",
        lambda **kwargs: judgments.append(kwargs),
    )
    monkeypatch.setattr(
        util_cmd_auto,
        "record_auto_pilot_run_finished",
        lambda **kwargs: outcomes.append(kwargs),
    )

    def fail_settings():
        raise AssertionError("decision settings must not be read in sentinel mode")

    monkeypatch.setattr(util_cmd_auto, "get_decision_settings", fail_settings)

    util_cmd_auto._run_auto_pilot_loop(
        "openai",
        object(),
        "main-model",
        [{"role": "assistant", "content": "<AUTO_COMPLETE>"}],
        core,
        lambda _core: ("openai", object(), "main-model"),
        lambda *_args, **_kwargs: None,
        lambda *_args, **_kwargs: None,
    )

    assert judgments[-1]["source"] == "sentinel"
    assert judgments[-1]["answer"] == "COMPLETE"
    assert judgments[-1]["additional_call"] is False
    assert outcomes[-1]["reason"] == "complete"
    assert outcomes[-1]["judgment_source"] == "sentinel"
