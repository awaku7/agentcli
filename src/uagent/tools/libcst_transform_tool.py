"""uagent tool: libcst_transform

Tool to analyze or transform Python code using libcst.
"""

from __future__ import annotations

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

import difflib
import fnmatch
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import libcst as cst

from .safe_file_ops import (
    ensure_within_workdir,
    is_path_dangerous,
    make_backup_before_overwrite,
)

BUSY_LABEL = True
STATUS_LABEL = "tool:libcst_transform"


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "libcst_transform",
        "description": _(
            "tool.description",
            default="""libcst transforms Python code by analyzing (analyze) or transforming (transform).
- analyze: Extract imports / classes / functions, etc.
- transform: Apply rule-based bulk transforms (rename_symbol/replace_call/rename_import, etc.)

Safety:
- Reject paths outside workdir
- Create .org/.orgN backup before overwrite when changes occur
""",
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default="""libcst-based Python code analyze/transform tool.

Basic input:
- Specify files/directories in paths (directories are scanned recursively)
- Narrow targets using include_glob/exclude_globs (default include_glob=**/*.py)

mode=analyze:
- Extract import / top-level class/function names and return JSON.

mode=transform:
- Specify an array of rules in ops.
- If a file is changed, create .org/.orgN backup immediately before overwrite.

ops examples:
1) rename_symbol: old_name -> new_name (replace Name nodes)
   {"op":"rename_symbol","old":"foo","new":"bar"}
2) replace_call: old_func(...) -> new_func(...)
   {"op":"replace_call","old":"old_func","new":"new_func"}
3) rename_import: from X import old -> from X import new (module is optional)
   {"op":"rename_import","module":"pkg.mod","old":"Old","new":"New"}
""",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["analyze", "transform"],
                    "description": _(
                        "param.mode.description",
                        default="Execution mode: analyze=analyze / transform=transform",
                    ),
                },
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _(
                        "param.paths.description",
                        default="Array of target files/directories (must be under workdir).",
                    ),
                },
                "include_glob": {
                    "type": "string",
                    "description": _(
                        "param.include_glob.description",
                        default="Include glob when scanning directories (e.g. **/*.py).",
                    ),
                    "default": "**/*.py",
                },
                "exclude_globs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _(
                        "param.exclude_globs.description",
                        default="Array of exclude globs (e.g. **/.venv/**, **/__pycache__/**).",
                    ),
                    "default": [
                        "**/.git/**",
                        "**/.venv/**",
                        "**/venv/**",
                        "**/__pycache__/**",
                        "**/node_modules/**",
                        "**/.mypy_cache/**",
                        "**/.ruff_cache/**",
                    ],
                },
                "max_files": {
                    "type": "integer",
                    "description": _(
                        "param.max_files.description",
                        default="Maximum number of files to scan (runaway protection).",
                    ),
                    "default": 20000,
                },
                "max_bytes": {
                    "type": "integer",
                    "description": _(
                        "param.max_bytes.description",
                        default="Maximum file size (bytes).",
                    ),
                    "default": 2_000_000,
                },
                "ops": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "op": {
                                "type": "string",
                                "enum": [
                                    "rename_symbol",
                                    "replace_call",
                                    "rename_import",
                                ],
                                "description": "Operation type",
                            },
                            "old": {"type": "string", "description": "Old name"},
                            "new": {"type": "string", "description": "New name"},
                            "module": {
                                "type": "string",
                                "description": "Module path for rename_import (optional)",
                            },
                            "receiver": {
                                "type": "string",
                                "description": "Receiver expression for replace_call (optional)",
                            },
                            "include_attributes": {
                                "type": "boolean",
                                "description": "Also rename attributes (optional)",
                                "default": False,
                            },
                        },
                    },
                    "description": _(
                        "param.ops.description",
                        default="""Transform rules array for mode=transform.

Note: use 'ops' (not 'operations') due to provider schema restrictions.

Supported ops:
- rename_symbol: replace identifier (requires old/new)
  - include_attributes=true also targets obj.old
- replace_call: replace function call name (requires old/new)
  - receiver targets only receiver.old(...)
  - receiver supports dotted expression (e.g. self.obj, pkg.obj)
  - if receiver is omitted, targets old(...) and *.old(...)
- rename_import:
  - from X import old -> from X import new (module is optional)
  - import old -> import new
""",
                    ),
                    "default": [],
                },
                "preview": {
                    "type": "boolean",
                    "description": _(
                        "param.preview.description",
                        default="If true, return diff preview without writing files (dry-run mode).",
                    ),
                    "default": False,
                },
            },
            "required": ["mode", "paths"],
        },
    },
}


