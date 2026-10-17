from __future__ import annotations

from typing import Any

from uagent.providers import util_providers
from uagent.providers.openai_compatible_runtime import OpenAICompatibleRuntime
from uagent.providers.openai_projection_policy import (
    build_openai_projection,
    sarashina_tool_schema_field_names,
    sarashina_tool_schema_fields_by_tool,
)
from uagent.providers.provider_caps import (
    DEFAULT_PROVIDER_REGISTRY,
    RESPONSES_PROVIDERS,
    supports_structured_output_wire,
    temperature_env_name,
)
from uagent.providers.runtime_registry import supports_provider_runtime
from uagent.runtime.chat_tool_policy import initial_sarashina_chat_completion_tools
from uagent.runtime.round_contracts import ProviderProjection, RoundIdentifiers


class _Core:
    credential_store = None

    def get_env(self, name: str, default: str | None = None) -> str | None:
        import os

        return os.environ.get(name, default)

    def get_env_url(self, name: str, default: str | None = None) -> str:
        return (self.get_env(name, default) or "").strip()


def test_sarashina_openai_compatible_client_defaults(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class FakeOpenAI:
        def __init__(self, *, api_key, base_url, http_client=None):
            captured.update(
                api_key=api_key,
                base_url=base_url,
                http_client=http_client,
            )

    monkeypatch.setenv("UAGENT_PROVIDER", "sarashina")
    monkeypatch.setenv("SARASHINA_API_KEY", "test-sarashina-key")
    monkeypatch.delenv("UAGENT_SARASHINA_API_KEY", raising=False)
    monkeypatch.delenv("UAGENT_SARASHINA_BASE_URL", raising=False)
    monkeypatch.delenv("UAGENT_SARASHINA_DEPNAME", raising=False)
    monkeypatch.setattr(util_providers, "_ensure_provider_dependency", lambda _: None)
    monkeypatch.setattr(util_providers, "make_httpx_client", lambda **_: None)
    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)

    provider, client, model = util_providers.make_client(_Core())

    assert provider == "sarashina"
    assert isinstance(client, FakeOpenAI)
    assert model == "sarashina3-mini"
    assert captured == {
        "api_key": "test-sarashina-key",
        "base_url": "https://api.sarashina.ai/v1",
        "http_client": None,
    }


def test_sarashina_registry_advertises_chat_only_capabilities() -> None:
    spec = DEFAULT_PROVIDER_REGISTRY.resolve("sarashina", "sarashina3-mini")

    assert supports_provider_runtime("sarashina") is True
    assert "chat" in spec.capabilities
    assert "streaming" in spec.capabilities
    assert "tools" in spec.capabilities
    assert "responses" not in spec.capabilities
    assert "sarashina" not in RESPONSES_PROVIDERS
    assert supports_structured_output_wire("sarashina", "chat_completions")
    assert not supports_structured_output_wire("sarashina", "responses")
    assert temperature_env_name("sarashina") == "UAGENT_SARASHINA_TEMPERATURE"


def test_sarashina_bootstrap_sends_three_discovery_tools_first() -> None:
    tools = [
        {"type": "function", "function": {"name": "tool_catalog"}},
        {"type": "function", "function": {"name": "tool_load"}},
        {"type": "function", "function": {"name": "unload_tool"}},
        {"type": "function", "function": {"name": "spawn_sub_agent"}},
    ]

    selected = initial_sarashina_chat_completion_tools(tools)

    assert [tool["function"]["name"] for tool in selected] == [
        "tool_catalog",
        "tool_load",
        "unload_tool",
    ]


def test_sarashina_tool_load_uses_string_list_instead_of_array_schema() -> None:
    from uagent.providers.openai_projection_policy import sanitize_sarashina_tool_specs

    specs = [
        {
            "type": "function",
            "function": {
                "name": "tool_load",
                "description": "Pass a names array.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "names": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": [],
                },
            },
        }
    ]

    sanitized = sanitize_sarashina_tool_specs(specs)[0]["function"]

    assert set(sanitized["parameters"]["properties"]) == {"name"}
    assert sanitized["parameters"]["required"] == ["name"]
    assert "comma- or whitespace-separated" in sanitized["description"]


def test_openrouter_sync_does_not_inject_empty_tools_for_sarashina() -> None:
    from uagent.providers.llm_openrouter import finalize_tool_schema_sync

    request = {"model": "sarashina3-mini", "messages": []}

    finalize_tool_schema_sync(request, provider="sarashina")

    assert "tools" not in request


