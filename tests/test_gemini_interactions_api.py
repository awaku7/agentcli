from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from uagent.providers import gemini_api_mode as mode_module
from uagent.providers.llm_gemini_interactions import (
    _dump,
    _build_interaction_input,
    gemini_interactions_chat_with_tools,
)


def test_gemini_api_mode_defaults_and_normalizes(monkeypatch) -> None:
    from uagent import llmcapa_util

    monkeypatch.delenv("UAGENT_GEMINI_API_MODE", raising=False)
    assert mode_module.gemini_api_mode() == "generate_content"

    monkeypatch.setattr(
        llmcapa_util,
        "supports_feature",
        lambda feature, model, provider, default=None: (
            True
            if (feature, model, provider)
            in {
                (
                    "interactions_api",
                    "gemini-4-carbon",
                    "gemini",
                ),
                ("tool_search", "gemini-3.8-flash", "gemini"),
            }
            else (
                False
                if (feature, model, provider)
                == ("interactions_api", "gemini-2.5-flash", "vertexai")
                else default
            )
        ),
    )
    assert mode_module.gemini_api_mode("gemini-4-carbon", "gemini") == "interactions"
    assert mode_module.gemini_api_mode("gemini-3.8-flash", "gemini") == "interactions"
    assert (
        mode_module.gemini_api_mode("gemini-2.5-flash", "vertexai")
        == "generate_content"
    )
    assert mode_module.gemini_api_mode("unknown-model", "gemini") == "generate_content"

    monkeypatch.setenv("UAGENT_GEMINI_API_MODE", "Interactions_API")
    assert mode_module.gemini_api_mode("unsupported-model", "gemini") == "interactions"

    monkeypatch.setenv("UAGENT_GEMINI_API_MODE", "generate-content")
    assert mode_module.gemini_api_mode() == "generate_content"

    monkeypatch.setenv("UAGENT_GEMINI_API_MODE", "responses")
    with pytest.raises(ValueError, match="UAGENT_GEMINI_API_MODE"):
        mode_module.gemini_api_mode()


def test_gemini_api_mode_routes_from_llmcapa_tool_search_flag(monkeypatch) -> None:
    from uagent import llmcapa_util

    monkeypatch.delenv("UAGENT_GEMINI_API_MODE", raising=False)
    monkeypatch.setattr(
        llmcapa_util,
        "supports_feature",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        llmcapa_util,
        "get_capability",
        lambda _model, _provider: SimpleNamespace(supports_tool_search=True),
    )

    assert mode_module.gemini_api_mode("gemini-3.8-flash", "gemini") == "interactions"


def test_build_interactions_input_replays_native_steps_and_tool_result() -> None:
    native_steps = [
        {"type": "thought", "signature": "opaque-thought-signature"},
        {
            "type": "function_call",
            "id": "fc-1",
            "name": "example_tool",
            "arguments": {"query": "hello"},
        },
    ]
    messages = [
        {"role": "system", "content": "Follow the system instructions."},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "fc-1", "function": {"name": "example_tool"}}],
            "_gemini_content": {"_gemini_interactions_steps": native_steps},
        },
        {
            "role": "tool",
            "name": "example_tool",
            "tool_call_id": "fc-1",
            "content": '{"ok": true}',
        },
        {"role": "user", "content": "Continue with the result."},
    ]

    steps, system_instruction = _build_interaction_input(messages)

    assert system_instruction == "Follow the system instructions."
    assert steps[:2] == native_steps
    assert steps[2] == {
        "type": "function_result",
        "call_id": "fc-1",
        "name": "example_tool",
        "result": [{"type": "text", "text": '{"ok": true}'}],
    }
    assert steps[3] == {
        "type": "user_input",
        "content": [{"type": "text", "text": "Continue with the result."}],
    }


def test_unknown_interactions_step_keeps_original_wire_payload() -> None:
    raw_step = {
        "type": "tool_search_call",
        "id": "search-1",
        "arguments": {"function_names": ["lookup"]},
        "signature": "opaque-signature",
    }
    unknown_step = SimpleNamespace(
        is_unknown=True,
        raw=raw_step,
        model_dump=lambda **_kwargs: {
            "type": "UNKNOWN",
            "raw": raw_step,
            "is_unknown": True,
        },
    )

    assert _dump(unknown_step) == raw_step


