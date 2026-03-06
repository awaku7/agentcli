from __future__ import annotations

import ast
import pathlib
import re

import pytest


def _repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[1]


TOOLS_DIR = _repo_root() / "src" / "uagent" / "tools"


# Policy A (realistic): only catch obvious user-facing messages returned as text.
# We intentionally ignore:
# - docstrings
# - raise ...("...") validation messages
# - print(...) / logging.*(...) developer/operator messages
#
# We only flag `return "..."` when it looks like an error/message.
USER_FACING_RETURN_RE = re.compile(
    r"(?i)(^\s*\[.*?error\]|^\s*error\s*:|error|failed|forbidden|denied|not\s+found|invalid|required|missing|blocked|cannot|can\s*not|unable|exception|timeout)"
)


def _is_docstring(node: ast.AST, parent: ast.AST) -> bool:
    if not isinstance(node, ast.Expr):
        return False
    if not isinstance(node.value, ast.Constant) or not isinstance(
        node.value.value, str
    ):
        return False
    # Module docstring
    if isinstance(parent, ast.Module) and parent.body and parent.body[0] is node:
        return True
    # Function/Class docstring
    if (
        isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and parent.body
        and parent.body[0] is node
    ):
        return True
    return False


def _iter_with_parents(tree: ast.AST):
    parents: dict[int, ast.AST] = {}

    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent

    for node in ast.walk(tree):
        yield node, parents.get(id(node))


def _collect_violations(path: pathlib.Path) -> list[tuple[int, str]]:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))

    violations: list[tuple[int, str]] = []

    for node, parent in _iter_with_parents(tree):
        if parent is not None and _is_docstring(node, parent):
            continue

        # return "..." (only if it looks like a message)
        if isinstance(node, ast.Return) and node.value is not None:
            v = node.value
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                s = v.value.strip()
                if USER_FACING_RETURN_RE.search(s):
                    violations.append(
                        (node.lineno, f"return message literal: {v.value!r}")
                    )

    return violations


def _tool_py_files() -> list[pathlib.Path]:
    files = sorted(TOOLS_DIR.glob("*_tool.py"))
    return [p for p in files if p.is_file()]


@pytest.mark.parametrize("path", _tool_py_files())
def test_tools_impl_no_user_facing_return_literals(path: pathlib.Path):
    violations = _collect_violations(path)
    if violations:
        detail = "\n".join([f"  L{ln}: {msg}" for ln, msg in violations[:30]])
        pytest.fail(
            "User-facing return string literals must be i18n'd via _() "
            f"in {path}\n{detail}\n"
        )
