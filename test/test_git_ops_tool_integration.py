import os
import shutil
import subprocess
import sys
import tempfile
import unittest

# Ensure we can import scheck tools package from repo layout
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/scheck"))
)

from uagent.tools.git_ops_tool import run_tool  # noqa: E402


def _git_available() -> bool:
    try:
        r = subprocess.run(
            ["git", "--version"], capture_output=True, text=True, timeout=10
        )
        return r.returncode == 0
    except Exception:
        return False


@unittest.skipUnless(_git_available(), "git command is required for integration tests")
class TestGitOpsToolIntegration(unittest.TestCase):
    """Integration tests that run real git against a temp repository.

    Notes:
    - These tests do not require network.
    - They create a brand-new repository in a temp directory.
    """

    def setUp(self) -> None:
        self._old_cwd = os.getcwd()
        self._tmpdir = tempfile.mkdtemp(prefix="scheck_git_ops_it_")
        os.chdir(self._tmpdir)

        # init repo
        r = subprocess.run(["git", "init"], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, msg=r.stderr)

        # configure identity locally for commits
        for k, v in (
            ("user.name", "scheck-test"),
            ("user.email", "scheck-test@example.com"),
        ):
            r = subprocess.run(
                ["git", "config", k, v], capture_output=True, text=True, timeout=30
            )
            self.assertEqual(r.returncode, 0, msg=r.stderr)

    def tearDown(self) -> None:
        os.chdir(self._old_cwd)
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_status_in_empty_repo(self) -> None:
        out = run_tool({"command": "status", "args": ["--porcelain"]})
        # empty repo => porcelain output should be empty
        self.assertEqual(out.strip(), "")

    def test_add_commit_log_show(self) -> None:
        # create a file
        with open("hello.txt", "w", encoding="utf-8") as f:
            f.write("hello\n")

        out = run_tool({"command": "add", "args": ["hello.txt"]})
        # add returns empty on success
        self.assertTrue(isinstance(out, str))

        out = run_tool({"command": "commit", "args": ["-m", "init"]})
        # commit output typically contains the summary line
        self.assertIn("init", out)

        out = run_tool({"command": "log", "args": ["--oneline", "-n", "1"]})
        self.assertIn("init", out)

        out = run_tool({"command": "show", "args": ["--stat"]})
        self.assertIn("hello.txt", out)

    def test_diff_staged(self) -> None:
        with open("a.txt", "w", encoding="utf-8") as f:
            f.write("a\n")
        run_tool({"command": "add", "args": ["a.txt"]})

        out = run_tool({"command": "diff", "args": ["--staged", "--name-only"]})
        self.assertIn("a.txt", out)

    def test_reset_hard_is_rejected_without_allow_danger(self) -> None:
        out = run_tool({"command": "reset", "args": ["--hard", "HEAD"]})
        self.assertIn("allow_danger=true", out)

    def test_rebase_requires_allow_danger(self) -> None:
        out = run_tool({"command": "rebase", "args": ["--abort"]})
        self.assertIn("allow_danger=true", out)


if __name__ == "__main__":
    unittest.main()