def _json_ok(payload: Dict[str, Any]) -> str:
    payload.setdefault("ok", True)
    return json.dumps(payload, ensure_ascii=False)


def _json_err(
    message: str,
    *,
    details: Any = None,
    file: Optional[str] = None,
    line: Optional[int] = None,
    column: Optional[int] = None,
) -> str:
    obj: Dict[str, Any] = {"ok": False, "error": message}
    if details is not None:
        obj["details"] = details
    if file is not None:
        obj["file"] = file
    if line is not None:
        obj["line"] = line
    if column is not None:
        obj["column"] = column
    return json.dumps(obj, ensure_ascii=False)


def _extract_error_location(exc: Exception) -> Tuple[Optional[int], Optional[int]]:
    line: Optional[int] = None
    column: Optional[int] = None
    if hasattr(exc, "editor_line"):
        line = getattr(exc, "editor_line", None)
    if hasattr(exc, "editor_column"):
        column = getattr(exc, "editor_column", None)
    return line, column


def _matches_any_glob(path_posix: str, globs: Sequence[str]) -> bool:
    for g in globs:
        if fnmatch.fnmatch(path_posix, g):
            return True
    return False


def _iter_py_files(
    roots: Sequence[str],
    *,
    include_glob: str,
    exclude_globs: Sequence[str],
    max_files: int,
) -> Tuple[List[str], List[str]]:
    files: List[str] = []
    errors: List[str] = []

    for r in roots:
        if not r:
            errors.append("empty path")
            continue
        if is_path_dangerous(r):
            errors.append(f"dangerous path rejected: {r}")
            continue
        try:
            abs_root = ensure_within_workdir(r)
        except Exception as e:
            errors.append(f"path rejected (outside workdir): {r} ({e})")
            continue

        p = Path(abs_root)
        if p.is_file():
            rel_posix = Path(r).as_posix() if not Path(r).is_absolute() else p.name
            if _matches_any_glob(rel_posix, exclude_globs):
                continue
            if fnmatch.fnmatch(rel_posix, include_glob) or p.suffix.lower() == ".py":
                files.append(str(p))
        elif p.is_dir():
            for child in p.rglob("*"):
                if len(files) >= max_files:
                    errors.append(f"max_files exceeded: {max_files}")
                    return files, errors
                if not child.is_file():
                    continue
                rel = child.relative_to(p).as_posix()
                if _matches_any_glob(rel, exclude_globs):
                    continue
                if fnmatch.fnmatch(rel, include_glob):
                    files.append(str(child))
        else:
            errors.append(f"path not found: {r}")

    seen = set()
    uniq: List[str] = []
    for f in files:
        if f in seen:
            continue
        seen.add(f)
        uniq.append(f)

    return uniq, errors


def _read_text(path: str, *, max_bytes: int) -> str:
    size = os.path.getsize(path)
    if size > max_bytes:
        raise ValueError(f"file too large: {size} > {max_bytes} bytes")
    try:
        return Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Fallback: try system default
        return Path(path).read_text(encoding=None)


