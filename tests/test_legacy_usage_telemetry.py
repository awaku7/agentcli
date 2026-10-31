from __future__ import annotations

from types import SimpleNamespace

from uagent.llm_round_helpers import _record_legacy_usage_telemetry


def test_legacy_usage_telemetry_uses_per_request_responses_usage(monkeypatch) -> None:
    events: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        "uagent.llm_round_helpers.log_event",
        lambda event_code, **fields: events.append((event_code, fields)),
    )
    core = SimpleNamespace(
        _last_responses_usage={
            "input_tokens": 15,
            "output_tokens": 5,
            "total_tokens": 20,
        }
    )

    _record_legacy_usage_telemetry(
        core=core,
        provider="openai",
        model="gpt-test",
        before={"input_tokens": 10, "output_tokens": 2},
    )

    assert events == [
        (
            "llm.usage.reconciled",
            {
                "provider": "openai",
                "model": "gpt-test",
                "usage_source": "legacy_core",
                "input_tokens_delta": 15,
                "output_tokens_delta": 5,
                "total_tokens_delta": 20,
            },
        )
    ]


def test_legacy_usage_reports_identical_new_snapshot_but_not_stale_reference(
    monkeypatch,
) -> None:
    events = []
    monkeypatch.setattr(
        "uagent.llm_round_helpers.log_event",
        lambda event_code, **fields: events.append((event_code, fields)),
    )
    before = {"input_tokens": 11, "output_tokens": 3}
    core = SimpleNamespace(_last_responses_usage=before)

    _record_legacy_usage_telemetry(
        core=core, provider="openai", model="test", before=before
    )
    assert events == []

    core._last_responses_usage = dict(before)
    _record_legacy_usage_telemetry(
        core=core, provider="openai", model="test", before=before
    )
    assert len(events) == 1
    assert events[0][1]["input_tokens_delta"] == 11
    assert events[0][1]["output_tokens_delta"] == 3
