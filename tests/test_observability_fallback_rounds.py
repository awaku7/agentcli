from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

from uagent.runtime import (
    legacy_openai_round,
    legacy_provider_dispatch,
    legacy_round_registry,
)
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
        self.active = []

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
        self.active.append(span)
        try:
            yield span
        finally:
            self.active.pop()

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

    def fake_provider_call(**kwargs):
        kwargs["core"]._last_responses_usage = {
            "input_tokens": 15,
            "output_tokens": 5,
            "total_tokens": 20,
        }
        return True, "client", "answer", []

    monkeypatch.setattr(
        legacy_provider_dispatch,
        "_call_claude_round",
        fake_provider_call,
    )

    result = legacy_provider_dispatch.call_legacy_claude_round(
        depname="claude-model",
        call_messages=[{"role": "user", "content": "hello"}],
        core=core,
    )

    assert result == (True, "client", "answer", [])
    assert backend.active == []
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
    assert span.status[-1] == ("ok", None)


def test_registered_legacy_handler_postprocess_runs_after_chat_span(
    monkeypatch,
) -> None:
    backend = _install_backend(monkeypatch)
    core = SimpleNamespace(_last_responses_usage={})
    active_during_postprocess: list[bool] = []

    monkeypatch.setattr(
        legacy_provider_dispatch,
        "_call_claude_round",
        lambda **_kwargs: (True, "client", "answer", []),
    )

    def fake_handler(**kwargs):
        ok, client, assistant_text, _tool_calls = (
            legacy_provider_dispatch.call_legacy_claude_round(
                depname=kwargs["depname"],
                call_messages=kwargs["call_messages"],
                core=kwargs["core"],
            )
        )
        assert ok is True
        active_during_postprocess.append(bool(backend.active))
        return ("ok", client, None, 0, assistant_text)

    monkeypatch.setitem(
        legacy_round_registry._LEGACY_ROUND_HANDLERS,
        "claude",
        fake_handler,
    )

    outcome = legacy_round_registry.run_legacy_provider_outcome(
        provider="claude",
        depname="claude-model",
        call_messages=[{"role": "user", "content": "hello"}],
        core=core,
    )

    assert outcome is not None
    assert outcome.summary is not None
    assert outcome.summary.status == "completed"
    assert active_during_postprocess == [False]
    assert [record["operation"] for record in backend.spans] == ["chat"]


def test_unregistered_legacy_probe_does_not_emit_extra_chat_span(monkeypatch) -> None:
    backend = _install_backend(monkeypatch)

    assert legacy_round_registry.run_legacy_provider_outcome(provider="openai") is None
    assert backend.spans == []


def test_openai_compatible_fallback_emits_chat_span(monkeypatch) -> None:
    backend = _install_backend(monkeypatch)
    core = SimpleNamespace(_last_responses_usage={})

    def fake_provider_call(**kwargs):
        kwargs["core"]._last_responses_usage = {
            "input_tokens": 7,
            "output_tokens": 4,
            "total_tokens": 11,
        }
        return True, "client", "answer", "", []

    monkeypatch.setattr(
        legacy_provider_dispatch,
        "_call_openai_azure_round",
        fake_provider_call,
    )

    outcome = legacy_openai_round.call_legacy_openai_compatible_outcome(
        provider="openai",
        client=object(),
        depname="gpt-test",
        call_messages=[{"role": "user", "content": "hello"}],
        core=core,
        make_client_fn=object(),
        call_maybe_thread_fn=object(),
        use_responses_api=False,
        stream_responses=False,
        send_tools_this_round=False,
        max_retries_429=0,
        retry_base=0.0,
        retry_cap=0.0,
        messages=[],
        responses_state={},
        round_count=1,
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


def test_inception_inner_orchestrator_owns_single_chat_span_when_registry_off(
    monkeypatch,
) -> None:
    backend = _install_backend(monkeypatch)
    core = SimpleNamespace(_last_responses_usage={})
    monkeypatch.setenv("UAGENT_PROVIDER_REGISTRY", "off")
    monkeypatch.setenv("UAGENT_ROUND_ORCHESTRATOR", "1")
    monkeypatch.setenv("UAGENT_PROVIDER_REGISTRY_INCEPTION", "1")

    def fake_inner_orchestrator_call(**_kwargs):
        with backend.start_span("chat", attributes={"owner": "inner"}) as span:
            span.set_status("ok")
        return True, "client", "answer", "", []

    monkeypatch.setattr(
        legacy_provider_dispatch,
        "_call_openai_azure_round",
        fake_inner_orchestrator_call,
    )

    outcome = legacy_openai_round.call_legacy_openai_compatible_outcome(
        provider="inception",
        client=object(),
        depname="mercury-test",
        call_messages=[{"role": "user", "content": "hello"}],
        core=core,
        make_client_fn=object(),
        call_maybe_thread_fn=object(),
        use_responses_api=False,
        stream_responses=True,
        send_tools_this_round=False,
        max_retries_429=0,
        retry_base=0.0,
        retry_cap=0.0,
        messages=[],
        responses_state={},
        round_count=1,
    )

    assert outcome.status == "ok"
    assert len(backend.spans) == 1
    assert backend.spans[0]["operation"] == "chat"
    assert backend.spans[0]["attributes"] == {"owner": "inner"}
