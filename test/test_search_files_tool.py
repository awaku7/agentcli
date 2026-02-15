import sys
import os
import unittest
import shutil

# Add src/scheck to sys.path
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/scheck"))
)

from uagent.tools.search_files_tool import run_tool


class TestSearchFilesTool(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.join(os.getcwd(), "test_search_tmp")
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir)

        # Create test files
        os.makedirs(os.path.join(self.test_dir, "subdir"))
        with open(os.path.join(self.test_dir, "file1.txt"), "w", encoding="utf-8") as f:
            f.write("apple banana cherry")
        with open(
            os.path.join(self.test_dir, "subdir", "file2.py"), "w", encoding="utf-8"
        ) as f:
            f.write("import os\ndef hello(): print('hello')")
        with open(os.path.join(self.test_dir, "file3.md"), "w", encoding="utf-8") as f:
            f.write("# Title\ncontent here")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_search_by_name(self):
        args = {"root_path": self.test_dir, "name_pattern": "*.py"}
        result = run_tool(args)
        self.assertIn("file2.py", result)
        self.assertNotIn("file1.txt", result)

    def test_search_by_content(self):
        args = {"root_path": self.test_dir, "content_pattern": "banana"}
        result = run_tool(args)
        self.assertIn("file1.txt", result)
        self.assertIn("L1: apple banana cherry", result)
        self.assertNotIn("file2.py", result)

    def test_search_recursive(self):
        args = {"root_path": self.test_dir, "name_pattern": "*"}
        result = run_tool(args)
        self.assertIn("file1.txt", result)
        self.assertIn("file2.py", result)
        self.assertIn("file3.md", result)

    def test_max_results(self):
        args = {"root_path": self.test_dir, "max_results": 1}
        result = run_tool(args)
        # It should contain "Found 1 results" or "truncated"
        self.assertIn("Found 1 results", result)
        self.assertIn("(Results truncated to 1)", result)

    def test_grep_excludes_binary_by_default(self):
        # NUL を含むバイナリっぽいファイルを追加
        bin_path = os.path.join(self.test_dir, "bin.dat")
        with open(bin_path, "wb") as f:
            f.write(b"\x00\x01\x02apple\x00banana")

        args = {
            "root_path": self.test_dir,
            "name_pattern": "*",
            "content_pattern": "apple",
            "max_results": 50,
            # exclude_binary はデフォルト True だが明示
            "exclude_binary": True,
        }
        result = run_tool(args)
        self.assertIn("file1.txt", result)
        self.assertNotIn("bin.dat", result)

    def test_fast_read_and_streaming_paths_both_work(self):
        # 大きめテキストを作成（ただしテスト用に控えめ）
        big_path = os.path.join(self.test_dir, "big.txt")
        with open(big_path, "w", encoding="utf-8", newline="\n") as f:
            for i in range(2000):
                f.write(f"LINE{i} hello\n")

        # ほぼ確実に streaming 側
        args_stream = {
            "root_path": self.test_dir,
            "name_pattern": "*.txt",
            "content_pattern": "LINE1999",
            "max_results": 50,
            "exclude_binary": True,
            "fast_read_threshold_bytes": 1,
        }
        res_stream = run_tool(args_stream)
        self.assertIn("big.txt", res_stream)
        self.assertIn("LINE1999", res_stream)

        # full_read 側
        args_full = {
            "root_path": self.test_dir,
            "name_pattern": "*.txt",
            "content_pattern": "LINE1999",
            "max_results": 50,
            "exclude_binary": True,
            "fast_read_threshold_bytes": 10_000_000,
        }
        res_full = run_tool(args_full)
        self.assertIn("big.txt", res_full)
        self.assertIn("LINE1999", res_full)


if __name__ == "__main__":
    unittest.main()
