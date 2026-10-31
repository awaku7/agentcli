from __future__ import annotations

from uagent.runtime.observability.semantic_mapping import map_attributes, map_span


def test_genai_provider_names_use_well_known_semconv_values() -> None:
    expected = {
        "azure": "azure.ai.openai",
        "bedrock": "aws.bedrock",
        "claude": "anthropic",
        "deepseek": "deepseek",
        "gemini": "gcp.gemini",
        "grok": "x_ai",
        "moonshot": "moonshot_ai",
        "openai": "openai",
        "vertexai": "gcp.vertex_ai",
    }

    for provider, semantic_name in expected.items():
        mapped = map_span(
            "chat",
            {
                "uag.llm.provider": provider,
                "uag.llm.model": "test-model",
            },
        )
        assert mapped.attributes["gen_ai.provider.name"] == semantic_name
        assert "uag.llm.provider" not in mapped.attributes
        assert "uag.llm.model" not in mapped.attributes


def test_custom_genai_provider_name_is_preserved() -> None:
    mapped = map_span(
        "chat",
        {
            "uag.llm.provider": "Custom.Provider",
            "uag.llm.model": "test-model",
        },
    )

    assert mapped.attributes["gen_ai.provider.name"] == "Custom.Provider"


def test_execute_tool_has_standard_name_and_operation() -> None:
    mapped = map_span(
        "execute_tool",
        {"uag.tool.name": "calculator", "uag.tool.side_effect": "none"},
    )
    assert mapped.name == "execute_tool calculator"
    assert mapped.attributes["gen_ai.operation.name"] == "execute_tool"
    assert mapped.attributes["gen_ai.tool.name"] == "calculator"


def test_standard_attributes_replace_uag_aliases_without_duplicates() -> None:
    mapped = map_span(
        "invoke_agent",
        {
            "uag.agent.name": "uag",
            "uag.agent.lifecycle_status": "running",
        },
    )
    assert mapped.attributes["gen_ai.agent.name"] == "uag"
    assert "uag.agent.name" not in mapped.attributes
    assert mapped.attributes["uag.agent.lifecycle_status"] == "running"

    tool = map_span(
        "execute_tool",
        {"uag.tool.name": "calculator", "uag.tool.side_effect": "none"},
    )
    assert tool.attributes["gen_ai.tool.name"] == "calculator"
    assert "uag.tool.name" not in tool.attributes
    assert tool.attributes["uag.tool.side_effect"] == "none"


def test_dynamic_metadata_maps_to_standard_usage_errors_and_span_status() -> None:
    mapped = map_attributes(
        {
            "uag.tokens.reported.input": 10,
            "uag.tokens.reported.output": 4,
            "uag.tokens.reported.total": 14,
            "uag.tokens.estimate.input": 12,
            "uag.error.type": "TimeoutError",
            "uag.status": "error",
            "uag.duration_ms": 300,
            "uag.context.decision.action": "KEEP",
        }
    )
    assert mapped == {
        "gen_ai.usage.input_tokens": 10,
        "gen_ai.usage.output_tokens": 4,
        "uag.tokens.estimate.input": 12,
        "error.type": "TimeoutError",
        "uag.context.decision.action": "KEEP",
    }


def test_explicit_standard_attributes_take_precedence() -> None:
    mapped = map_attributes(
        {
            "uag.llm.provider": "grok",
            "gen_ai.provider.name": "openai",
            "uag.tokens.reported.input": 7,
            "gen_ai.usage.input_tokens": 8,
            "uag.tokens.reported.output": -2,
        }
    )
    assert mapped == {
        "gen_ai.provider.name": "openai",
        "gen_ai.usage.input_tokens": 8,
    }


def test_invalid_usage_values_are_not_exported_as_standard_counts() -> None:
    assert map_attributes(
        {
            "uag.tokens.reported.input": 1.5,
            "uag.tokens.reported.output": True,
            "uag.tokens.estimate.input": 9,
        }
    ) == {"uag.tokens.estimate.input": 9}


def test_cancellation_and_disabled_remain_distinguishable_from_unset_or_ok() -> None:
    assert map_attributes({"uag.status": "cancelled"}) == {"uag.status": "cancelled"}
    assert map_attributes({"uag.status": "disabled"}) == {"uag.status": "disabled"}
    assert map_attributes({"uag.status": "completed"}) == {}
