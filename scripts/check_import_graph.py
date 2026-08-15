"""Fail if runtime/provider modules introduce forbidden core back-references."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "uagent"
FORBIDDEN_PREFIXES = ("uagent.runtime", "uagent.providers")


def main() -> int:
    violations: list[str] = []
    for path in ROOT.rglob("*.py"):
        module = ".".join(path.relative_to(ROOT.parent).with_suffix("").parts)
        if not module.startswith(FORBIDDEN_PREFIXES):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
        except SyntaxError as exc:
            violations.append(f"{path}: syntax error: {exc}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = (
                    [node.module or ""]
                    if node.level == 0
                    else ["uagent." + (node.module or "")]
                )
            else:
                continue
            if any(name == "uagent.core" for name in names):
                violations.append(f"{path}:{getattr(node, 'lineno', 0)} imports core")
    if violations:
        print("\n".join(violations))
        return 1
    print("import graph policy: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
