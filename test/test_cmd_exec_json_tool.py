import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/scheck"))
)
import unittest
import json
import os
import shutil
from unittest.mock import patch, MagicMock
from tools.cmd_exec_json_tool import run_tool


class TestCmdExecJsonTool(unittest.TestCase):
    def setUp(self):
        self.original_cwd = os.getcwd()
        # ワークディレクトリ内にテスト用ディレクトリを作成
        self.test_dir = os.path.join(self.original_cwd, "test", "tmp_cmd_json_test")
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir)

    def tearDown(self):
        os.chdir(self.original_cwd)
        if os.path.exists(self.test_dir):
            try:
                shutil.rmtree(self.test_dir)
            except Exception:
                pass

    def test_echo_json(self):
        """JSON形式での正常実行テスト"""
        args = {"command": "echo Success"}
        result = json.loads(run_tool(args))
        self.assertTrue(result["ok"])
        self.assertEqual(result["returncode"], 0)
        self.assertIn("Success", result["stdout"])

    def test_cwd_execution(self):
        """cwd（ディレクトリ指定）での実行テスト"""
        with open(os.path.join(self.test_dir, "here.txt"), "w") as f:
            f.write("I am here")

        cmd = "dir" if os.name == "nt" else "ls"
        rel_test_dir = os.path.relpath(self.test_dir, self.original_cwd)

        args = {"command": cmd, "cwd": rel_test_dir}
        result = json.loads(run_tool(args))
        self.assertTrue(result["ok"])
        self.assertIn("here.txt", result["stdout"])

    def test_invalid_cwd(self):
        """ワークディレクトリ外のcwd指定を拒否するか"""
        args = {"command": "echo fail", "cwd": "../../../"}  # ワークディレクトリ外
        result = json.loads(run_tool(args))
        self.assertFalse(result["ok"])
        # "dangerous" または "not allowed" が含まれていれば拒否されているとみなす
        error_msg = result.get("error", "").lower()
        self.assertTrue("dangerous" in error_msg or "not allowed" in error_msg)

    def test_timeout_json(self):
        """JSON形式でのタイムアウト判定"""
        with patch("tools.cmd_exec_json_tool.get_callbacks") as mock_get_cb:
            mock_cb = MagicMock()
            mock_cb.cmd_exec_timeout_ms = 100
            mock_cb.cmd_encoding = "utf-8"
            mock_cb.truncate_output = None
            mock_get_cb.return_value = mock_cb

            args = {"command": 'python -c "import time; time.sleep(2)"'}
            result = json.loads(run_tool(args))
            self.assertFalse(result["ok"])
            self.assertTrue(result["timeout"])
            self.assertIn("timeout", result["message"])


if __name__ == "__main__":
    unittest.main()
