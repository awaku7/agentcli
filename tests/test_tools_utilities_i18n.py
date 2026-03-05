from __future__ import annotations

import ast
from pathlib import Path

import pytest


TOOLS_DIR = Path(__file__).resolve().parents[1] / "src" / "uagent" / "tools"


def _is_non_tool_module(path: Path) -> bool:
    # utilities: anything under tools/ that isn't a tool entry module
    # (tools are standardized as *_tool.py)
    return path.suffix == ".py" and not path.name.endswith("_tool.py") and path.name != "__init__.py"


def _has_non_ascii_outside_docstrings(path: Path) -> bool:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))

    # Collect ranges for module/class/function docstrings so we can exclude them.
    docstring_ranges: list[tuple[int, int]] = []

    def add_docstring_range(node: ast.AST) -> None:
        doc = ast.get_docstring(node, clean=False)
        if not doc:
            return

        body = getattr(node, "body", None)
        if not body:
            return

        first = body[0]
        if not isinstance(first, ast.Expr) or not isinstance(first.value, ast.Constant):
            return
        if not isinstance(first.value.value, str):
            return

        start = getattr(first, "lineno", None)
        end = getattr(first, "end_lineno", None)
        if start is None or end is None:
            return
        docstring_ranges.append((start, end))

    add_docstring_range(tree)
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            add_docstring_range(n)

    def is_in_docstring(line_no: int) -> bool:
        for s, e in docstring_ranges:
            if s <= line_no <= e:
                return True
        return False

    for i, line in enumerate(src.splitlines(), start=1):
        if is_in_docstring(i):
            continue
        if any(ord(ch) >= 128 for ch in line):
            return True

    return False


def test_tools_utilities_no_non_ascii_outside_docstrings() -> None:
    if not TOOLS_DIR.exists():
        pytest.skip("tools dir not found")

    offenders: list[str] = []
    for p in sorted(TOOLS_DIR.glob("*.py")):
        if not _is_non_tool_module(p):
            continue
        if _has_non_ascii_outside_docstrings(p):
            offenders.append(p.name)

    assert offenders == [], "Non-ASCII characters found outside docstrings in: " + ", ".join(offenders)
