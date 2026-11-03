"""A2A retains its callable entry point while freeing uaga for the Web host."""

from pathlib import Path
import subprocess
import sys
import tomllib


def test_console_scripts_separate_a2a_and_web():
    config = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    scripts = config["project"]["scripts"]
    assert scripts["uaga2a"] == "uagent.a2a.server:main"
    assert scripts["uagw"] == "uagent.web:main"
    assert "uaga" not in scripts


def test_a2a_module_still_exposes_help_without_starting_server():
    result = subprocess.run(
        [sys.executable, "-m", "uagent.a2a.server", "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "uaga2a" in result.stdout
    assert "--host" in result.stdout
    assert "--port" in result.stdout
