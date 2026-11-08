"""Sakana Responses usage regression tests."""

from types import SimpleNamespace

import pytest

from uagent.providers.llm_sakana_usage import sakana_responses_usage_to_dict
from uagent.providers.openai_compatible_runtime import _reported_usage


def test_fugu_orchestration_counts_reconcile_with_provider_total() -> None:
    usage = {
        "input_tokens": 120,
        "output_tokens": 80,
        "total_tokens": 245,
        "input_tokens_details": {
            "cached_tokens": 20,
            "orchestration_input_tokens": 30,
            "orchestration_input_cached_tokens": 10,
        },
        "output_tokens_details": {"orchestration_output_tokens": 15},
    }
    expected = {
        "input_tokens": 150,
        "output_tokens": 95,
        "total_tokens": 245,
        "cache_read_input_tokens": 30,
    }
    assert sakana_responses_usage_to_dict(usage) == expected
    assert _reported_usage(usage, responses=True, provider="sakana") == expected


def test_fugu_sdk_object_with_no_orchestration_uses_regular_usage() -> None:
    usage = SimpleNamespace(
        input_tokens=120,
        output_tokens=80,
        total_tokens=200,
        input_tokens_details=SimpleNamespace(cached_tokens=25),
    )
    assert sakana_responses_usage_to_dict(usage) == {
        "input_tokens": 120,
        "output_tokens": 80,
        "total_tokens": 200,
        "cache_read_input_tokens": 25,
    }


@pytest.mark.parametrize(
    ("usage", "expected"),
    [
        (None, {}),
        ({"input_tokens": True, "output_tokens": -1}, {}),
        ({"input_tokens": 17}, {"input_tokens": 17}),
        (
            {
                "input_tokens": 120,
                "output_tokens": 80,
                "total_tokens": 200,
                "input_tokens_details": {"orchestration_input_tokens": 30},
                "output_tokens_details": {"orchestration_output_tokens": 15},
            },
            {"input_tokens": 120, "output_tokens": 80, "total_tokens": 200},
        ),
        (
            {
                "input_tokens": 120,
                "output_tokens": 80,
                "total_tokens": 245,
                "input_tokens_details": {
                    "orchestration_input_tokens": 30,
                    "orchestration_input_cached_tokens": 40,
                },
                "output_tokens_details": {"orchestration_output_tokens": 15},
            },
            {"input_tokens": 150, "output_tokens": 95, "total_tokens": 245},
        ),
    ],
)
def test_fugu_missing_or_invalid_usage_is_not_invented(usage, expected) -> None:
    assert sakana_responses_usage_to_dict(usage) == expected
