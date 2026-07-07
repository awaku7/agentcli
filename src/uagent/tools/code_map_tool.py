# src/uagent/tools/code_map_tool.py
from __future__ import annotations

import ast
import datetime
import json
import urllib.request
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "devel",
    "x_parallel_safe": True,
    "function": {
        "name": "code_map",
        "description": _(
            "tool.description",
            default="Analyze a codebase directory and output file tree with symbol definitions (classes, functions, etc.) across multiple languages. Supports C#, Python, TypeScript, Go, Rust, C/C++, Java, Kotlin, and more. Reads .sln/.csproj, build.gradle.kts, Cargo.toml, go.mod, CMakeLists.txt, Makefile, package.json, pyproject.toml for project-aware source scanning.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "code map",
                "codebase structure",
                "file tree",
                "symbol list",
                "project analysis",
                "source code overview",
                "repository structure",
                "コードマップ",
            ],
        ),
        "x_search_terms_en": [
            "code map",
            "codebase structure",
            "file tree",
            "symbol list",
            "project analysis",
            "source code overview",
            "repository structure",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Root directory to analyze (default: current working directory).",
                    ),
                    "default": ".",
                },
                "depth": {
                    "type": "integer",
                    "description": _(
                        "param.depth.description",
                        default="Maximum directory depth to display in tree (0 = unlimited).",
                    ),
                    "default": 0,
                },
                "include_symbols": {
                    "type": "boolean",
                    "description": _(
                        "param.include_symbols.description",
                        default="Whether to extract symbol definitions from source files.",
                    ),
                    "default": True,
                },
                "project_only": {
                    "type": "boolean",
                    "description": _(
                        "param.project_only.description",
                        default="Only scan files referenced by project files (.sln, .csproj, build.gradle.kts, etc.).",
                    ),
                    "default": False,
                },
                "format": {
                    "type": "string",
                    "description": _(
                        "param.format.description",
                        default="Output format: 'json' for structured data, 'mermaid' for visual diagram, 'ontology' for JSON-LD knowledge graph with file relations.",
                    ),
                    "enum": ["json", "mermaid", "ontology"],
                    "default": "json",
                },
                "output_dir": {
                    "type": "string",
                    "description": _(
                        "param.output_dir.description",
                        default="Directory to save the output file instead of returning it. For mermaid format with render_image=true, saves as PNG. Uses naming convention: code_map_<timestamp>.<ext>.",
                    ),
                },
                "render_image": {
                    "type": "boolean",
                    "description": _(
                        "param.render_image.description",
                        default="When format is 'mermaid' and output_dir is set, also render the diagram as a PNG image via Mermaid.ink API.",
                    ),
                    "default": False,
                },
                "include_relations": {
                    "type": "boolean",
                    "description": _(
                        "param.include_relations.description",
                        default="Extract import/require relations between files. When format='ontology', defaults to True. Supported languages: Python, TypeScript, JavaScript, Go, Rust.",
                    ),
                },
            },
            "required": [],
            "additionalProperties": False,
        },
    },
}

BUSY_LABEL = False
STATUS_LABEL = None

# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------
EXTENSION_MAP: dict[str, str] = {
    ".py": "Python",
    ".pyw": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript (React)",
    ".js": "JavaScript",
    ".jsx": "JavaScript (React)",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".go": "Go",
    ".rs": "Rust",
    ".c": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".h": "C/C++ Header",
    ".hpp": "C++ Header",
    ".cs": "C#",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin Script",
    ".swift": "Swift",
    ".rb": "Ruby",
    ".php": "PHP",
    ".scala": "Scala",
    ".dart": "Dart",
    ".lua": "Lua",
    ".r": "R",
    ".m": "Objective-C",
    ".mm": "Objective-C++",
}

# Languages supporting import/relation extraction
RELATION_LANGUAGES: set[str] = {
    "Python",
    "TypeScript",
    "JavaScript",
    "TypeScript (React)",
    "JavaScript (React)",
    "Go",
    "Rust",
}

