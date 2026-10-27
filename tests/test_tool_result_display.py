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

    # The developer shell may already export the opt-in; start from unset.
    monkeypatch.delenv("UAGENT_SHOW_TOOL_RESULTS", raising=False)
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
    assert (
        _tool_result_status({"timeout": True, "ok": False, "error": "expired"})
        == "timeout"
    )
    assert _tool_result_status({"timeout": False, "ok": False}) == "failed"
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


def test_powershell_truncation_keeps_localized_failure_status(monkeypatch) -> None:
    from uagent.runtime.history import truncate_output
    from uagent.tools import i18n_helper, pwsh_exec_tool

    monkeypatch.setattr(i18n_helper, "get_locale", lambda: "fr")
    monkeypatch.setattr(
        i18n_helper,
        "_load_tool_dict",
        lambda _path: {
            "fr": {
                "err.returncode": (
                    "[Erreur pwsh_exec] returncode=%(code)s\\nSTDOUT:\\n"
                    "%(stdout)s\\nSTDERR:\\n%(stderr)s"
                )
            }
        },
    )
    monkeypatch.setattr(pwsh_exec_tool.shutil, "which", lambda shell: shell)
    monkeypatch.setattr(pwsh_exec_tool, "decide_cmd_exec", None)
    monkeypatch.setattr(
        pwsh_exec_tool,
        "get_callbacks",
        lambda: SimpleNamespace(
            cmd_encoding="utf-8",
            cmd_exec_timeout_ms=120_000,
            truncate_output=truncate_output,
        ),
    )
    monkeypatch.setattr(
        pwsh_exec_tool.subprocess,
        "run",
        lambda **kwargs: SimpleNamespace(
            returncode=7, stdout="x" * 400_100, stderr="error"
        ),
    )

    result = pwsh_exec_tool.run_tool({"command": "example"})
    assert result.startswith("[Erreur pwsh_exec]")
    assert "[pwsh_exec truncated:" in result
    assert getattr(result, "_uag_execution_status", None) == "failed"


def test_display_mode_parsing_covers_default_and_localized() -> None:
    from uagent.runtime.tool_result_display import parse_tool_result_display_mode

    assert parse_tool_result_display_mode("") == 0
    assert parse_tool_result_display_mode("0") == 0
    assert parse_tool_result_display_mode("off") == 0
    assert parse_tool_result_display_mode("1") == 1
    assert parse_tool_result_display_mode("on") == 1
    assert parse_tool_result_display_mode("2") == 2
    assert parse_tool_result_display_mode("localized") == 2
    # Unknown values must not silently enable the display.
    assert parse_tool_result_display_mode("3") == 0
    assert parse_tool_result_display_mode("yes please") == 0


def test_mode_2_disables_the_result_line(monkeypatch) -> None:
    cli_core = SimpleNamespace(_is_web=False, IS_GUI=False)
    web_core = SimpleNamespace(_is_web=True, IS_GUI=False)

    # Mode 2 replaces the pre-execution [TOOL] trace with a localized action
    # sentence, so no post-execution result line is shown.
    monkeypatch.setenv("UAGENT_SHOW_TOOL_RESULTS", "2")
    assert _cli_tool_result_display_enabled(cli_core) is False
    assert _host_tool_result_display_enabled(web_core) is False

    monkeypatch.setenv("UAGENT_SHOW_TOOL_RESULTS", "1")
    assert _cli_tool_result_display_enabled(cli_core) is True
    assert _host_tool_result_display_enabled(web_core) is True


def test_bound_display_text_is_masked_and_bounded() -> None:
    from uagent.runtime.tool_result_display import bound_display_text

    assert len(bound_display_text("x" * 1000)) == 400
    masked = bound_display_text("api_key=abcd1234efgh")
    assert "abcd1234efgh" not in masked
    assert bound_display_text("  a\n\n b  ") == "a b"
    assert bound_display_text(None) == ""
    assert bound_display_text("x", max_chars=0) == ""


def test_build_tool_description_uses_registry_and_degrades_safely() -> None:
    from uagent import tools as tools_pkg

    def fake(args):
        return f"act:{args.get('k')}"

    def boom(args):
        raise RuntimeError("broken describer")

    tools_pkg._TOOL_DESCRIBERS["fake_tool"] = fake
    tools_pkg._TOOL_DESCRIBERS["boom_tool"] = boom
    tools_pkg._TOOL_DESCRIBERS["none_tool"] = lambda args: None
    try:
        assert tools_pkg.build_tool_description("fake_tool", {"k": 1}) == "act:1"
        assert tools_pkg.build_tool_description("boom_tool", {}) == ""
        assert tools_pkg.build_tool_description("none_tool", {}) == ""
        assert tools_pkg.build_tool_description("no_such_tool", {}) == ""
        assert tools_pkg.build_tool_description("fake_tool", None) == "act:None"
    finally:
        for name in ("fake_tool", "boom_tool", "none_tool"):
            tools_pkg._TOOL_DESCRIBERS.pop(name, None)


def test_trace_body_switches_with_display_mode(monkeypatch) -> None:
    from uagent import tools as tools_pkg

    tools_pkg._TOOL_DESCRIBERS["trace_probe"] = lambda args: "probe line"
    try:
        monkeypatch.delenv("UAGENT_SHOW_TOOL_RESULTS", raising=False)
        classic = tools_pkg._tool_trace_body("trace_probe", {"a": 1})
        assert classic == 'name=trace_probe args={"a":1}'

        monkeypatch.setenv("UAGENT_SHOW_TOOL_RESULTS", "1")
        assert tools_pkg._tool_trace_body("trace_probe", {"a": 1}) == classic

        monkeypatch.setenv("UAGENT_SHOW_TOOL_RESULTS", "2")
        assert tools_pkg._tool_trace_body("trace_probe", {"a": 1}) == "probe line"
        # A tool without a describer keeps the machine-readable body.
        assert tools_pkg._tool_trace_body("mystery", {"a": 1}).startswith(
            "name=mystery args="
        )
    finally:
        tools_pkg._TOOL_DESCRIBERS.pop("trace_probe", None)


def test_read_file_describer_is_localized(monkeypatch) -> None:
    from uagent.tools import i18n_helper, read_file_tool

    monkeypatch.setattr(i18n_helper, "get_locale", lambda: "ja")
    text = read_file_tool.describe({"filename": "src/a.py"})
    assert "src/a.py" in text
    assert read_file_tool.describe({}).count("?") == 1
