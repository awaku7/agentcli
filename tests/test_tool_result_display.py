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
    from uagent.runtime.tool_result_display import tool_result_display_mode

    tools_pkg._TOOL_DESCRIBERS["trace_probe"] = lambda args: "probe line"
    try:
        monkeypatch.delenv("UAGENT_SHOW_TOOL_RESULTS", raising=False)
        assert tool_result_display_mode() == 2
        assert tools_pkg._tool_trace_body("trace_probe", {"a": 1}) == "probe line"

        monkeypatch.setenv("UAGENT_SHOW_TOOL_RESULTS", "0")
        classic = tools_pkg._tool_trace_body("trace_probe", {"a": 1})
        assert classic == 'name=trace_probe args={"a":1}'

        monkeypatch.setenv("UAGENT_SHOW_TOOL_RESULTS", "1")
        assert tools_pkg._tool_trace_body("trace_probe", {"a": 1}) == classic

        monkeypatch.setenv("UAGENT_SHOW_TOOL_RESULTS", "2")
        assert tools_pkg._tool_trace_body("trace_probe", {"a": 1}) == "probe line"
        # Tools without a describer get a generic, compact action summary.
        generic = tools_pkg._tool_trace_body(
            "mystery",
            {
                "action": "read",
                "path": "src/a.py",
                "dry_run": True,
                "payload": "private content",
            },
        )
        assert "mystery" in generic
        assert 'action="read"' in generic
        assert 'path="src/a.py"' in generic
        assert "dry_run" not in generic
        assert "About to use mystery" in generic or "mystery を実行します" in generic
        assert "payload=<15 chars>" in generic
        assert len(generic) < 150
        assert "private content" not in generic
    finally:
        tools_pkg._TOOL_DESCRIBERS.pop("trace_probe", None)


def test_web_tool_trace_uses_the_cli_description_without_raw_results(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from uagent import core, tools as tools_pkg
    from uagent.web_impl import rooms

    displayed = []
    room = SimpleNamespace(add_message=displayed.append)
    monkeypatch.setenv("UAGENT_SHOW_TOOL_RESULTS", "2")
    monkeypatch.setattr(core, "_is_web", True, raising=False)
    monkeypatch.setattr(core, "IS_GUI", False, raising=False)
    monkeypatch.setattr(rooms, "get_context_web_room", lambda: room)
    monkeypatch.setattr(tools_pkg, "_spinner_stop_quietly", lambda: None)
    monkeypatch.setitem(
        tools_pkg._TOOL_DESCRIBERS,
        "web_trace_probe",
        lambda _args: "Reading file api_key=abcd1234efgh",
    )

    tools_pkg._emit_tool_trace("web_trace_probe", {"content": "private payload"})

    assert len(displayed) == 1
    assert displayed[0]["role"] == "tool"
    assert displayed[0]["name"] == "web_trace_probe"
    assert "Reading file" in displayed[0]["content"]
    assert "abcd1234efgh" not in displayed[0]["content"]
    assert len(displayed[0]["content"]) <= 400
    assert "[TOOL]" not in capsys.readouterr().out


def test_web_tool_trace_does_not_fallback_to_other_rooms(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from uagent import core, tools as tools_pkg
    from uagent.web_impl import rooms

    monkeypatch.setenv("UAGENT_SHOW_TOOL_RESULTS", "2")
    monkeypatch.setattr(core, "_is_web", True, raising=False)
    monkeypatch.setattr(rooms, "get_context_web_room", lambda: None)
    monkeypatch.setattr(rooms._thread_ctx, "room", None, raising=False)
    monkeypatch.setattr(tools_pkg, "_spinner_stop_quietly", lambda: None)

    tools_pkg._emit_tool_trace("web_trace_probe", {"path": "src/example.py"})

    assert "[TOOL]" not in capsys.readouterr().out


def test_read_file_describer_is_localized(monkeypatch) -> None:
    from uagent.tools import i18n_helper, read_file_tool

    monkeypatch.setattr(i18n_helper, "get_locale", lambda: "ja")
    text = read_file_tool.describe({"filename": "src/a.py"})
    assert "src/a.py" in text
    assert read_file_tool.describe({}).count("?") == 1


def test_apply_patch_describer_includes_target_paths() -> None:
    from uagent.tools import apply_patch_tool

    patch_text = "\n".join(
        [
            "--- a/src/alpha.py",
            "+++ b/src/alpha.py",
            "@@ -1 +1 @@",
            "-old",
            "+new",
            "--- a/src/beta.py",
            "+++ b/src/beta.py",
            "@@ -1 +1 @@",
            "-before",
            "+after",
        ]
    )

    preview = apply_patch_tool.describe({"patch_text": patch_text, "dry_run": True})
    apply = apply_patch_tool.describe({"patch_text": patch_text, "dry_run": False})

    assert "src/alpha.py" in preview
    assert "src/beta.py" in preview
    assert "src/alpha.py" in apply
    assert "src/beta.py" in apply
    assert "Preview" in preview or "プレビュー" in preview
    assert "Applying" in apply or "適用" in apply


def test_generic_tool_action_uses_localized_schema_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent import tools as tools_pkg
    from uagent.tools import i18n_helper

    spec = {
        "function": {
            "name": "generic_schema_probe",
            "description": "ファイルを読み取る",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "対象ファイル"},
                    "message": {"type": "string", "description": "自由形式テキスト"},
                },
            },
        }
    }
    tools_pkg.TOOL_SPECS.append(spec)
    monkeypatch.setattr(i18n_helper, "get_locale", lambda: "ja")
    try:
        preview = tools_pkg._generic_tool_action(
            "generic_schema_probe",
            {"path": "src/target.txt", "message": "private message"},
        )
    finally:
        tools_pkg.TOOL_SPECS.remove(spec)

    assert "generic_schema_probe を実行します" in preview
    assert 'path="src/target.txt"' in preview
    assert "message=<15 chars>" in preview
    assert "ファイルを読み取る" not in preview
    assert "対象ファイル" not in preview
    assert "自由形式テキスト" not in preview
    assert "private message" not in preview
    assert len(preview) < 120


def test_human_ask_trace_remains_suppressed_in_all_display_modes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent import tools as tools_pkg

    previous = tools_pkg._TOOL_TRACE_FLAGS.get("human_ask")
    tools_pkg._TOOL_TRACE_FLAGS["human_ask"] = False
    try:
        for mode in ("0", "1", "2"):
            monkeypatch.setenv("UAGENT_SHOW_TOOL_RESULTS", mode)
            assert tools_pkg._should_emit_tool_trace("human_ask") is False
    finally:
        if previous is None:
            tools_pkg._TOOL_TRACE_FLAGS.pop("human_ask", None)
        else:
            tools_pkg._TOOL_TRACE_FLAGS["human_ask"] = previous
