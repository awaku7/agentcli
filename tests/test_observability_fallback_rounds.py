from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

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
    assert span.attributes["uag.tokens.estimate.output"] > 0
    assert span.attributes["uag.tokens.reported.input"] == 15
    assert span.attributes["uag.tokens.reported.output"] == 5
    assert span.attributes["uag.tokens.reported.total"] == 20
    assert span.status[-1] == ("ok", None)


def test_fallback_usage_uses_current_response_even_when_smaller(monkeypatch) -> None:
    backend = _install_backend(monkeypatch)
    core = SimpleNamespace(
        _last_responses_usage={
            "input_tokens": 100,
            "output_tokens": 40,
            "total_tokens": 140,
        }
    )

    with observability_runtime.fallback_chat_span(
        provider="openai",
        model="gpt-test",
        request_input=[{"role": "user", "content": "hello"}],
        core=core,
    ):
        core._last_responses_usage = {
            "input_tokens": 7,
            "output_tokens": 4,
            "total_tokens": 11,
        }

    span = backend.spans[0]["span"]
    assert span.attributes["uag.tokens.reported.input"] == 7
    assert span.attributes["uag.tokens.reported.output"] == 4
    assert span.attributes["uag.tokens.reported.total"] == 11


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


def test_inception_direct_fallback_gets_its_own_chat_span(monkeypatch) -> None:
    backend = _install_backend(monkeypatch)
    core = SimpleNamespace(_last_responses_usage={})
    monkeypatch.setenv("UAGENT_PROVIDER_REGISTRY_INCEPTION", "1")

    def call_direct(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    def fake_provider_call(**kwargs):
        with backend.start_span("chat", attributes={"owner": "inner"}) as span:
            span.set_status("error", "orchestrator failed")
        fallback_result = kwargs["call_maybe_thread_fn"](lambda: "fallback-ok")
        assert fallback_result == "fallback-ok"
        return True, "client", "answer", "", []

    monkeypatch.setattr(
        legacy_provider_dispatch,
        "_call_openai_azure_round",
        fake_provider_call,
    )

    outcome = legacy_openai_round.call_legacy_openai_compatible_outcome(
        provider="inception",
        client=object(),
        depname="mercury-test",
        call_messages=[{"role": "user", "content": "hello"}],
        core=core,
        make_client_fn=object(),
        call_maybe_thread_fn=call_direct,
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
    assert len(backend.spans) == 2
    assert backend.spans[0]["attributes"] == {"owner": "inner"}
    assert backend.spans[1]["operation"] == "chat"
    assert backend.spans[1]["attributes"] == {
        "uag.llm.provider": "inception",
        "uag.llm.model": "mercury-test",
    }
    assert backend.spans[1]["span"].status[-1] == ("ok", None)


def test_fallback_span_keeps_provider_cache_subset_separate(monkeypatch) -> None:
    backend = _install_backend(monkeypatch)
    core = SimpleNamespace(_last_responses_usage={})
    with observability_runtime.fallback_chat_span(
        provider="openai",
        model="gpt-test",
        request_input=[{"role": "user", "content": "SECRET"}],
        core=core,
    ):
        core._last_responses_usage = {
            "input_tokens": 100,
            "output_tokens": 5,
            "input_tokens_details": {"cached_tokens": 75},
        }
    attrs = backend.spans[0]["span"].attributes
    assert attrs["uag.tokens.reported.input"] == 100
    assert attrs["gen_ai.usage.cache_read.input_tokens"] == 75
    assert attrs["uag.tokens.context.messages"] > 0
    assert "SECRET" not in str(attrs)


def test_legacy_observer_estimates_selected_tool_definitions(monkeypatch) -> None:
    backend = _install_backend(monkeypatch)
    core = SimpleNamespace(
        _last_responses_usage={},
        context_tool_specs=[{"type": "function", "name": "read_file"}],
    )

    monkeypatch.setattr(
        legacy_provider_dispatch,
        "_call_claude_round",
        lambda **kwargs: (True, "client", "answer", []),
    )
    result = legacy_provider_dispatch.call_legacy_claude_round(
        depname="claude-model",
        call_messages=[{"role": "user", "content": "SECRET_USER_TEXT"}],
        core=core,
        send_tools=True,
    )
    assert result[0] is True
    attrs = backend.spans[0]["span"].attributes
    assert attrs["uag.tokens.context.tools"] > 0
    assert attrs["uag.tokens.context.messages"] > 0
    assert "read_file" not in str(attrs)
    assert "SECRET_USER_TEXT" not in str(attrs)


def test_claude_fallback_span_exports_standard_cache_read_and_write(
    monkeypatch,
) -> None:
    from uagent.runtime.telemetry import anthropic_usage_to_dict

    backend = _install_backend(monkeypatch)
    previous = {"input_tokens": 9999}
    core = SimpleNamespace(_last_responses_usage=previous)
    with observability_runtime.fallback_chat_span(
        provider="claude",
        model="claude-test",
        request_input=[{"role": "user", "content": "PRIVATE_TEXT"}],
        core=core,
    ):
        core._last_responses_usage = anthropic_usage_to_dict(
            {
                "input_tokens": 5,
                "output_tokens": 3,
                "cache_read_input_tokens": 60,
                "cache_creation_input_tokens": 35,
            }
        )

    attrs = backend.spans[0]["span"].attributes
    assert attrs["uag.tokens.reported.input"] == 100
    assert attrs["uag.tokens.reported.output"] == 3
    assert attrs["gen_ai.usage.cache_read.input_tokens"] == 60
    assert attrs["gen_ai.usage.cache_write.input_tokens"] == 35
    assert "PRIVATE_TEXT" not in str(attrs)


def test_gemini_vertex_otel_exports_prompt_cache_and_reasoning(monkeypatch) -> None:
    from uagent.runtime.telemetry import gemini_usage_to_dict

    backend = _install_backend(monkeypatch)
    for provider in ("gemini", "vertexai"):
        previous = {"input_tokens": 9999}
        core = SimpleNamespace(_last_responses_usage=previous)
        with observability_runtime.fallback_chat_span(
            provider=provider,
            model="gemini-test",
            request_input=[{"role": "user", "content": "PRIVATE_TEXT"}],
            core=core,
        ):
            core._last_responses_usage = gemini_usage_to_dict(
                {
                    "prompt_token_count": 100,
                    "cached_content_token_count": 40,
                    "candidates_token_count": 8,
                    "thoughts_token_count": 12,
                    "tool_use_prompt_token_count": 5,
                }
            )

    for event in backend.spans:
        attrs = event["span"].attributes
        assert attrs["uag.tokens.reported.input"] == 105
        assert attrs["uag.tokens.reported.output"] == 20
        assert attrs["gen_ai.usage.cache_read.input_tokens"] == 40
        assert attrs["gen_ai.usage.reasoning.output_tokens"] == 12
        assert "gen_ai.usage.cache_write.input_tokens" not in attrs
        assert "PRIVATE_TEXT" not in str(attrs)


def test_zai_fallback_otel_exports_measured_cache_and_reasoning(monkeypatch) -> None:
    from uagent.runtime.telemetry import zai_chat_usage_to_dict

    backend = _install_backend(monkeypatch)
    previous = {"input_tokens": 9999}
    core = SimpleNamespace(_last_responses_usage=previous)
    with observability_runtime.fallback_chat_span(
        provider="zai",
        model="glm-test",
        request_input=[{"role": "user", "content": "PRIVATE_TEXT"}],
        core=core,
    ):
        core._last_responses_usage = zai_chat_usage_to_dict(
            {
                "prompt_tokens": 100,
                "completion_tokens": 25,
                "prompt_tokens_details": {"cached_tokens": 40},
                "completion_tokens_details": {"reasoning_tokens": 10},
            }
        )

    attrs = backend.spans[0]["span"].attributes
    assert attrs["uag.tokens.reported.input"] == 100
    assert attrs["uag.tokens.reported.output"] == 25
    assert attrs["uag.tokens.reported.total"] == 125
    assert attrs["gen_ai.usage.cache_read.input_tokens"] == 40
    assert attrs["gen_ai.usage.reasoning.output_tokens"] == 10
    assert "PRIVATE_TEXT" not in str(attrs)


def test_together_fallback_otel_exports_measured_cache_and_reasoning(
    monkeypatch,
) -> None:
    from uagent.runtime.telemetry import together_chat_usage_to_dict

    backend = _install_backend(monkeypatch)
    previous = {"input_tokens": 9999}
    core = SimpleNamespace(_last_responses_usage=previous)
    with observability_runtime.fallback_chat_span(
        provider="together",
        model="together-test",
        request_input=[{"role": "user", "content": "PRIVATE_TEXT"}],
        core=core,
    ):
        core._last_responses_usage = together_chat_usage_to_dict(
            {
                "prompt_tokens": 80,
                "completion_tokens": 20,
                "cached_tokens": 30,
                "completion_tokens_details": {"reasoning_tokens": 8},
            }
        )

    attrs = backend.spans[0]["span"].attributes
    assert attrs["uag.tokens.reported.input"] == 80
    assert attrs["uag.tokens.reported.output"] == 20
    assert attrs["uag.tokens.reported.total"] == 100
    assert attrs["gen_ai.usage.cache_read.input_tokens"] == 30
    assert attrs["gen_ai.usage.reasoning.output_tokens"] == 8
    assert "gen_ai.usage.cache_write.input_tokens" not in attrs
    assert "PRIVATE_TEXT" not in str(attrs)


def test_vllm_legacy_fallback_otel_exports_measured_cache_and_reasoning(
    monkeypatch,
) -> None:
    from uagent.providers.llm_vllm_usage import publish_vllm_legacy_usage

    backend = _install_backend(monkeypatch)
    old = {"input_tokens": 9999}
    core = SimpleNamespace(_last_responses_usage=old)
    with observability_runtime.fallback_chat_span(
        provider="vllm",
        model="served-model",
        request_input=[{"role": "user", "content": "PRIVATE_TEXT"}],
        core=core,
    ):
        publish_vllm_legacy_usage(
            core,
            {
                "prompt_tokens": 80,
                "completion_tokens": 20,
                "prompt_tokens_details": {
                    "cached_tokens": 30,
                    "created_cache_tokens": 10,
                },
                "completion_tokens_details": {"reasoning_tokens": 8},
            },
            responses=False,
        )

    attrs = backend.spans[0]["span"].attributes
    assert attrs["uag.tokens.reported.input"] == 80
    assert attrs["uag.tokens.reported.output"] == 20
    assert attrs["gen_ai.usage.cache_read.input_tokens"] == 30
    assert attrs["gen_ai.usage.cache_write.input_tokens"] == 10
    assert attrs["gen_ai.usage.reasoning.output_tokens"] == 8
    assert "PRIVATE_TEXT" not in str(attrs)


def test_novita_fallback_otel_exports_measured_token_subsets(monkeypatch) -> None:
    from uagent.providers.llm_novita_usage import novita_chat_usage_to_dict

    backend = _install_backend(monkeypatch)
    previous = {"input_tokens": 9999}
    core = SimpleNamespace(_last_responses_usage=previous)
    with observability_runtime.fallback_chat_span(
        provider="novita",
        model="novita-model",
        request_input=[{"role": "user", "content": "PRIVATE_TEXT"}],
        core=core,
    ):
        core._last_responses_usage = novita_chat_usage_to_dict(
            {
                "prompt_tokens": 80,
                "completion_tokens": 20,
                "prompt_tokens_details": {
                    "cached_tokens": 30,
                    "cache_write_tokens": 10,
                },
                "completion_tokens_details": {"reasoning_tokens": 8},
            }
        )

    attrs = backend.spans[0]["span"].attributes
    assert attrs["uag.tokens.reported.input"] == 80
    assert attrs["uag.tokens.reported.output"] == 20
    assert attrs["uag.tokens.reported.total"] == 100
    assert attrs["gen_ai.usage.cache_read.input_tokens"] == 30
    assert attrs["gen_ai.usage.cache_write.input_tokens"] == 10
    assert attrs["gen_ai.usage.reasoning.output_tokens"] == 8
    assert "PRIVATE_TEXT" not in str(attrs)


@pytest.mark.parametrize("streaming", [True, False])
def test_vercel_legacy_round_publishes_measured_tokens_to_chat_span(
    monkeypatch, streaming: bool
) -> None:
    backend = _install_backend(monkeypatch)
    monkeypatch.setenv("UAGENT_STREAMING", "1" if streaming else "0")
    previous = {"input_tokens": 900, "output_tokens": 300, "total_tokens": 1200}
    core = SimpleNamespace(_is_web=True, _last_responses_usage=previous)

    class Completions:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            if kwargs.get("stream"):
                return iter(
                    [
                        SimpleNamespace(
                            choices=[
                                SimpleNamespace(
                                    delta=SimpleNamespace(
                                        content="answer", tool_calls=[]
                                    )
                                )
                            ],
                            usage=None,
                        ),
                        SimpleNamespace(
                            choices=[],
                            usage=SimpleNamespace(
                                prompt_tokens=80,
                                completion_tokens=20,
                                total_tokens=100,
                            ),
                        ),
                    ]
                )
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="answer", tool_calls=[])
                    )
                ],
                usage=SimpleNamespace(
                    prompt_tokens=80, completion_tokens=20, total_tokens=100
                ),
            )

    completions = Completions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    result = legacy_provider_dispatch.call_legacy_reasoning_round(
        provider="vercel",
        client=client,
        depname="test-model",
        call_messages=[{"role": "user", "content": "hello"}],
        core=core,
        make_client_fn=lambda _: ("vercel", client),
        call_maybe_thread_fn=lambda action: action(),
        send_tools_this_round=False,
        max_retries_429=1,
        retry_base=0.1,
        retry_cap=1.0,
    )

    assert result[0] is True
    assert core._last_responses_usage == {
        "input_tokens": 80,
        "output_tokens": 20,
        "total_tokens": 100,
    }
    assert core._last_responses_usage is not previous
    if streaming:
        assert completions.calls[0]["stream_options"]["include_usage"] is True
    else:
        assert "stream_options" not in completions.calls[0]
    span = next(
        record["span"] for record in backend.spans if record["operation"] == "chat"
    )
    assert span.attributes["uag.tokens.reported.input"] == 80
    assert span.attributes["uag.tokens.reported.output"] == 20
    assert span.attributes["uag.tokens.reported.total"] == 100