# ---------------------------------------------------------------------------
# Symbol patterns per language
# ---------------------------------------------------------------------------
SYMBOL_PATTERNS: dict[str, list[str]] = {
    "Python": [
        r"^\s*class\s+(\w+)",
        r"^\s*async\s+def\s+(\w+)",
        r"^\s*def\s+(\w+)",
    ],
    "TypeScript": [
        r"(?:export\s+)?(?:default\s+)?class\s+(\w+)",
        r"(?:export\s+)?interface\s+(\w+)",
        r"(?:export\s+)?type\s+(\w+)",
        r"(?:export\s+)?(?:async\s+)?function\s+(\w+)",
        r"(?:export\s+)?const\s+(\w+)\s*[=:]",
        r"(?:export\s+)?enum\s+(\w+)",
        r"(?:export\s+)?abstract\s+class\s+(\w+)",
    ],
    "JavaScript": [
        r"(?:export\s+)?(?:default\s+)?class\s+(\w+)",
        r"(?:export\s+)?(?:async\s+)?function\s+(\w+)",
        r"(?:export\s+)?const\s+(\w+)\s*[=:]",
    ],
    "Go": [
        r"^func\s+(?:\([^)]+\)\s+)?(\w+)",
        r"^type\s+(\w+)\s+struct",
        r"^type\s+(\w+)\s+interface",
    ],
    "Rust": [
        r"^fn\s+(\w+)",
        r"^pub\s+fn\s+(\w+)",
        r"^struct\s+(\w+)",
        r"^enum\s+(\w+)",
        r"^trait\s+(\w+)",
        r"^impl(?:\s*<[^>]+>)?\s+(\w+)",
        r"^mod\s+(\w+)",
        r"^type\s+(\w+)",
    ],
    "C": [
        r"^struct\s+(\w+)",
        r"^enum\s+(\w+)",
        r"^#define\s+(\w+)",
        r"^(?:static\s+)?(?:inline\s+)?(?:\w+\s+)+\*?\w+\s*\([^)]*\)\s*\{",
        r"^(?:void|int|char|long|float|double|size_t|uint\d+_t|int\d+_t)\s+\*?(\w+)\s*\(",
    ],
    "C++": [
        r"^class\s+(\w+)",
        r"^struct\s+(\w+)",
        r"^enum\s+(\w+)",
        r"^namespace\s+(\w+)",
        r"^template\s*<",
        r"^(?:virtual\s+)?(?:void|int|char|long|float|double|bool|std::\w+|\w+)\s+\*?(\w+)\s*\(",
    ],
    "C#": [
        r"^(?:\s*(?:public|private|protected|internal|static|virtual|override|abstract|sealed|partial|readonly)\s+)*(?:class|interface|struct|enum|record)\s+(\w+)",
        r"^(?:\s*(?:public|private|protected|internal|static|virtual|override|abstract|sealed|partial|async|readonly)\s+)*(?:void|int|string|bool|long|double|float|decimal|char|byte|short|Task|ValueTask|IEnumerable|IActionResult|ActionResult|IActionResult|JsonResult|Task<[^>]+>|Task<(?:IEnumerable<[^>]+>|List<[^>]+>|ActionResult<[^>]+>|[A-Z]\w+))>\s+(\w+)\s*\(",
    ],
    "Java": [
        r"^(?:\s*(?:public|private|protected|static|final|abstract|synchronized)\s+)*(?:class|interface|enum|@interface|record)\s+(\w+)",
        r"@(\w+)",
        r"^(?:\s*(?:public|private|protected|static|final|abstract|synchronized)\s+)*(?:void|[A-Z]\w*|int|long|double|float|boolean|char|byte|short|String|List|Map|Set|Optional|Stream)\s*(?:<[^>]+>)?\s+(\w+)\s*\(",
    ],
    "Kotlin": [
        r"^(?:\s*(?:public|private|protected|internal|open|data|sealed|abstract|override)\s+)*(?:class|data class|sealed class|abstract class|open class|inner class)\s+(\w+)",
        r"^(?:\s*(?:public|private|protected|internal|open|abstract|override)\s+)*interface\s+(\w+)",
        r"^(?:\s*(?:public|private|protected|internal)\s+)*object\s+(\w+)",
        r"^(?:\s*(?:public|private|protected|internal)\s+)*fun\s+(\w+)",
        r"^(?:\s*(?:public|private|protected|internal)\s+)*enum class\s+(\w+)",
    ],
    "Swift": [
        r"^(?:\s*(?:public|private|internal|fileprivate|open)\s+)*(?:class|struct|enum|protocol|extension)\s+(\w+)",
        r"^(?:\s*(?:public|private|internal|fileprivate|open)\s+)*func\s+(\w+)",
        r"^(?:\s*(?:public|private|internal|fileprivate|open)\s+)*var\s+(\w+)",
    ],
    "Ruby": [
        r"^\s*class\s+(\w+)",
        r"^\s*module\s+(\w+)",
        r"^\s*def\s+(?:self\.)?(\w+)",
    ],
    "PHP": [
        r"^\s*(?:abstract\s+|final\s+)?class\s+(\w+)",
        r"^\s*interface\s+(\w+)",
        r"^\s*trait\s+(\w+)",
        r"^\s*(?:public|private|protected|static)\s+function\s+(\w+)",
    ],
    "Scala": [
        r"^\s*(?:case\s+)?class\s+(\w+)",
        r"^\s*object\s+(\w+)",
        r"^\s*trait\s+(\w+)",
        r"^\s*def\s+(\w+)",
    ],
    "Dart": [
        r"^\s*class\s+(\w+)",
        r"^\s*(?:Future|Stream|void|int|String|bool|double|List|Map|Set)\s*<?[^>]*>?\s+(\w+)\s*\(",
    ],
    "Lua": [
        r"^\s*function\s+(\w+)",
        r"^\s*local\s+function\s+(\w+)",
    ],
}

