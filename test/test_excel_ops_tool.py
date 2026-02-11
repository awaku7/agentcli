import sys
import os
import unittest
import tempfile
import shutil
import json

# モジュール検索パスに src/scheck を追加
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/scheck"))
)

from tools.excel_ops_tool import run_tool


class TestExcelOpsTool(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.file_path = os.path.join(self.test_dir, "test.xlsx")

    def tearDown(self):
        import time

        for _ in range(5):
            try:
                shutil.rmtree(self.test_dir)
                break
            except PermissionError:
                time.sleep(0.1)

    def test_write_and_read_excel(self):
        """Excel書き込みと読み込み"""
        # Write
        data = [{"Name": "Alice", "Age": 30}, {"Name": "Bob", "Age": 25}]
        args_write = {
            "action": "write",
            "file_path": self.file_path,
            "data": json.dumps(data),
            "sheet_name": "TestSheet",
        }
        res_write = run_tool(args_write)
        self.assertIn("Successfully wrote", res_write)
        self.assertTrue(os.path.exists(self.file_path))

        # Get sheet names
        res_names_json = run_tool(
            {"action": "get_sheet_names", "file_path": self.file_path}
        )
        res_names = json.loads(res_names_json)
        self.assertIn("TestSheet", res_names["sheet_names"])

        # Read
        args_read = {
            "action": "read",
            "file_path": self.file_path,
            "sheet_name": "TestSheet",
        }
        res_read_json = run_tool(args_read)
        res_read = json.loads(res_read_json)
        self.assertEqual(len(res_read), 2)
        self.assertEqual(res_read[0]["Name"], "Alice")
        self.assertEqual(res_read[1]["Age"], 25)

    def test_write_append_sheet(self):
        """既存ファイルへのシート追加"""
        # First sheet
        run_tool(
            {
                "action": "write",
                "file_path": self.file_path,
                "data": json.dumps([{"A": 1}]),
                "sheet_name": "Sheet1",
            }
        )

        # Second sheet
        run_tool(
            {
                "action": "write",
                "file_path": self.file_path,
                "data": json.dumps([{"B": 2}]),
                "sheet_name": "Sheet2",
            }
        )

        # Verify both exist
        res_names = json.loads(
            run_tool({"action": "get_sheet_names", "file_path": self.file_path})
        )
        self.assertIn("Sheet1", res_names["sheet_names"])
        self.assertIn("Sheet2", res_names["sheet_names"])

    def test_backup_on_write(self):
        """書き込み時のバックアップ作成"""
        # Initial write
        run_tool(
            {
                "action": "write",
                "file_path": self.file_path,
                "data": json.dumps([{"A": 1}]),
            }
        )

        # Overwrite (triggers backup)
        run_tool(
            {
                "action": "write",
                "file_path": self.file_path,
                "data": json.dumps([{"A": 2}]),
            }
        )

        backup_path = self.file_path + ".org"
        self.assertTrue(os.path.exists(backup_path))

    def test_invalid_json_data(self):
        """無効なJSONデータでのエラー"""
        args = {"action": "write", "file_path": self.file_path, "data": "invalid json"}
        res = run_tool(args)
        self.assertIn("must be a valid JSON string", res)

    def test_missing_file_path(self):
        """file_path不足"""
        res = run_tool({"action": "read"})
        self.assertIn("file_path is required", res)


if __name__ == "__main__":
    unittest.main()
