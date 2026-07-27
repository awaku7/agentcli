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
    assert set(action_prop["enum"]) == {"start", "stop", "status"}


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

        with patch("uagent.tools.pybitchat_subscribe_tool._ensure_dependencies") as mock_deps:
            mock_deps.return_value = True
            with patch("uagent.tools.pybitchat_shared._listener_loop"):
                result = mod.run_tool({
                    "action": "start",
                    "nickname": "testnode",
                    "network": "testnet",
                })

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
