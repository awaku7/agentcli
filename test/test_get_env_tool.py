import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/scheck"))
)
import unittest
from unittest.mock import patch, MagicMock
from tools.get_env_tool import run_tool


class TestGetEnvTool(unittest.TestCase):
    def setUp(self):
        # テスト用の環境変数を設定
        os.environ["TEST_ENV_VAR"] = "SecretValue123"

    def tearDown(self):
        if "TEST_ENV_VAR" in os.environ:
            del os.environ["TEST_ENV_VAR"]

    def test_get_env_masked_default(self):
        """デフォルトでマスクされることの確認"""
        args = {"name": "TEST_ENV_VAR"}
        result = run_tool(args)
        # デフォルト keep=2 なので "Se***23" のようになるはず
        self.assertIn("TEST_ENV_VAR=Se***23", result)

    def test_get_env_unmasked(self):
        """マスクなしでの取得"""
        args = {"name": "TEST_ENV_VAR", "mask": False}
        result = run_tool(args)
        self.assertEqual(result, "TEST_ENV_VAR=SecretValue123")

    def test_get_env_custom_mask(self):
        """マスク文字数の指定"""
        args = {"name": "TEST_ENV_VAR", "mask": True, "unmasked_chars": 4}
        result = run_tool(args)
        # keep=4 なので "Secr***e123"
        self.assertIn("TEST_ENV_VAR=Secr***e123", result)

    def test_missing_env_error(self):
        """存在しない環境変数のエラー"""
        args = {"name": "NON_EXISTENT_VAR"}
        result = run_tool(args)
        self.assertIn("[get_env error]", result)
        self.assertIn("is not set", result)

    def test_missing_env_ok(self):
        """存在しない環境変数でも missing_ok=True の場合"""
        args = {"name": "NON_EXISTENT_VAR", "missing_ok": True}
        result = run_tool(args)
        self.assertEqual(result, "NON_EXISTENT_VAR=(not set)")

    def test_callback_usage(self):
        """コールバックが優先的に使用されるか"""
        with patch("tools.get_env_tool.get_callbacks") as mock_get_cb:
            mock_cb = MagicMock()
            mock_cb.get_env.return_value = "CallbackValue"
            mock_get_cb.return_value = mock_cb

            args = {"name": "ANY_VAR", "mask": False}
            result = run_tool(args)
            self.assertEqual(result, "ANY_VAR=CallbackValue")
            mock_cb.get_env.assert_called_with("ANY_VAR")

    def test_short_value_masking(self):
        """短い値のマスク（完全に隠されるか）"""
        os.environ["SHORT_VAR"] = "123"
        args = {"name": "SHORT_VAR", "mask": True, "unmasked_chars": 2}
        result = run_tool(args)
        # len("123")=3, keep*2+1 = 2*2+1 = 5. 3 <= 5 なので "***"
        self.assertIn("SHORT_VAR=***", result)


if __name__ == "__main__":
    unittest.main()
