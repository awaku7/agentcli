"""Symbol extraction helpers for code_map."""

from __future__ import annotations

import re
from typing import Any

from .language_detection import SYMBOL_PATTERNS, detect_source_language
from .tree_sitter_symbols import extract_tree_sitter_symbols


def extract_symbols(filepath: str) -> list[dict[str, Any]]:
    """Extract symbol definitions from a source file."""
    lang = detect_source_language(filepath)
    if not lang:
        return []

    # Prefer a syntax tree when a supported grammar is available.  The helper
    # deliberately returns an empty list on optional-dependency or parse
    # failures, so the established regex extractor remains a reliable fallback.
    tree_symbols = extract_tree_sitter_symbols(filepath, lang)
    if tree_symbols:
        return tree_symbols

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
                    if lang in ("VBA", "LotusScript"):
                        if re.search(r"\b(?:Sub|Function|Property)\b", pattern):
                            symbol_type = "function"
                        elif re.search(r"\b(?:Type|Enum|Class)\b", pattern):
                            symbol_type = "class"
                    elif "def " in pattern or "fn " in pattern or "func " in pattern:
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
