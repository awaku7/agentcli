from __future__ import annotations

import pytest

from uagent.providers.llm_deepseek import (
    _normalize_chat_image_content,
    _resolve_deepseek_effort,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Known effort values map to DeepSeek-valid reasoning_effort values.
        ("minimal", "high"),
        ("low", "high"),
        ("medium", "high"),
        ("high", "high"),
        ("xhigh", "max"),
        ("max", "max"),
        # Case-insensitive and whitespace-tolerant.
        ("HIGH", "high"),
        ("  Medium  ", "high"),
        ("XHIGH", "max"),
        ("\tminimal\n", "high"),
    ],
)
def test_resolve_deepseek_effort_maps(raw: str, expected: str) -> None:
    assert _resolve_deepseek_effort(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        # Thinking explicitly disabled.
        "off",
        "OFF",
        # Empty / blank input.
        "",
        "   ",
        # "auto" is resolved by the caller before this function.
        "auto",
        "Auto",
        # Unknown values are not in the map.
        "unknown",
        "none",
        "ultra",
    ],
)
def test_resolve_deepseek_effort_none(raw: str) -> None:
    assert _resolve_deepseek_effort(raw) is None


def test_normalize_responses_image_for_chat_completions() -> None:
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "describe"},
                {"type": "input_image", "image_url": "data:image/png;base64,abc"},
            ],
        }
    ]

    normalized = _normalize_chat_image_content(messages)

    assert normalized[0]["content"][1] == {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64,abc"},
    }
    assert messages[0]["content"][1]["type"] == "input_image"
