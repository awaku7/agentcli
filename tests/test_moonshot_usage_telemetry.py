"""Moonshot/Kimi token usage unit tests."""

from types import SimpleNamespace

import pytest

from uagent.providers.llm_moonshot_usage import moonshot_chat_usage_to_dict
from uagent.providers.openai_compatible_runtime import _reported_usage


def test_moonshot_chat_usage_reports_cached_subset_once():
    usage = {
        "prompt_tokens": 120,
        "completion_tokens": 17,
        "total_tokens": 137,
        "cached_tokens": 46,
        "completion_tokens_details": {"reasoning_tokens": 7},
    }
    expected = {
        "input_tokens": 120,
        "output_tokens": 17,
        "total_tokens": 137,
        "cache_read_input_tokens": 46,
        "reasoning_output_tokens": 7,
    }
    assert moonshot_chat_usage_to_dict(usage) == expected
    assert _reported_usage(usage, responses=False, provider="moonshot") == expected


def test_moonshot_sdk_object_accepts_nested_cached_tokens():
    usage = SimpleNamespace(
        prompt_tokens=31,
        completion_tokens=9,
        prompt_tokens_details=SimpleNamespace(cached_tokens=12),
        completion_tokens_details=SimpleNamespace(reasoning_tokens=4),
    )
    assert moonshot_chat_usage_to_dict(usage) == {
        "input_tokens": 31,
        "output_tokens": 9,
        "total_tokens": 40,
        "cache_read_input_tokens": 12,
        "reasoning_output_tokens": 4,
    }


@pytest.mark.parametrize(
    ("usage", "expected"),
    [
        (None, {}),
        ({"prompt_tokens": 20}, {"input_tokens": 20}),
        ({"completion_tokens": 4}, {"output_tokens": 4}),
        ({"prompt_tokens": True, "completion_tokens": -2}, {}),
        ({"prompt_tokens": 4.3, "completion_tokens": "8"}, {}),
        (
            {"prompt_tokens": 10, "completion_tokens": 2, "cached_tokens": 20},
            {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
        ),
        (
            {"prompt_tokens": 5, "completion_tokens": 2, "cached_tokens": True},
            {"input_tokens": 5, "output_tokens": 2, "total_tokens": 7},
        ),
        (
            {"prompt_tokens": 5, "completion_tokens": 2,
             "completion_tokens_details": {"reasoning_tokens": 7}},
            {"input_tokens": 5, "output_tokens": 2, "total_tokens": 7},
        ),
    ],
)
def test_moonshot_missing_or_invalid_counts_are_not_invented(usage, expected):
    assert moonshot_chat_usage_to_dict(usage) == expected