def test_interactions_request_is_stateless_and_normalizes_response(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_GEMINI_WEB_SEARCH", "0")
    monkeypatch.setenv("UAGENT_GEMINI_TEMPERATURE", "0.6")
    monkeypatch.setenv("UAGENT_REASONING", "off")
    monkeypatch.setenv("UAGENT_GEMINI_INCLUDE_THOUGHTS", "0")
    monkeypatch.setattr(
        "uagent.llmcapa_util.get_capability", lambda _model, _provider: None
    )
    monkeypatch.setattr(
        "uagent.providers.llm_gemini._llmcapa_reasoning_levels", lambda _model: None
    )
    from uagent.runtime import execution_broker

    monkeypatch.setattr(execution_broker, "computer_use_allowed", lambda: False)

    response = {
        "steps": [
            {
                "type": "thought",
                "signature": "opaque-signature",
                "summary": [{"type": "text", "text": "private reasoning summary"}],
            },
            {
                "type": "model_output",
                "content": [{"type": "text", "text": "Checking now."}],
            },
            {
                "type": "function_call",
                "id": "fc-live-1",
                "name": "lookup",
                "arguments": {"key": "value"},
            },
        ],
        "output_text": "Checking now.",
        "usage": {
            "total_input_tokens": 14,
            "total_output_tokens": 7,
            "total_tokens": 21,
            "total_cached_tokens": 3,
            "total_thought_tokens": 2,
        },
    }

    class FakeInteractions:
        def __init__(self):
            self.requests = []

        def create(self, **kwargs):
            self.requests.append(kwargs)
            return response

    api = FakeInteractions()
    client = SimpleNamespace(interactions=api)
    core = SimpleNamespace(
        context_tool_specs=[
            {
                "type": "function",
                "function": {
                    "name": "lookup",
                    "description": "Look up a value.",
                    "parameters": {
                        "type": "object",
                        "properties": {"key": {"type": "string"}},
                        "required": ["key"],
                    },
                },
            }
        ],
        _gemini_tool_catalog_ready=True,
        _last_responses_usage={},
    )

    text, calls, content_dump = gemini_interactions_chat_with_tools(
        client,
        "gemini-4-hydrogen",
        [
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "Look up the value."},
        ],
        core=core,
        provider="gemini",
        send_tools=True,
    )

    request = api.requests[0]
    assert request["model"] == "gemini-4-hydrogen"
    assert request["store"] is False
    assert request["system_instruction"] == "Be concise."
    assert request["input"] == [
        {
            "type": "user_input",
            "content": [{"type": "text", "text": "Look up the value."}],
        }
    ]
    assert request["tools"] == [
        {
            "type": "function",
            "name": "lookup",
            "description": "Look up a value.",
            "parameters": {
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"],
            },
        }
    ]
    assert request["generation_config"]["thinking_summaries"] == "none"
    assert request["extra_body"]["generation_config"]["temperature"] == 0.6
    assert request["extra_body"]["generation_config"]["thinking_summaries"] == "none"
    assert request["safety_settings"][0] == {
        "type": "harassment",
        "threshold": "off",
    }
    assert {setting["type"] for setting in request["safety_settings"]} == {
        "harassment",
        "hate_speech",
        "sexually_explicit",
        "dangerous_content",
        "jailbreak",
    }
    assert text == "Checking now."
    assert calls == [
        {
            "id": "fc-live-1",
            "type": "function",
            "function": {
                "name": "lookup",
                "arguments": json.dumps({"key": "value"}),
            },
        }
    ]
    assert content_dump["_gemini_interactions_steps"] == response["steps"]
    assert core._last_responses_usage == {
        "input_tokens": 14,
        "output_tokens": 7,
        "total_tokens": 21,
        "cache_read_input_tokens": 3,
        "reasoning_output_tokens": 2,
    }


