import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/scheck"))
)
import unittest
import os
import shutil
from tools.read_file_tool import run_tool


class TestReadFileTool(unittest.TestCase):
    def setUp(self):
        self.original_cwd = os.getcwd()
        self.test_dir = os.path.join(self.original_cwd, "test", "tmp_read_test")
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir)

        # テキストファイルの作成 (LF) - 1行ごとに改行を入れる
        self.lf_file = os.path.join(self.test_dir, "test_lf.txt")
        with open(self.lf_file, "w", newline="\n", encoding="utf-8") as f:
            f.write("line 1\nline 2\nline 3\nline 4\nline 5\n")

        # テキストファイルの作成 (CRLF) - 1行ごとに改行を入れる
        self.crlf_file = os.path.join(self.test_dir, "test_crlf.txt")
        # FIX: バイナリモードで書き込むことで、意図しない二重改行を防ぐ
        with open(self.crlf_file, "wb") as f:
            f.write(b"line 1\r\nline 2\r\nline 3\r\nline 4\r\nline 5\r\n")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            try:
                shutil.rmtree(self.test_dir)
            except Exception:
                pass

    def test_read_full(self):
        """ファイル全体の読み取りテスト"""
        args = {"filename": self.lf_file}
        result = run_tool(args)
        self.assertEqual(result, "line 1\nline 2\nline 3\nline 4\nline 5\n")

    def test_read_start_line(self):
        """開始行指定のテスト"""
        args = {"filename": self.lf_file, "start_line": 3}
        result = run_tool(args)
        # 3行目以降
        self.assertEqual(result, "line 3\nline 4\nline 5\n")

    def test_read_max_lines(self):
        """最大行数指定のテスト"""
        args = {"filename": self.lf_file, "start_line": 2, "max_lines": 2}
        result = run_tool(args)
        # 2行目から2行分
        self.assertEqual(result, "line 2\nline 3\n")

    def test_read_crlf_normalization(self):
        """CRLFファイルの正規化読み取りテスト"""
        args = {"filename": self.crlf_file, "start_line": 2, "max_lines": 2}
        result = run_tool(args)
        # デバッグ用
        if result != "line 2\nline 3\n":
            print(f"\nDEBUG: result={repr(result)}")
        # ツール内で newline=None により正規化されているため、出力は \n になる
        self.assertEqual(result, "line 2\nline 3\n")

    def test_read_out_of_range(self):
        """範囲外の開始行を指定したテスト"""
        args = {"filename": self.lf_file, "start_line": 10}
        result = run_tool(args)
        self.assertIn("out of range", result)

    def test_read_encoding_fallback(self):
        """Shift-JIS ファイルの読み取りテスト"""
        sjis_file = os.path.join(self.test_dir, "test_sjis.txt")
        content = "あいうえお"
        with open(sjis_file, "w", encoding="cp932") as f:
            f.write(content)

        args = {"filename": sjis_file}
        result = run_tool(args)
        self.assertEqual(result, content)

    def test_read_head_lines(self):
        """head_lines 指定のテスト"""
        args = {"filename": self.lf_file, "head_lines": 3}
        result = run_tool(args)
        self.assertEqual(result, "line 1\nline 2\nline 3\n")

    def test_read_tail_lines(self):
        """tail_lines 指定のテスト"""
        args = {"filename": self.lf_file, "tail_lines": 2}
        result = run_tool(args)
        self.assertEqual(result, "line 4\nline 5\n")

    def test_read_tail_lines_small_file(self):
        """tail_lines がファイル行数を超える場合のテスト"""
        args = {"filename": self.lf_file, "tail_lines": 10}
        result = run_tool(args)
        # ファイル全体が返る
        self.assertEqual(result, "line 1\nline 2\nline 3\nline 4\nline 5\n")

    def test_read_head_tail_error(self):
        """head_lines と tail_lines を同時に指定した場合のエラーテスト"""
        args = {"filename": self.lf_file, "head_lines": 2, "tail_lines": 2}
        result = run_tool(args)
        self.assertIn("cannot be specified together", result)


if __name__ == "__main__":
    unittest.main()
