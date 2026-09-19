from __future__ import annotations

from types import SimpleNamespace

from uagent.llm_flow_helpers import (
    _cli_tool_result_display_enabled,
    _tool_result_status,
)


def test_tool_result_display_is_opt_in_and_cli_only(monkeypatch) -> None:
    core = SimpleNamespace(_is_web=False, IS_GUI=False)

    monkeypatch.delenv("UAGENT_SHOW_TOOL_RESULTS", raising=False)
    assert _cli_tool_result_display_enabled(core) is False

    monkeypatch.setenv("UAGENT_SHOW_TOOL_RESULTS", "1")
    assert _cli_tool_result_display_enabled(core) is True
    assert (
        _cli_tool_result_display_enabled(SimpleNamespace(_is_web=True, IS_GUI=False))
        is False
    )
    assert (
        _cli_tool_result_display_enabled(SimpleNamespace(_is_web=False, IS_GUI=True))
        is False
    )


def test_tool_result_status_classifies_common_results() -> None:
    assert _tool_result_status({"ok": True}) == "success"
    assert _tool_result_status({"ok": False, "error": "nope"}) == "failed"
    assert _tool_result_status({"status": "cancelled"}) == "cancelled"
    assert _tool_result_status("[tool runtime error] failed") == "failed"
    assert _tool_result_status("MCP_CANCELLED") == "cancelled"
    assert _tool_result_status("request timed out") == "timeout"