def test_sarashina_messages_drop_undocumented_fields_and_map_developer_role() -> None:
    from uagent.providers.openai_projection_policy import sanitize_sarashina_messages

    messages = [
        {
            "role": "developer",
            "content": "system instruction",
            "reasoning_content": "private reasoning",
            "metadata": {"internal": True},
        },
        {"role": "user", "content": "hello", "name": "client"},
    ]

    assert sanitize_sarashina_messages(messages) == [
        {"role": "system", "content": "system instruction"},
        {"role": "user", "content": "hello"},
    ]


def test_sarashina_projection_uses_documented_fields_and_token_ceiling(
    monkeypatch,
) -> None:
    monkeypatch.setenv("UAGENT_REASONING", "high")
    monkeypatch.setenv("UAGENT_MAX_TOKENS", "12000")

    projection = build_openai_projection(
        provider="sarashina",
        model="sarashina3-mini",
        transport="chat_completions",
        messages=[{"role": "user", "content": "hello"}],
        send_tools=True,
        compaction_threshold=1000,
    )

    assert projection.options["tool_choice"] == "auto"
    assert projection.options["max_completion_tokens"] == 8000
    assert "reasoning_effort" not in projection.options
    assert "max_tokens" not in projection.options


def test_sarashina_serialization_strips_undocumented_tool_schema_fields() -> None:
    tool_spec = {
        "type": "function",
        "function": {
            "name": "example",
            "description": "Example tool",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "enabled": {
                        "type": "boolean",
                        "default": False,
                        "minimum": 0,
                        "maximum": 1,
                        "additionalProperties": False,
                    }
                },
                "required": ["enabled"],
            },
        },
    }
    identifiers = RoundIdentifiers(
        turn_id="turn",
        round_id="round",
        attempt_id="attempt",
        request_id="request",
        stream_id="stream",
        session_generation=0,
    )
    runtime = OpenAICompatibleRuntime(
        client=None,
        provider="sarashina",
        model="sarashina3-mini",
        identifiers=identifiers,
        transport="chat_completions",
        streaming=True,
    )
    projection = ProviderProjection(
        plan_id="plan",
        projection_id="projection",
        provider="sarashina",
        model="sarashina3-mini",
        transport="chat_completions",
        messages=({"role": "user", "content": "hello"},),
        tool_specs=(tool_spec,),
    )

    payload = runtime.serialize(projection).payload
    parameters = payload["tools"][0]["function"]["parameters"]

    assert "additionalProperties" not in parameters
    assert "default" not in parameters["properties"]["enabled"]
    assert "additionalProperties" not in parameters["properties"]["enabled"]
    assert "minimum" not in parameters["properties"]["enabled"]
    assert "maximum" not in parameters["properties"]["enabled"]
    assert sarashina_tool_schema_field_names(payload["tools"]) == [
        "properties",
        "required",
        "type",
    ]
    assert sarashina_tool_schema_fields_by_tool(payload["tools"]) == {
        "example": ["properties", "required", "type"]
    }


def test_sarashina_runtime_debug_logs_request_shape_without_prompt(monkeypatch, capsys):
    from types import SimpleNamespace

    monkeypatch.setenv("UAGENT_DEBUG_OPENAI_RUNTIME", "1")

    class FakeCompletions:
        def create(self, **_kwargs):
            raise RuntimeError("synthetic BadRequest")

    runtime = OpenAICompatibleRuntime(
        client=SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions())),
        provider="sarashina",
        model="sarashina3-mini",
        identifiers=RoundIdentifiers(
            turn_id="turn",
            round_id="round",
            attempt_id="attempt",
            request_id="request",
            stream_id="stream",
            session_generation=0,
        ),
    )
    projection = ProviderProjection(
        plan_id="plan",
        projection_id="projection",
        provider="sarashina",
        model="sarashina3-mini",
        transport="chat_completions",
        messages=({"role": "user", "content": "private prompt text"},),
        tool_specs=(
            {
                "type": "function",
                "function": {
                    "name": "test_tool",
                    "parameters": {
                        "type": "object",
                        "properties": {"arg": {"type": "string"}},
                    },
                },
            },
        ),
    )
    request = runtime.serialize(projection)

    class NeverCancelled:
        def is_cancelled(self):
            return False

    list(runtime.run(request, NeverCancelled()))
    debug_output = capsys.readouterr().err

    assert "request_fields" in debug_output
    assert "message_shapes" in debug_output
    assert "tool_schema_fields" in debug_output
    assert "tool_schema_fields_by_tool" in debug_output
    assert "test_tool" in debug_output
    assert "private prompt text" not in debug_output