# ---------------------------------------------------------------------------
# Project file patterns
# ---------------------------------------------------------------------------


def _find_project_files(root: str) -> dict[str, Any]:
    """Detect project files and extract source references."""
    result: dict[str, Any] = {
        "projects": [],
        "sources": [],
        "project_type": None,
    }
    root_path = Path(root)

    # .sln (Visual Studio)
    sln_files = list(root_path.rglob("*.sln"))
    if sln_files:
        csproj_files: list[Path] = []
        for sln in sln_files:
            content = sln.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r'"([^"]+\.csproj)"', content):
                csproj_path = sln.parent / m.group(1)
                if csproj_path.exists():
                    csproj_files.append(csproj_path)
        if csproj_files:
            result["project_type"] = "dotnet"
            result["projects"] = [str(sln) for sln in sln_files]
            for csproj in csproj_files:
                try:
                    tree = ET.parse(str(csproj))
                    root_xml = tree.getroot()
                    # SDK-style projects auto-include all .cs
                    for item in root_xml.iter(
                        "{http://schemas.microsoft.com/developer/msbuild/2003}Compile"
                    ):
                        include = item.get("Include", "")
                        if include:
                            full_path = csproj.parent / include.replace("\\", "/")
                            if full_path.exists():
                                result["sources"].append(str(full_path))
                    # If no explicit Compile items, scan project dir for .cs
                    if not result["sources"]:
                        proj_dir = csproj.parent
                        for cs_file in proj_dir.rglob("*.cs"):
                            result["sources"].append(str(cs_file))
                except Exception:
                    # Fallback: scan project dir
                    proj_dir = csproj.parent
                    for cs_file in proj_dir.rglob("*.cs"):
                        result["sources"].append(str(cs_file))
            return result

    # build.gradle.kts (Android / Kotlin/Java)
    gradle_files = list(root_path.rglob("build.gradle.kts"))
    gradle_files += list(root_path.rglob("build.gradle"))
    if gradle_files:
        result["project_type"] = "gradle"
        result["projects"] = [str(f) for f in gradle_files]
        # Scan for .java and .kt in src/
        for gf in gradle_files:
            proj_dir = gf.parent
            for src_dir in ["src/main/java", "src/main/kotlin", "src"]:
                src_path = proj_dir / src_dir
                if src_path.exists():
                    for ext in [".java", ".kt"]:
                        for f in src_path.rglob(f"*{ext}"):
                            result["sources"].append(str(f))
        return result

    # Cargo.toml (Rust)
    cargo_files = list(root_path.rglob("Cargo.toml"))
    if cargo_files:
        result["project_type"] = "rust"
        result["projects"] = [str(f) for f in cargo_files]
        for cf in cargo_files:
            proj_dir = cf.parent
            src_path = proj_dir / "src"
            if src_path.exists():
                for f in src_path.rglob("*.rs"):
                    result["sources"].append(str(f))
        return result

    # go.mod (Go)
    go_mod_files = list(root_path.rglob("go.mod"))
    if go_mod_files:
        result["project_type"] = "go"
        result["projects"] = [str(f) for f in go_mod_files]
        for gm in go_mod_files:
            proj_dir = gm.parent
            for f in proj_dir.rglob("*.go"):
                result["sources"].append(str(f))
        return result

    # CMakeLists.txt (C/C++)
    cmake_files = list(root_path.rglob("CMakeLists.txt"))
    if cmake_files:
        result["project_type"] = "cmake"
        result["projects"] = [str(f) for f in cmake_files]
        for cm in cmake_files:
            try:
                content = cm.read_text(encoding="utf-8", errors="replace")
                # Extract source files from add_executable / add_library / file(GLOB ...)
                for m in re.finditer(
                    r"(?:add_executable|add_library|target_sources)\s*\(\s*\w+\s+([^)]+)\)",
                    content,
                ):
                    parts = re.findall(r"[\w./]+\.\w+", m.group(1))
                    for p in parts:
                        full = cm.parent / p.replace("/", "\\")
                        if full.exists():
                            result["sources"].append(str(full))
            except Exception:
                pass
        return result

    # Makefile
    makefiles = list(root_path.rglob("Makefile"))
    makefiles += list(root_path.rglob("makefile"))
    if makefiles:
        result["project_type"] = "make"
        result["projects"] = [str(f) for f in makefiles]
        for mf in makefiles:
            try:
                content = mf.read_text(encoding="utf-8", errors="replace")
                for m in re.finditer(
                    r"^(?:SRCS?|SOURCES?|C_SOURCES|CPP_SOURCES)\s*[+:?]?=\s*(.+)$",
                    content,
                    re.MULTILINE,
                ):
                    parts = re.findall(r"[\w./]+\.\w+", m.group(1))
                    for p in parts:
                        full = mf.parent / p.replace("/", "\\")
                        if full.exists():
                            result["sources"].append(str(full))
            except Exception:
                pass
        return result

    # package.json (Node/TypeScript)
    pkg_files = list(root_path.rglob("package.json"))
    if pkg_files:
        result["project_type"] = "node"
        result["projects"] = [str(f) for f in pkg_files]
        for pf in pkg_files:
            proj_dir = pf.parent
            for src_dir in ["src", "lib", "app"]:
                src_path = proj_dir / src_dir
                if src_path.exists():
                    for ext in [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"]:
                        for f in src_path.rglob(f"*{ext}"):
                            result["sources"].append(str(f))
        return result

    # pyproject.toml (Python)
    pyproj_files = list(root_path.rglob("pyproject.toml"))
    if pyproj_files:
        result["project_type"] = "python"
        result["projects"] = [str(f) for f in pyproj_files]
        for pf in pyproj_files:
            proj_dir = pf.parent
            src_dirs = ["src", ".", proj_dir.name]
            for src_dir in src_dirs:
                src_path = proj_dir / src_dir
                if src_path.exists():
                    for f in src_path.rglob("*.py"):
                        result["sources"].append(str(f))
        return result

    # Fallback: no project files found
    return result


# ---------------------------------------------------------------------------
# Symbol extraction
# ---------------------------------------------------------------------------


def _extract_symbols(filepath: str) -> list[dict[str, Any]]:
    """Extract symbol definitions from a source file."""
    ext = Path(filepath).suffix.lower()
    lang = EXTENSION_MAP.get(ext)
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
                imports.append({
                    "type": "import",
                    "module": alias.name,
                    "line": node.lineno,
                })
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [alias.name for alias in node.names]
            imports.append({
                "type": "import_from",
                "module": module,
                "names": names,
                "line": node.lineno,
            })
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
            imports.append({
                "type": "import",
                "module": module,
                "names": [],
                "line": source[: m.start()].count("\n") + 1,
            })

    # const x = require('...')
    for m in re.finditer(
        r"(?:require|import)\s*\([\'\"]([^\'\"]+)[\'\"]\)", source
    ):
        module = m.group(1)
        if module.startswith("."):
            imports.append({
                "type": "require",
                "module": module,
                "line": source[: m.start()].count("\n") + 1,
            })

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
    for line in source.split("\n"):
        stripped = line.strip()
        if stripped.startswith("import"):
            in_import_block = True
            # Single-line import
            for m in re.finditer(r'"([^"]+)"', stripped):
                imports.append({
                    "type": "import",
                    "module": m.group(1),
                })
            if "(" not in stripped:
                in_import_block = False
        elif in_import_block:
            if stripped.startswith(")"):
                in_import_block = False
            else:
                for m in re.finditer(r'"([^"]+)"', stripped):
                    imports.append({
                        "type": "import",
                        "module": m.group(1),
                    })
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
        imports.append({
            "type": "use",
            "module": module_path,
            "line": source[: m.start()].count("\n") + 1,
        })

    # extern crate ...
    for m in re.finditer(r"^\s*extern\s+crate\s+(\w+);", source, re.MULTILINE):
        imports.append({
            "type": "extern_crate",
            "module": m.group(1),
        })

    return imports


def _extract_imports(filepath: str) -> list[dict[str, Any]]:
    """Extract import relations from a source file based on its extension."""
    ext = Path(filepath).suffix.lower()
    lang = EXTENSION_MAP.get(ext)
    if lang == "Python":
        return _extract_imports_python(filepath)
    elif lang in (
        "TypeScript", "JavaScript",
        "TypeScript (React)", "JavaScript (React)",
    ):
        return _extract_imports_typescript(filepath)
    elif lang == "Go":
        return _extract_imports_go(filepath)
    elif lang == "Rust":
        return _extract_imports_rust(filepath)
    return []


# ---------------------------------------------------------------------------
# Module → file path resolution
# ---------------------------------------------------------------------------

_RELATIVE_IMPORT_RE = re.compile(r"^\.+")


def _resolve_module_to_file(
    module: str,
    importing_file: str,
    root: str,
    language: str,
) -> list[str]:
    """Resolve a module/import name to actual file paths within the project.

    Returns a list of candidate file paths (empty if unresolvable).
    """
    if language == "Python":
        return _resolve_python_module(module, importing_file, root)
    elif language in (
        "TypeScript", "JavaScript",
        "TypeScript (React)", "JavaScript (React)",
    ):
        return _resolve_ts_module(module, importing_file, root)
    return []


def _resolve_python_module(
    module: str, importing_file: str, root: str
) -> list[str]:
    """Resolve a Python module path to file path(s)."""
    imp_dir = Path(importing_file).parent

    if module.startswith("."):
        # Relative import
        depth = len(_RELATIVE_IMPORT_RE.match(module).group())
        rel_module = module[depth:]
        # Go up `depth - 1` directories
        rel_dir = imp_dir
        for _ in range(depth - 1):
            rel_dir = rel_dir.parent
        if rel_module:
            parts = rel_module.split(".")
            candidate = rel_dir.joinpath(*parts)
        else:
            candidate = rel_dir
        return _find_python_file_for_module_path(candidate)

    # Absolute import: try relative to root
    parts = module.split(".")
    # Try module as file: src/uagent/core.py → src/uagent/core.py
    # Try module as package: src/uagent/__init__.py
    root_path = Path(root)

    # Try relative to root for each package part
    for i in range(len(parts), 0, -1):
        prefix = parts[:i]
        prefix_path = root_path.joinpath(*prefix)
        candidates = _find_python_file_for_module_path(prefix_path)
        if candidates:
            return candidates

    return []


def _find_python_file_for_module_path(base: Path) -> list[str]:
    """Find .py file(s) for a dotted module path base."""
    results: list[str] = []
    py_file = base.with_suffix(".py")
    if py_file.exists() and py_file.is_file():
        results.append(str(py_file.resolve()))
    init_file = base / "__init__.py"
    if init_file.exists() and init_file.is_file():
        results.append(str(init_file.resolve()))
    return results


def _resolve_ts_module(
    module: str, importing_file: str, root: str
) -> list[str]:
    """Resolve a TypeScript/JavaScript module path to file path(s)."""
    imp_dir = Path(importing_file).parent

    if module.startswith("."):
        # Relative import: resolve from importing file's directory
        rel_path = imp_dir / module
    else:
        # Absolute import: resolve from root/src
        root_path = Path(root)
        for base_dir in [root_path / "src", root_path]:
            candidate = base_dir / module
            files = _find_ts_file_for_module_path(candidate)
            if files:
                return files
        return []

    return _find_ts_file_for_module_path(rel_path)


def _find_ts_file_for_module_path(base: Path) -> list[str]:
    """Find TS/JS file(s) for a bare module path (no extension)."""
    results: list[str] = []
    for ext in [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"]:
        f = base.with_suffix(ext)
        if f.exists() and f.is_file():
            results.append(str(f.resolve()))
    # index files
    for ext in [".ts", ".tsx", ".js", ".jsx"]:
        index_file = base / f"index{ext}"
        if index_file.exists() and index_file.is_file():
            results.append(str(index_file.resolve()))
    return results


# ---------------------------------------------------------------------------
# Relation graph builder
# ---------------------------------------------------------------------------


def _build_relations(
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
            if not module:
                continue

            if lang == "Rust":
                # For Rust, check crate:: or self:: references
                if "crate::" in module or "self::" in module:
                    resolved = _resolve_rs_internal(
                        module, fpath, root, file_paths
                    )
                else:
                    # External crate reference - skip unless it's a relative path
                    continue
            elif lang == "Go":
                # For Go, check if the import path contains our root path
                root_path = Path(root).resolve()
                if str(root_path) in module or module.startswith("./") or module.startswith("../"):
                    resolved = _resolve_go_module(module, fpath, root, file_paths)
                else:
                    # External dependency - skip
                    continue
            else:
                resolved = _resolve_module_to_file(
                    module, fpath, root, lang
                )

            for target_path in resolved:
                if target_path in file_paths:
                    relations.append({
                        "type": "import",
                        "source": fpath,
                        "target": target_path,
                        "source_line": imp.get("line", 0),
                        "module": module,
                    })

    return relations


def _resolve_rs_internal(
    module: str, importing_file: str, root: str, file_paths: set[str]
) -> list[str]:
    """Resolve Rust crate:: and self:: paths to actual files."""
    imp_dir = Path(importing_file).parent
    root_path = Path(root).resolve()

    # crate::symbol → look in src/
    module = module.replace("crate::", "")
    # self::symbol → relative to current file's directory
    module = module.replace("self::", "")

    parts = module.split("::")
    # Try as files in src/ or relative
    src_dirs = [root_path / "src", imp_dir]
    results: list[str] = []
    for src_dir in src_dirs:
        for i in range(len(parts), 0, -1):
            prefix = parts[:i]
            candidate = src_dir.joinpath(*prefix)
            # Check candidate.rs
            rs_file = candidate.with_suffix(".rs")
            if rs_file.exists() and str(rs_file.resolve()) in file_paths:
                results.append(str(rs_file.resolve()))
            # Check candidate/mod.rs
            mod_file = candidate / "mod.rs"
            if mod_file.exists() and str(mod_file.resolve()) in file_paths:
                results.append(str(mod_file.resolve()))
    return results


def _resolve_go_module(
    module: str, importing_file: str, root: str, file_paths: set[str]
) -> list[str]:
    """Resolve a Go import (relative) to actual file path."""
    imp_dir = Path(importing_file).parent
    try:
        candidate = (imp_dir / module).resolve()
    except ValueError:
        return []
    if candidate.is_dir():
        # Importing a package directory - check for .go files
        go_files = list(candidate.rglob("*.go"))
        return [str(f.resolve()) for f in go_files if str(f.resolve()) in file_paths]
    return []


# ---------------------------------------------------------------------------
# JSON-LD ontology builder
# ---------------------------------------------------------------------------


def _make_uri(path: str, root: str) -> str:
    """Create a URI-safe identifier from a file path."""
    root_path = Path(root).resolve()
    try:
        rel = Path(path).resolve().relative_to(root_path)
    except ValueError:
        rel = Path(path).name
    return f"uag:file/{rel.as_posix()}"


def _make_symbol_uri(symbol_name: str, file_uri: str) -> str:
    """Create a URI for a symbol."""
    return f"{file_uri}#{symbol_name}"


def _build_ontology(
    core_result: dict[str, Any],
    relations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a JSON-LD ontology graph from code_map results and relations."""
    root = core_result["root"]
    graph: list[dict[str, Any]] = []

    # File nodes
    file_uri_map: dict[str, str] = {}  # absolute path → URI

    for entry in core_result["files"]:
        fpath = entry["path"]
        uri = _make_uri(fpath, root)
        file_uri_map[fpath] = uri

        # File node
        file_node: dict[str, Any] = {
            "@id": uri,
            "@type": "uag:SourceFile",
            "uag:language": entry.get("language", "Unknown"),
            "uag:relative_path": entry.get("relative_path", ""),
        }
        graph.append(file_node)

        # Symbol nodes
        for sym in entry.get("symbols", []):
            sym_uri = _make_symbol_uri(sym["name"], uri)
            sym_type = _symbol_type_to_ontology(sym.get("type", "symbol"))
            sym_node: dict[str, Any] = {
                "@id": sym_uri,
                "@type": sym_type,
                "uag:file": {"@id": uri},
                "uag:line": sym["line"],
                "uag:name": sym["name"],
            }
            graph.append(sym_node)

    # Relation edges
    for rel in relations:
        source_uri = file_uri_map.get(rel["source"])
        target_uri = file_uri_map.get(rel["target"])
        if source_uri and target_uri:
            rel_node: dict[str, Any] = {
                "@id": f"{source_uri}/imports/{Path(rel['target']).name}",
                "@type": "uag:ImportRelation",
                "uag:source": {"@id": source_uri},
                "uag:target": {"@id": target_uri},
                "uag:module": rel.get("module", ""),
                "uag:source_line": rel.get("source_line", 0),
            }
            graph.append(rel_node)

    # Project metadata node
    project_info = core_result.get("project")
    if project_info:
        graph.append({
            "@id": "uag:project",
            "@type": "uag:Project",
            "uag:project_type": project_info.get("type"),
            "uag:root": root,
            "uag:total_files": core_result.get("total_files", 0),
        })

    # Stats node
    graph.append({
        "@id": "uag:stats",
        "@type": "uag:ScanStats",
        "uag:total_files": core_result.get("total_files", 0),
        "uag:total_relations": len(relations),
        "uag:root": root,
    })

    return {
        "@context": {
            "schema": "https://schema.org/",
            "uag": "https://uagent.local/ontology/",
        },
        "@graph": graph,
    }


def _symbol_type_to_ontology(symbol_type: str) -> str:
    """Map code_map symbol types to ontology types."""
    mapping = {
        "function": "uag:Function",
        "class": "uag:Class",
        "interface": "uag:Interface",
        "struct": "uag:Struct",
        "enum": "uag:Enum",
        "symbol": "uag:Symbol",
    }
    return mapping.get(symbol_type, "uag:Symbol")


# ---------------------------------------------------------------------------
# Tree builder
# ---------------------------------------------------------------------------


def _build_tree(
    file_list: list[str], root: str, max_depth: int
) -> list[dict[str, Any]]:
    """Build a nested tree structure from flat file list."""
    root_path = Path(root).resolve()
    tree: list[dict[str, Any]] = []

    for fpath in file_list:
        p = Path(fpath).resolve()
        try:
            rel = p.relative_to(root_path)
        except ValueError:
            continue
        parts = rel.parts
        if max_depth > 0 and len(parts) > max_depth:
            continue

        current = tree
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                # File node
                current.append(
                    {
                        "name": part,
                        "type": "file",
                        "path": str(p),
                    }
                )
            else:
                # Directory node
                existing = [
                    n
                    for n in current
                    if n.get("name") == part and n.get("type") == "dir"
                ]
                if existing:
                    current = existing[0].setdefault("children", [])
                else:
                    new_dir = {"name": part, "type": "dir", "children": []}
                    current.append(new_dir)
                    current = new_dir["children"]

    return tree


def _tree_to_mermaid(tree: list[dict[str, Any]], root_name: str = "root") -> str:
    """Convert a nested tree structure to Mermaid graph TD format."""
    lines = ["graph TD"]
    node_id = [0]

    def _add_node(node: dict[str, Any], parent_id: str | None = None) -> str:
        node_id[0] += 1
        nid = f"n{node_id[0]}"
        name = node.get("name", "")
        safe_name = name.replace('"', "'").replace("(", "").replace(")", "")
        safe_name = (
            safe_name.replace("[", "")
            .replace("]", "")
            .replace("{", "")
            .replace("}", "")
        )

        if node.get("type") == "dir":
            label = f"{safe_name}/"
            lines.append(f'    {nid}["{label}"]')
        else:
            label = safe_name
            lines.append(f'    {nid}["{label}"]')

        if parent_id:
            lines.append(f"    {parent_id} --> {nid}")

        for child in node.get("children", []):
            _add_node(child, nid)

        return nid

    for child in tree:
        _add_node(child, None)

    return "\n".join(lines)


def _render_mermaid_to_image(mermaid_code: str, output_path: str) -> str | None:
    """Render Mermaid diagram to PNG and save to file.

    Returns None on success, or an error message string on failure.
    Uses mermaid-cli (playwright-based) if available, falls back to Mermaid.ink API.
    """
    mermaid_cli_hint = "Install mermaid-cli: pip install mermaid-cli"
    from .._pip_auto import install_with_status

    # Try mermaid-cli Python package first (local playwright rendering)
    if install_with_status("mermaid-cli", "mermaid_cli"):
        try:
            import asyncio
            from mermaid_cli import render_mermaid

            async def _render():
                _, _, png_bytes = await render_mermaid(
                    mermaid_code, output_format="png"
                )
                if png_bytes:
                    with open(output_path, "wb") as f:
                        f.write(png_bytes)
                    return None
                return "render returned no data"

            return asyncio.run(_render())
        except Exception:
            pass

    # Fallback: Mermaid.ink API via base64 GET
    try:
        import base64

        encoded = base64.urlsafe_b64encode(mermaid_code.encode("utf-8")).decode("ascii")
        url = f"https://mermaid.ink/img/{encoded}"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0")
        with urllib.request.urlopen(req, timeout=30) as resp:
            png_bytes = resp.read()
            if png_bytes:
                with open(output_path, "wb") as f:
                    f.write(png_bytes)
                return None
            return "Mermaid.ink returned no data"
    except Exception:
        pass

    return f"Render failed (try: {mermaid_cli_hint})"


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------


def run_tool(args: dict[str, Any]) -> str:
    base_path = args.get("path", ".").strip()
    if not base_path:
        base_path = "."
    max_depth = int(args.get("depth", 0))
    include_symbols = bool(args.get("include_symbols", True))
    project_only = bool(args.get("project_only", False))
    output_format = args.get("format", "json")
    output_dir = args.get("output_dir", "").strip() or None
    render_image = bool(args.get("render_image", False))

    # include_relations: default True when format=ontology
    include_relations_raw = args.get("include_relations")
    if include_relations_raw is None:
        include_relations = output_format == "ontology"
    else:
        include_relations = bool(include_relations_raw)

    root = Path(base_path).resolve()
    if not root.exists() or not root.is_dir():
        return json.dumps(
            {"ok": False, "error": f"Directory not found: {base_path}"},
            ensure_ascii=False,
        )

    result: dict[str, Any] = {
        "ok": True,
        "root": str(root),
        "project": None,
        "files": [],
        "total_files": 0,
    }

    # Detect project files
    project_info = _find_project_files(str(root))
    if project_info["project_type"]:
        result["project"] = {
            "type": project_info["project_type"],
            "files": project_info["projects"],
        }

    # Gather file list
    if project_only and project_info["sources"]:
        file_list = project_info["sources"]
    else:
        # Walk filesystem from root
        file_list = []
        for dirpath, _dirnames, filenames in os.walk(str(root)):
            # Skip hidden dirs and common generated dirs
            skip_dirs = {
                ".git",
                ".svn",
                "__pycache__",
                "node_modules",
                "bin",
                "obj",
                "build",
                "dist",
                ".gradle",
                "target",
                ".next",
                ".nuxt",
                ".output",
                "venv",
                ".venv",
                ".tox",
            }
            _dirnames[:] = [
                d for d in _dirnames if d not in skip_dirs and not d.startswith(".")
            ]
            for fname in filenames:
                fpath = os.path.join(dirpath, fname)
                ext = os.path.splitext(fname)[1].lower()
                if ext in EXTENSION_MAP:
                    file_list.append(fpath)
        # Deduplicate
        file_list = list(dict.fromkeys(file_list))

    if project_info["sources"] and not project_only:
        # Merge: project sources take priority, but also include other detected files
        extra = [f for f in file_list if f not in set(project_info["sources"])]
        file_list = list(dict.fromkeys(project_info["sources"] + extra))

    # Extract symbols
    files_with_symbols: list[dict[str, Any]] = []
    for fpath in file_list:
        entry: dict[str, Any] = {"path": fpath}
        rel = (
            Path(fpath).relative_to(root) if Path(fpath).is_relative_to(root) else fpath
        )
        entry["relative_path"] = str(rel)
        ext = os.path.splitext(fpath)[1].lower()
        lang = EXTENSION_MAP.get(ext, "Unknown")
        entry["language"] = lang

        if include_symbols:
            symbols = _extract_symbols(fpath)
            if symbols:
                entry["symbols"] = symbols
            else:
                entry["symbols"] = []
        files_with_symbols.append(entry)

    result["files"] = files_with_symbols
    result["total_files"] = len(files_with_symbols)

    # Build relations if requested
    relations: list[dict[str, Any]] = []
    if include_relations:
        relations = _build_relations(files_with_symbols, str(root))

    # Build tree structure
    tree_root = _build_tree(file_list, str(root), max_depth)

    def _timestamp() -> str:
        return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    def _save_file(content_str: str, ext: str) -> str:
        ts = _timestamp()
        fname = f"code_map_{ts}.{ext}"
        if output_dir:
            d = Path(output_dir)
            d.mkdir(parents=True, exist_ok=True)
            fpath = str(d / fname)
        else:
            fpath = fname
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content_str)
        return fpath

    # Mermaid output
    if output_format == "mermaid" and tree_root:
        mermaid_output = _tree_to_mermaid(tree_root)
        saved_files = []

        if output_dir:
            mmd_path = _save_file(mermaid_output, "mmd")
            saved_files.append(mmd_path)

            if render_image:
                png_path = mmd_path.replace(".mmd", ".png")
                err = _render_mermaid_to_image(mermaid_output, png_path)
                if err is None:
                    saved_files.append(png_path)
                else:
                    saved_files.append(f"{png_path} ({err})")

            return json.dumps(
                {
                    "ok": True,
                    "saved_files": saved_files,
                    "message": f"Saved {len(saved_files)} file(s).",
                },
                ensure_ascii=False,
                indent=2,
            )

        return mermaid_output

    # Ontology output (JSON-LD)
    if output_format == "ontology":
        ontology = _build_ontology(result, relations)
        json_output = json.dumps(ontology, ensure_ascii=False, indent=2)

        if output_dir:
            jsonld_path = _save_file(json_output, "jsonld")
            return json.dumps(
                {
                    "ok": True,
                    "saved_files": [jsonld_path],
                    "message": f"Saved ontology to {jsonld_path}",
                },
                ensure_ascii=False,
                indent=2,
            )

        return json_output

    # JSON output (standard)
    if include_relations and relations:
        result["relations"] = relations

    json_output = json.dumps(result, ensure_ascii=False, indent=2)

    if output_dir:
        json_path = _save_file(json_output, "json")
        return json.dumps(
            {
                "ok": True,
                "saved_files": [json_path],
                "message": f"Saved to {json_path}",
            },
            ensure_ascii=False,
            indent=2,
        )

    return json_output
