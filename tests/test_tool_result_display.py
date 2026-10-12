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
    assert _tool_result_status({"cancelled": True}) == "cancelled"
    assert _tool_result_status({"timed_out": True, "cancelled": True}) == "timeout"
    assert _tool_result_status({"timed_out": False, "cancelled": False}) == "success"
    assert _tool_result_status("[tool runtime error] failed") == "failed"
    assert _tool_result_status("[tool argument error] bad alias") == "failed"
    assert _tool_result_status("[tool error] unknown tool") == "failed"
    assert _tool_result_status("  Error: plugin failed") == "failed"
    assert _tool_result_status("エラー: コマンドを実行できません") == "failed"
    assert _tool_result_status("[ツール引数エラー] 引数不正") == "failed"
    assert _tool_result_status("[ツール実行時エラー] 実行失敗") == "failed"
    assert _tool_result_status("[get_env error] missing") == "failed"
    assert _tool_result_status("[tool policy] confirmation denied") == "failed"
    assert _tool_result_status({"status": "blocked"}) == "failed"
    assert _tool_result_status({"status": "timed_out"}) == "timeout"
    assert _tool_result_status("timeout: tool request expired") == "timeout"
    assert _tool_result_status("[python_exec timeout] exceeded limit") == "timeout"
    assert _tool_result_status("MCP_CANCELLED") == "cancelled"
    assert _tool_result_status("request timed out") == "success"
    assert _tool_result_status("timeout = 30; cancelled = False") == "success"
    assert _tool_result_status("source code: request cancelled") == "success"


def test_translated_tool_errors_keep_explicit_status(monkeypatch) -> None:
    from uagent.tools import i18n_helper

    monkeypatch.setattr(i18n_helper, "get_locale", lambda: "fr")
    monkeypatch.setattr(
        i18n_helper,
        "_load_tool_dict",
        lambda _path: {"fr": {"err.path_required": "Erreur : 'path' est requis."}},
    )
    translate = i18n_helper.make_tool_translator(__file__)
    message = translate("err.path_required", default="Error: path is required.")
    assert str(message) == "Erreur : 'path' est requis."
    assert message._uag_execution_status == "failed"
    assert message.format()._uag_execution_status == "failed"

    # bash_exec formats with .format(); pwsh_exec uses % interpolation.
    bash_timeout = translate(
        "err.timeout",
        default="[bash_exec timeout] exceeded {seconds}s",
    )
    assert bash_timeout.format(seconds=12)._uag_execution_status == "timeout"
    pwsh_timeout = translate(
        "err.timeout",
        default="[pwsh_exec timeout] exceeded %(seconds)s seconds",
    )
    assert (pwsh_timeout % {"seconds": 12})._uag_execution_status == "timeout"
    assert str(bash_timeout.format(seconds=12)).startswith("[bash_exec timeout]")
    assert str(pwsh_timeout % {"seconds": 12}).startswith("[pwsh_exec timeout]")

    complete = translate("msg.completed", default="Processed {count} files.")
    assert complete.format(count=2) == "Processed 2 files."
    assert getattr(complete, "_uag_execution_status", None) is None
