import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/scheck"))
)
import unittest
import json
import os
import shutil
import subprocess
import stat
from unittest.mock import patch
from uagent.tools.apply_patch_tool import run_tool


def remove_readonly(func, path, excinfo):
    """読み取り専用ファイルを削除可能にするためのハンドラ"""
    os.chmod(path, stat.S_IWRITE)
    func(path)


class TestApplyPatchTool(unittest.TestCase):
    def setUp(self):
        self.original_cwd = os.getcwd()
        self.repo_dir = os.path.join(self.original_cwd, "test", "tmp_repo_apply")
        if os.path.exists(self.repo_dir):
            shutil.rmtree(self.repo_dir, onerror=remove_readonly)
        os.makedirs(self.repo_dir)
        os.chdir(self.repo_dir)

        subprocess.run(["git", "init"], check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], check=True)

        with open("test_file.txt", "w", newline="\n") as f:
            f.write("Hello world\n")
        subprocess.run(["git", "add", "test_file.txt"], check=True)
        subprocess.run(["git", "commit", "-m", "initial commit"], check=True)

        with open("test_file.txt", "w", newline="\n") as f:
            f.write("Hello universe\n")
        self.valid_patch = subprocess.run(
            ["git", "diff"], capture_output=True, text=True
        ).stdout
        subprocess.run(["git", "checkout", "test_file.txt"], check=True)

        # Mock os.path.expanduser to avoid touching real home directory
        self.expanduser_patcher = patch(
            "os.path.expanduser", return_value=self.repo_dir
        )
        self.expanduser_patcher.start()

    def tearDown(self):
        self.expanduser_patcher.stop()
        os.chdir(self.original_cwd)
        if os.path.exists(self.repo_dir):
            try:
                shutil.rmtree(self.repo_dir, onerror=remove_readonly)
            except Exception:
                pass

    def test_dry_run_success(self):
        args = {"patch_text": self.valid_patch, "dry_run": True}
        result = run_tool(args)
        result_dict = json.loads(result)
        self.assertTrue(result_dict["ok"], f"Error: {result_dict.get('error')}")

    def test_apply_success(self):
        with patch("uagent.tools.apply_patch_tool._human_confirm", return_value=True):
            args = {"patch_text": self.valid_patch, "dry_run": False}
            result = run_tool(args)
            result_dict = json.loads(result)
            self.assertTrue(result_dict["ok"], f"Error: {result_dict.get('error')}")
            with open("test_file.txt", "r") as f:
                content = f.read()
            self.assertEqual(content, "Hello universe\n")

    def test_dangerous_path_rejection(self):
        """ディレクトリトラバーサルを含むパッチが拒否されるか"""
        dangerous_patch = (
            "--- a/../../outside.txt\n"
            "+++ b/../../outside.txt\n"
            "@@ -1,1 +1,1 @@\n"
            "-old\n"
            "+new\n"
        )
        args = {"patch_text": dangerous_patch, "dry_run": True}
        result = json.loads(run_tool(args))
        self.assertFalse(result["ok"])
        self.assertIn("dangerous path", result["error"])

    def test_strip_option(self):
        """-p1 オプションが正しく機能するか"""
        os.makedirs("subdir", exist_ok=True)
        # 改行コードを LF に固定
        with open("subdir/target.txt", "w", newline="\n") as f:
            f.write("base\n")
        subprocess.run(["git", "add", "subdir/target.txt"], check=True)
        subprocess.run(["git", "commit", "-m", "add subdir file"], check=True)

        p1_patch = (
            "--- x/subdir/target.txt\n"
            "+++ x/subdir/target.txt\n"
            "@@ -1,1 +1,1 @@\n"
            "-base\n"
            "+modified\n"
        )
        args = {
            "patch_text": p1_patch,
            "dry_run": False,
            "strip": 1,
            "confirm": "never",
        }
        result_json = run_tool(args)
        result = json.loads(result_json)
        self.assertTrue(
            result["ok"],
            f"Error: {result.get('error')}\nStderr: {result.get('stderr')}",
        )
        with open("subdir/target.txt", "r") as f:
            self.assertEqual(f.read(), "modified\n")

    def test_confirm_auto_threshold(self):
        """追加行数が閾値を超えた場合に確認が求められるか"""
        many_added = "+++\n" + "\n".join([f"+line {i}" for i in range(600)])
        large_patch = (
            "--- a/test_file.txt\n"
            "+++ b/test_file.txt\n"
            "@@ -1,1 +1,601 @@\n"
            "-Hello world\n" + many_added + "\n"
        )

        with patch(
            "uagent.tools.apply_patch_tool._human_confirm", return_value=False
        ) as mock_confirm:
            args = {
                "patch_text": large_patch,
                "dry_run": False,
                "confirm": "auto",
                "confirm_if_added_lines_over": 500,
            }
            result = json.loads(run_tool(args))
            self.assertFalse(result["ok"])
            self.assertEqual(result["error"], "cancelled by user")
            mock_confirm.assert_called_once()


if __name__ == "__main__":
    unittest.main()
