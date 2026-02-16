import sys
import os
import unittest
import tempfile
import shutil

# モジュール検索パスに src/scheck を追加
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/scheck"))
)

from uagent.tools.rename_path_tool import run_tool


class TestRenamePathTool(unittest.TestCase):
    def setUp(self):
        # 現在のディレクトリを作業ディレクトリとして保存
        self.old_cwd = os.getcwd()
        # テスト用のディレクトリを作成
        self.test_dir = tempfile.mkdtemp()
        # テストディレクトリに移動 (safe_file_opsがgetcwdを参照するため)
        os.chdir(self.test_dir)

        # テスト用のファイルとディレクトリを作成
        self.src_file = "file.txt"
        with open(self.src_file, "w") as f:
            f.write("hello")

        self.src_dir = "subdir"
        os.mkdir(self.src_dir)
        with open(os.path.join(self.src_dir, "subfile.txt"), "w") as f:
            f.write("sub hello")

    def tearDown(self):
        # 作業ディレクトリを戻す
        os.chdir(self.old_cwd)
        import time

        # Windowsのファイルロック対策
        for _ in range(5):
            try:
                shutil.rmtree(self.test_dir)
                break
            except PermissionError:
                time.sleep(0.1)

    def test_rename_file_success(self):
        """ファイルの単純なリネーム"""
        dst = "renamed.txt"
        args = {"src": self.src_file, "dst": dst}
        result = run_tool(args)

        self.assertIn("[OK] renamed:", result)
        self.assertTrue(os.path.exists(dst))
        self.assertFalse(os.path.exists(self.src_file))
        with open(dst, "r") as f:
            self.assertEqual(f.read(), "hello")

    def test_rename_dir_success(self):
        """ディレクトリの単純なリネーム"""
        dst = "moved_dir"
        args = {"src": self.src_dir, "dst": dst}
        result = run_tool(args)

        self.assertIn("[OK] renamed:", result)
        self.assertTrue(os.path.exists(dst))
        self.assertTrue(os.path.isdir(dst))
        self.assertFalse(os.path.exists(self.src_dir))
        self.assertTrue(os.path.exists(os.path.join(dst, "subfile.txt")))

    def test_rename_with_mkdirs(self):
        """mkdirs=Trueでの移動（親ディレクトリ作成）"""
        dst = "nested/path/to/new_file.txt"
        args = {"src": self.src_file, "dst": dst, "mkdirs": True}
        result = run_tool(args)

        self.assertIn("[OK] renamed:", result)
        self.assertTrue(os.path.exists(dst))
        self.assertTrue(os.path.exists("nested/path/to"))

    def test_rename_fail_dst_exists(self):
        """dstが存在し、overwrite=Falseの場合のエラー"""
        dst = "existing.txt"
        with open(dst, "w") as f:
            f.write("existing")

        args = {"src": self.src_file, "dst": dst, "overwrite": False}
        result = run_tool(args)

        self.assertIn("[rename_path error] FileExistsError:", result)
        self.assertTrue(os.path.exists(self.src_file))
        with open(dst, "r") as f:
            self.assertEqual(f.read(), "existing")

    def test_rename_fail_src_not_found(self):
        """srcが存在しない場合のエラー"""
        args = {"src": "non_existent.txt", "dst": "new.txt"}
        result = run_tool(args)

        self.assertIn("[rename_path error] FileNotFoundError:", result)

    def test_rename_missing_args(self):
        """引数不足"""
        self.assertIn("ValueError", run_tool({"src": "file.txt"}))
        self.assertIn("ValueError", run_tool({"dst": "file.txt"}))


if __name__ == "__main__":
    unittest.main()
