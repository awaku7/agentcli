from __future__ import annotations

from uagent.runtime.observability.semantic_mapping import map_span


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


def test_custom_genai_provider_name_is_preserved() -> None:
    mapped = map_span(
        "chat",
        {
            "uag.llm.provider": "Custom.Provider",
            "uag.llm.model": "test-model",
        },
    )

    assert mapped.attributes["gen_ai.provider.name"] == "Custom.Provider"
