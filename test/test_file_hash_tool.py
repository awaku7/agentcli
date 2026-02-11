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
import hashlib
from tools.file_hash_tool import run_tool


class TestFileHashTool(unittest.TestCase):
    def setUp(self):
        self.original_cwd = os.getcwd()
        self.test_dir = tempfile.mkdtemp()
        os.chdir(self.test_dir)

        self.file1 = "test1.txt"
        self.content1 = b"hello world"
        with open(self.file1, "wb") as f:
            f.write(self.content1)

        self.file2 = "test2.txt"
        self.content2 = b"foo bar"
        with open(self.file2, "wb") as f:
            f.write(self.content2)

    def tearDown(self):
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_sha256_single_file_json(self):
        """SHA256 (デフォルト) で単一ファイルを計算 (JSON)"""
        args = {"paths": [self.file1]}
        result_str = run_tool(args)
        result = json.loads(result_str)

        self.assertTrue(result["ok"])
        self.assertEqual(len(result["results"]), 1)
        r = result["results"][0]
        # ensure_within_workdir が絶対パスを返す可能性があるため basename で比較するか os.path.samefile を使用
        self.assertTrue(os.path.samefile(r["path"], self.file1))
        self.assertTrue(r["ok"])
        self.assertEqual(r["algo"], "sha256")

        expected_hash = hashlib.sha256(self.content1).hexdigest()
        self.assertEqual(r["hash"], expected_hash)
        self.assertEqual(r["size"], len(self.content1))

    def test_multiple_algorithms(self):
        """SHA1 と MD5 のテスト"""
        # SHA1
        result_sha1 = json.loads(run_tool({"paths": [self.file1], "algo": "sha1"}))
        self.assertEqual(
            result_sha1["results"][0]["hash"], hashlib.sha1(self.content1).hexdigest()
        )

        # MD5
        result_md5 = json.loads(run_tool({"paths": [self.file1], "algo": "md5"}))
        self.assertEqual(
            result_md5["results"][0]["hash"], hashlib.md5(self.content1).hexdigest()
        )

    def test_multiple_files(self):
        """複数ファイルの同時計算"""
        args = {"paths": [self.file1, self.file2]}
        result = json.loads(run_tool(args))
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["results"]), 2)

        # パスが絶対パスで返ってくるため、比較用に変換
        hashes = {}
        for r in result["results"]:
            for original in [self.file1, self.file2]:
                if os.path.samefile(r["path"], original):
                    hashes[original] = r["hash"]

        self.assertEqual(hashes[self.file1], hashlib.sha256(self.content1).hexdigest())
        self.assertEqual(hashes[self.file2], hashlib.sha256(self.content2).hexdigest())

    def test_text_format(self):
        """テキスト形式出力のテスト"""
        args = {"paths": [self.file1], "return": "text"}
        result = run_tool(args)
        expected_hash = hashlib.sha256(self.content1).hexdigest()
        self.assertIn(expected_hash, result)
        self.assertIn(self.file1, result)

    def test_file_not_found(self):
        """存在しないファイルの挙動"""
        args = {"paths": ["nonexistent.txt"]}
        result = json.loads(run_tool(args))
        self.assertFalse(result["ok"])
        self.assertFalse(result["results"][0]["ok"])
        self.assertEqual(result["results"][0]["error"], "file not found")

    def test_dangerous_path(self):
        """危険なパスの拒否"""
        # "../" などを含むパス
        args = {"paths": ["../../etc/passwd"]}
        result = json.loads(run_tool(args))
        self.assertFalse(result["ok"])
        # is_path_dangerous or ensure_within_workdir で拒否される
        self.assertIn(
            "rejected",
            result["results"][0]["error"].lower()
            + result["results"][0].get("error", ""),
        )

    def test_invalid_arguments(self):
        """無効な引数のエラーハンドリング"""
        # 空のパス
        self.assertFalse(json.loads(run_tool({"paths": []}))["ok"])
        # 無効なアルゴリズム
        self.assertFalse(
            json.loads(run_tool({"paths": [self.file1], "algo": "invalid"}))["ok"]
        )


if __name__ == "__main__":
    unittest.main()