@pytest.mark.parametrize(
    "provider",
    [
        "openai",
        "azure",
        "nvidia",
        "openrouter",
        "perplexity",
        "alibaba",
        "moonshot",
        "bedrock",
        "ollama",
        "lmstudio",
        "meta",
        "sakana",
        "inception",
        "hf",
        "minimax",
        "sakura",
        "sarashina",
        "foundry_local",
        "llama_cpp",
    ],
)
@pytest.mark.parametrize("has_usage", [True, False])
def test_remaining_openai_compatible_legacy_chat_reports_only_measured_usage(
    monkeypatch, provider: str, has_usage: bool
) -> None:
    backend = _install_backend(monkeypatch)
    monkeypatch.setenv("UAGENT_REASONING", "off")
    previous = {"input_tokens": 999, "output_tokens": 888}
    core = SimpleNamespace(
        _is_web=True,
        responses_state={},
        _last_responses_usage=previous,
    )
    usage = (
        SimpleNamespace(prompt_tokens=50, completion_tokens=13, total_tokens=63)
        if has_usage
        else SimpleNamespace(
            prompt_tokens=True, completion_tokens=-1, total_tokens="invalid"
        )
    )
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="answer", tool_calls=[], reasoning_content=None
                )
            )
        ],
        usage=usage,
    )
    calls: list[dict] = []

    def create(**kwargs):
        calls.append(kwargs)
        return response

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    result = legacy_provider_dispatch.call_legacy_openai_azure_round(
        provider=provider,
        client=client,
        depname="test-model",
        call_messages=[{"role": "user", "content": "hello"}],
        core=core,
        make_client_fn=lambda _: (provider, client),
        call_maybe_thread_fn=lambda call: call(),
        use_responses_api=False,
        stream_responses=False,
        send_tools_this_round=False,
        max_retries_429=0,
        retry_base=0.1,
        retry_cap=1.0,
        messages=[{"role": "user", "content": "hello"}],
        responses_state={},
    )
    assert result[0] is True
    assert "stream_options" not in calls[0]
    span = next(
        record["span"] for record in backend.spans if record["operation"] == "chat"
    )
    if has_usage:
        assert core._last_responses_usage == {
            "input_tokens": 50,
            "output_tokens": 13,
            "total_tokens": 63,
        }
        assert core._last_responses_usage is not previous
        assert span.attributes["uag.tokens.reported.input"] == 50
        assert span.attributes["uag.tokens.reported.output"] == 13
        assert span.attributes["uag.tokens.reported.total"] == 63
    else:
        assert core._last_responses_usage is previous
        assert not any(
            key.startswith("uag.tokens.reported.") for key in span.attributes
        )


