import sys
import os
import sqlite3
import unittest
import json
import tempfile
import shutil

# モジュール検索パスに src/scheck を追加
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/scheck"))
)

from tools.db_query_tool import run_tool


class TestDbQueryTool(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test.db")

        # テスト用DBの作成
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)"
        )
        cursor.execute("INSERT INTO users (name, age) VALUES ('Alice', 30)")
        cursor.execute("INSERT INTO users (name, age) VALUES ('Bob', 25)")
        conn.commit()
        conn.close()

    def tearDown(self):
        import time

        # Windowsでファイルがロックされている場合があるため、少し待機してリトライ
        for _ in range(5):
            try:
                shutil.rmtree(self.test_dir)
                break
            except PermissionError:
                time.sleep(0.1)
        else:
            # それでも消せない場合は警告を出すがテストは落とさない、あるいは無視
            pass

    def test_select_success(self):
        """SELECTクエリの成功ケース"""
        args = {"db_path": self.db_path, "sql": "SELECT * FROM users ORDER BY id"}
        result = run_tool(args)
        self.assertIn("[db_query] Result:", result)

        # JSON部分を抽出して検証
        json_str = result.split("Result:\n")[1]
        data = json.loads(json_str)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["name"], "Alice")
        self.assertEqual(data[1]["name"], "Bob")

    def test_pragma_success(self):
        """PRAGMAクエリの成功ケース"""
        args = {"db_path": self.db_path, "sql": "PRAGMA table_info(users)"}
        result = run_tool(args)
        self.assertIn("[db_query] Result:", result)
        self.assertIn("name", result)
        self.assertIn("age", result)

    def test_explain_success(self):
        """EXPLAINクエリの成功ケース"""
        args = {"db_path": self.db_path, "sql": "EXPLAIN SELECT * FROM users"}
        result = run_tool(args)
        self.assertIn("[db_query] Result:", result)

    def test_forbidden_query(self):
        """許可されていないクエリ（INSERT/UPDATE/DELETEなど）の拒否"""
        queries = [
            "INSERT INTO users (name, age) VALUES ('Charlie', 20)",
            "UPDATE users SET age = 31 WHERE name = 'Alice'",
            "DELETE FROM users WHERE id = 1",
            "DROP TABLE users",
            "CREATE TABLE dummy (id INTEGER)",
        ]
        for sql in queries:
            with self.subTest(sql=sql):
                args = {"db_path": self.db_path, "sql": sql}
                result = run_tool(args)
                self.assertIn(
                    "[db_query error] 安全のため、実行できるSQLは SELECT / PRAGMA / EXPLAIN のみに制限されています。",
                    result,
                )

    def test_db_not_found(self):
        """データベースファイルが見つからない場合のエラー"""
        args = {"db_path": "non_existent.db", "sql": "SELECT 1"}
        result = run_tool(args)
        self.assertIn("[db_query error] データベースファイルが見つかりません", result)

    def test_invalid_sql_syntax(self):
        """SQL文法エラー"""
        args = {"db_path": self.db_path, "sql": "SELECT * FROM non_existent_table"}
        result = run_tool(args)
        self.assertIn("[db_query error] SQL execution failed", result)

    def test_missing_args(self):
        """引数不足"""
        self.assertIn("db_path が指定されていません", run_tool({"sql": "SELECT 1"}))
        self.assertIn("sql が指定されていません", run_tool({"db_path": "test.db"}))


if __name__ == "__main__":
    unittest.main()
