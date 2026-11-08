"""OpenRouter measured usage and stream-option regression tests."""

from types import SimpleNamespace

import pytest

from uagent.providers.llm_openrouter_usage import (
    openrouter_usage_to_dict,
    request_openrouter_stream_usage,
)
from uagent.providers.openai_compatible_runtime import _reported_usage


@pytest.mark.parametrize("responses", [False, True])
def test_openrouter_usage_maps_measured_subsets(responses):
    prompt = "input_tokens" if responses else "prompt_tokens"
    completion = "output_tokens" if responses else "completion_tokens"
    prompt_details = "input_tokens_details" if responses else "prompt_tokens_details"
    completion_details = (
        "output_tokens_details" if responses else "completion_tokens_details"
    )
    usage = {
        prompt: 100,
        completion: 40,
        prompt_details: {"cached_tokens": 30, "cache_write_tokens": 10},
        completion_details: {"reasoning_tokens": 12},
        "total_tokens": 999,
    }
    expected = {
        "input_tokens": 100,
        "output_tokens": 40,
        "total_tokens": 140,
        "cache_read_input_tokens": 30,
        "cache_write_input_tokens": 10,
        "reasoning_output_tokens": 12,
    }
    assert openrouter_usage_to_dict(usage, responses=responses) == expected
    assert _reported_usage(usage, responses=responses, provider="openrouter") == expected


def test_openrouter_usage_accepts_sdk_objects():
    usage = SimpleNamespace(
        prompt_tokens=8,
        completion_tokens=3,
        prompt_tokens_details=SimpleNamespace(cached_tokens=2),
        completion_tokens_details=SimpleNamespace(reasoning_tokens=1),
    )
    assert openrouter_usage_to_dict(usage, responses=False) == {
        "input_tokens": 8,
        "output_tokens": 3,
        "total_tokens": 11,
        "cache_read_input_tokens": 2,
        "reasoning_output_tokens": 1,
    }


def test_openrouter_usage_rejects_invalid_subsets_and_counts():
    assert openrouter_usage_to_dict(
        {
            "prompt_tokens": 5,
            "completion_tokens": 2,
            "prompt_tokens_details": {"cached_tokens": 6, "cache_write_tokens": True},
            "completion_tokens_details": {"reasoning_tokens": 3},
        },
        responses=False,
    ) == {"input_tokens": 5, "output_tokens": 2, "total_tokens": 7}
    assert openrouter_usage_to_dict(
        {"prompt_tokens": True, "completion_tokens": -1, "total_tokens": 8},
        responses=False,
    ) == {}


def test_openrouter_stream_options_preserve_explicit_choice():
    payload = {"stream_options": {"include_usage": False, "other": "value"}}
    request_openrouter_stream_usage(payload)
    assert payload["stream_options"] == {
        "include_usage": False,
        "other": "value",
    }
    blank = {}
    request_openrouter_stream_usage(blank)
    assert blank["stream_options"] == {"include_usage": True}
