import sys
import os
import unittest
import tempfile
import shutil
import json

# モジュール検索パスに src/scheck を追加
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/scheck"))
)

from uagent.tools.zip_ops_tool import run_tool


class TestZipOpsTool(unittest.TestCase):
    def setUp(self):
        self.old_cwd = os.getcwd()
        self.test_dir = tempfile.mkdtemp()
        os.chdir(self.test_dir)

        # テスト用のファイルとディレクトリを作成
        self.src_file = "file.txt"
        with open(self.src_file, "w") as f:
            f.write("zip content")

        self.src_dir = "subdir"
        os.mkdir(self.src_dir)
        with open(os.path.join(self.src_dir, "subfile.txt"), "w") as f:
            f.write("sub zip content")

    def tearDown(self):
        os.chdir(self.old_cwd)
        import time

        for _ in range(5):
            try:
                shutil.rmtree(self.test_dir)
                break
            except PermissionError:
                time.sleep(0.1)

    def test_create_and_list_zip(self):
        """ZIP作成と一覧取得"""
        zip_path = "test.zip"
        args = {
            "action": "create",
            "zip_path": zip_path,
            "sources": [self.src_file, self.src_dir],
        }
        res_create_json = run_tool(args)
        res_create = json.loads(res_create_json)
        self.assertTrue(res_create["ok"])
        self.assertTrue(os.path.exists(zip_path))

        # list
        args_list = {"action": "list", "zip_path": zip_path}
        res_list_json = run_tool(args_list)
        res_list = json.loads(res_list_json)
        self.assertTrue(res_list["ok"])
        entries = [e["name"] for e in res_list["entries"]]
        self.assertIn("file.txt", entries)
        # os.walk の arcname 依存だが、subdir/subfile.txt が含まれているはず
        self.assertTrue(any("subfile.txt" in e for e in entries))

    def test_extract_zip(self):
        """ZIP展開"""
        zip_path = "test.zip"
        # 1. 作成
        run_tool({"action": "create", "zip_path": zip_path, "sources": [self.src_file]})

        # 2. 削除（展開確認のため）
        os.remove(self.src_file)

        # 3. 展開
        args_extract = {
            "action": "extract",
            "zip_path": zip_path,
            "dest_dir": "extracted",
        }
        res_extract_json = run_tool(args_extract)
        res_extract = json.loads(res_extract_json)
        self.assertTrue(res_extract["ok"])

        target = os.path.join("extracted", "file.txt")
        self.assertTrue(os.path.exists(target))
        with open(target, "r") as f:
            self.assertEqual(f.read(), "zip content")

    def test_extract_dry_run(self):
        """extractのdry_run"""
        zip_path = "test.zip"
        run_tool({"action": "create", "zip_path": zip_path, "sources": [self.src_file]})

        args_extract = {
            "action": "extract",
            "zip_path": zip_path,
            "dest_dir": "extracted_dry",
            "dry_run": True,
        }
        res_extract_json = run_tool(args_extract)
        res_extract = json.loads(res_extract_json)
        self.assertTrue(res_extract["ok"])
        self.assertTrue(res_extract["dry_run"])
        self.assertFalse(os.path.exists("extracted_dry"))

    def test_dangerous_path_rejected(self):
        """危険なパスの拒否"""
        # 絶対パス (Windowsなら C:\... など)
        bad_path = "/tmp/bad.zip" if os.name != "nt" else "C:\\bad.zip"
        args = {"action": "create", "zip_path": bad_path, "sources": [self.src_file]}
        res = json.loads(run_tool(args))
        self.assertFalse(res["ok"])
        self.assertIn("rejected", res["error"])

    def test_zip_bomb_protection(self):
        """Zip bomb 対策の確認"""
        zip_path = "bomb.zip"
        run_tool({"action": "create", "zip_path": zip_path, "sources": [self.src_file]})

        # max_files を 0 にして拒否させる
        args = {"action": "extract", "zip_path": zip_path, "max_files": 0}
        res = json.loads(run_tool(args))
        self.assertFalse(res["ok"])
        self.assertIn("too many files", res["error"])


if __name__ == "__main__":
    unittest.main()
