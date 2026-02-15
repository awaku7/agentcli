import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/scheck"))
)
import unittest
import json
import shutil
import tempfile
from unittest.mock import patch
from uagent.tools.mcp_servers_add_tool import run_tool as run_add
from uagent.tools.mcp_servers_list_tool import run_tool as run_list
from uagent.tools.mcp_servers_remove_tool import run_tool as run_remove


class TestMcpServersTools(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.test_dir, "mcp_servers.json")
        self.patcher = patch("uagent.tools.safe_file_ops._is_trigger_path", return_value=False)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        shutil.rmtree(self.test_dir)

    def test_mcp_add_and_list(self):
        """サーバーの追加と一覧取得"""
        # 1. 新規追加
        res_add = run_add(
            {"name": "srv1", "url": "http://srv1/mcp", "path": self.config_path}
        )
        self.assertIn("OK: added: name='srv1'", res_add)

        # 2. 一覧確認
        res_list = run_list({"path": self.config_path, "raw": True})
        obj = json.loads(res_list)
        self.assertEqual(obj["count"], 1)
        self.assertEqual(obj["servers"][0]["name"], "srv1")

        # 3. 2つ目追加 (デフォルトに設定)
        run_add(
            {
                "name": "srv2",
                "url": "http://srv2/mcp",
                "path": self.config_path,
                "set_default": True,
            }
        )
        res_list2 = json.loads(run_list({"path": self.config_path, "raw": True}))
        self.assertEqual(res_list2["count"], 2)
        # srv2 がデフォルト(先頭)のはず
        self.assertEqual(res_list2["servers"][0]["name"], "srv2")

    def test_mcp_replace(self):
        """サーバーの上書き"""
        run_add({"name": "srv1", "url": "url1", "path": self.config_path})

        # replace=False だとエラー
        res = run_add(
            {"name": "srv1", "url": "url2", "path": self.config_path, "replace": False}
        )
        self.assertIn("ERROR", res)

        # replace=True で上書き
        res2 = run_add(
            {"name": "srv1", "url": "url2", "path": self.config_path, "replace": True}
        )
        self.assertIn("OK: replaced", res2)

        # URLが更新されているか
        res_list = json.loads(run_list({"path": self.config_path, "raw": True}))
        self.assertEqual(res_list["servers"][0]["url"], "url2")

    def test_mcp_remove(self):
        """サーバーの削除"""
        run_add({"name": "A", "url": "uA", "path": self.config_path})
        run_add({"name": "B", "url": "uB", "path": self.config_path})

        # name指定で削除
        res = run_remove({"name": "A", "path": self.config_path})
        self.assertIn("removed index=0 name='A'", res)

        # 残りを確認
        res_list = json.loads(run_list({"path": self.config_path, "raw": True}))
        self.assertEqual(res_list["count"], 1)
        self.assertEqual(res_list["servers"][0]["name"], "B")

        # index指定で削除
        run_remove({"index": 0, "path": self.config_path})
        res_list2 = json.loads(run_list({"path": self.config_path, "raw": True}))
        self.assertEqual(res_list2["count"], 0)

    def test_mcp_validation(self):
        """バリデーション警告の確認"""
        # url が /mcp で終わっていない
        run_add({"name": "bad_url", "url": "http://bad", "path": self.config_path})
        res_list = run_list({"path": self.config_path, "validate": True, "raw": True})
        obj = json.loads(res_list)
        self.assertTrue(any("/mcp' で終わっていません" in w for w in obj["warnings"]))


if __name__ == "__main__":
    unittest.main()
