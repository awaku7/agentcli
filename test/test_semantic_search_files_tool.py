import sys
import os
import unittest
import shutil
from unittest.mock import patch

# Add src/scheck to sys.path
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/scheck"))
)

from uagent.tools.semantic_search_files_tool import run_tool


class TestSemanticSearchFilesTool(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.join(os.getcwd(), "test_semantic_tmp")
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir)

        # Create some test files
        self.file1 = os.path.join(self.test_dir, "test1.txt")
        with open(self.file1, "w", encoding="utf-8") as f:
            f.write("The quick brown fox jumps over the lazy dog.")

        self.file2 = os.path.join(self.test_dir, "test2.md")
        with open(self.file2, "w", encoding="utf-8") as f:
            f.write(
                "# Python Programming\nPython is a high-level, interpreted programming language."
            )

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        # Clean up database created in ~/.scheck/dbs or similar if possible
        # but since we mock, it shouldn't be an issue.

    @patch(
        "uagent.tools.semantic_search_files_tool._is_embedding_api_reachable",
        return_value=True,
    )
    @patch("uagent.tools.semantic_search_files_tool._get_embedding")
    def test_run_tool_success(self, mock_get_embedding, mock_reachable):
        # Mock embedding response: a simple vector
        mock_get_embedding.return_value = [0.1] * 768

        args = {"query": "python language", "root_path": self.test_dir, "top_k": 2}

        result = run_tool(args)
        self.assertIn("検索クエリ: python language", result)
        self.assertIn("test2.md", result)
        self.assertIn("ヒット件数", result)

    def test_run_tool_no_query(self):
        args = {}
        result = run_tool(args)
        self.assertIn("エラー: query は必須です。", result)


if __name__ == "__main__":
    unittest.main()
