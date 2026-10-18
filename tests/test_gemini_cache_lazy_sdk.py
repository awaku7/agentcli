"""Regression tests for lazy Gemini SDK loading."""

import os
import subprocess
import sys
from pathlib import Path


def test_non_gemini_cache_init_does_not_import_google_genai():
    """Non-Gemini requests must not import the Google SDK for cache setup."""
    src_dir = Path(__file__).resolve().parents[1] / "src"
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        path for path in (str(src_dir), env.get("PYTHONPATH", "")) if path
    )
    script = """
import builtins
import sys

original_import = builtins.__import__


def block_google_genai(name, globals=None, locals=None, fromlist=(), level=0):
    if name == "google.genai" or name.startswith("google.genai."):
        raise AssertionError("A non-Gemini request imported google.genai")
    return original_import(name, globals, locals, fromlist, level)


builtins.__import__ = block_google_genai

from uagent.llm_message_helpers import _init_gemini_cache

cache_mgr, cache_name = _init_gemini_cache(
    provider="openai", client=None, depname="gpt-test", messages=[]
)
assert cache_mgr is not None
assert cache_name is None
assert "google.genai" not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
