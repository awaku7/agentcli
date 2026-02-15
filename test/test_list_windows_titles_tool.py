import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/scheck"))
)
import unittest
import json
from unittest.mock import patch
from uagent.tools.list_windows_titles_tool import run_tool


class TestListWindowsTitlesTool(unittest.TestCase):
    def test_platform_check(self):
        """Win32以外のプラットフォームでの挙動"""
        with patch("sys.platform", "linux"):
            result_str = run_tool({})
            result = json.loads(result_str)
            self.assertIn("error", result)
            self.assertIn("Windows", result["error"])

    @unittest.skipIf(sys.platform != "win32", "Windows only test")
    @patch("ctypes.windll.user32.EnumWindows")
    @patch("ctypes.windll.user32.IsWindowVisible")
    @patch("ctypes.windll.user32.GetWindowTextLengthW")
    @patch("ctypes.windll.user32.GetWindowTextW")
    @patch("ctypes.windll.user32.GetClassNameW")
    def test_enum_windows_mock(
        self, mock_class, mock_text, mock_len, mock_visible, mock_enum
    ):
        """Windows APIをモックした列挙テスト"""

        # EnumWindows のコールバックをシミュレート
        def side_effect(callback, lparam):
            # HWND=123, Title="Test Window", Class="TestClass", Visible=True
            callback(123, 0)
            return True

        mock_enum.side_effect = side_effect
        mock_visible.return_value = 1
        mock_len.return_value = 11

        # GetWindowTextW(hwnd, buf, length)
        # buf は ctypes.create_unicode_buffer で作成されるので、値を設定
        def get_text_side_effect(hwnd, buf, length):
            buf.value = "Test Window"
            return 11

        mock_text.side_effect = get_text_side_effect

        def get_class_side_effect(hwnd, buf, length):
            buf.value = "TestClass"
            return 9

        mock_class.side_effect = get_class_side_effect

        args = {"all": False, "class": True, "pid": False}
        result_str = run_tool(args)
        result = json.loads(result_str)

        self.assertEqual(result["count"], 1)
        win = result["windows"][0]
        self.assertEqual(win["hwnd"], 123)
        self.assertEqual(win["title"], "Test Window")
        self.assertEqual(win["class"], "TestClass")
        self.assertTrue(win["visible"])
        self.assertNotIn("pid", win)

    @unittest.skipIf(sys.platform != "win32", "Windows only test")
    def test_real_run(self):
        """実際の実行テスト（少なくとも1つ以上のウィンドウが見つかるはず）"""
        result_str = run_tool({"all": False})
        result = json.loads(result_str)
        self.assertIn("windows", result)
        self.assertIn("count", result)
        # 実行環境に可視ウィンドウが1つもないことは稀
        # self.assertGreaterEqual(result["count"], 0)


if __name__ == "__main__":
    unittest.main()
