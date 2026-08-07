"""Project-local module and dependency path resolvers."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from .language_detection import RELATION_LANGUAGES

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
        "TypeScript",
        "JavaScript",
        "TypeScript (React)",
        "JavaScript (React)",
    ):
        return _resolve_ts_module(module, importing_file, root)
    elif language in ("COBOL", "COBOL Copybook"):
        return _resolve_cobol_module(module, importing_file, root)
    elif language in RELATION_LANGUAGES:
        return _resolve_extended_module(module, importing_file, root, language)
    return []


def _resolve_python_module(
    module: str,
    importing_file: str,
    root: str,
    *,
    level: int = 0,
    names: list[str] | None = None,
) -> list[str]:
    imp_dir = Path(importing_file).resolve().parent
    root_path = Path(root).resolve()
    if level > 0 or module.startswith("."):
        if level <= 0:
            match = _RELATIVE_IMPORT_RE.match(module)
            level = len(match.group()) if match else 0
            module = module[level:]
        base_dir = imp_dir
        for _ in range(max(level - 1, 0)):
            base_dir = base_dir.parent
        modules = ([module] if module else []) + [
            n for n in (names or []) if n and n != module
        ]
        results = []
        for item in modules:
            candidate = base_dir.joinpath(*item.split(".")) if item else base_dir
            results.extend(_find_python_file_for_module_path(candidate))
        return list(dict.fromkeys(results))
    parts = module.split(".") if module else []
    for base in (root_path, root_path / "src"):
        candidates = _find_python_file_for_module_path(base.joinpath(*parts))
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


def _resolve_cobol_module(module: str, importing_file: str, root: str) -> list[str]:
    """Resolve COBOL COPY/CALL names to local source or copybook files."""
    name = Path(module).name
    importing_dir = Path(importing_file).resolve().parent
    root_path = Path(root).resolve()
    search_dirs = [importing_dir, root_path, root_path / "src", root_path / "copybooks", root_path / "cpy"]
    suffixes = ["", ".cpy", ".CPY", ".cbl", ".CBL", ".cob", ".COB", ".cobol"]
    results: list[str] = []
    for directory in search_dirs:
        for suffix in suffixes:
            candidate = directory / (name + suffix)
            if candidate.is_file():
                results.append(str(candidate.resolve()))
    return list(dict.fromkeys(results))


def _resolve_extended_module(module: str, importing_file: str, root: str, language: str) -> list[str]:
    """Resolve common project-local imports/includes for extended languages."""
    root_path = Path(root).resolve()
    source_dir = Path(importing_file).resolve().parent
    module = module.strip().strip("'\"")
    if language in ("C", "C++", "C/C++ Header", "Ruby", "PHP", "Dart", "Lua", "R") and (module.startswith("/") or module.startswith(".")):
        base = source_dir / module
    elif language in ("Java", "Kotlin", "Kotlin Script", "Scala", "C#"):
        base = root_path.joinpath(*module.replace("\\", ".").split("."))
    else:
        base = root_path / module
    suffixes = [""]
    suffixes += {
        "Java": [".java"], "Kotlin": [".kt", ".kts"], "Kotlin Script": [".kt", ".kts"],
        "Scala": [".scala"], "C#": [".cs"], "C": [".c", ".h"],
        "C++": [".cpp", ".cc", ".cxx", ".hpp", ".h"],
        "Objective-C": [".m", ".h"], "Objective-C++": [".mm", ".h", ".hpp"], "C/C++ Header": [".h", ".hpp"],
        "PHP": [".php"], "Ruby": [".rb"], "Swift": [".swift"], "Dart": [".dart"],
        "Lua": [".lua"], "R": [".r"],
    }.get(language, [])
    candidates = [base]
    if not str(base).startswith(str(root_path)):
        candidates.append(root_path / module)
    results: list[str] = []
    for candidate in candidates:
        for suffix in suffixes:
            path = candidate if not suffix else Path(str(candidate) + suffix)
            if path.is_file(): results.append(str(path.resolve()))
        if candidate.is_dir():
            for suffix in suffixes:
                if suffix and (candidate / (candidate.name + suffix)).is_file():
                    results.append(str((candidate / (candidate.name + suffix)).resolve()))
    return list(dict.fromkeys(results))


def _resolve_ts_module(module: str, importing_file: str, root: str) -> list[str]:
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
    return list(dict.fromkeys(results))


def _read_go_module(root: str) -> str | None:
    for go_mod in [
        Path(root).resolve() / "go.mod",
        *Path(root).resolve().rglob("go.mod"),
    ]:
        try:
            for line in go_mod.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines():
                match = re.match(r"\s*module\s+(\S+)", line)
                if match:
                    return match.group(1)
        except OSError:
            continue
    return None


def _resolve_go_module(
    module: str, importing_file: str, root: str, file_paths: set[str]
) -> list[str]:
    root_path = Path(root).resolve()
    module_name = _read_go_module(str(root_path))
    if module_name and (module == module_name or module.startswith(module_name + "/")):
        candidate = root_path / module[len(module_name) :].lstrip("/")
    elif module.startswith(("./", "../")):
        candidate = (Path(importing_file).parent / module).resolve()
    else:
        return []
    if not candidate.is_dir():
        return []
    return [
        str(f.resolve())
        for f in candidate.glob("*.go")
        if str(f.resolve()) in file_paths
    ]


