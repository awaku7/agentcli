import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/scheck"))
)
import unittest
import os
from unittest.mock import patch, MagicMock
from uagent.tools.cmd_exec_tool import run_tool


class TestCmdExecTool(unittest.TestCase):
    def test_echo_command(self):
        """簡単なechoコマンドの実行テスト"""
        args = {"command": "echo Hello"}
        result = run_tool(args)
        # Windowsのechoは末尾に空白や改行が入ることがあるため strip() で比較
        self.assertIn("Hello", result)

    def test_command_failure(self):
        """失敗するコマンド（存在しないコマンドなど）のテスト"""
        # 存在しないコマンドを実行（OS依存を避けるため、無効な引数などで失敗させる）
        args = {"command": "dir non_existent_file_12345"}
        result = run_tool(args)
        self.assertIn("[cmd_exec error]", result)
        self.assertIn("returncode=", result)

    def test_timeout_handling(self):
        """タイムアウトのテスト"""
        # callbacksをモックしてタイムアウト時間を短く設定
        with patch("uagent.tools.cmd_exec_tool.get_callbacks") as mock_get_cb:
            mock_cb = MagicMock()
            mock_cb.cmd_exec_timeout_ms = 100  # 0.1秒
            mock_cb.cmd_encoding = "utf-8"
            mock_cb.truncate_output = None
            mock_get_cb.return_value = mock_cb

            # 2秒待機するコマンド
            args = {"command": 'python -c "import time; time.sleep(2)"'}
            result = run_tool(args)
            self.assertIn("[cmd_exec timeout]", result)

    def test_security_block(self):
        """危険なコマンドのブロックテスト"""
        # decide_cmd_exec をモックしてブロックをシミュレート
        with patch("uagent.tools.cmd_exec_tool.decide_cmd_exec") as mock_decide:
            mock_decision = MagicMock()
            mock_decision.allowed = False
            mock_decision.reason = "Dangerous command detected"
            mock_decide.return_value = mock_decision

            args = {"command": "rm -rf /"}
            result = run_tool(args)
            self.assertIn("[cmd_exec blocked]", result)
            self.assertIn("Dangerous command detected", result)


if __name__ == "__main__":
    unittest.main()
