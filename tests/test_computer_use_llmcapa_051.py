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


@pytest.mark.parametrize("model", ["muse-spark-1.2", "muse-spark-1.3"])
def test_muse_spark_computer_use_tracks_llmcapa_metadata(model):
    from uagent.llmcapa_util import get_capability

    metadata = get_capability(model, "meta")
    computer_use = getattr(metadata, "computer_use", None)
    if computer_use is None:
        with pytest.raises(ComputerUseCapabilityError):
            get_computer_use_capability(model, "meta")
        return

    assert get_computer_use_capability(model, "meta") is computer_use
