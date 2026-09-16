from __future__ import annotations

from uagent.runtime.context_recovery import ContextRecoveryManager


def test_apply_legacy_bounded_rollback_mutates_projection_and_returns_metadata() -> (
    None
):
    messages = [
        {"role": "user", "content": "small"},
        {"role": "assistant", "content": "x" * 100},
        {"role": "tool", "content": "tail"},
    ]

    result = ContextRecoveryManager.apply_legacy_bounded_rollback(
        messages,
        lookback=3,
        notice_builder=lambda lookback, removed, size: {
            "role": "system",
            "content": f"rollback:{lookback}:{removed}:{size}",
        },
    )

    assert result == {"index": 1, "size": 136, "removed": 2}
    assert messages == [
        {"role": "user", "content": "small"},
        {"role": "system", "content": "rollback:3:2:136"},
    ]


__all__ = []
