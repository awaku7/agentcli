from __future__ import annotations

from uagent.providers.llm_meta_responses import apply_meta_responses_reasoning_summary


def test_meta_adds_reasoning_summary_with_effort() -> None:
    kwargs = {"reasoning": {"effort": "medium"}, "model": "muse-spark-1.3"}

    apply_meta_responses_reasoning_summary(kwargs, provider="meta")

    assert kwargs["reasoning"] == {"effort": "medium", "summary": "auto"}


def test_meta_does_not_send_summary_without_effort() -> None:
    kwargs: dict = {}

    apply_meta_responses_reasoning_summary(kwargs, provider="meta")

    assert kwargs == {}


def test_meta_reasoning_summary_is_noop_for_other_providers() -> None:
    kwargs = {"reasoning": {"effort": "medium"}}

    apply_meta_responses_reasoning_summary(kwargs, provider="openai")

    assert kwargs == {"reasoning": {"effort": "medium"}}
