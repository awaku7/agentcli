import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/scheck"))
)
import unittest
import json
import os
import shutil
import tempfile
from tools.find_large_files_tool import run_tool


class TestFindLargeFilesTool(unittest.TestCase):
    def setUp(self):
        self.original_cwd = os.getcwd()
        self.test_dir = tempfile.mkdtemp()
        os.chdir(self.test_dir)

        # テスト用ファイル作成
        os.makedirs("subdir", exist_ok=True)
        os.makedirs(".git", exist_ok=True)

        # 100バイト
        with open("small.txt", "wb") as f:
            f.write(b"a" * 100)
        # 1000バイト
        with open("large.txt", "wb") as f:
            f.write(b"b" * 1000)
        # 2000バイト
        with open("subdir/huge.log", "wb") as f:
            f.write(b"c" * 2000)
        # 5000バイト (.git 内 - 除外対象)
        with open(".git/hidden.bin", "wb") as f:
            f.write(b"d" * 5000)

    def tearDown(self):
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_find_large_files_basic(self):
        """基本的な検索 (min_bytes を下げてテスト)"""
        args = {"root": ".", "min_bytes": 500, "exclude_dirs": [".git"]}
        result = json.loads(run_tool(args))

        self.assertTrue(result["ok"])
        # large.txt (1000) と huge.log (2000) が見つかるはず。 hidden.bin は .git なので除外
        paths = [f["path"] for f in result["files"]]
        self.assertEqual(len(paths), 2)
        self.assertTrue(any(p.endswith("large.txt") for p in paths))
        self.assertTrue(any(p.endswith("huge.log") for p in paths))
        self.assertFalse(any(p.endswith("hidden.bin") for p in paths))

    def test_top_n(self):
        """上位N件の制限"""
        args = {"root": ".", "min_bytes": 100, "top_n": 1, "exclude_dirs": [".git"]}
        result = json.loads(run_tool(args))
        self.assertEqual(len(result["files"]), 1)
        self.assertEqual(result["files"][0]["bytes"], 2000)  # huge.log がトップ

    def test_exclude_dirs(self):
        """除外ディレクトリのテスト"""
        # subdir と .git を除外
        args = {"root": ".", "min_bytes": 500, "exclude_dirs": ["subdir", ".git"]}
        result = json.loads(run_tool(args))
        paths = [f["path"] for f in result["files"]]
        self.assertEqual(len(paths), 1)
        self.assertTrue(paths[0].endswith("large.txt"))
        self.assertFalse(any("huge.log" in p for p in paths))

    def test_group_by_ext(self):
        """拡張子別集計"""
        args = {"root": ".", "min_bytes": 100, "group_by_ext": True}
        result = json.loads(run_tool(args))
        stats = {s["ext"]: s for s in result["ext_stats"]}

        self.assertIn(".txt", stats)
        self.assertIn(".log", stats)
        self.assertEqual(stats[".txt"]["count"], 2)  # small.txt, large.txt
        self.assertEqual(stats[".txt"]["bytes"], 1100)

    def test_max_files(self):
        """最大ファイル数制限"""
        args = {"root": ".", "max_files": 1}
        result = json.loads(run_tool(args))
        # 2つ目のファイル走査時にエラーになるはず (最初のファイル + 次)
        # 実際には 2つ目の fn in filenames で判定
        self.assertFalse(result["ok"])
        self.assertIn("max_files exceeded", result["error"])

    def test_dangerous_root(self):
        """危険なルートパスの拒否"""
        args = {"root": "../../"}
        result = json.loads(run_tool(args))
        self.assertFalse(result["ok"])
        # "allowed" か "rejected" のいずれかが含まれることを確認
        err = result["error"].lower()
        self.assertTrue("allowed" in err or "rejected" in err)


if __name__ == "__main__":
    unittest.main()
