import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/scheck"))
)
import unittest
from unittest.mock import patch, MagicMock
from uagent.tools.git_ops_tool import run_tool


class TestGitOpsTool(unittest.TestCase):
    @patch("subprocess.run")
    def test_git_status(self, mock_run):
        """git status のテスト"""
        mock_run.return_value = MagicMock(
            returncode=0, stdout=b"On branch main\nnothing to commit", stderr=b""
        )

        args = {"command": "status"}
        result = run_tool(args)

        self.assertIn("On branch main", result)
        mock_run.assert_called()
        self.assertEqual(mock_run.call_args[0][0][1], "status")

    @patch("subprocess.run")
    def test_git_log_default_n(self, mock_run):
        """git log のデフォルト件数制限テスト"""
        mock_run.return_value = MagicMock(
            returncode=0, stdout=b"commit 123", stderr=b""
        )

        args = {"command": "log"}
        run_tool(args)

        # コマンドに -n 10 が含まれているか
        executed_args = mock_run.call_args[0][0]
        self.assertIn("-n", executed_args)
        self.assertIn("10", executed_args)

    @patch("subprocess.run")
    def test_git_add_requirement(self, mock_run):
        """git add に引数が必要なことのテスト"""
        args = {"command": "add", "args": []}
        result = run_tool(args)
        self.assertIn("対象ファイルの指定が必要です", result)
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_git_commit_requirement(self, mock_run):
        """git commit にメッセージが必要なことのテスト"""
        args = {"command": "commit", "args": ["--amend"]}
        result = run_tool(args)
        self.assertIn("コミットメッセージが必要です", result)
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_git_command_failure(self, mock_run):
        """コマンド失敗時のハンドリング"""
        mock_run.return_value = MagicMock(
            returncode=128, stdout=b"", stderr=b"fatal: not a git repository"
        )

        args = {"command": "status"}
        result = run_tool(args)
        self.assertIn("[git_ops error]", result)
        self.assertIn("code=128", result)
        self.assertIn("fatal: not a git repository", result)

    @patch("subprocess.run")
    def test_git_not_found(self, mock_run):
        """git コマンドが存在しない場合"""
        mock_run.side_effect = FileNotFoundError()

        args = {"command": "status"}
        result = run_tool(args)
        self.assertIn("git コマンドが見つかりません", result)


if __name__ == "__main__":
    unittest.main()
