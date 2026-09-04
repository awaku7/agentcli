from __future__ import annotations

from uagent.providers.llm_meta_responses import apply_meta_responses_compat


def test_meta_responses_compat_removes_server_side_compaction() -> None:
    kwargs = {
        "context_management": [
            {"type": "compaction", "compact_threshold": 1000}
        ],
        "model": "muse-spark-1.3",
    }

    apply_meta_responses_compat(
        kwargs,
        provider="meta",
        depname="muse-spark-1.3",
    )

    assert "context_management" not in kwargs


def test_meta_responses_compat_does_not_modify_other_providers() -> None:
    kwargs = {"context_management": [{"type": "compaction"}]}

    apply_meta_responses_compat(kwargs, provider="openai", depname="gpt-5.4-nano")

    assert "context_management" in kwargs
