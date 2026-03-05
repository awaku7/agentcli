from __future__ import annotations

import ast
from pathlib import Path

import pytest


TOOLS_DIR = Path(__file__).resolve().parents[1] / "src" / "uagent" / "tools"

# Utilities that are infrastructure/internal and are allowed to contain string literals
# (they are not intended to surface user-facing messages directly).
EXCLUDE_FILES = {
    "__init__.py",
    # i18n infrastructure
    "i18n_helper.py",
    # misc infra/helpers
    "context.py",
    "response_util.py",
    "arg_util.py",
}


def _is_non_tool_module(path: Path) -> bool:
    # utilities: anything under tools/ that isn't a tool entry module
    # (tools are standardized as *_tool.py)
    return path.suffix == ".py" and not path.name.endswith("_tool.py") and path.name not in EXCLUDE_FILES


def _iter_docstring_ranges(tree: ast.AST) -> list[tuple[int, int]]:
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

    return docstring_ranges


def _is_in_ranges(line_no: int, ranges: list[tuple[int, int]]) -> bool:
    for s, e in ranges:
        if s <= line_no <= e:
            return True
    return False


def _has_non_ascii_outside_docstrings(path: Path) -> bool:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))
    docstring_ranges = _iter_docstring_ranges(tree)

    for i, line in enumerate(src.splitlines(), start=1):
        if _is_in_ranges(i, docstring_ranges):
            continue
        if any(ord(ch) >= 128 for ch in line):
            return True

    return False


def _is_allowed_i18n_call(node: ast.AST) -> bool:
    """Return True if node is a translation call like _(key, default=...)."""

    if not isinstance(node, ast.Call):
        return False

    # _( ... )
    if isinstance(node.func, ast.Name) and node.func.id == "_":
        return True

    return False


def _is_print_or_logging_call(node: ast.Call) -> bool:
    # print(...)
    if isinstance(node.func, ast.Name) and node.func.id == "print":
        return True

    # logger.info(...), logging.warning(...), etc.
    if isinstance(node.func, ast.Attribute):
        if node.func.attr in {"debug", "info", "warning", "error", "exception", "critical"}:
            return True

    return False


def _stringish(node: ast.AST) -> bool:
    return isinstance(node, (ast.Constant, ast.JoinedStr)) and (
        not isinstance(node, ast.Constant) or isinstance(node.value, str)
    )


def _find_user_facing_string_literals(path: Path) -> list[str]:
    """Find likely user-facing string literals outside docstrings.

    Policy (strict): utilities should not embed user-facing English/Japanese strings
    directly. They should either:
      - use tool-local i18n via _(key, default=...), or
      - not emit user-facing text.

    We ONLY flag strings used as messages:
      - return "..."
      - raise X("...")
      - print("...") / logger.*("...") / logging.*("...")

    We intentionally ignore other strings like regex patterns, env var names,
    dictionary keys, file extensions, etc.
    """

    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))
    docstring_ranges = _iter_docstring_ranges(tree)

    offenders: list[str] = []

    def add(node: ast.AST, label: str) -> None:
        lineno = getattr(node, "lineno", None)
        if lineno is None:
            return
        if _is_in_ranges(lineno, docstring_ranges):
            return
        offenders.append(f"L{lineno}: {label}")

    for node in ast.walk(tree):
        # return "..."
        if isinstance(node, ast.Return) and node.value is not None:
            if _is_allowed_i18n_call(node.value):
                continue
            if _stringish(node.value):
                add(node, "return <string>")

        # raise X("...")
        if isinstance(node, ast.Raise) and node.exc is not None:
            exc = node.exc
            if _is_allowed_i18n_call(exc):
                continue
            if isinstance(exc, ast.Call) and exc.args:
                if _is_allowed_i18n_call(exc.args[0]):
                    continue
                if _stringish(exc.args[0]):
                    add(node, "raise <string>")

        # print/logging
        if isinstance(node, ast.Call) and node.args:
            if not _is_print_or_logging_call(node):
                continue
            arg0 = node.args[0]
            if _is_allowed_i18n_call(arg0):
                continue
            if _stringish(arg0):
                add(node, "print/log <string>")

    return offenders


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


def test_tools_utilities_no_user_facing_string_literals() -> None:
    if not TOOLS_DIR.exists():
        pytest.skip("tools dir not found")

    offenders: list[str] = []

    for p in sorted(TOOLS_DIR.glob("*.py")):
        if not _is_non_tool_module(p):
            continue

        hits = _find_user_facing_string_literals(p)
        if hits:
            offenders.append(p.name + "\n  " + "\n  ".join(hits))

    assert offenders == [], "User-facing string literals found in utilities:\n" + "\n\n".join(offenders)
