# src/uagent/tools/code_map_tool.py
from __future__ import annotations

import datetime
import json
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
                        default="Output format: 'json' for structured data, 'mermaid' for visual diagram.",
                    ),
                    "enum": ["json", "mermaid"],
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
                    # Filter out non-symbol matches (e.g. template <...>)
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
                    symbols.append(
                        {
                            "name": name,
                            "line": lineno,
                            "type": (
                                "function"
                                if "def " in pattern
                                or "fn " in pattern
                                or "func " in pattern
                                else "class" if "class " in pattern else "symbol"
                            ),
                        }
                    )
                    break  # one match per line (first pattern wins)

    return symbols


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


def _render_mermaid_to_image(mermaid_code: str, output_path: str) -> bool:
    """Render Mermaid diagram to PNG and save to file.

    Uses mermaid-cli (playwright-based) if available, falls back to Mermaid.ink API.
    """
    # Try mermaid-cli Python package first (local playwright rendering)
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
                return True
            return False

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
                return True
    except Exception:
        pass

    return False


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

    # Build tree
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
                ok = _render_mermaid_to_image(mermaid_output, png_path)
                if ok:
                    saved_files.append(png_path)
                else:
                    saved_files.append(f"{png_path} (render failed)")

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

    # JSON output
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
