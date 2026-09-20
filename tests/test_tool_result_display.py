from __future__ import annotations

from types import SimpleNamespace

import pytest

from uagent.llm_flow_helpers import (
    _cli_tool_result_display_enabled,
    _host_tool_result_display_enabled,
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


def test_host_tool_result_display_is_enabled_for_gui_and_web(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    web_core = SimpleNamespace(_is_web=True, IS_GUI=False)
    gui_core = SimpleNamespace(_is_web=False, IS_GUI=True)

    assert _host_tool_result_display_enabled(web_core) is False
    assert _host_tool_result_display_enabled(gui_core) is False
    assert (
        _host_tool_result_display_enabled(SimpleNamespace(_is_web=False, IS_GUI=False))
        is False
    )
    assert _host_tool_result_display_enabled(None) is False

    # GUI/Web use the same explicit opt-in as the CLI.
    monkeypatch.setenv("UAGENT_SHOW_TOOL_RESULTS", "1")
    assert _host_tool_result_display_enabled(web_core) is True
    assert _host_tool_result_display_enabled(gui_core) is True


def test_tool_result_status_classifies_common_results() -> None:
    assert _tool_result_status({"ok": True}) == "success"
    assert _tool_result_status({"ok": False, "error": "nope"}) == "failed"
    assert _tool_result_status({"status": "cancelled"}) == "cancelled"
    assert _tool_result_status("[tool runtime error] failed") == "failed"
    assert _tool_result_status("MCP_CANCELLED") == "cancelled"
    assert _tool_result_status("request timed out") == "timeout"
