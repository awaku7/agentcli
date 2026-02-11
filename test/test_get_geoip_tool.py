import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/scheck"))
)
import unittest
import json
from unittest.mock import patch
from tools.get_geoip_tool import run_tool


class TestGetGeoipTool(unittest.TestCase):
    @patch("tools.get_geoip_tool.fetch_url_run")
    def test_get_geoip_text(self, mock_fetch):
        """テキスト形式での正常系テスト"""
        mock_fetch.return_value = (
            "[fetch_url] ...\n"
            "{\n"
            '  "ip": "1.2.3.4",\n'
            '  "city": "Tokyo",\n'
            '  "region": "Tokyo",\n'
            '  "country": "JP",\n'
            '  "loc": "35.6895,139.6917",\n'
            '  "timezone": "Asia/Tokyo"\n'
            "}"
        )

        args = {"format": "text"}
        result = run_tool(args)

        self.assertIn("[get_geoip]", result)
        self.assertIn("IP: 1.2.3.4", result)
        self.assertIn("都市: Tokyo", result)
        self.assertIn("国: JP", result)

    @patch("tools.get_geoip_tool.fetch_url_run")
    def test_get_geoip_json(self, mock_fetch):
        """JSON形式での正常系テスト"""
        mock_fetch.return_value = (
            '{"ip": "8.8.8.8", "city": "Mountain View", "country": "US"}'
        )

        args = {"format": "json"}
        result_str = run_tool(args)
        result = json.loads(result_str)

        self.assertEqual(result["ip"], "8.8.8.8")
        self.assertEqual(result["city"], "Mountain View")
        self.assertEqual(result["country"], "US")

    @patch("tools.get_geoip_tool.fetch_url_run")
    def test_get_geoip_fetch_error(self, mock_fetch):
        """fetch_url がエラーを返した場合"""
        mock_fetch.return_value = "[fetch_url error] Failed to connect"

        result = run_tool({})
        self.assertIn("[get_geoip error]", result)
        self.assertIn("解析できませんでした", result)

    @patch("tools.get_geoip_tool.fetch_url_run")
    def test_get_geoip_invalid_json(self, mock_fetch):
        """ipinfo が不正な JSON を返した場合"""
        mock_fetch.return_value = "Not a JSON"

        result = run_tool({})
        self.assertIn("[get_geoip error]", result)


if __name__ == "__main__":
    unittest.main()
