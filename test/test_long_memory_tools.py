import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/scheck"))
)
import unittest
import json
import shutil
import tempfile
from uagent.tools.add_long_memory_tool import run_tool as run_add
from uagent.tools.get_long_memory_tool import run_tool as run_get


class TestLongMemoryTools(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.memory_file = os.path.join(self.test_dir, "memory.jsonl")
        # 環境変数でメモリファイルの場所を固定
        os.environ["UAGENT_MEMORY_FILE"] = self.memory_file

    def tearDown(self):
        if "UAGENT_MEMORY_FILE" in os.environ:
            del os.environ["UAGENT_MEMORY_FILE"]
        shutil.rmtree(self.test_dir)

    def test_add_and_get_memory(self):
        """メモの追加と取得の連携テスト"""
        # 初期状態
        initial = run_get({})
        self.assertIn("no long-term memory", initial)

        # 1つ追加
        res1 = run_add({"note": "First memory"})
        self.assertIn("保存しました", res1)

        # 2つ目追加
        run_add({"note": "Second memory"})

        # 取得して確認
        content = run_get({})
        lines = [line for line in content.strip().split("\n") if line.strip()]
        self.assertEqual(len(lines), 2)

        rec1 = json.loads(lines[0])
        rec2 = json.loads(lines[1])
        self.assertEqual(rec1["note"], "First memory")
        self.assertEqual(rec2["note"], "Second memory")
        self.assertTrue("ts" in rec1)

    def test_add_empty_note(self):
        """空のノート追加時のエラー"""
        res = run_add({"note": ""})
        self.assertIn("error", res)
        self.assertIn("note が空です", res)


if __name__ == "__main__":
    unittest.main()
