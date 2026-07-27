"""BLE スキャナー threading のテスト."""

from __future__ import annotations

from unittest.mock import patch


class TestBLEScanner:
    """BLE スキャナー threading の動作検証."""

    def test_start_stop_cycle(self) -> None:
        """start → stop のサイクル."""
        from uagent.tools.pybitchat_shared import start, stop

        with patch("uagent.tools.pybitchat_shared._listener_loop"):
            result = start("testnode", "testnet")

        assert result.get("ok") is True
        assert result.get("state") == "running"

        stop_result = stop()
        assert stop_result.get("ok") is True
        assert stop_result.get("state") == "stopped"

    def test_double_start(self) -> None:
        """二重起動はエラーにならず Already running を返す."""
        from uagent.tools.pybitchat_shared import start, stop

        with patch("uagent.tools.pybitchat_shared._listener_loop"):
            start("test", "testnet")
            result2 = start("test2", "mainnet")

        assert result2.get("state") == "running"
        assert "Already running" in result2.get("message", "")

        stop()

    def test_status_running(self) -> None:
        """起動中は status が running を返す."""
        from uagent.tools.pybitchat_shared import start, stop, status

        with patch("uagent.tools.pybitchat_shared._listener_loop"):
            start("test", "testnet")
            st = status()

        assert st.get("state") == "running"
        stop()

    def test_status_stopped(self) -> None:
        """停止後は status が stopped を返す."""
        from uagent.tools.pybitchat_shared import status

        st = status()
        assert st.get("state") == "stopped"
