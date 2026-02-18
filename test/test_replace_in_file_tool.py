import os
import unittest
import json
import shutil
from unittest.mock import patch, MagicMock
from uagent.tools.replace_in_file_tool import run_tool


class TestReplaceInFileTool(unittest.TestCase):
    def setUp(self):
        self.original_cwd = os.getcwd()
        os.chdir(self.original_cwd)
        self.test_dir = os.path.join(self.original_cwd, "test", "tmp_replace_test")
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir)

        self.test_rel_path = os.path.join("test", "tmp_replace_test", "test_file.txt")
        self.test_abs_path = os.path.join(self.test_dir, "test_file.txt")

        with open(self.test_abs_path, "w", newline="\n") as f:
            f.write("Hello world\nThis is a test file\nGoodbye world")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            try:
                shutil.rmtree(self.test_dir)
            except Exception:
                pass

    def test_literal_replace_preview_true(self):
        """literal モード、preview=True のテスト"""
        args = {
            "path": self.test_rel_path,
            "mode": "literal",
            "pattern": "world",
            "replacement": "universe",
            "preview": True,
        }
        result = run_tool(args)
        result_dict = json.loads(result)
        self.assertTrue(result_dict["ok"], f"Error: {result_dict.get('error')}")
        self.assertTrue(result_dict["preview"])
        self.assertEqual(result_dict["match_count"], 2)
        self.assertTrue(result_dict["changed"])
        self.assertIn("diff", result_dict)
        self.assertIn("summary", result_dict)

    def test_literal_replace_preview_false(self):
        """literal モード、preview=False のテスト"""
        args = {
            "path": self.test_rel_path,
            "mode": "literal",
            "pattern": "world",
            "replacement": "universe",
            "preview": False,
        }
        result = run_tool(args)
        result_dict = json.loads(result)
        self.assertTrue(result_dict["ok"], f"Error: {result_dict.get('error')}")
        self.assertFalse(result_dict["preview"])

        with open(self.test_abs_path, "r", newline="") as f:
            content = f.read()
        self.assertIn("Hello universe\n", content)

    def test_regex_replace(self):
        """regex モードのテスト"""
        with patch(
            "uagent.tools.replace_in_file_tool._human_confirm", return_value=True
        ):
            args = {
                "path": self.test_rel_path,
                "mode": "regex",
                "pattern": r"\bworld\b",
                "replacement": "universe",
                "preview": False,
            }
            result = run_tool(args)
            result_dict = json.loads(result)
            self.assertTrue(result_dict["ok"], f"Error: {result_dict.get('error')}")

    def test_count_limit(self):
        """置換回数上限(count)のテスト"""
        args = {
            "path": self.test_rel_path,
            "mode": "literal",
            "pattern": "world",
            "replacement": "universe",
            "count": 1,
            "preview": False,
        }
        result = json.loads(run_tool(args))
        self.assertTrue(result["ok"])
        with open(self.test_abs_path, "r", newline="") as f:
            content = f.read()
        self.assertIn("Hello universe", content)
        self.assertIn("Goodbye world", content)

    def test_backup_rotation(self):
        """バックアップが連番 (.org, .org1...) で作成されるか"""
        # 初回: Hello -> Hi
        run_tool(
            {
                "path": self.test_rel_path,
                "mode": "literal",
                "pattern": "Hello",
                "replacement": "Hi",
                "preview": False,
            }
        )
        # 2回目: Hi -> Hey
        run_tool(
            {
                "path": self.test_rel_path,
                "mode": "literal",
                "pattern": "Hi",
                "replacement": "Hey",
                "preview": False,
            }
        )
        # 3回目: Hey -> Yo
        run_tool(
            {
                "path": self.test_rel_path,
                "mode": "literal",
                "pattern": "Hey",
                "replacement": "Yo",
                "preview": False,
            }
        )

        self.assertTrue(
            os.path.exists(self.test_abs_path + ".org"), "Backup .org missing"
        )
        self.assertTrue(
            os.path.exists(self.test_abs_path + ".org1"), "Backup .org1 missing"
        )
        self.assertTrue(
            os.path.exists(self.test_abs_path + ".org2"), "Backup .org2 missing"
        )

    def test_encoding_sjis(self):
        """Shift-JIS ファイルの置換テスト"""
        sjis_content = "こんにちは世界"
        with open(self.test_abs_path, "w", encoding="shift_jis") as f:
            f.write(sjis_content)

        args = {
            "path": self.test_rel_path,
            "mode": "literal",
            "pattern": "世界",
            "replacement": "宇宙",
            "encoding": "shift_jis",
            "preview": False,
        }
        result = json.loads(run_tool(args))
        self.assertTrue(result["ok"], f"Error: {result.get('error')}")
        with open(self.test_abs_path, "r", encoding="shift_jis") as f:
            self.assertEqual(f.read(), "こんにちは宇宙")

    def test_file_too_large(self):
        """巨大ファイル制限のテスト"""
        with patch("uagent.tools.context.get_callbacks") as mock_get_cb:
            mock_cb = MagicMock()
            mock_cb.read_file_max_bytes = 5
            mock_get_cb.return_value = mock_cb

            args = {
                "path": self.test_rel_path,
                "pattern": "world",
                "replacement": "universe",
            }
            result = json.loads(run_tool(args))
            self.assertFalse(result["ok"])
            self.assertIn("file too large", result["error"])

    def test_dangerous_path_rejection(self):
        """ワークディレクトリ外へのアクセス拒否"""
        args = {
            "path": "../../../etc/passwd",
            "pattern": "root",
            "replacement": "admin",
        }
        result = json.loads(run_tool(args))
        self.assertFalse(result["ok"])
        self.assertTrue(
            "dangerous path" in result["error"] or "not allowed" in result["error"]
        )

    def test_invalid_path(self):
        """存在しないファイルパスのテスト"""
        args = {
            "path": "test/tmp_replace_test/nonexistent.txt",
            "pattern": "world",
            "replacement": "universe",
        }
        result = json.loads(run_tool(args))
        self.assertFalse(result["ok"])
        self.assertIn("file not found", result["error"])

    def test_multiline_diff(self):
        """複数行への置換とDiffの正確性のテスト"""
        args = {
            "path": self.test_rel_path,
            "mode": "literal",
            "pattern": "This is a test file",
            "replacement": "Line A\nLine B\nLine C",
            "preview": True,
        }
        result = json.loads(run_tool(args))
        self.assertTrue(result["ok"])
        self.assertTrue(result["changed"])
        self.assertIn("+Line A", result["diff"])
        self.assertIn("-This is a test file", result["diff"])
        self.assertEqual(len(result["hits"]), 1)
        self.assertIn("Line A\nLine B", result["hits"][0]["line_after"])

    def test_python_string_literal_newline_injection_breaks_syntax(self):
        """Pythonコード中の通常文字列リテラルに実改行が混入すると構文が壊れる（置換で起こり得る）ことを再現する。

        replace_in_file 自体は「そのまま書く」ため、replacement に実改行が入ると
        "..." の途中に改行が挿入され、py_compile が失敗するケースがある。
        """
        py_rel = os.path.join("test", "tmp_replace_test", "broken.py")
        py_abs = os.path.join(self.test_dir, "broken.py")

        with open(py_abs, "w", newline="\n", encoding="utf-8") as f:
            f.write('s = "AAA"\\n')

        # replacement に「実改行」を含めて通常文字列を壊す
        args = {
            "path": py_rel,
            "mode": "literal",
            "pattern": "AAA",
            "replacement": "A\nA",
            "preview": False,
        }
        result = json.loads(run_tool(args))
        self.assertFalse(result["ok"], f"Expected rejection; got: {result}")

        import py_compile

        with self.assertRaises(py_compile.PyCompileError):
            py_compile.compile(py_abs, doraise=True)

    def test_no_match_summary(self):
        """マッチしなかった場合のサマリーとDiffのテスト"""
        args = {
            "path": self.test_rel_path,
            "mode": "literal",
            "pattern": "NONEXISTENT_STRING",
            "replacement": "SHOULD_NOT_REPLACE",
            "preview": True,
        }
        result = json.loads(run_tool(args))
        self.assertTrue(result["ok"])
        self.assertFalse(result["changed"])
        self.assertEqual(result["match_count"], 0)
        self.assertEqual(result["diff"], "")
        self.assertIn("Successfully no change (0 matches)", result["summary"])

    def test_invalid_regex_pattern(self):
        """不正な正規表現パターンのエラーハンドリングテスト"""
        args = {
            "path": self.test_rel_path,
            "mode": "regex",
            "pattern": "[invalid regex",
            "replacement": "test",
        }
        result = json.loads(run_tool(args))
        self.assertFalse(result["ok"])
        err = result["error"].lower()
        # 'unterminated', 'invalid', 'patternerror' のいずれかが含まれることを確認
        self.assertTrue(
            any(x in err for x in ["unterminated", "invalid", "patternerror"])
        )

    def test_regex_replacement_with_newline_escapes_can_break_python_string_literal(
        self,
    ):
        """regex置換で replacement に改行を入れると、.py内の通常文字列が壊れ得ることを再現"""
        py_rel = os.path.join("test", "tmp_replace_test", "broken_regex.py")
        py_abs = os.path.join(self.test_dir, "broken_regex.py")

        # 通常文字列（単一クォート/ダブルクォート）を用意
        with open(py_abs, "w", newline="\n", encoding="utf-8") as f:
            f.write('s = "HELLO"\\n')

        # regex で HELLO を改行を含む文字列に置換（実改行が入って構文が壊れる）
        with patch(
            "uagent.tools.replace_in_file_tool._human_confirm", return_value=True
        ):
            args = {
                "path": py_rel,
                "mode": "regex",
                "pattern": "HELLO",
                "replacement": "A\\nA",
                "preview": False,
            }
            result = json.loads(run_tool(args))
            self.assertTrue(result["ok"], f"Error: {result.get('error')}")

        import py_compile

        with self.assertRaises(py_compile.PyCompileError):
            py_compile.compile(py_abs, doraise=True)

    def test_json_escape_layer_mistake_causes_actual_newline_in_replacement(self):
        """JSON経由のエスケープ段数ミスを疑似的に再現。

        呼び出し側が replacement を "\\n" のつもりで "\n" を渡すと、
        （Python側では実改行として扱われ）.py中の通常文字列が壊れ得る。

        ここでは run_tool に直接渡すので『本当のJSON事故』そのものではないが、
        replacement に実改行が混入した場合の結果を再現する。
        """
        py_rel = os.path.join("test", "tmp_replace_test", "broken_json.py")
        py_abs = os.path.join(self.test_dir, "broken_json.py")

        with open(py_abs, "w", newline="\n", encoding="utf-8") as f:
            f.write('s = "HELLO"\\n')

        # ここが事故点: replacement に実改行が混入している想定
        bad_replacement = "A\nA"  # 実改行を含む

        with patch(
            "uagent.tools.replace_in_file_tool._human_confirm", return_value=True
        ):
            args = {
                "path": py_rel,
                "mode": "literal",
                "pattern": "HELLO",
                "replacement": bad_replacement,
                "preview": False,
            }
            result = json.loads(run_tool(args))
            self.assertFalse(result["ok"], f"Expected rejection; got: {result}")

        import py_compile

        with self.assertRaises(py_compile.PyCompileError):
            py_compile.compile(py_abs, doraise=True)

    def test_summary_messages(self):
        """サマリーメッセージの文言テスト"""
        args_preview = {
            "path": self.test_rel_path,
            "pattern": "world",
            "replacement": "X",
            "preview": True,
        }
        res_preview = json.loads(run_tool(args_preview))
        self.assertIn("Preview: 2 matches found", res_preview["summary"])

        args_exec_no = {
            "path": self.test_rel_path,
            "pattern": "NOTFOUND",
            "replacement": "X",
            "preview": False,
        }
        res_exec_no = json.loads(run_tool(args_exec_no))
        self.assertIn("Successfully no change (0 matches)", res_exec_no["summary"])


if __name__ == "__main__":
    unittest.main()
