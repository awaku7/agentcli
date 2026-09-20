from __future__ import annotations


def test_add_long_memory_reports_save_failure(monkeypatch) -> None:
    from uagent.tools import long_memory
    from uagent.tools.add_long_memory_tool import run_tool

    monkeypatch.setattr(long_memory, "append_long_memory", lambda note: False)

    result = run_tool({"note": "must not be reported as saved"})

    assert "error" in result.lower()
    assert "saved" not in result.lower()


def test_long_memory_formatter_prefers_note_and_recent_records() -> None:
    from uagent.util_message import build_long_memory_system_message

    result = build_long_memory_system_message(
        [
            {"ts": 1, "note": "old note", "id": "old"},
            {"ts": 2, "note": "new note", "id": "new"},
        ]
    )
    content = result["content"]

    assert "new note" in content
    assert "old note" in content
    assert '"ts"' not in content
    assert '"id"' not in content
    assert content.index("new note") < content.index("old note")


def test_long_memory_formatter_respects_marker_in_4000_char_limit() -> None:
    from uagent.util_message import build_long_memory_system_message

    result = build_long_memory_system_message(
        [{"note": "x" * 5000}, {"note": "newest"}]
    )

    assert len(result["content"]) <= 4000
