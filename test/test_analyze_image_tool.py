import sys
import os
import unittest
import shutil
from unittest.mock import patch

# Add src/scheck to sys.path
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/scheck"))
)

from tools.analyze_image_tool import run_tool


class TestAnalyzeImageTool(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.join(os.getcwd(), "test_analyze_tmp")
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir)

        self.test_image = os.path.join(self.test_dir, "dummy.png")
        with open(self.test_image, "wb") as f:
            f.write(
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\xd7c\xf8\xff\xff? \x05\xfe\x02\xfe\x1cE\xef\x00\x00\x00\x00IEND\xaeB`\x82"
            )

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    @patch("tools.analyze_image_tool._run_gemini")
    @patch(
        "os.environ.get",
        side_effect=lambda k, d=None: "gemini" if k == "UAGENT_PROVIDER" else d,
    )
    def test_run_tool_gemini(self, mock_env, mock_run_gemini):
        mock_run_gemini.return_value = (
            "[analyze_image] 以下の応答が得られました:\nThis is a test image."
        )

        args = {"image_path": self.test_image, "prompt": "describe this"}
        result = run_tool(args)
        self.assertIn("This is a test image.", result)
        mock_run_gemini.assert_called_once()

    def test_run_tool_no_path(self):
        args = {"prompt": "what is this"}
        result = run_tool(args)
        self.assertIn("image_path が空です。", result)

    def test_run_tool_not_exists(self):
        args = {"image_path": "no_such_file.png"}
        result = run_tool(args)
        self.assertIn("ファイルが見つかりません", result)


if __name__ == "__main__":
    unittest.main()
