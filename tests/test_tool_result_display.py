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
    from uagent.web_impl.io import web_tool_trace

    monkeypatch.setattr(tools_pkg.get_callbacks(), "tool_trace", web_tool_trace)

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


def test_browser_pre_execution_summary_explains_actions_without_echoing_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent.tools import browser_playwright_tool as browser_tool

    def use_english_defaults(_key, *, default, **kwargs):
        return default % kwargs if kwargs and isinstance(default, str) else default

    monkeypatch.setattr(browser_tool, "_", use_english_defaults)
    summary = browser_tool._describe_browser_action(
        {
            "actions": [
                {
                    "type": "goto",
                    "url": "https://user:password@example.invalid/landing?token=secret#fragment",
                },
                {"type": "fill", "selector": "#password", "value": "secret"},
                {"type": "click", "selector": "button"},
                {"type": "content"},
            ]
        }
    )
    assert "Perform browser actions" in summary
    assert "Open a page: https://example.invalid/landing?…" in summary
    assert "password" not in summary
    assert "secret" not in summary
    assert "Fill a field" in summary
    assert "Click an element" in summary
    assert "4 actions" in summary
    assert "secret" not in summary
    assert browser_tool._describe_browser_action({"session_action": "close"}) == (
        "Close the browser session."
    )
    assert "existing browser session" in browser_tool._describe_browser_action(
        {"session_action": "act", "actions": [{"type": "screenshot"}]}
    )


