"""pybitchat_subscribe_tool の TDD テスト."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch


def test_tool_spec_structure() -> None:
    """pybitchat_subscribe_tool が正しい TOOL_SPEC をエクスポートする."""
    from uagent.tools import pybitchat_subscribe_tool as mod

    spec: dict[str, Any] = mod.TOOL_SPEC
    assert isinstance(spec, dict)
    assert spec.get("type") == "function"
    fn = spec.get("function", {})
    assert fn.get("name") == "pybitchat_subscribe"
    params = fn.get("parameters", {})
    assert params.get("type") == "object"
    props = params.get("properties", {})
    assert "action" in props
    action_prop = props["action"]
    assert "enum" in action_prop
    assert set(action_prop["enum"]) == {"start", "stop", "status", "chat_mode"}


def test_tool_has_run_tool() -> None:
    """pybitchat_subscribe_tool が run_tool() 関数を持つ."""
    from uagent.tools import pybitchat_subscribe_tool as mod

    assert hasattr(mod, "run_tool")
    assert callable(mod.run_tool)


class TestRunToolStartStop:
    """run_tool の start/stop/status の動作."""

    def test_status_when_stopped(self) -> None:
        """未起動時に status を呼ぶと stopped を返す."""
        from uagent.tools import pybitchat_subscribe_tool as mod

        result = mod.run_tool({"action": "status"})
        import json

        data = json.loads(result) if isinstance(result, str) else result
        assert data.get("state") == "stopped"

    def test_start_returns_ok(self) -> None:
        """start アクションが正常に応答する."""
        from uagent.tools import pybitchat_subscribe_tool as mod

        with patch(
            "uagent.tools.pybitchat_subscribe_tool._ensure_dependencies"
        ) as mock_deps:
            mock_deps.return_value = True
            with patch("uagent.tools.pybitchat_shared._listener_loop"):
                result = mod.run_tool(
                    {
                        "action": "start",
                        "nickname": "testnode",
                        "network": "testnet",
                    }
                )

                import json

                data = json.loads(result) if isinstance(result, str) else result
                assert data.get("ok") is True

        # Cleanup
        mod.run_tool({"action": "stop"})

    def test_stop_returns_ok(self) -> None:
        """stop アクションが正常に応答する."""
        from uagent.tools import pybitchat_subscribe_tool as mod

        result = mod.run_tool({"action": "stop"})
        import json

        data = json.loads(result) if isinstance(result, str) else result
        assert data.get("ok") is True
        assert data.get("state") == "stopped"


def test_cmd_specs_include_start_stop_peers() -> None:
    """CMD_SPECS に start/stop/peers サブコマンドが登録されている."""
    from uagent.tools import pybitchat_subscribe_tool as mod

    subcommands = [
        s.get("subcommand") for s in mod.CMD_SPECS if s.get("command") == "bitchat"
    ]
    assert "start" in subcommands
    assert "stop" in subcommands
    assert "peers" in subcommands


class TestCmdStartStop:
    """:bitchat start / stop ハンドラの動作."""

    def test_start_handler_prints_started(self, capsys: Any) -> None:
        """start ハンドラが開始メッセージを出力する."""
        from uagent.tools import pybitchat_subscribe_tool as mod

        with patch(
            "uagent.tools.pybitchat_subscribe_tool._ensure_dependencies"
        ) as mock_deps:
            mock_deps.return_value = True
            with patch("uagent.tools.pybitchat_shared._listener_loop"):
                mod._cmd_bitchat_start("testnode")
        out = capsys.readouterr().out
        assert "testnode" in out
        assert ("started" in out) or ("開始" in out)
        # Cleanup
        mod._cmd_bitchat_stop("")

    def test_start_handler_rejects_unknown_arg(self, capsys: Any) -> None:
        """start ハンドラが不明な引数をエラー表示する."""
        from uagent.tools import pybitchat_subscribe_tool as mod

        mod._cmd_bitchat_start("--bogus")
        out = capsys.readouterr().out
        assert ("Unknown argument" in out) or ("不明な引数" in out)

    def test_stop_handler_prints_stopped(self, capsys: Any) -> None:
        """stop ハンドラが停止メッセージを出力する."""
        from uagent.tools import pybitchat_subscribe_tool as mod

        mod._cmd_bitchat_stop("")
        out = capsys.readouterr().out
        assert ("stopped" in out) or ("停止" in out)


def test_dynamic_command_dispatch_start(capsys: Any) -> None:
    """handle_dynamic_command 経由で :bitchat start がディスパッチされる."""
    from uagent.tools import handle_dynamic_command

    with patch(
        "uagent.tools.pybitchat_subscribe_tool._ensure_dependencies"
    ) as mock_deps:
        mock_deps.return_value = True
        with patch("uagent.tools.pybitchat_shared._listener_loop"):
            res = handle_dynamic_command("bitchat", "start testnode")
    assert res is not None
    out = capsys.readouterr().out
    assert "testnode" in out
    # Cleanup
    handle_dynamic_command("bitchat", "stop")