@pytest.mark.parametrize("provider", ["openrouter", "moonshot"])
def test_common_legacy_chat_preserves_provider_measured_usage_subsets(
    monkeypatch, provider: str
) -> None:
    backend = _install_backend(monkeypatch)
    monkeypatch.setenv("UAGENT_REASONING", "off")
    usage = SimpleNamespace(
        prompt_tokens=100,
        completion_tokens=40,
        total_tokens=999,
        cached_tokens=30,
        prompt_tokens_details=SimpleNamespace(cached_tokens=30, cache_write_tokens=10),
        completion_tokens_details=SimpleNamespace(reasoning_tokens=12),
    )
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="answer", tool_calls=[], reasoning_content=None
                )
            )
        ],
        usage=usage,
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **_kwargs: response)
        )
    )
    core = SimpleNamespace(
        _is_web=True,
        responses_state={},
        _last_responses_usage={"input_tokens": 900},
    )
    result = legacy_provider_dispatch.call_legacy_openai_azure_round(
        provider=provider,
        client=client,
        depname="test-model",
        call_messages=[{"role": "user", "content": "hello"}],
        core=core,
        make_client_fn=lambda _: (provider, client),
        call_maybe_thread_fn=lambda call: call(),
        use_responses_api=False,
        stream_responses=False,
        send_tools_this_round=False,
        max_retries_429=0,
        retry_base=0.1,
        retry_cap=1.0,
        messages=[{"role": "user", "content": "hello"}],
        responses_state={},
    )
    assert result[0] is True
    assert core._last_responses_usage["total_tokens"] == 140
    assert core._last_responses_usage["cache_read_input_tokens"] == 30
    assert core._last_responses_usage["reasoning_output_tokens"] == 12
    if provider == "openrouter":
        assert core._last_responses_usage["cache_write_input_tokens"] == 10
    span = next(
        record["span"] for record in backend.spans if record["operation"] == "chat"
    )
    assert span.attributes["uag.tokens.reported.total"] == 140
    assert span.attributes["gen_ai.usage.cache_read.input_tokens"] == 30
    assert span.attributes["gen_ai.usage.reasoning.output_tokens"] == 12
