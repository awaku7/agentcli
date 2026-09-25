from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

from uagent.runtime import legacy_openai_round, legacy_round_registry
from uagent.runtime.observability import runtime as observability_runtime


class _Span:
    def __init__(self) -> None:
        self.attributes = {}
        self.status = []

    def set_attribute(self, key, value) -> None:
        self.attributes[key] = value

    def add_event(self, name, attributes=None) -> None:
        return None

    def record_exception(self, exc) -> None:
        return None

    def set_status(self, status, description=None) -> None:
        self.status.append((status, description))


class _Backend:
    enabled = True

    def __init__(self) -> None:
        self.spans = []

    @contextmanager
    def start_span(self, operation, *, attributes=None, root=False):
        span = _Span()
        self.spans.append(
            {
                "operation": operation,
                "attributes": dict(attributes or {}),
                "root": root,
                "span": span,
            }
        )
        yield span

    def record_event(self, name, attributes=None):
        return None

    def current_trace_ids(self):
        return None


def _install_backend(monkeypatch) -> _Backend:
    backend = _Backend()
    monkeypatch.setattr(
        observability_runtime, "get_observability_backend", lambda: backend
    )
    return backend


def test_registered_legacy_provider_emits_chat_span_and_token_metrics(
    monkeypatch,
) -> None:
    backend = _install_backend(monkeypatch)
    core = SimpleNamespace(
        _last_responses_usage={
            "input_tokens": 10,
            "output_tokens": 2,
            "total_tokens": 12,
        }
    )

    def fake_handler(**kwargs):
        kwargs["core"]._last_responses_usage = {
            "input_tokens": 15,
            "output_tokens": 5,
            "total_tokens": 20,
        }
        return ("break", "client", None, 0, "answer")

    monkeypatch.setitem(
        legacy_round_registry._LEGACY_ROUND_HANDLERS, "claude", fake_handler
    )

    outcome = legacy_round_registry.run_legacy_provider_outcome(
        provider="claude",
        depname="claude-model",
        call_messages=[{"role": "user", "content": "hello"}],
        core=core,
    )

    assert outcome is not None
    assert len(backend.spans) == 1
    record = backend.spans[0]
    assert record["operation"] == "chat"
    assert record["attributes"] == {
        "uag.llm.provider": "claude",
        "uag.llm.model": "claude-model",
    }
    span = record["span"]
    assert span.attributes["uag.tokens.estimate.input"] > 0
    assert span.attributes["uag.tokens.reported.input"] == 5
    assert span.attributes["uag.tokens.reported.output"] == 3
    assert span.attributes["uag.tokens.reported.total"] == 8


def test_unregistered_legacy_probe_does_not_emit_extra_chat_span(monkeypatch) -> None:
    backend = _install_backend(monkeypatch)

    assert legacy_round_registry.run_legacy_provider_outcome(provider="openai") is None
    assert backend.spans == []


def test_openai_compatible_fallback_emits_chat_span(monkeypatch) -> None:
    backend = _install_backend(monkeypatch)
    core = SimpleNamespace(_last_responses_usage={})

    def fake_round(**kwargs):
        kwargs["core"]._last_responses_usage = {
            "input_tokens": 7,
            "output_tokens": 4,
            "total_tokens": 11,
        }
        return True, "client", "answer", "", [], False

    monkeypatch.setattr(
        legacy_openai_round, "call_legacy_openai_compatible_round", fake_round
    )

    outcome = legacy_openai_round.call_legacy_openai_compatible_outcome(
        provider="openai",
        depname="gpt-test",
        call_messages=[{"role": "user", "content": "hello"}],
        core=core,
        stream_responses=False,
    )

    assert outcome.status == "ok"
    assert len(backend.spans) == 1
    record = backend.spans[0]
    assert record["operation"] == "chat"
    assert record["attributes"] == {
        "uag.llm.provider": "openai",
        "uag.llm.model": "gpt-test",
    }
    span = record["span"]
    assert span.attributes["uag.tokens.estimate.input"] > 0
    assert span.attributes["uag.tokens.reported.input"] == 7
    assert span.attributes["uag.tokens.reported.output"] == 4
    assert span.attributes["uag.tokens.reported.total"] == 11
    assert span.status[-1] == ("ok", None)
