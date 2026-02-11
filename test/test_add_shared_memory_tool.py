import sys
import os
import unittest
import tempfile
import shutil
from unittest.mock import patch

# Add src/scheck to sys.path
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/scheck"))
)

from tools.add_shared_memory_tool import run_tool


class TestAddSharedMemoryTool(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.shared_file = os.path.join(self.test_dir, "shared.jsonl")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch("tools.shared_memory.is_enabled", return_value=True)
    @patch("tools.shared_memory.append_shared_memory")
    def test_run_tool_success(self, mock_append, mock_enabled):
        args = {"note": "This is a shared note."}
        result = run_tool(args)
        self.assertIn("共有長期記憶にメモを1件追記しました", result)
        self.assertIn("note=This is a shared note.", result)
        mock_append.assert_called_once_with("This is a shared note.")

    @patch("tools.shared_memory.is_enabled", return_value=False)
    def test_run_tool_disabled(self, mock_enabled):
        args = {"note": "Some note"}
        result = run_tool(args)
        self.assertIn("共有長期記憶は無効です", result)


if __name__ == "__main__":
    unittest.main()
