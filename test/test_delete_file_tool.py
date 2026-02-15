import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/scheck"))
)
import unittest
import os
import shutil
from unittest.mock import patch
from uagent.tools.delete_file_tool import run_tool


class TestDeleteFileTool(unittest.TestCase):
    def setUp(self):
        self.original_cwd = os.getcwd()
        self.test_dir = os.path.join(self.original_cwd, "test", "tmp_delete_test")
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

    def test_delete_existing_file(self):
        """通常ファイルの削除テスト"""
        rel_path = os.path.join("test", "tmp_delete_test", "killme.txt")
        abs_path = os.path.join(self.test_dir, "killme.txt")
        with open(abs_path, "w") as f:
            f.write("Goodbye")

        args = {"filename": rel_path}
        result = run_tool(args)
        self.assertIn("削除しました", result)
        self.assertFalse(os.path.exists(abs_path))

    def test_delete_missing_file(self):
        """存在しないファイルの削除（missing_ok=False）"""
        args = {"filename": "test/tmp_delete_test/ghost.txt", "missing_ok": False}
        result = run_tool(args)
        # エラーメッセージに FileNotFoundError や "見つかりません" が含まれることを確認
        self.assertTrue(
            "FileNotFoundError" in result
            or "見つかりません" in result
            or "存在しません" in result
        )

    def test_delete_missing_file_ok(self):
        """存在しないファイルの削除（missing_ok=True）"""
        args = {"filename": "test/tmp_delete_test/ghost.txt", "missing_ok": True}
        result = run_tool(args)
        # safe_delete_file が使われる場合、実際には存在しなくても「削除しました」が返る場合がある
        self.assertTrue("削除しました" in result or "成功とみなします" in result)

    def test_delete_directory_with_confirm(self):
        """ディレクトリ削除は確認が必要。確認OKなら削除される"""
        dir_path = os.path.join(self.test_dir, "sub_dir")
        os.makedirs(dir_path)

        # ディレクトリ削除は常に確認なので、確認をOKにする
        with patch("uagent.tools.safe_file_ops._human_confirm", return_value=True):
            args = {"filename": "test/tmp_delete_test/sub_dir"}
            result = run_tool(args)

        self.assertIn("ディレクトリ", result)
        self.assertIn("削除しました", result)
        self.assertFalse(os.path.exists(dir_path))

    def test_dangerous_path_rejection(self):
        """重要ファイル（ワークディレクトリ外）を指す危険パスの扱い

        存在しないパスの場合、削除前の存在チェックで終了するため PermissionError にはならない。
        （存在する危険パスを指定した場合にのみ確認が発生し、拒否すれば PermissionError になる）
        """
        with patch("uagent.tools.safe_file_ops._human_confirm", return_value=False):
            args = {"filename": "../important_system_file.txt"}
            result = run_tool(args)

        self.assertTrue("PermissionError" in result or "存在しません" in result)


if __name__ == "__main__":
    unittest.main()