def test_interactions_uses_llmcapa_tool_retrieval_when_supported(monkeypatch) -> None:
    monkeypatch.delenv("UAGENT_GEMINI_API_MODE", raising=False)
    monkeypatch.setenv("UAGENT_GEMINI_WEB_SEARCH", "0")
    monkeypatch.setenv("UAGENT_REASONING", "off")
    monkeypatch.setenv("UAGENT_GEMINI_SAFETY_OFF", "0")
    monkeypatch.setattr(
        "uagent.llmcapa_util.supports_feature",
        lambda feature, _model, _provider, default=None: (
            True if feature in {"interactions_api", "tool_search"} else default
        ),
    )
    monkeypatch.setattr(
        "uagent.llmcapa_util.get_capability", lambda _model, _provider: None
    )
    monkeypatch.setattr(
        "uagent.providers.llm_gemini._llmcapa_reasoning_levels", lambda _model: None
    )
    from uagent import tools
    from uagent.runtime import execution_broker

    monkeypatch.setattr(execution_broker, "computer_use_allowed", lambda: False)
    monkeypatch.setattr(
        tools,
        "get_tool_specs",
        lambda: [
            {
                "type": "function",
                "function": {
                    "name": "lookup",
                    "description": "Look up a value.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "another_tool",
                    "description": "Another operation.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "tool_catalog",
                    "description": "Internal discovery tool.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "tool_load",
                    "description": "Internal tool loader.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "unload_tool",
                    "description": "Internal tool unloader.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
        ],
    )

    class FakeInteractions:
        request = None

        def create(self, **kwargs):
            self.request = kwargs
            return {"steps": []}

    api = FakeInteractions()
    core = SimpleNamespace(
        context_tool_specs=[
            {
                "type": "function",
                "function": {
                    "name": "lookup",
                    "description": "Budget-selected version.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mcp_extra",
                    "description": "External tool.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
        ],
        _gemini_tool_catalog_ready=False,
    )

    gemini_interactions_chat_with_tools(
        SimpleNamespace(interactions=api),
        "gemini-search-supported",
        [
            {
                "role": "system",
                "content": "Keep the answer concise.",
            },
            {
                "role": "assistant",
                "content": "",
                "_gemini_content": {
                    "_gemini_interactions_steps": [
                        {
                            "type": "function_call",
                            "id": "old-catalog-call",
                            "name": "tool_catalog",
                            "arguments": {"query": "weather"},
                        }
                    ]
                },
            },
            {
                "role": "tool",
                "name": "tool_catalog",
                "tool_call_id": "old-catalog-call",
                "content": '{"tools": ["get_weather_wttr"]}',
            },
            {"role": "user", "content": "Use the right tool."},
        ],
        core=core,
        provider="gemini",
        send_tools=True,
    )

    assert "tools" not in api.request
    assert api.request["system_instruction"] == "Keep the answer concise."
    assert not any(
        item.get("type") in {"function_call", "function_result"}
        and item.get("name") == "tool_catalog"
        for item in api.request["input"]
    )
    assert api.request["extra_body"]["tools"] == [
        {"type": "tool_search"},
        {
            "type": "function",
            "name": "lookup",
            "description": "Look up a value.",
            "parameters": {"type": "object", "properties": {}},
            "defer_loading": True,
        },
        {
            "type": "function",
            "name": "another_tool",
            "description": "Another operation.",
            "parameters": {"type": "object", "properties": {}},
            "defer_loading": True,
        },
        {
            "type": "function",
            "name": "mcp_extra",
            "description": "External tool.",
            "parameters": {"type": "object", "properties": {}},
            "defer_loading": True,
        },
    ]
    assert "tool_choice" not in api.request.get("generation_config", {})

    monkeypatch.setenv("UAGENT_PROVIDER", "gemini")
    monkeypatch.setenv("UAGENT_GEMINI_DEPNAME", "gemini-search-supported")
    monkeypatch.delenv("UAGENT_RESPONSES", raising=False)
    assert tools._should_preload_lazy_specs()
    from uagent.tools.llm_tool_narrowing import should_emit_catalog_steering

    assert not should_emit_catalog_steering(
        provider="gemini",
        depname="gemini-search-supported",
        use_responses_api=False,
    )


def test_interactions_tool_retrieval_reads_llmcapa_flag(monkeypatch) -> None:
    from uagent.runtime.tool_discovery import (
        gemini_interactions_tool_retrieval_enabled,
    )

    monkeypatch.delenv("UAGENT_GEMINI_API_MODE", raising=False)
    monkeypatch.setattr(
        "uagent.llmcapa_util.supports_feature",
        lambda feature, _model, _provider, default=None: (
            True if feature == "interactions_api" else default
        ),
    )
    monkeypatch.setattr(
        "uagent.llmcapa_util.get_capability",
        lambda _model, _provider: SimpleNamespace(supports_tool_search=True),
    )

    assert gemini_interactions_tool_retrieval_enabled(
        "gemini", "gemini-search-supported"
    )


def test_interactions_continues_long_decode_and_preserves_all_steps(
    monkeypatch,
) -> None:
    monkeypatch.setenv("UAGENT_GEMINI_WEB_SEARCH", "0")
    monkeypatch.setenv("UAGENT_REASONING", "off")
    monkeypatch.setenv("UAGENT_GEMINI_SAFETY_OFF", "0")
    monkeypatch.setattr(
        "uagent.llmcapa_util.get_capability", lambda _model, _provider: None
    )
    monkeypatch.setattr(
        "uagent.providers.llm_gemini._llmcapa_reasoning_levels", lambda _model: None
    )
    from uagent.runtime import execution_broker

    monkeypatch.setattr(execution_broker, "computer_use_allowed", lambda: False)

    partial = {
        "status": "requires_continuation",
        "continuation_token": "opaque-token",
        "steps": [
            {
                "type": "model_output",
                "content": [{"type": "text", "text": "Partial "}],
            }
        ],
    }
    completed = {
        "status": "completed",
        "steps": [
            {
                "type": "model_output",
                "content": [{"type": "text", "text": "answer."}],
            }
        ],
    }

    class FakeInteractions:
        def __init__(self):
            self.requests = []

        def create(self, **kwargs):
            self.requests.append(kwargs)
            return partial if len(self.requests) == 1 else completed

    api = FakeInteractions()
    text, _calls, content_dump = gemini_interactions_chat_with_tools(
        SimpleNamespace(interactions=api),
        "gemini-4-hydrogen",
        [{"role": "user", "content": "Continue the long answer."}],
        provider="gemini",
        send_tools=False,
    )

    assert text == "Partial answer."
    assert api.requests[1] == {
        "model": "gemini-4-hydrogen",
        "continuation_token": "opaque-token",
        "store": False,
    }
    assert len(content_dump["_gemini_interactions_steps"]) == 2


def test_interactions_does_not_return_incomplete_response_as_complete(
    monkeypatch,
) -> None:
    monkeypatch.setenv("UAGENT_GEMINI_SAFETY_OFF", "0")
    monkeypatch.setattr(
        "uagent.llmcapa_util.get_capability", lambda _model, _provider: None
    )
    monkeypatch.setattr(
        "uagent.providers.llm_gemini._llmcapa_reasoning_levels", lambda _model: None
    )
    from uagent.runtime import execution_broker

    monkeypatch.setattr(execution_broker, "computer_use_allowed", lambda: False)

    class FakeInteractions:
        def create(self, **_kwargs):
            return {"status": "incomplete", "steps": []}

    with pytest.raises(RuntimeError, match="status incomplete"):
        gemini_interactions_chat_with_tools(
            SimpleNamespace(interactions=FakeInteractions()),
            "gemini-4-hydrogen",
            [{"role": "user", "content": "Hello"}],
            provider="gemini",
            send_tools=False,
        )


def test_interactions_initial_discovery_forces_catalog_tool(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_GEMINI_WEB_SEARCH", "1")
    monkeypatch.setenv("UAGENT_REASONING", "off")
    monkeypatch.setattr(
        "uagent.llmcapa_util.get_capability", lambda _model, _provider: None
    )
    monkeypatch.setattr(
        "uagent.providers.llm_gemini._llmcapa_reasoning_levels", lambda _model: None
    )
    from uagent.runtime import execution_broker

    monkeypatch.setattr(execution_broker, "computer_use_allowed", lambda: False)

    class FakeInteractions:
        request = None

        def create(self, **kwargs):
            self.request = kwargs
            return {"steps": []}

    api = FakeInteractions()
    core = SimpleNamespace(
        context_tool_specs=[
            {
                "type": "function",
                "function": {"name": "tool_catalog", "parameters": {"type": "object"}},
            },
            {
                "type": "function",
                "function": {
                    "name": "some_other_tool",
                    "parameters": {"type": "object"},
                },
            },
        ],
        _gemini_tool_catalog_ready=False,
    )

    gemini_interactions_chat_with_tools(
        SimpleNamespace(interactions=api),
        "gemini-4-hydrogen",
        [{"role": "user", "content": "Find a tool."}],
        core=core,
        provider="vertexai",
    )

    assert api.request["tools"] == [
        {
            "type": "function",
            "name": "tool_catalog",
            "description": "",
            "parameters": {"type": "object"},
        }
    ]
    assert api.request["generation_config"]["tool_choice"] == {
        "allowed_tools": {"mode": "any", "tools": ["tool_catalog"]}
    }


def test_interactions_maps_native_structured_output(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_GEMINI_WEB_SEARCH", "0")
    monkeypatch.setenv("UAGENT_REASONING", "off")
    monkeypatch.setenv("UAGENT_GEMINI_SAFETY_OFF", "0")
    monkeypatch.setattr(
        "uagent.llmcapa_util.get_capability", lambda _model, _provider: None
    )
    monkeypatch.setattr(
        "uagent.providers.llm_gemini._llmcapa_reasoning_levels", lambda _model: None
    )
    monkeypatch.setattr(
        "uagent.runtime.capability_resolver.native_structured_output_request_for_runtime",
        lambda *_args, **_kwargs: {
            "type": "json_schema",
            "json_schema": {"schema": {"type": "object", "properties": {}}},
        },
    )
    from uagent.runtime import execution_broker

    monkeypatch.setattr(execution_broker, "computer_use_allowed", lambda: False)

    class FakeInteractions:
        request = None

        def create(self, **kwargs):
            self.request = kwargs
            return {"steps": []}

    api = FakeInteractions()
    gemini_interactions_chat_with_tools(
        SimpleNamespace(interactions=api),
        "gemini-4-hydrogen",
        [{"role": "user", "content": "Return JSON."}],
        provider="gemini",
        send_tools=False,
    )

    assert api.request["response_format"] == {
        "type": "text",
        "mime_type": "application/json",
        "schema": {"type": "object", "properties": {}},
    }


def test_interactions_buffers_text_then_emits_legacy_stream_callbacks(
    monkeypatch,
) -> None:
    monkeypatch.setenv("UAGENT_GEMINI_WEB_SEARCH", "0")
    monkeypatch.setenv("UAGENT_REASONING", "off")
    monkeypatch.setenv("UAGENT_GEMINI_SAFETY_OFF", "0")
    monkeypatch.setattr(
        "uagent.llmcapa_util.get_capability", lambda _model, _provider: None
    )
    monkeypatch.setattr(
        "uagent.providers.llm_gemini._llmcapa_reasoning_levels", lambda _model: None
    )
    from uagent.runtime import execution_broker

    monkeypatch.setattr(execution_broker, "computer_use_allowed", lambda: False)

    class FakeInteractions:
        def create(self, **_kwargs):
            return {
                "steps": [
                    {
                        "type": "model_output",
                        "content": [{"type": "text", "text": "Buffered answer."}],
                    }
                ]
            }

    events = []
    callbacks = SimpleNamespace(
        on_delta=lambda text: events.append(("delta", text)),
        on_terminal=lambda kind, _data: events.append(("terminal", kind)),
        on_reasoning=None,
        on_tool_call=None,
    )
    text, _calls, _dump = gemini_interactions_chat_with_tools(
        SimpleNamespace(interactions=FakeInteractions()),
        "gemini-4-hydrogen",
        [{"role": "user", "content": "Answer"}],
        stream=True,
        callbacks=callbacks,
    )

    assert text == "Buffered answer."
    assert events == [
        ("terminal", "ResponseStarted"),
        ("delta", "Buffered answer."),
        ("terminal", "ResponseCompleted"),
    ]


def test_interactions_transport_routes_from_gemini_adapter(monkeypatch) -> None:
    from uagent.providers import llm_gemini
    from uagent.providers import llm_gemini_interactions

    monkeypatch.setattr(llm_gemini, "gemini_api_mode", lambda *_args: "interactions")
    monkeypatch.setattr(
        llm_gemini_interactions,
        "gemini_interactions_chat_with_tools",
        lambda *_args, **_kwargs: ("interaction", [], {"native": True}),
    )

    assert llm_gemini.gemini_chat_with_tools(
        object(), "gemini-4-hydrogen", [], provider="gemini"
    ) == ("interaction", [], {"native": True})


def test_provider_projection_preserves_interactions_steps_only_for_google(
    monkeypatch,
) -> None:
    from uagent.runtime import provider_context

    message = {
        "role": "assistant",
        "content": "answer",
        "_gemini_content": {"_gemini_interactions_steps": [{"type": "thought"}]},
    }
    monkeypatch.setattr(
        provider_context, "gemini_api_mode", lambda *_args: "interactions"
    )
    projected = provider_context.project_messages_for_provider(
        [message], provider="gemini"
    )
    assert projected[0]["_gemini_content"] == message["_gemini_content"]
    assert (
        "_gemini_content"
        not in provider_context.project_messages_for_provider(
            [message], provider="openai"
        )[0]
    )


def test_interactions_mode_skips_generate_content_cache_setup(monkeypatch) -> None:
    from uagent import llm_message_helpers
    from uagent.providers import gemini_cache_mgr

    class FakeCacheManager:
        def __init__(self, _model):
            pass

    monkeypatch.setattr(gemini_cache_mgr, "GeminiCacheManager", FakeCacheManager)
    monkeypatch.setattr(
        llm_message_helpers, "gemini_api_mode", lambda *_args: "interactions"
    )
    monkeypatch.setattr(
        llm_message_helpers,
        "_lazy_gemini_types",
        lambda: (_ for _ in ()).throw(
            AssertionError("GenerateContent cache setup ran")
        ),
    )

    _cache_manager, cache_name = llm_message_helpers._init_gemini_cache(
        provider="gemini",
        client=object(),
        depname="gemini-4-hydrogen",
        messages=[{"role": "system", "content": "private"}],
    )

    assert cache_name is None


def test_setup_wizard_exposes_google_api_mode() -> None:
    from uagent.setup_cli import PROVIDER_FIELDS

    for provider in ("gemini", "vertexai"):
        fields = {name for name, _required, _label in PROVIDER_FIELDS[provider]}
        assert "UAGENT_GEMINI_API_MODE" in fields


def test_startup_validation_warns_for_unknown_gemini_api_mode(monkeypatch) -> None:
    from uagent.env_validate import validate_startup_env

    monkeypatch.setenv("UAGENT_PROVIDER", "gemini")
    monkeypatch.setenv("UAGENT_GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("UAGENT_GEMINI_API_MODE", "unknown")

    provider, _missing, warnings = validate_startup_env()

    assert provider == "gemini"
    assert any("UAGENT_GEMINI_API_MODE" in warning for warning in warnings)


def test_interactions_transport_rejects_catalogued_unsupported_model(
    monkeypatch,
) -> None:
    monkeypatch.setenv("UAGENT_REASONING", "off")
    monkeypatch.setattr(
        "uagent.llmcapa_util.get_capability",
        lambda _model, _provider: SimpleNamespace(supports_interactions_api=False),
    )

    with pytest.raises(
        ValueError, match="not listed as supporting the Interactions API"
    ):
        gemini_interactions_chat_with_tools(
            SimpleNamespace(
                interactions=SimpleNamespace(create=lambda **_kwargs: None)
            ),
            "gemini-old-model",
            [{"role": "user", "content": "Hello"}],
            provider="gemini",
        )


__all__ = []
