from __future__ import annotations

from types import SimpleNamespace

from uagent.llm_round_helpers import _record_legacy_usage_telemetry


def test_legacy_usage_telemetry_reconciles_responses_usage(monkeypatch) -> None:
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
                "input_tokens_delta": 5,
                "output_tokens_delta": 3,
                "total_tokens_delta": 20,
            },
        )
    ]
