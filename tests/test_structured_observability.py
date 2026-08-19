import json
import logging

from uagent.runtime.logging_setup import event_context, log_event


def test_event_context_adds_correlation_fields(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="uagent.events"):
        with event_context(agent_id="a1", task_id="t1", correlation_id="c1"):
            log_event("tool.completed", duration_ms=12, status="ok")

    payload = json.loads(caplog.records[-1].message)
    assert payload["event_code"] == "tool.completed"
    assert payload["agent_id"] == "a1"
    assert payload["task_id"] == "t1"
    assert payload["correlation_id"] == "c1"
    assert payload["duration_ms"] == 12
    assert payload["status"] == "ok"
    assert payload["event_id"]
    assert payload["timestamp"]


def test_standalone_event_gets_common_schema_fields(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="uagent.events"):
        log_event("standalone")

    payload = json.loads(caplog.records[-1].message)
    assert payload["schema_version"] == "1"
    assert payload["event_id"]
    assert payload["correlation_id"]
    assert payload["timestamp"]
    assert payload["event_code"] == "standalone"
    assert payload["status"] == "event"
    assert payload["agent_id"] is None
    assert payload["session_id"] is None
    assert payload["task_id"] is None
    assert payload["tool_call_id"] is None
    assert payload["provider"] is None
    assert payload["duration_ms"] is None
    assert payload["error_type"] is None


def test_event_context_does_not_leak(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="uagent.events"):
        with event_context(session_id="s1"):
            log_event("inside")
        log_event("outside")

    inside, outside = (json.loads(record.message) for record in caplog.records[-2:])
    assert inside["session_id"] == "s1"
    assert outside["session_id"] is None


def test_llm_observer_emits_completion_event(caplog) -> None:
    import logging
    from uagent.uagent_llm import _observed_llm_rounds

    @_observed_llm_rounds
    def fake(provider, client, depname, messages, **kwargs):
        return "ok"

    with caplog.at_level(logging.INFO, logger="uagent.events"):
        assert fake("demo", object(), "model", []) == "ok"

    events = [json.loads(record.message) for record in caplog.records]
    assert [event["event_code"] for event in events] == ["llm.started", "llm.completed"]
    assert events[-1]["provider"] == "demo"
    assert "duration_ms" in events[-1]


def test_tool_runner_emits_call_id_and_duration(caplog) -> None:
    import logging
    from uagent.tools import _call_tool_runner

    with caplog.at_level(logging.INFO, logger="uagent.events"):
        assert (
            _call_tool_runner("demo", lambda _args: "ok", {}, tool_call_id="call-1")
            == "ok"
        )

    event = json.loads(caplog.records[-1].message)
    assert event["event_code"] == "tool.completed"
    assert event["tool_call_id"] == "call-1"
    assert "duration_ms" in event
