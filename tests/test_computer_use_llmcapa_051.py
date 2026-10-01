import pytest

from uagent.computer_use.capability import (
    ComputerUseCapabilityError,
    get_computer_use_capability,
)


@pytest.mark.parametrize(
    (
        "model",
        "provider",
        "expected_provider",
        "expected_api_type",
        "expected_tool_type",
    ),
    [
        (
            "claude-sonnet-4-6",
            "claude",
            "anthropic",
            "messages",
            "computer_20251124",
        ),
        (
            "claude-sonnet-5-5",
            "claude",
            "anthropic",
            "messages",
            "computer_toolset_20260801",
        ),
        (
            "muse-spark-1.3",
            "meta",
            "meta",
            "responses",
            "computer",
        ),
    ],
)
def test_llmcapa_051_exposes_provider_specific_computer_use(
    model,
    provider,
    expected_provider,
    expected_api_type,
    expected_tool_type,
):
    capability = get_computer_use_capability(model, provider)

    assert capability.supported is True
    assert capability.native is True
    assert capability.provider == expected_provider
    assert capability.api_type == expected_api_type
    assert capability.tool_type == expected_tool_type


def test_llmcapa_051_does_not_infer_muse_spark_12_computer_use():
    with pytest.raises(ComputerUseCapabilityError):
        get_computer_use_capability("muse-spark-1.2", "meta")
