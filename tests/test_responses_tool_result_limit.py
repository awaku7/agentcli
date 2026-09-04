from __future__ import annotations

from uagent.runtime.history import truncate_history_tool_result


def test_tool_result_uses_small_safe_default(monkeypatch) -> None:
    monkeypatch.delenv("UAGENT_TOOL_RESULT_MAX_CHARS", raising=False)
    monkeypatch.delenv("UAGENT_HISTORY_TOOL_RESULT_MAX_CHARS", raising=False)
    value = "a" * 20_000

    result = truncate_history_tool_result(value)

    assert len(result) == 12_000
    assert result.startswith("a")
    assert "original length=20000" in result
    assert result.endswith("a")


def test_tool_result_limit_is_configurable(monkeypatch) -> None:
    monkeypatch.delenv("UAGENT_TOOL_RESULT_MAX_CHARS", raising=False)
    monkeypatch.setenv("UAGENT_HISTORY_TOOL_RESULT_MAX_CHARS", "100")

    result = truncate_history_tool_result("0123456789" * 30)

    assert len(result) == 100
    assert "original length=300" in result
    assert result.startswith("0123")
    assert result.endswith("6789")


def test_primary_tool_result_limit_overrides_legacy(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_HISTORY_TOOL_RESULT_MAX_CHARS", "100")
    monkeypatch.setenv("UAGENT_TOOL_RESULT_MAX_CHARS", "80")

    result = truncate_history_tool_result("0123456789" * 30)

    assert len(result) == 80
    assert "original length=300" in result


def test_tool_result_limit_zero_disables_truncation(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_TOOL_RESULT_MAX_CHARS", "0")
    monkeypatch.delenv("UAGENT_HISTORY_TOOL_RESULT_MAX_CHARS", raising=False)
    value = "x" * 20_000

    assert truncate_history_tool_result(value) == value
