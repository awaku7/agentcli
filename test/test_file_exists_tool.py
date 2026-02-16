import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/scheck"))
)
import unittest
import os
import shutil
import tempfile
from uagent.tools.file_exists_tool import run_tool


class TestFileExistsTool(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.test_dir, "test.txt")
        with open(self.test_file, "w") as f:
            f.write("hello")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_file_exists_true(self):
        """存在するファイルのテスト"""
        args = {"path": self.test_file}
        result = run_tool(args)
        self.assertIn("exists=True", result)
        self.assertIn("is_dir=False", result)
        self.assertIn("size=5 bytes", result)

    def test_directory_exists_true(self):
        """存在するディレクトリのテスト"""
        args = {"path": self.test_dir}
        result = run_tool(args)
        self.assertIn("exists=True", result)
        self.assertIn("is_dir=True", result)
        self.assertIn("size=n/a (directory)", result)

    def test_not_exists(self):
        """存在しないパスのテスト"""
        args = {"path": os.path.join(self.test_dir, "ghost.txt")}
        result = run_tool(args)
        self.assertIn("exists=False", result)

    def test_empty_path(self):
        """パスが空の場合のエラーハンドリング"""
        args = {"path": ""}
        result = run_tool(args)
        self.assertIn("[file_exists error]", result)
        self.assertIn("path が空です", result)

    def test_tilde_expansion(self):
        """チルダ展開のテスト (mocking os.path.expanduser)"""
        from unittest.mock import patch

        with patch("os.path.expanduser") as mock_expand:
            mock_expand.return_value = self.test_file
            args = {"path": "~/test.txt"}
            result = run_tool(args)
            self.assertIn("exists=True", result)
            mock_expand.assert_called_with("~/test.txt")


if __name__ == "__main__":
    unittest.main()
