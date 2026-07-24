from __future__ import annotations

from pathlib import Path

from uagent.tools.py2idx_tool import run_tool


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def test_py2idx_class_method_async_decorator(repo_tmp_path: Path) -> None:
    src = '''"""mod doc"""
from __future__ import annotations

@decorator
class Foo:
    def method(self, x: int) -> int:
        return x

    @property
    def name(self) -> str:
        return "n"

def top_level(a, b):
    """doc"""
    return a + b

async def async_fn():
    pass
'''
    path = repo_tmp_path / "sample.py"
    _write(path, src)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "class Foo" in out
    assert "def method" in out
    assert "def name" in out
    assert "def top_level" in out
    assert "async def async_fn" in out

    sec = run_tool({"path": str(path), "mode": "section", "section": 1})
    assert "class Foo" in sec
    assert "def method" in sec


def test_py2idx_section_single_line_and_oor(repo_tmp_path: Path) -> None:
    path = repo_tmp_path / "one.py"
    _write(path, "def only():\n    return 1\n")
    idx = run_tool({"path": str(path), "mode": "index"})
    assert "def only" in idx
    sec = run_tool({"path": str(path), "mode": "section", "section": 1})
    assert "def only" in sec
    assert sec.strip() != ""

    bad = run_tool({"path": str(path), "mode": "section", "section": 99})
    assert "99" in bad


def test_py2idx_missing_file(repo_tmp_path: Path) -> None:
    missing = repo_tmp_path / "no_such.py"
    out = run_tool({"path": str(missing), "mode": "index"})
    assert (
        "ファイルが見つかりません" in out
        or "not found" in out.lower()
        or "No such" in out
    )
