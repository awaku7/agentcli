# src/uagent/tools/code_map_tool.py
from __future__ import annotations

import ast
import datetime
import errno
import json
import urllib.request
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from ..i18n_helper import make_tool_translator
from .language_detection import EXTENSION_MAP, SYMBOL_PATTERNS, detect_source_language
from .symbols import extract_symbols
from .conflicts import normalize_dependency_versions
from .cmake import cmake_active_source
from .resolvers import (_resolve_go_module, _resolve_module_to_file, _resolve_python_module, _resolve_rs_internal)
from .relations import build_relations
from .manifests import (extract_project_dependencies, extract_manifest_graph, extract_local_artifact_edges, extract_recursive_artifact_edges, extract_dependency_edges)
from .caches import resolve_dependency_cache, dependency_classpath_paths, project_target_frameworks
from .lockfiles import extract_lock_dependencies
from .renderers import build_ontology, build_tree, tree_to_mermaid, render_mermaid_to_image











# Keep the translation catalog at the public tool facade path.
_ = make_tool_translator(Path(__file__).resolve().parent.parent / "code_map_tool.py")

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "devel",
    "x_parallel_safe": True,
    "function": {
        "name": "code_map",
        "description": _(
            "tool.description",
            default="Analyze a codebase directory and output file tree with symbol definitions (classes, functions, etc.) across multiple languages. Supports C#, Python, TypeScript, Go, Rust, C/C++, Java, Kotlin, COBOL, PHP, Ruby, Swift, Dart, Scala, Lua, R, and more. Reads .sln/.csproj, build.gradle.kts, Cargo.toml, go.mod, CMakeLists.txt, Makefile, package.json, pyproject.toml for project-aware source scanning.",
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
                "Code map",
                "COBOL dependencies",
                "COPY dependency",
                "CALL dependency",
                "Java imports",
                "Kotlin imports",
                "C include",
                "C++ include",
                "C# using",
                "Composer autoload",
                "Ruby require",
                "Swift import",
                "Dart import",
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
            "COBOL dependencies",
            "COPY dependency",
            "CALL dependency",
            "Java imports",
            "Kotlin imports",
            "C include",
            "C++ include",
            "C# using",
            "Composer autoload",
            "Ruby require",
            "Swift import",
            "Dart import",
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
# Languages supporting import/relation extraction
SKIP_DIRS = {
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
RELATION_LANGUAGES: set[str] = {
    "Python",
    "TypeScript",
    "JavaScript",
    "TypeScript (React)",
    "JavaScript (React)",
    "Go",
    "Rust",
    "COBOL",
    "COBOL Copybook",
    "Java",
    "Kotlin",
    "Kotlin Script",
    "C",
    "C++",
    "C/C++ Header",
    "Objective-C",
    "Objective-C++",
    "C#",
    "PHP",
    "Ruby",
    "Swift",
    "Dart",
    "Scala",
    "Lua",
    "R",
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
    "Objective-C": [
        r"^\s*@interface\s+(\w+)",
        r"^\s*@protocol\s+(\w+)",
        r"^\s*@implementation\s+(\w+)",
        r"^\s*-\s*\([^)]*\)\s*(\w+)",
        r"^\s*\+\s*\([^)]*\)\s*(\w+)",
    ],
    "Objective-C++": [
        r"^\s*@interface\s+(\w+)",
        r"^\s*@protocol\s+(\w+)",
        r"^\s*@implementation\s+(\w+)",
        r"^\s*class\s+(\w+)",
        r"^\s*namespace\s+(\w+)",
    ],
}

# ---------------------------------------------------------------------------
# Project file patterns
# ---------------------------------------------------------------------------


def _deduplicate_paths(paths: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in paths:
        path = Path(value).resolve()
        key = os.path.normcase(str(path))
        if path.is_file() and key not in seen:
            seen.add(key)
            result.append(str(path))
    return result


def _collect_source_files(root: Path) -> list[str]:
    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(str(root)):
        dirnames[:] = [
            d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")
        ]
        for filename in filenames:
            if Path(filename).suffix.lower() in EXTENSION_MAP:
                files.append(str(Path(dirpath) / filename))
    return _deduplicate_paths(files)


def _resolve_project_dependencies(dependencies: list[dict[str, Any]], root: Path) -> list[dict[str, Any]]:
    result=[]
    dart_config = root / ".dart_tool" / "package_config.json"
    dart_packages: dict[str, str] = {}
    if dart_config.is_file():
        try:
            cfg=json.loads(dart_config.read_text(encoding="utf-8", errors="replace"))
            for pkg in cfg.get("packages", []):
                if pkg.get("name") and pkg.get("rootUri"):
                    dart_packages[str(pkg["name"])] = str((dart_config.parent / pkg["rootUri"]).resolve())
        except Exception: pass
    for dep in dependencies:
        item=dict(dep)
        if item.get("manager") == "DartPub" and item.get("name") in dart_packages:
            paths=[dart_packages[item["name"]]]
        else:
            paths=resolve_dependency_cache(item, root)
        if paths:
            item["resolved_paths"]=paths
            classpath=dependency_classpath_paths(item, paths, root)
            if classpath: item["classpath_paths"]=classpath
        result.append(item)
    return result


def _find_project_files(root: str) -> dict[str, Any]:
    """Detect all supported project files and merge their source references."""
    root_path = Path(root).resolve()
    projects: list[str] = []
    sources: list[str] = []
    types: list[str] = []

    sln_files = list(root_path.rglob("*.sln"))
    csproj_files: list[Path] = []
    for sln in sln_files:
        try:
            content = sln.read_text(encoding="utf-8", errors="replace")
        except OSError:
            content = ""
        for match in re.finditer(r'"([^"\r\n]+\.csproj)"', content):
            candidate = (sln.parent / match.group(1)).resolve()
            if candidate.is_file():
                csproj_files.append(candidate)
    csproj_files.extend(f for f in root_path.rglob("*.csproj") if f not in csproj_files)
    if sln_files or csproj_files:
        types.append("dotnet")
        projects.extend(str(f.resolve()) for f in sln_files)
        for csproj in csproj_files:
            projects.append(str(csproj))
            try:
                xml_root = ET.parse(csproj).getroot()
                explicit = []
                for item in xml_root.iter():
                    if item.tag.rsplit("}", 1)[-1] == "Compile" and item.get("Include"):
                        explicit.append(
                            str(csproj.parent / item.get("Include").replace("\\", "/"))
                        )
                sources.extend(
                    explicit or [str(f) for f in csproj.parent.rglob("*.cs")]
                )
            except (OSError, ET.ParseError):
                sources.extend(str(f) for f in csproj.parent.rglob("*.cs"))

    gradle_files = list(root_path.rglob("build.gradle.kts")) + list(
        root_path.rglob("build.gradle")
    )
    if gradle_files:
        types.append("gradle")
        projects.extend(str(f.resolve()) for f in gradle_files)
        for project in gradle_files:
            for dirname in ("src/main/java", "src/main/kotlin", "src"):
                base = project.parent / dirname
                for ext in (".java", ".kt"):
                    sources.extend(
                        str(f) for f in base.rglob(f"*{ext}") if base.is_dir()
                    )

    cargo_files = list(root_path.rglob("Cargo.toml"))
    if cargo_files:
        types.append("rust")
        projects.extend(str(f.resolve()) for f in cargo_files)
        for cargo in cargo_files:
            base = cargo.parent / "src"
            sources.extend(str(f) for f in base.rglob("*.rs") if base.is_dir())

    go_mod_files = list(root_path.rglob("go.mod"))
    if go_mod_files:
        types.append("go")
        projects.extend(str(f.resolve()) for f in go_mod_files)
        for go_mod in go_mod_files:
            sources.extend(str(f) for f in go_mod.parent.rglob("*.go"))

    cmake_files = list(root_path.rglob("CMakeLists.txt"))
    if cmake_files:
        types.append("cmake")
        projects.extend(str(f.resolve()) for f in cmake_files)
        for cmake in cmake_files:
            try:
                content = cmake.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for match in re.finditer(
                r"(?:add_executable|add_library|target_sources)\s*\(\s*\w+\s+([^)]+)\)",
                content,
            ):
                for filename in re.findall(r"[\w./]+\.\w+", match.group(1)):
                    sources.append(str(cmake.parent / filename))

    makefiles = list(root_path.rglob("Makefile")) + list(root_path.rglob("makefile"))
    if makefiles:
        types.append("make")
        projects.extend(str(f.resolve()) for f in makefiles)
        for makefile in makefiles:
            try:
                content = makefile.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for match in re.finditer(
                r"^(?:SRCS?|SOURCES?|C_SOURCES|CPP_SOURCES)\s*[+:?]?=\s*(.+)$",
                content,
                re.MULTILINE,
            ):
                for filename in re.findall(r"[\w./]+\.\w+", match.group(1)):
                    sources.append(str(makefile.parent / filename))

    for cmake in cmake_files:
        try: cmake_text = cmake.read_text(encoding="utf-8", errors="replace")
        except OSError: cmake_text = ""
        for m in re.finditer(r"\bfind_package\s*\(\s*([A-Za-z0-9_+.-]+)", cmake_text, re.IGNORECASE):
            projects.append(str(cmake.resolve()))
        for m in re.finditer(r"\btarget_link_libraries\s*\(\s*[^\s)]+\s+([^)]*)\)", cmake_text, re.IGNORECASE | re.DOTALL):
            projects.append(str(cmake.resolve()))

    package_files = list(root_path.rglob("package.json"))
    if package_files:
        types.append("node")
        projects.extend(str(f.resolve()) for f in package_files)
        for package in package_files:
            for dirname in ("src", "lib", "app"):
                base = package.parent / dirname
                for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
                    sources.extend(
                        str(f) for f in base.rglob(f"*{ext}") if base.is_dir()
                    )

    pyproject_files = list(root_path.rglob("pyproject.toml"))
    if pyproject_files:
        types.append("python")
        projects.extend(str(f.resolve()) for f in pyproject_files)
        for pyproject in pyproject_files:
            dirs = ["src", pyproject.parent.name]
            if pyproject.parent != root_path:
                dirs.append(".")
            for dirname in dirs:
                base = pyproject.parent / dirname
                sources.extend(str(f) for f in base.rglob("*.py") if base.is_dir())

    target_frameworks=[]
    for csproj in csproj_files:
        try:
            xml_root=ET.parse(csproj).getroot()
            for node in xml_root.iter():
                if node.tag.rsplit("}",1)[-1] in ("TargetFramework","TargetFrameworks") and node.text:
                    target_frameworks.extend(x.strip() for x in node.text.split(";") if x.strip())
        except (ET.ParseError,OSError): pass
    project_paths = [Path(x) for x in _deduplicate_paths(projects)]
    manifest_candidates= list(root_path.rglob("pom.xml")) + list(root_path.rglob("composer.json")) + list(root_path.rglob("Gemfile")) + list(root_path.rglob("Package.swift")) + list(root_path.rglob("pubspec.yaml")) + list(root_path.rglob("build.sbt")) + list(root_path.rglob("DESCRIPTION")) + list(root_path.rglob("*.rockspec"))
    project_paths.extend(manifest_candidates)
    project_paths = [Path(x) for x in _deduplicate_paths([str(x) for x in project_paths])]
    declared_dependencies = extract_project_dependencies(root_path, project_paths)
    lock_dependencies = extract_lock_dependencies(root_path)
    resolved_dependencies = _resolve_project_dependencies(declared_dependencies, root_path)
    resolved_dependencies, dependency_conflicts = normalize_dependency_versions(resolved_dependencies)
    local_edges = extract_local_artifact_edges(resolved_dependencies, root_path)
    dependency_edges = extract_dependency_edges(root_path) + extract_manifest_graph(root_path) + local_edges + extract_recursive_artifact_edges(resolved_dependencies, root_path)
    return {
        "projects": [str(x) for x in project_paths],
        "dependencies": resolved_dependencies,
        "dependency_conflicts": dependency_conflicts,
        "transitive_dependencies": lock_dependencies,
        "dependency_edges": dependency_edges,
        "sources": _deduplicate_paths(sources),
        "project_type": types[0] if types else None,
        "project_types": types,
        "target_frameworks": sorted(set(target_frameworks)),
    }


# ---------------------------------------------------------------------------
# Symbol extraction
# ---------------------------------------------------------------------------


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
    if output_format not in {"json", "mermaid", "ontology"}:
        return json.dumps(
            {"ok": False, "error": "Unsupported format"}, ensure_ascii=False
        )
    if max_depth < 0:
        return json.dumps(
            {"ok": False, "error": "depth must be >= 0"}, ensure_ascii=False
        )

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
            "dependencies": project_info.get("dependencies", []),
            "dependency_conflicts": project_info.get("dependency_conflicts", []),
            "transitive_dependencies": project_info.get("transitive_dependencies", []),
            "dependency_edges": project_info.get("dependency_edges", []),
            "target_frameworks": project_info.get("target_frameworks", []),
        }

    # Gather file list
    file_list = (
        list(project_info["sources"]) if project_only else _collect_source_files(root)
    )

    # Extract symbols
    files_with_symbols: list[dict[str, Any]] = []
    for fpath in file_list:
        entry: dict[str, Any] = {"path": fpath}
        rel = (
            Path(fpath).relative_to(root) if Path(fpath).is_relative_to(root) else fpath
        )
        entry["relative_path"] = str(rel)
        ext = os.path.splitext(fpath)[1].lower()
        lang = detect_source_language(fpath)
        entry["language"] = lang

        if include_symbols:
            symbols = extract_symbols(fpath)
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
        relations = build_relations(files_with_symbols, str(root))

    # Build tree structure
    tree_root = build_tree(file_list, str(root), max_depth)

    def _timestamp() -> str:
        return datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    def _save_file(content_str: str, ext: str) -> str:
        directory = Path(output_dir) if output_dir else Path.cwd()
        directory.mkdir(parents=True, exist_ok=True)
        stem = f"code_map_{_timestamp()}"
        for index in range(1000):
            suffix = f"_{index}" if index else ""
            candidate = directory / f"{stem}{suffix}.{ext}"
            try:
                fd = os.open(str(candidate), os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            except FileExistsError:
                continue
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content_str)
            return str(candidate)
        raise OSError(errno.EEXIST, "Unable to create a unique output file")

    # Mermaid output
    if output_format == "mermaid" and tree_root:
        mermaid_output = tree_to_mermaid(tree_root)
        saved_files = []

        if output_dir:
            mmd_path = _save_file(mermaid_output, "mmd")
            saved_files.append(mmd_path)

            if render_image:
                png_path = mmd_path.replace(".mmd", ".png")
                err = render_mermaid_to_image(mermaid_output, png_path)
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
        ontology = build_ontology(result, relations)
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
