"""Import and dependency relation extraction for code_map."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from .language_detection import detect_source_language

try:
    from .language_detection import RELATION_LANGUAGES
except ImportError:  # compatibility with a stale module during hot reload
    RELATION_LANGUAGES = {
        "Python",
        "TypeScript",
        "JavaScript",
        "Go",
        "Rust",
        "COBOL",
        "COBOL Copybook",
        "Java",
        "Kotlin",
        "Scala",
        "C",
        "C++",
        "C#",
        "PHP",
        "Ruby",
        "Swift",
        "Dart",
        "Lua",
        "R",
        "Objective-C",
        "Objective-C++",
    }
from .resolvers import (
    _resolve_go_module,
    _resolve_module_to_file,
    _resolve_python_module,
    _resolve_rs_internal,
)

# ---------------------------------------------------------------------------
# Import / relation extraction
# ---------------------------------------------------------------------------


def _extract_imports_python(filepath: str) -> list[dict[str, Any]]:
    """Extract import relations from a Python file using AST."""
    imports: list[dict[str, Any]] = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        tree = ast.parse(source, filename=filepath)
    except (SyntaxError, Exception):
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(
                    {
                        "type": "import",
                        "module": alias.name,
                        "line": node.lineno,
                    }
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [alias.name for alias in node.names]
            imports.append(
                {
                    "type": "import_from",
                    "module": module,
                    "names": names,
                    "level": node.level,
                    "line": node.lineno,
                }
            )
    return imports


def _extract_imports_typescript(filepath: str) -> list[dict[str, Any]]:
    """Extract import/require relations from TypeScript/JavaScript using regex."""
    imports: list[dict[str, Any]] = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
    except Exception:
        return imports

    # import ... from '...'
    for m in re.finditer(
        r'(?:import\s+(?:[\w*{}\s,]+)\s+from\s+[\'"]([^\'"]+)[\'"]|'
        r'import\s+[\'"]([^\'"]+)[\'"])',
        source,
    ):
        module = m.group(1) or m.group(2)
        if module.startswith("."):
            imports.append(
                {
                    "type": "import",
                    "module": module,
                    "names": [],
                    "line": source[: m.start()].count("\n") + 1,
                }
            )

    # const x = require('...')
    for m in re.finditer(r"(?:require|import)\s*\([\'\"]([^\'\"]+)[\'\"]\)", source):
        module = m.group(1)
        if module.startswith("."):
            imports.append(
                {
                    "type": "require",
                    "module": module,
                    "line": source[: m.start()].count("\n") + 1,
                }
            )

    return imports


def _extract_imports_go(filepath: str) -> list[dict[str, Any]]:
    """Extract import relations from a Go file using regex."""
    imports: list[dict[str, Any]] = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
    except Exception:
        return imports

    # import ( "..." )  or  import "..."
    # Extract quoted paths
    in_import_block = False
    for line_number, line in enumerate(source.split("\n"), 1):
        stripped = line.strip()
        if stripped.startswith("import"):
            in_import_block = True
            # Single-line import
            for m in re.finditer(r'"([^"]+)"', stripped):
                imports.append(
                    {
                        "type": "import",
                        "module": m.group(1),
                        "line": line_number,
                    }
                )
            if "(" not in stripped:
                in_import_block = False
        elif in_import_block:
            if stripped.startswith(")"):
                in_import_block = False
            else:
                for m in re.finditer(r'"([^"]+)"', stripped):
                    imports.append(
                        {
                            "type": "import",
                            "module": m.group(1),
                        }
                    )
    return imports


def _extract_imports_rust(filepath: str) -> list[dict[str, Any]]:
    """Extract import relations from a Rust file using regex."""
    imports: list[dict[str, Any]] = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
    except Exception:
        return imports

    # use crate::...  or  use ...::...
    for m in re.finditer(r"^\s*use\s+([^;]+);", source, re.MULTILINE):
        module_path = m.group(1).strip()
        imports.append(
            {
                "type": "use",
                "module": module_path,
                "line": source[: m.start()].count("\n") + 1,
            }
        )

    # extern crate ...
    for m in re.finditer(r"^\s*extern\s+crate\s+(\w+);", source, re.MULTILINE):
        imports.append(
            {
                "type": "extern_crate",
                "module": m.group(1),
            }
        )

    return imports


def _extract_imports_cobol(filepath: str) -> list[dict[str, Any]]:
    """Extract COBOL COPY and CALL dependencies from a source file."""
    imports: list[dict[str, Any]] = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
    except Exception:
        return imports

    # COPY copybook [REPLACING ...].  Ignore commented source lines.
    for line_number, line in enumerate(source.splitlines(), 1):
        if len(line) >= 7 and line[6] in ("*", "/"):
            continue
        code = line[7:] if len(line) > 7 else line
        copy_match = re.search(r"\bCOPY\s+([A-Za-z0-9_-]+)", code, re.IGNORECASE)
        if copy_match:
            imports.append(
                {"type": "copy", "module": copy_match.group(1), "line": line_number}
            )
        for call_match in re.finditer(
            r"\bCALL\s+([A-Za-z0-9_-]+|\"[^\"]+\"|'[^']+')", code, re.IGNORECASE
        ):
            module = call_match.group(1).strip("\"'")
            if module:
                imports.append({"type": "call", "module": module, "line": line_number})
    return imports


def _extract_imports_extended(filepath: str, language: str) -> list[dict[str, Any]]:
    """Extract common dependency declarations for additional languages."""
    try:
        source = Path(filepath).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    imports: list[dict[str, Any]] = []
    patterns: list[tuple[str, str]] = []
    if language in ("Java", "Kotlin", "Kotlin Script", "Scala"):
        patterns.append(("import", r"^\s*import\s+([A-Za-z_][\w.]*)"))
    elif language in ("C", "C++", "C/C++ Header", "Objective-C", "Objective-C++"):
        patterns.append(
            ("include", r"^\s*#\s*(?:include|import)\s*[<\"]([^>\"]+)[>\"]")
        )
    elif language == "C#":
        patterns.append(("using", r"^\s*using\s+(?:static\s+)?([A-Za-z_][\w.]*)\s*;"))
    elif language == "PHP":
        patterns.extend(
            [
                (
                    "require",
                    r"\b(?:require|require_once|include|include_once)\s*[('\"]([^)'\"]+)[)'\"]",
                ),
                ("use", r"^\s*use\s+([A-Za-z_][\\\w]*)"),
            ]
        )
    elif language == "Ruby":
        patterns.extend(
            [
                ("require", r"^\s*require(?:_relative)?\s*[('\"]([^)'\"]+)[)'\"]"),
            ]
        )
    elif language == "Swift":
        patterns.append(("import", r"^\s*import\s+(?:typealias\s+)?([A-Za-z_][\w.]*)"))
    elif language == "Dart":
        patterns.append(("import", r"^\s*import\s+['\"]([^'\"]+)['\"]"))
    elif language == "Lua":
        patterns.append(("require", r"\brequire\s*[('\"]([^)'\"]+)[)'\"]"))
    elif language == "R":
        patterns.extend(
            [
                ("library", r"\b(?:library|require)\s*\(\s*['\"]?([A-Za-z0-9_.-]+)"),
                ("source", r"\bsource\s*\(\s*['\"]([^'\"]+)['\"]"),
            ]
        )
    elif language == "VBA":
        patterns.extend(
            [
                (
                    "declare",
                    r"^\s*(?:Public\s+|Private\s+)?Declare\s+(?:PtrSafe\s+)?(?:Function|Sub)\s+(\w+)",
                ),
                ("reference", r"^\s*Attribute\s+VB_Name\s*=\s*[\"']([^\"']+)"),
            ]
        )
    elif language == "LotusScript":
        patterns.extend(
            [
                ("use", r"^\s*(?:Option\s+)?Use(?:LSX)?\s+[\"']?([^\"'\s]+)"),
                ("use", r"^\s*UseLSX\s+[\"']([^\"']+)"),
            ]
        )
    for kind, pattern in patterns:
        for match in re.finditer(pattern, source, re.IGNORECASE | re.MULTILINE):
            module = match.group(1).strip()
            if module:
                imports.append(
                    {
                        "type": kind,
                        "module": module,
                        "line": source[: match.start()].count("\n") + 1,
                    }
                )
    return imports


def _extract_imports(filepath: str) -> list[dict[str, Any]]:
    """Extract import relations from a source file based on its extension."""
    lang = detect_source_language(filepath)
    if lang == "Python":
        return _extract_imports_python(filepath)
    elif lang in (
        "TypeScript",
        "JavaScript",
        "TypeScript (React)",
        "JavaScript (React)",
    ):
        return _extract_imports_typescript(filepath)
    elif lang == "Go":
        return _extract_imports_go(filepath)
    elif lang == "Rust":
        return _extract_imports_rust(filepath)
    elif lang in ("COBOL", "COBOL Copybook"):
        return _extract_imports_cobol(filepath)
    elif lang in RELATION_LANGUAGES:
        return _extract_imports_extended(filepath, lang)
    return []


# Relation graph builder


def build_relations(
    files_with_symbols: list[dict[str, Any]],
    root: str,
) -> list[dict[str, Any]]:
    """Build a relation graph from import statements across all files.

    Returns a list of relation objects:
      {
        "type": "import",
        "source": "<absolute path of importing file>",
        "target": "<absolute path of imported file>",
        "source_line": <line number>,
        "module": "<raw module string>"
      }
    """
    # Build a lookup of absolute path → file entry for quick resolution
    file_paths: set[str] = {entry["path"] for entry in files_with_symbols}
    relations: list[dict[str, Any]] = []

    for entry in files_with_symbols:
        fpath = entry["path"]
        lang = entry.get("language", "")
        if lang not in RELATION_LANGUAGES:
            continue

        imports = _extract_imports(fpath)
        for imp in imports:
            module = imp.get("module", "")
            if not module and not (lang == "Python" and imp.get("names")):
                continue

            if lang == "Rust":
                # For Rust, check crate:: or self:: references
                if "crate::" in module or "self::" in module:
                    resolved = _resolve_rs_internal(module, fpath, root, file_paths)
                else:
                    # External crate reference - skip unless it's a relative path
                    continue
            elif lang == "Go":
                resolved = _resolve_go_module(module, fpath, root, file_paths)
            elif lang == "Python":
                resolved = _resolve_python_module(
                    module,
                    fpath,
                    root,
                    level=int(imp.get("level", 0)),
                    names=imp.get("names", []),
                )
            else:
                resolved = _resolve_module_to_file(module, fpath, root, lang)

            for target_path in resolved:
                if target_path in file_paths:
                    relations.append(
                        {
                            "type": "import",
                            "source": fpath,
                            "target": target_path,
                            "source_line": imp.get("line", 0),
                            "module": module,
                        }
                    )

    return relations