def test_web_tool_trace_does_not_fallback_to_other_rooms(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from uagent import core, tools as tools_pkg
    from uagent.web_impl import rooms
    from uagent.web_impl.io import web_tool_trace

    monkeypatch.setattr(tools_pkg.get_callbacks(), "tool_trace", web_tool_trace)
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


def test_apply_patch_describer_includes_target_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent.tools import apply_patch_tool

    monkeypatch.setattr(
        apply_patch_tool,
        "_",
        lambda _key, *, default, **kwargs: (
            default % kwargs if kwargs and isinstance(default, str) else default
        ),
    )

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

    reverse_preview = apply_patch_tool.describe(
        {"patch_text": patch_text, "dry_run": True, "revert": True}
    )
    reverse_apply = apply_patch_tool.describe(
        {"patch_text": patch_text, "dry_run": False, "revert": True}
    )
    assert "Preview" in reverse_preview
    assert "Reversing" in reverse_preview
    assert "Reversing" in reverse_apply

    deleted_patch = "\n".join(
        [
            "--- a/old.txt",
            "+++ /dev/null",
            "@@ -1 +0,0 @@",
            "-old",
        ]
    )
    restore_summary = apply_patch_tool.describe(
        {"patch_text": deleted_patch, "dry_run": True, "revert": True}
    )
    assert "old.txt" in restore_summary
    assert "(deleted)" not in restore_summary

    created_patch = "\n".join(
        [
            "--- /dev/null",
            "+++ b/new.txt",
            "@@ -0,0 +1 @@",
            "+new",
        ]
    )
    remove_summary = apply_patch_tool.describe(
        {"patch_text": created_patch, "dry_run": True, "revert": True}
    )
    assert "new.txt" in remove_summary
    assert "(deleted)" in remove_summary


def test_apply_patch_describer_names_deleted_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent.tools import apply_patch_tool

    monkeypatch.setattr(
        apply_patch_tool,
        "_",
        lambda _key, *, default, **kwargs: (
            default % kwargs if kwargs and isinstance(default, str) else default
        ),
    )

    patch_text = "\n".join(
        [
            "--- a/old_config.yaml",
            "+++ /dev/null",
            "@@ -1,2 +0,0 @@",
            "-key: value",
            "-foo: bar",
            "--- a/src/app.py",
            "+++ b/src/app.py",
            "@@ -1 +1 @@",
            "-x = 1",
            "+x = 2",
        ]
    )

    text = apply_patch_tool.describe({"patch_text": patch_text, "dry_run": False})
    assert "old_config.yaml" in text
    assert "src/app.py" in text


def test_rename_path_describer_includes_src_and_dst() -> None:
    from uagent.tools import rename_path_tool

    text = rename_path_tool.describe({"src": "old/a.txt", "dst": "new/b.txt"})
    assert "old/a.txt" in text
    assert "new/b.txt" in text
    assert rename_path_tool.describe({}).count("?") == 2


def test_change_workdir_describer_includes_new_dir() -> None:
    from uagent.tools import change_workdir_tool

    text = change_workdir_tool.describe({"new_dir": "src/project"})
    assert "src/project" in text
    assert change_workdir_tool.describe({}).count("?") == 1


def test_python_exec_describer_does_not_echo_source_code() -> None:
    from uagent.tools import python_exec_tool

    source = "password = 'SENSITIVE_SENTINEL_9381'"
    text = python_exec_tool.describe({"code": source})
    assert "Python" in text or "コード" in text
    assert source not in text
    assert "SENSITIVE_SENTINEL_9381" not in text


def test_analyze_image_describer_does_not_echo_path_or_prompt() -> None:
    from uagent.tools import analyze_image_tool

    text = analyze_image_tool.describe(
        {"img": "shots/chart.png", "prompt": "read the private title"}
    )
    assert "shots/chart.png" not in text
    assert "read the private title" not in text


def test_echonet_property_set_describer_includes_value() -> None:
    from uagent.tools import echonet_property_set_tool

    text = echonet_property_set_tool.describe(
        {"ip": "192.168.1.50", "obj": "013001", "epc": "80", "value": 1}
    )
    assert "192.168.1.50" in text
    assert "80" in text
    assert "1" in text


def test_echonet_property_set_describer_matches_execution_precedence() -> None:
    from uagent.tools import echonet_property_set_tool

    # edt wins over value at execution time; the announcement must too.
    text = echonet_property_set_tool.describe(
        {"ip": "192.168.1.50", "epc": "80", "value": 49, "edt": "30"}
    )
    assert "30" in text
    # eoj wins over obj; with neither, execution targets the node profile.
    text = echonet_property_set_tool.describe(
        {
            "ip": "192.168.1.50",
            "obj": "0290",
            "eoj": "013001",
            "epc": "80",
            "value": 1,
        }
    )
    assert "013001" in text
    assert "029001" not in text
    text = echonet_property_set_tool.describe(
        {"ip": "192.168.1.50", "epc": "80", "value": 1}
    )
    assert "0EF001" in text


def test_bacnet_write_describer_includes_value() -> None:
    from uagent.tools import bacnet_write_tool

    text = bacnet_write_tool.describe(
        {
            "ip": "192.168.1.60",
            "object_type": "analogValue",
            "object_instance": 3,
            "property_name": "presentValue",
            "value": 42.5,
        }
    )
    assert "192.168.1.60" in text
    assert "presentValue" in text
    assert "42.5" in text


def test_git_ops_describer_shows_operation_and_arguments() -> None:
    from uagent.tools.git_ops_tool import describe

    text = describe({"command": "add", "args": ["src/app.py"]})
    assert "git add" in text
    assert "src/app.py" in text

    dangerous = describe({"command": "reset", "args": ["--hard"], "allow_danger": True})
    assert "reset" in dangerous
    assert "--hard" in dangerous

    private_message = "SENSITIVE_COMMIT_NOTE_4731"
    commit = describe({"command": "commit", "args": ["-m", private_message]})
    assert "commit" in commit
    assert "<commit message omitted>" in commit
    assert private_message not in commit
    inline = describe({"command": "commit", "args": [f"--message={private_message}"]})
    assert private_message not in inline


def test_run_tests_describer_shows_framework_target_and_timeout() -> None:
    from uagent.tools.run_tests_tool import describe

    text = describe(
        {
            "framework": "pytest",
            "target": "tests/test_api.py",
            "cwd": "project",
            "timeout_sec": 45,
            "xargs": ["-k", "login"],
        }
    )
    assert "pytest" in text
    assert "tests/test_api.py" in text
    assert "project" in text
    assert "45" in text
    assert "-k login" in text


def test_composite_and_side_effect_tool_describers_explain_targets_and_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent.tools import (
        batch_state_tool,
        disc_image_ops_tool,
        echonet_control_tool,
        packet_probe_tool,
        packet_send_tool,
        switchbot_batch_tool,
        ucp_ap2_tool,
        ucp_cart_tool,
        ucp_checkout_tool,
    )

    def use_english_defaults(_key, *, default, **kwargs):
        return default % kwargs if kwargs and isinstance(default, str) else default

    modules = (
        batch_state_tool,
        disc_image_ops_tool,
        echonet_control_tool,
        packet_probe_tool,
        packet_send_tool,
        switchbot_batch_tool,
        ucp_ap2_tool,
        ucp_cart_tool,
        ucp_checkout_tool,
    )
    for module in modules:
        monkeypatch.setattr(module, "_", use_english_defaults)

    switchbot = switchbot_batch_tool.describe(
        {"commands": [{"devname": "Desk lamp", "action": "off"}]}
    )
    assert "Desk lamp" in switchbot
    assert "Turn off" in switchbot

    packet_preview = packet_send_tool.describe(
        {
            "action": "udp_send",
            "target": "192.0.2.10",
            "port": 9000,
            "payload": "secret payload",
            "count": 2,
        }
    )
    assert "Preview only" in packet_preview
    assert "192.0.2.10:9000" in packet_preview
    assert "2 send(s)" in packet_preview
    assert "secret payload" not in packet_preview

    probe = packet_probe_tool.describe(
        {"action": "tcp_connect", "target": "example.invalid", "port": 443}
    )
    assert "example.invalid" in probe
    assert "443" in probe

    echonet = echonet_control_tool.describe(
        {"ip": "192.0.2.20", "eoj": "013001", "action": "off"}
    )
    assert "192.0.2.20" in echonet
    assert "013001" in echonet

    disc = disc_image_ops_tool.describe(
        {"action": "convert", "path": "images/game.iso", "output": "out/game.chd"}
    )
    assert "images/game.iso" in disc
    assert "out/game.chd" in disc

    batch = batch_state_tool.describe(
        {
            "action": "init",
            "batch_id": "release-1",
            "targets": [{"dir": "src", "files": ["a.py", "b.py"]}],
        }
    )
    assert "release-1" in batch
    assert "a.py" in batch

    cart = ucp_cart_tool.describe(
        {
            "mode": "create",
            "business_url": "https://user:password@shop.example/store?token=private#fragment",
            "line_items": [{"item_id": "SKU-17", "quantity": 2}],
            "currency": "JPY",
        }
    )
    assert "https://shop.example/store?…" in cart
    assert "password" not in cart
    assert "private" not in cart
    assert "SKU-17" in cart
    assert "2" in cart

    checkout = ucp_checkout_tool.describe(
        {
            "mode": "complete",
            "business_url": "https://shop.example",
            "checkout_id": "checkout-9",
            "currency": "JPY",
        }
    )
    assert "checkout-9" in checkout
    assert "trigger payment" in checkout

    ap2 = ucp_ap2_tool.describe(
        {
            "mode": "mandate_create",
            "merchant_name": "Example Shop",
            "max_amount": 50000,
            "currency": "JPY",
            "ap2_token": "never-show-this-token",
        }
    )
    assert "Example Shop" in ap2
    assert "50000" in ap2
    assert "never-show-this-token" not in ap2


def test_external_communication_and_api_describers_show_targets_without_payloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent.tools import (
        a2a_send_tool,
        aws_api_tool,
        azure_api_tool,
        bluesky_tool,
        discord_channel_tool,
        gmail_send_tool,
        gcp_api_tool,
        http_request_tool,
        matter_control_tool,
        mqtt_publish_tool,
        pybitchat_send_tool,
        teams_webhook_tool,
    )

    def use_english_defaults(_key, *, default, **kwargs):
        return default % kwargs if kwargs and isinstance(default, str) else default

    modules = (
        a2a_send_tool,
        aws_api_tool,
        azure_api_tool,
        bluesky_tool,
        discord_channel_tool,
        gmail_send_tool,
        gcp_api_tool,
        http_request_tool,
        matter_control_tool,
        mqtt_publish_tool,
        pybitchat_send_tool,
        teams_webhook_tool,
    )
    for module in modules:
        monkeypatch.setattr(module, "_", use_english_defaults)

    post = bluesky_tool.describe(
        {"action": "post", "actor": "user.example", "text": "Public announcement"}
    )
    assert "user.example" in post
    assert "Public announcement" not in post

    email = gmail_send_tool.describe(
        {"to": "person@example.test", "subject": "Schedule", "body": "Meet at noon"}
    )
    assert "person@example.test" in email
    assert "Schedule" not in email
    assert "Meet at noon" not in email

    discord = discord_channel_tool.describe(
        {"action": "send", "channel_id": "12345", "message": "Deploy now"}
    )
    assert "12345" in discord
    assert "Deploy now" not in discord

    teams = teams_webhook_tool.describe(
        {"webhook_env": "TEAMS_WEBHOOK", "title": "Build", "message": "Passed"}
    )
    assert "TEAMS_WEBHOOK" in teams
    assert "Build" not in teams
    assert "Passed" not in teams

    mqtt = mqtt_publish_tool.describe(
        {
            "host": "broker.example",
            "topic": "devices/light/set",
            "payload": "ON",
            "retain": True,
        }
    )
    assert "broker.example" in mqtt
    assert "devices/light/set" in mqtt
    assert "ON" not in mqtt

    aws = aws_api_tool.describe(
        {
            "action": "call",
            "service": "s3",
            "operation": "PutObject",
            "region": "us-east-1",
            "parameters": {"Bucket": "archive"},
            "confirm_write": True,
        }
    )
    assert "service=s3" in aws
    assert "operation=PutObject" in aws
    assert "us-east-1" in aws
    assert "Bucket" in aws

    azure = azure_api_tool.describe(
        {
            "provider": "Microsoft.Storage",
            "method": "PUT",
            "resource": "/subscriptions/1/storage",
            "parameters": {"api-version": "2023"},
            "body": {"sku": "Standard"},
            "confirm_write": True,
        }
    )
    assert "PUT" in azure
    assert "Microsoft.Storage" in azure
    assert "storage" in azure

    gcp = gcp_api_tool.describe(
        {
            "action": "call",
            "api": "compute",
            "version": "v1",
            "method": "instances.insert",
            "resource": "projects/demo",
            "parameters": {"zone": "us-central1-a"},
        }
    )
    assert "compute.v1" in gcp
    assert "instances.insert" in gcp
    assert "projects/demo" in gcp

    a2a = a2a_send_tool.describe(
        {"profile": "review-agent", "message": "Please review this change"}
    )
    assert "review-agent" in a2a
    assert "Please review this change" not in a2a

    mesh = pybitchat_send_tool.describe(
        {"type": "text", "payload": "Hello mesh", "recipient": "peer-1", "via": "ble"}
    )
    assert "peer-1" in mesh
    assert "Hello mesh" not in mesh

    request = http_request_tool.describe(
        {
            "method": "POST",
            "url": "https://api.example.test/items?token=do-not-show",
            "query": {"page": 2},
            "body": {"name": "item"},
        }
    )
    assert "POST" in request
    assert "api.example.test/items" in request
    assert "do-not-show" not in request

    matter = matter_control_tool.describe(
        {"dev": "device-7", "action": "set_value", "value": 42, "ctrl": "ctrl-1"}
    )
    assert "device-7" in matter
    assert "set_value" in matter
    assert "42" in matter


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


def test_sensitive_payloads_are_not_echoed_in_action_summaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent.tools import (
        add_long_memory_tool,
        analyze_image_tool,
        python_exec_tool,
        update_long_memory_tool,
    )

    def use_english_defaults(_key, *, default, **kwargs):
        return default % kwargs if kwargs and isinstance(default, str) else default

    for module in (
        add_long_memory_tool,
        analyze_image_tool,
        python_exec_tool,
        update_long_memory_tool,
    ):
        monkeypatch.setattr(module, "_", use_english_defaults)

    secret = "SENSITIVE_SENTINEL_9381"
    summaries = [
        python_exec_tool.describe({"code": f"password = '{secret}'"}),
        analyze_image_tool.describe({"img": secret, "prompt": secret}),
        add_long_memory_tool.describe({"note": secret}),
        update_long_memory_tool.describe({"note": secret}),
    ]
    assert all(secret not in summary for summary in summaries)


def test_safe_display_url_hides_credentials_query_values_and_fragments() -> None:
    from uagent.tools.i18n_helper import safe_display_url

    safe = safe_display_url(
        "https://user:password@example.test/private?access_token=secret#fragment"
    )
    assert safe == "https://example.test/private?…"
    assert "password" not in safe
    assert "secret" not in safe
    assert safe_display_url("/items?page=private#details") == "/items?…"
    malformed = safe_display_url("https://user:password@[invalid/path?token=secret")
    assert "password" not in malformed
    assert "secret" not in malformed
    path_token = safe_display_url(
        "https://example.test/api/token/secret-value-123?mode=private"
    )
    assert path_token == "https://example.test/api/token/[redacted]?…"
    assert "secret-value-123" not in path_token
    opaque_id = safe_display_url(
        "https://example.test/items/1234567890abcdef1234567890abcdef"
    )
    assert opaque_id == "https://example.test/items/[redacted]"
