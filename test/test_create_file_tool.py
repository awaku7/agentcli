import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/scheck"))
)
import unittest
import os
import shutil
from unittest.mock import patch
from tools.create_file_tool import run_tool


class TestCreateFileTool(unittest.TestCase):
    def setUp(self):
        self.original_cwd = os.getcwd()
        self.test_dir = os.path.join(self.original_cwd, "test", "tmp_create_test")
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

    def test_create_new_file(self):
        """新規ファイル作成のテスト"""
        rel_path = os.path.join("test", "tmp_create_test", "new.txt")
        args = {"filename": rel_path, "content": "Hello World", "overwrite": False}
        result = run_tool(args)
        self.assertIn("作成しました", result)

        abs_path = os.path.join(self.test_dir, "new.txt")
        self.assertTrue(os.path.exists(abs_path))
        with open(abs_path, "r") as f:
            self.assertEqual(f.read(), "Hello World")

    def test_create_with_auto_dirs(self):
        """ディレクトリの自動作成を伴うファイル作成"""
        rel_path = os.path.join("test", "tmp_create_test", "sub", "dir", "deep.txt")
        args = {"filename": rel_path, "content": "Deep content"}
        result = run_tool(args)
        self.assertIn("作成しました", result)
        self.assertTrue(
            os.path.exists(os.path.join(self.test_dir, "sub", "dir", "deep.txt"))
        )

    def test_overwrite_with_backup(self):
        """上書き時のバックアップ作成テスト"""
        rel_path = os.path.join("test", "tmp_create_test", "exists.txt")
        abs_path = os.path.join(self.test_dir, "exists.txt")

        with open(abs_path, "w") as f:
            f.write("Original")

        args = {"filename": rel_path, "content": "Updated", "overwrite": True}
        result = run_tool(args)
        self.assertIn("上書きしました", result)
        self.assertIn("バックアップ作成", result)
        self.assertTrue(os.path.exists(abs_path + ".org"))

    def test_prevent_overwrite_without_flag(self):
        """overwrite=False の場合に既存ファイルが守られるか"""
        rel_path = os.path.join("test", "tmp_create_test", "exists.txt")
        abs_path = os.path.join(self.test_dir, "exists.txt")
        with open(abs_path, "w") as f:
            f.write("Preserve me")

        args = {"filename": rel_path, "content": "Malicious", "overwrite": False}
        result = run_tool(args)
        self.assertIn("既に存在するため", result)

        with open(abs_path, "r") as f:
            self.assertEqual(f.read(), "Preserve me")

    def test_dangerous_path_rejection(self):
        """ワークディレクトリ外への作成拒否テスト（人間確認をシミュレート）"""
        # safe_file_ops._human_confirm を mock して False (キャンセル) を返す
        with patch("tools.safe_file_ops._human_confirm", return_value=False):
            args = {"filename": "../outside_create.txt", "content": "Secret"}
            result = run_tool(args)
            self.assertIn("PermissionError", result)


if __name__ == "__main__":
    unittest.main()
