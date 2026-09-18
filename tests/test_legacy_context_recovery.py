from __future__ import annotations

from uagent.runtime.legacy_context_recovery import rollback_largest_recent_history


def test_rollback_largest_recent_history_adds_shared_notice(monkeypatch) -> None:
    monkeypatch.setattr(
        "uagent.runtime.legacy_context_recovery._",
        lambda _key, *, default, **values: default % values,
    )
    messages = [
        {"role": "user", "content": "small"},
        {"role": "tool", "content": "x" * 100},
        {"role": "assistant", "content": "after"},
    ]

    result = rollback_largest_recent_history(messages, lookback=3)

    assert result == {"index": 1, "size": 131, "removed": 2}
    assert messages[0] == {"role": "user", "content": "small"}
    assert messages[1]["role"] == "system"
    assert messages[1]["_uagent_internal"] is True
    assert "2 message(s)" in messages[1]["content"]
