import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/scheck"))
)
import unittest
import json
import platform
from tools.get_os_tool import run_tool


class TestGetOsTool(unittest.TestCase):
    def test_get_os_format(self):
        """JSON形式で正しいOS名が返るか"""
        result_str = run_tool({})
        result = json.loads(result_str)
        self.assertIn("os_name", result)
        self.assertEqual(result["os_name"], platform.system())

    def test_get_os_mock(self):
        """モックを使用したテスト"""
        from unittest.mock import patch

        with patch("platform.system", return_value="SuperOS"):
            result_str = run_tool({})
            result = json.loads(result_str)
            self.assertEqual(result["os_name"], "SuperOS")


if __name__ == "__main__":
    unittest.main()
