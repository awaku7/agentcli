import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/scheck"))
)
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError, URLError
import ssl
from uagent.tools.fetch_url_tool import run_tool


class TestFetchUrlTool(unittest.TestCase):
    def test_fetch_url_success(self):
        """正常なレスポンス取得のテスト"""
        with patch("uagent.tools.fetch_url_tool.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b"Hello from web"
            mock_resp.getcode.return_value = 200
            mock_resp.headers.get.return_value = "text/plain"
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp

            args = {"url": "https://example.com"}
            result = run_tool(args)

            self.assertIn("status=200", result)
            self.assertIn("Hello from web", result)
            self.assertIn("content-type=text/plain", result)

    def test_fetch_url_http_error(self):
        """HTTPエラー(404等)のテスト"""
        with patch("uagent.tools.fetch_url_tool.urlopen") as mock_urlopen:
            # HTTPError(url, code, msg, hdrs, fp)
            mock_urlopen.side_effect = HTTPError(
                "http://ex.com", 404, "Not Found", {}, None
            )

            args = {"url": "https://example.com/404"}
            result = run_tool(args)
            self.assertIn("status=404", result)
            self.assertIn("HTTPError 404", result)

    def test_fetch_url_ssl_error_fallback(self):
        """SSL証明書エラー時のフォールバックテスト"""
        with patch("uagent.tools.fetch_url_tool.urlopen") as mock_urlopen:
            # 1回目は SSL 証明書エラー
            err = URLError(ssl.SSLCertVerificationError("cert failed"))

            # 2回目は成功するように設定 (副作用をリストで渡す)
            mock_resp = MagicMock()
            mock_resp.read.return_value = b"Unverified Content"
            mock_resp.getcode.return_value = 200
            mock_resp.headers.get.return_value = "text/plain"
            mock_resp.__enter__.return_value = mock_resp

            mock_urlopen.side_effect = [err, mock_resp]

            args = {"url": "https://bad-ssl.com"}
            result = run_tool(args)

            self.assertIn("SSL 証明書の検証に失敗したため", result)
            self.assertIn("Unverified Content", result)
            self.assertEqual(mock_urlopen.call_count, 2)

    def test_fetch_url_truncation(self):
        """巨大レスポンスの切り詰めテスト"""
        with patch("uagent.tools.fetch_url_tool.urlopen") as mock_urlopen:
            with patch("uagent.tools.fetch_url_tool.get_callbacks") as mock_get_cb:
                mock_cb = MagicMock()
                mock_cb.url_fetch_max_bytes = 10
                mock_cb.url_fetch_timeout_ms = 1000
                mock_get_cb.return_value = mock_cb

                mock_resp = MagicMock()
                # 11バイト
                mock_resp.read.return_value = b"abcdefghijk"
                mock_resp.getcode.return_value = 200
                mock_resp.__enter__.return_value = mock_resp
                mock_urlopen.return_value = mock_resp

                args = {"url": "https://large.com"}
                result = run_tool(args)

                self.assertIn("truncated", result)
                # 10バイトに切り詰められているか
                self.assertIn("abcdefghij", result)
                self.assertNotIn("abcdefghijk", result)

    def test_fetch_url_empty_url(self):
        """URLが空の場合"""
        args = {"url": ""}
        result = run_tool(args)
        self.assertIn("[fetch_url error]", result)
        self.assertIn("url が空です", result)


if __name__ == "__main__":
    unittest.main()
