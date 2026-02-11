import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/scheck"))
)
import unittest
import json
from unittest.mock import patch
from tools.lint_format_tool import run_tool


class TestLintFormatTool(unittest.TestCase):
    @patch("tools.lint_format_tool._cmd_exec_json")
    def test_lint_format_check(self, mock_exec):
        """検査モード(check)のテスト"""
        # mock version check for ruff
        mock_exec.side_effect = [
            ("ruff 0.0.1", "", 0, None),  # version check
            ("no issues", "", 0, None),  # actual run
        ]

        args = {"tools": ["ruff"], "mode": "check", "targets": ["file.py"]}
        result = json.loads(run_tool(args))

        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "check")
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["tool"], "ruff")
        self.assertIn("ruff check", result["results"][0]["command"])

    @patch("tools.lint_format_tool._human_confirm")
    @patch("tools.lint_format_tool._cmd_exec_json")
    def test_lint_format_fix_success(self, mock_exec, mock_confirm):
        """修正モード(fix)でユーザー同意ありのテスト"""
        mock_confirm.return_value = True
        mock_exec.return_value = ("fixed", "", 0, None)

        args = {"tools": ["black"], "mode": "fix", "targets": ["."]}
        result = json.loads(run_tool(args))

        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "fix")
        mock_confirm.assert_called_once()
        self.assertIn("black", result["results"][0]["command"])
        self.assertNotIn("--check", result["results"][0]["command"])

    @patch("tools.lint_format_tool._human_confirm")
    def test_lint_format_fix_cancel(self, mock_confirm):
        """修正モード(fix)でユーザーキャンセルした場合"""
        mock_confirm.return_value = False

        args = {"tools": ["black"], "mode": "fix"}
        result = json.loads(run_tool(args))

        self.assertFalse(result["ok"])
        self.assertIn("cancelled", result["error"])

    def test_shell_metacharacters(self):
        """危険なシェルメタ文字の拒否"""
        args = {"tools": ["ruff"], "extra_args": ["-v; rm -rf /"]}
        result = json.loads(run_tool(args))
        self.assertFalse(result["ok"])
        self.assertIn("metacharacters", result["error"])

    @patch("tools.lint_format_tool._tool_exists_py")
    @patch("tools.lint_format_tool._cmd_exec_json")
    def test_auto_select_tools(self, mock_exec, mock_exists):
        """ツール未指定時の自動選択"""
        # ruff と black が存在すると仮定
        mock_exists.side_effect = lambda m: m in ["ruff", "black"]
        mock_exec.return_value = ("ok", "", 0, None)

        args = {"tools": [], "mode": "check"}
        result = json.loads(run_tool(args))

        self.assertTrue(result["ok"])
        tools = [r["tool"] for r in result["results"]]
        self.assertIn("ruff", tools)
        self.assertIn("black", tools)
        self.assertNotIn("mypy", tools)

    def test_dangerous_path(self):
        """危険なターゲットパスの拒否"""
        args = {"targets": ["/etc/passwd"]}
        result = json.loads(run_tool(args))
        self.assertFalse(result["ok"])
        err = result["error"].lower()
        self.assertTrue("allowed" in err or "rejected" in err)


if __name__ == "__main__":
    unittest.main()