def _write_text(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8", newline="\n")


def _node_to_code(node: cst.CSTNode) -> str:
    return cst.Module([]).code_for_node(node).strip()


def _expr_to_dotted_name(expr: cst.BaseExpression) -> Optional[str]:
    if isinstance(expr, cst.Name):
        return expr.value
    if isinstance(expr, cst.Attribute):
        left = _expr_to_dotted_name(expr.value)
        if left is None:
            return None
        if not isinstance(expr.attr, cst.Name):
            return None
        return f"{left}.{expr.attr.value}"
    return None


def _unified_diff(a: str, b: str, *, fromfile: str, tofile: str) -> str:
    a_lines = a.splitlines(keepends=True)
    b_lines = b.splitlines(keepends=True)
    return "".join(
        difflib.unified_diff(
            a_lines,
            b_lines,
            fromfile=fromfile,
            tofile=tofile,
            lineterm="",
        )
    )


@dataclass
class AnalyzeResult:
    imports: List[str]
    functions: List[str]
    classes: List[str]


class _TopLevelAnalyzer(cst.CSTVisitor):
    def __init__(self) -> None:
        self.imports: List[str] = []
        self.functions: List[str] = []
        self.classes: List[str] = []
        self._depth: int = 0

    def visit_Import(self, node: cst.Import) -> Optional[bool]:
        try:
            self.imports.append(_node_to_code(node))
        except Exception:
            self.imports.append("import <unrenderable>")
        return True

    def visit_ImportFrom(self, node: cst.ImportFrom) -> Optional[bool]:
        try:
            self.imports.append(_node_to_code(node))
        except Exception:
            self.imports.append("from <unrenderable> import <unrenderable>")
        return True

    def visit_FunctionDef(self, node: cst.FunctionDef) -> Optional[bool]:
        if self._depth == 0:
            self.functions.append(node.name.value)
        self._depth += 1
        return True

    def leave_FunctionDef(self, node: cst.FunctionDef) -> None:
        self._depth -= 1

    def visit_AsyncFunctionDef(self, node: cst.AsyncFunctionDef) -> Optional[bool]:
        if self._depth == 0:
            self.functions.append(node.name.value)
        self._depth += 1
        return True

    def leave_AsyncFunctionDef(self, node: cst.AsyncFunctionDef) -> None:
        self._depth -= 1

    def visit_ClassDef(self, node: cst.ClassDef) -> Optional[bool]:
        if self._depth == 0:
            self.classes.append(node.name.value)
        self._depth += 1
        return True

    def leave_ClassDef(self, node: cst.ClassDef) -> None:
        self._depth -= 1


class RenameSymbolTransformer(cst.CSTTransformer):
    def __init__(self, old: str, new: str, *, include_attributes: bool = False) -> None:
        self.old = old
        self.new = new
        self.include_attributes = include_attributes
        self.change_count: int = 0

    def leave_Name(self, original_node: cst.Name, updated_node: cst.Name) -> cst.Name:
        if original_node.value == self.old:
            self.change_count += 1
            return updated_node.with_changes(value=self.new)
        return updated_node

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.Attribute:
        if not self.include_attributes:
            return updated_node
        if (
            isinstance(original_node.attr, cst.Name)
            and original_node.attr.value == self.old
        ):
            self.change_count += 1
            return updated_node.with_changes(attr=cst.Name(self.new))
        return updated_node


class ReplaceCallTransformer(cst.CSTTransformer):
    def __init__(self, old: str, new: str, *, receiver: Optional[str] = None) -> None:
        self.old = old
        self.new = new
        self.receiver = receiver
        self.change_count: int = 0

    def _receiver_matches(self, value_expr: cst.BaseExpression) -> bool:
        if self.receiver is None:
            return True
        dotted = _expr_to_dotted_name(value_expr)
        return dotted == self.receiver

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        # old(...)
        if (
            isinstance(original_node.func, cst.Name)
            and original_node.func.value == self.old
        ):
            if self.receiver is None:
                self.change_count += 1
                return updated_node.with_changes(func=cst.Name(self.new))
            return updated_node

        # receiver.old(...)
        if isinstance(original_node.func, cst.Attribute):
            attr = original_node.func
            if isinstance(attr.attr, cst.Name) and attr.attr.value == self.old:
                if self._receiver_matches(attr.value):
                    self.change_count += 1
                    return updated_node.with_changes(
                        func=updated_node.func.with_changes(attr=cst.Name(self.new))
                    )
        return updated_node


class RenameImportTransformer(cst.CSTTransformer):
    def __init__(self, module: Optional[str], old: str, new: str) -> None:
        self.module = module
        self.old = old
        self.new = new
        self.change_count: int = 0

    def _module_matches(self, original_node: cst.ImportFrom) -> bool:
        if self.module is None:
            return True
        try:
            mod_code = _node_to_code(original_node.module)  # type: ignore[arg-type]
        except Exception:
            mod_code = None
        return mod_code == self.module

    def leave_ImportFrom(
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.ImportFrom:
        if not self._module_matches(original_node):
            return updated_node
        names = updated_node.names
        if not isinstance(names, (list, tuple)):
            return updated_node
        new_names: List[cst.ImportAlias] = []
        changes_in_node = 0
        for alias in names:
            if not isinstance(alias, cst.ImportAlias):
                new_names.append(alias)
                continue
            if isinstance(alias.name, cst.Name) and alias.name.value == self.old:
                new_names.append(alias.with_changes(name=cst.Name(self.new)))
                changes_in_node += 1
            else:
                new_names.append(alias)
        if changes_in_node > 0:
            self.change_count += changes_in_node
            return updated_node.with_changes(names=new_names)
        return updated_node

    def leave_Import(
        self, original_node: cst.Import, updated_node: cst.Import
    ) -> cst.Import:
        # `import a.b as c` is not renamed by design (ambiguous). Only handle `import Old`.
        new_names: List[cst.ImportAlias] = []
        changes_in_node = 0
        for alias in updated_node.names:
            if not isinstance(alias, cst.ImportAlias):
                new_names.append(alias)
                continue
            if isinstance(alias.name, cst.Name) and alias.name.value == self.old:
                new_names.append(alias.with_changes(name=cst.Name(self.new)))
                changes_in_node += 1
            else:
                new_names.append(alias)
        if changes_in_node > 0:
            self.change_count += changes_in_node
            return updated_node.with_changes(names=new_names)
        return updated_node


@dataclass
class _OpTransformer:
    op: Dict[str, Any]
    transformer: cst.CSTTransformer


def _build_transformers(
    operations: Sequence[Dict[str, Any]],
) -> Tuple[List[_OpTransformer], List[str]]:
    transformers: List[_OpTransformer] = []
    errors: List[str] = []

    for op in operations:
        if not isinstance(op, dict):
            errors.append(f"invalid operation (not object): {op!r}")
            continue
        name = str(op.get("op") or "").strip()
        if name == "rename_symbol":
            old = str(op.get("old") or "")
            new = str(op.get("new") or "")
            include_attributes = bool(op.get("include_attributes", False))
            if not old or not new:
                errors.append(f"rename_symbol requires old/new: {op!r}")
                continue
            transformers.append(
                _OpTransformer(
                    op=op,
                    transformer=RenameSymbolTransformer(
                        old, new, include_attributes=include_attributes
                    ),
                )
            )
        elif name == "replace_call":
            old = str(op.get("old") or "")
            new = str(op.get("new") or "")
            receiver_raw = op.get("receiver", None)
            receiver = None if receiver_raw in (None, "") else str(receiver_raw)
            if not old or not new:
                errors.append(f"replace_call requires old/new: {op!r}")
                continue
            transformers.append(
                _OpTransformer(
                    op=op,
                    transformer=ReplaceCallTransformer(old, new, receiver=receiver),
                )
            )
        elif name == "rename_import":
            module_raw = op.get("module", None)
            module = None if module_raw in (None, "") else str(module_raw)
            old = str(op.get("old") or "")
            new = str(op.get("new") or "")
            if not old or not new:
                errors.append(f"rename_import requires old/new: {op!r}")
                continue
            transformers.append(
                _OpTransformer(
                    op=op,
                    transformer=RenameImportTransformer(module, old, new),
                )
            )
        else:
            errors.append(f"unknown op: {name!r}")
    return transformers, errors


def _validate_operations(operations: Any) -> Tuple[List[Dict[str, Any]], List[str]]:
    if operations is None:
        return [], []
    if not isinstance(operations, list):
        return [], ["operations must be an array"]
    op_errors: List[str] = []
    ops: List[Dict[str, Any]] = []
    for i, op in enumerate(operations):
        if not isinstance(op, dict):
            op_errors.append(f"operations[{i}] must be an object: {op!r}")
            continue
        if not str(op.get("op") or "").strip():
            op_errors.append(f"operations[{i}] missing 'op': {op!r}")
            continue
        ops.append(op)
    return ops, op_errors


def _transformer_change_count(t: cst.CSTTransformer) -> Optional[int]:
    return getattr(t, "change_count", None)


def run_tool(args: Dict[str, Any]) -> str:
    mode = str(args.get("mode") or "").strip().lower()
    paths = args.get("paths", None)
    include_glob = str(args.get("include_glob") or "**/*.py")
    exclude_globs = args.get("exclude_globs", None)
    max_files = int(args.get("max_files", 20000))
    max_bytes = int(args.get("max_bytes", 2_000_000))
    preview = bool(args.get("preview", False))

    if mode not in ("analyze", "transform"):
        return _json_err(f"invalid mode: {mode!r}")
    if not isinstance(paths, list) or not paths:
        return _json_err("paths must be a non-empty array")
    if exclude_globs is None:
        exclude_globs_list: List[str] = list(
            TOOL_SPEC["function"]["parameters"]["properties"]["exclude_globs"][
                "default"
            ]
        )
    elif isinstance(exclude_globs, list):
        exclude_globs_list = [str(x) for x in exclude_globs]
    else:
        return _json_err("exclude_globs must be an array")

    roots = [str(p) for p in paths]
    files, walk_errors = _iter_py_files(
        roots,
        include_glob=include_glob,
        exclude_globs=exclude_globs_list,
        max_files=max_files,
    )

    result: Dict[str, Any] = {
        "mode": mode,
        "include_glob": include_glob,
        "exclude_globs": exclude_globs_list,
        "files_total": len(files),
        "walk_errors": walk_errors,
        "analyze": {},
        "transform": {},
    }

    if mode == "analyze":
        analyze_out: Dict[str, Any] = {}
        errors: Dict[str, Dict[str, Any]] = {}
        for f in files:
            try:
                src = _read_text(f, max_bytes=max_bytes)
                mod = cst.parse_module(src)
                v = _TopLevelAnalyzer()
                mod.visit(v)
                analyze_out[f] = {
                    "imports": v.imports,
                    "functions": sorted(set(v.functions)),
                    "classes": sorted(set(v.classes)),
                }
            except Exception as e:
                line, column = _extract_error_location(e)
                error_info: Dict[str, Any] = {"message": repr(e)}
                if line is not None:
                    error_info["line"] = line
                if column is not None:
                    error_info["column"] = column
                errors[f] = error_info
        result["analyze"] = {"files": analyze_out, "errors": errors}
        return _json_ok(result)

    _ops_arg = (
        args.get("ops")
        if (isinstance(args, dict) and ("ops" in args))
        else args.get("operations")
    )
    operations_list, op_validation_errors = _validate_operations(_ops_arg)
    transformers, op_errors = _build_transformers(operations_list)
    op_errors_all = op_validation_errors + op_errors

    changed_files: List[str] = []
    unchanged_files: List[str] = []
    backups: Dict[str, str] = {}
    per_file_errors: Dict[str, Dict[str, Any]] = {}
    previews: Dict[str, Dict[str, Any]] = {}

    op_stats: List[Dict[str, Any]] = []
    for ot in transformers:
        op_stats.append({"op": ot.op, "change_count": 0})

    for f in files:
        try:
            src = _read_text(f, max_bytes=max_bytes)
            mod = cst.parse_module(src)
            updated = mod

            # Reset per-file
            per_file_counts: List[int] = []
            for ot in transformers:
                before = _transformer_change_count(ot.transformer) or 0
                updated = updated.visit(ot.transformer)
                after = _transformer_change_count(ot.transformer) or 0
                per_file_counts.append(after - before)

            out = updated.code
            if out == src:
                unchanged_files.append(f)
                continue

            if preview:
                diff_text = _unified_diff(
                    src,
                    out,
                    fromfile=f"{f} (original)",
                    tofile=f"{f} (modified)",
                )
                previews[f] = {
                    "diff": diff_text,
                    "lines_added": len(out.splitlines()) - len(src.splitlines()),
                    "op_change_counts": per_file_counts,
                }
                changed_files.append(f)
            else:
                backup_path = make_backup_before_overwrite(f)
                backups[f] = backup_path
                _write_text(f, out)
                changed_files.append(f)

            for i, delta in enumerate(per_file_counts):
                op_stats[i]["change_count"] += delta

        except Exception as e:
            line, column = _extract_error_location(e)
            error_info: Dict[str, Any] = {"message": repr(e)}
            if line is not None:
                error_info["line"] = line
            if column is not None:
                error_info["column"] = column
            per_file_errors[f] = error_info

    result["transform"] = {
        "operations": args.get("operations", []),
        "op_errors": op_errors_all,
        "op_stats": op_stats,
        "changed_files": changed_files,
        "unchanged_files": unchanged_files,
        "backups": backups,
        "errors": per_file_errors,
        "preview": preview,
    }
    if preview and previews:
        result["transform"]["previews"] = previews
    return _json_ok(result)
