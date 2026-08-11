"""Symbol extraction helpers for code_map."""

from __future__ import annotations

import re
from typing import Any

from .language_detection import SYMBOL_PATTERNS, detect_source_language


def extract_symbols(filepath: str) -> list[dict[str, Any]]:
    """Extract symbol definitions from a source file."""
    lang = detect_source_language(filepath)
    if not lang:
        return []

    patterns = SYMBOL_PATTERNS.get(lang, [])
    if not patterns and lang not in ("C/C++ Header",):
        return []

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception:
        return []

    symbols: list[dict[str, Any]] = []
    seen: set[str] = set()

    for lineno, line in enumerate(lines, 1):
        stripped = line.rstrip("\n").rstrip("\r")
        # Skip comments and empty lines
        if not stripped or stripped.lstrip().startswith(("//", "#", "--", "/*", "*")):
            continue
        for pattern in patterns:
            for m in re.finditer(pattern, stripped):
                name = m.group(1) if m.lastindex else m.group(0)
                if name and name not in seen:
                    # Filter out non-symbol matches
                    if name in (
                        "if",
                        "else",
                        "for",
                        "while",
                        "switch",
                        "return",
                        "import",
                        "from",
                    ):
                        continue
                    seen.add(name)
                    symbol_type: str = "symbol"
                    if "def " in pattern or "fn " in pattern or "func " in pattern:
                        symbol_type = "function"
                    elif "class " in pattern:
                        symbol_type = "class"
                    elif "interface " in pattern:
                        symbol_type = "interface"
                    elif "struct " in pattern:
                        symbol_type = "struct"
                    elif "enum " in pattern:
                        symbol_type = "enum"
                    symbols.append(
                        {
                            "name": name,
                            "line": lineno,
                            "type": symbol_type,
                        }
                    )
                    break  # one match per line (first pattern wins)

    return symbols
