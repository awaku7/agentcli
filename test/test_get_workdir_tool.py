import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/scheck"))
)
import unittest
from uagent.tools.get_workdir_tool import run_tool


class TestGetWorkdirTool(unittest.TestCase):
    def test_get_workdir(self):
        """現在の作業ディレクトリが返るか"""
        result = run_tool({})
        self.assertEqual(result, os.getcwd())

    def test_get_workdir_change(self):
        """ディレクトリを変更した後に正しく反映されるか"""
        original = os.getcwd()
        temp_dir = os.path.join(original, "test", "tmp_workdir_test")
        os.makedirs(temp_dir, exist_ok=True)
        try:
            os.chdir(temp_dir)
            result = run_tool({})
            self.assertEqual(result, os.getcwd())
            self.assertIn("tmp_workdir_test", result)
        finally:
            os.chdir(original)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)


if __name__ == "__main__":
    unittest.main()
