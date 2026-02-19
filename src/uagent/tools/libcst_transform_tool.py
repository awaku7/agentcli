"""uagent tool: libcst_transform

libcst を用いた Python コードの解析(A) / ルールベース変換(B/D) を行うツール。

要件（ユーザー指定）:
- ツール名: libcst_transform
- 用途: A,B,D
- 対象: 複数ファイル（ディレクトリ再帰）
- 実行: バックアップを作成し即時書き換え
- バックアップ方式: replace_in_file_tool と同じ .org/.orgN（safe_file_ops_extras.make_backup_before_overwrite）

安全設計:
- workdir 外のパスは拒否（ensure_within_workdir）
- 実行前に危険なパス形式（.. / 絶対パス）も拒否（is_path_dangerous）
- 変更がないファイルは書き込みもバックアップ作成もしない

出力:
- JSON 文字列（ensure_ascii=False）

注意:
- 本ツールは「任意の Python コードを実行する」機能は提供しない。
  変換ルールは operations（辞書）で指定された範囲に限定する。
"""

from __future__ import annotations

import fnmatch
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import libcst as cst

from .safe_file_ops_extras import (
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
        "description": (
            "libcst を用いて Python コードを解析(analyze) または変換(transform)します。\n"
            "- analyze: import/class/function 等の抽出\n"
            "- transform: ルールベースの一括変換（rename_symbol/replace_call/rename_import など）\n"
            "\n"
            "安全設計:\n"
            "- workdir 外のパスは拒否\n"
            "- 変更時は上書き直前に .org/.orgN バックアップを作成\n"
        ),
        "system_prompt": (
            "libcst による Python コード解析・変換ツールです。\n"
            "\n"
            "入力の基本:\n"
            "- paths にファイル/ディレクトリを指定（ディレクトリは再帰走査）\n"
            "- include_glob/exclude_globs で対象を絞り込み（既定 include_glob=**/*.py）\n"
            "\n"
            "mode=analyze:\n"
            "- import / top-level class/function 名等を抽出し JSON で返します。\n"
            "\n"
            "mode=transform:\n"
            "- operations に変換ルールの配列を指定します。\n"
            "- 変更が発生したファイルは上書き直前に .org/.orgN バックアップを作成して即時書き換えます。\n"
            "\n"
            "operations 例:\n"
            "1) rename_symbol: old_name -> new_name（Name ノードを置換）\n"
            '  {"op":"rename_symbol","old":"foo","new":"bar"}\n'
            "2) replace_call: old_func(...) -> new_func(...)\n"
            '  {"op":"replace_call","old":"old_func","new":"new_func"}\n'
            "3) rename_import: from X import old -> from X import new（module 指定は任意）\n"
            '  {"op":"rename_import","module":"pkg.mod","old":"Old","new":"New"}\n'
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["analyze", "transform"],
                    "description": "実行モード: analyze=解析 / transform=変換",
                },
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "対象ファイル/ディレクトリの配列（workdir 配下のみ）。",
                },
                "include_glob": {
                    "type": "string",
                    "description": "ディレクトリ走査時の include glob（例: **/*.py）。",
                    "default": "**/*.py",
                },
                "exclude_globs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "除外 glob の配列（例: **/.venv/**, **/__pycache__/**）。",
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
                    "description": "走査する最大ファイル数（暴走防止）。",
                    "default": 20000,
                },
                "max_bytes": {
                    "type": "integer",
                    "description": "1ファイルの最大サイズ（bytes）。",
                    "default": 2_000_000,
                },
                "operations": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": (
                        "mode=transform のときの変換ルール配列。\n"
                        "\n"
                        "サポートする op:\n"
                        "- rename_symbol: old/new を指定して識別子を置換\n"
                        "  - include_attributes=true で obj.old の old も対象\n"
                        "- replace_call: old/new を指定して関数呼び出し名を置換\n"
                        "  - receiver を指定すると receiver.old(...) のみ対象\n"
                        "  - receiver 未指定だと old(...) と *.old(...) を対象\n"
                        "- rename_import: from X import old -> from X import new（module 指定は任意）\n"
                    ),
                    "default": [],
                },
            },
            "required": ["mode", "paths"],
        },
    },
}


def _json_ok(payload: Dict[str, Any]) -> str:
    payload.setdefault("ok", True)
    return json.dumps(payload, ensure_ascii=False)


def _json_err(message: str, *, details: Any = None) -> str:
    obj: Dict[str, Any] = {"ok": False, "error": message}
    if details is not None:
        obj["details"] = details
    return json.dumps(obj, ensure_ascii=False)


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
    """Return (files, errors)."""

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
            # walk all files; apply include/exclude to relative posix path
            for child in p.rglob("*"):
                if len(files) >= max_files:
                    errors.append(f"max_files exceeded: {max_files}")
                    return files, errors

                if not child.is_file():
                    continue

                rel = child.relative_to(p).as_posix()
                rel_posix = rel
                # apply exclude globs relative to this root
                if _matches_any_glob(rel_posix, exclude_globs):
                    continue

                if fnmatch.fnmatch(rel_posix, include_glob):
                    files.append(str(child))
        else:
            errors.append(f"path not found: {r}")

    # de-dup while preserving order
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

    # Try utf-8 first; fall back to locale preferred.
    try:
        return Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return Path(path).read_text(encoding=None)


def _write_text(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8", newline="\n")


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

    def visit_Import(self, node: cst.Import) -> Optional[bool]:
        # Render as code for readability
        try:
            self.imports.append(cst.Module([]).code_for_node(node).strip())
        except Exception:
            self.imports.append("import <unrenderable>")
        return True

    def visit_ImportFrom(self, node: cst.ImportFrom) -> Optional[bool]:
        try:
            self.imports.append(cst.Module([]).code_for_node(node).strip())
        except Exception:
            self.imports.append("from <unrenderable> import <unrenderable>")
        return True

    def visit_FunctionDef(self, node: cst.FunctionDef) -> Optional[bool]:
        # only top-level: parent is Module body; libcst visitor doesn't provide parent,
        # so we approximate by checking indentation via node.leading_lines (not reliable).
        # Instead, we gather all and caller can filter if needed.
        self.functions.append(node.name.value)
        return True

    def visit_ClassDef(self, node: cst.ClassDef) -> Optional[bool]:
        self.classes.append(node.name.value)
        return True


class RenameSymbolTransformer(cst.CSTTransformer):
    def __init__(self, old: str, new: str, *, include_attributes: bool = False) -> None:
        self.old = old
        self.new = new
        self.include_attributes = include_attributes

    def leave_Name(self, original_node: cst.Name, updated_node: cst.Name) -> cst.Name:
        if original_node.value == self.old:
            return updated_node.with_changes(value=self.new)
        return updated_node

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.Attribute:
        # Optionally rename attribute accesses like obj.old
        if not self.include_attributes:
            return updated_node

        if (
            isinstance(original_node.attr, cst.Name)
            and original_node.attr.value == self.old
        ):
            return updated_node.with_changes(attr=cst.Name(self.new))
        return updated_node


class ReplaceCallTransformer(cst.CSTTransformer):
    def __init__(self, old: str, new: str, *, receiver: Optional[str] = None) -> None:
        self.old = old
        self.new = new
        self.receiver = receiver

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        # Replace calls:
        # - old(...)
        # - *.old(...)
        # If receiver is specified, only replace receiver.old(...)

        # old(...)
        if (
            isinstance(original_node.func, cst.Name)
            and original_node.func.value == self.old
        ):
            if self.receiver is None:
                return updated_node.with_changes(func=cst.Name(self.new))
            return updated_node

        # obj.old(...)
        if isinstance(original_node.func, cst.Attribute):
            attr = original_node.func
            if isinstance(attr.attr, cst.Name) and attr.attr.value == self.old:
                if self.receiver is None:
                    return updated_node.with_changes(
                        func=updated_node.func.with_changes(attr=cst.Name(self.new))
                    )

                # receiver filter
                if (
                    isinstance(attr.value, cst.Name)
                    and attr.value.value == self.receiver
                ):
                    return updated_node.with_changes(
                        func=updated_node.func.with_changes(attr=cst.Name(self.new))
                    )

        return updated_node


class RenameImportTransformer(cst.CSTTransformer):
    def __init__(self, module: Optional[str], old: str, new: str) -> None:
        self.module = module
        self.old = old
        self.new = new

    def leave_ImportFrom(
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.ImportFrom:
        # module filter (optional)
        if self.module is not None:
            try:
                mod_code = cst.Module([]).code_for_node(original_node.module).strip()  # type: ignore[arg-type]
            except Exception:
                mod_code = None
            if mod_code != self.module:
                return updated_node

        names = updated_node.names
        if not isinstance(names, (list, tuple)):
            return updated_node

        new_names: List[cst.ImportAlias] = []
        changed = False
        for alias in names:
            if not isinstance(alias, cst.ImportAlias):
                new_names.append(alias)
                continue
            if isinstance(alias.name, cst.Name) and alias.name.value == self.old:
                new_names.append(alias.with_changes(name=cst.Name(self.new)))
                changed = True
            else:
                new_names.append(alias)

        if changed:
            return updated_node.with_changes(names=new_names)
        return updated_node


def _build_transformers(
    operations: Sequence[Dict[str, Any]],
) -> Tuple[List[cst.CSTTransformer], List[str]]:
    transformers: List[cst.CSTTransformer] = []
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
                RenameSymbolTransformer(old, new, include_attributes=include_attributes)
            )
        elif name == "replace_call":
            old = str(op.get("old") or "")
            new = str(op.get("new") or "")
            receiver_raw = op.get("receiver", None)
            receiver = None if receiver_raw in (None, "") else str(receiver_raw)
            if not old or not new:
                errors.append(f"replace_call requires old/new: {op!r}")
                continue
            transformers.append(ReplaceCallTransformer(old, new, receiver=receiver))
        elif name == "rename_import":
            module_raw = op.get("module", None)
            module = None if module_raw in (None, "") else str(module_raw)
            old = str(op.get("old") or "")
            new = str(op.get("new") or "")
            if not old or not new:
                errors.append(f"rename_import requires old/new: {op!r}")
                continue
            transformers.append(RenameImportTransformer(module, old, new))
        else:
            errors.append(f"unknown op: {name!r}")

    return transformers, errors


def run_tool(args: Dict[str, Any]) -> str:
    mode = str(args.get("mode") or "").strip().lower()
    paths = args.get("paths", None)
    include_glob = str(args.get("include_glob") or "**/*.py")
    exclude_globs = args.get("exclude_globs", None)
    max_files = int(args.get("max_files", 20000))
    max_bytes = int(args.get("max_bytes", 2_000_000))

    if mode not in ("analyze", "transform"):
        return _json_err(f"invalid mode: {mode!r}")

    if not isinstance(paths, list) or not paths:
        return _json_err("paths must be a non-empty array")

    if exclude_globs is None:
        exclude_globs_list: List[str] = list(TOOL_SPEC["function"]["parameters"]["properties"]["exclude_globs"]["default"])  # type: ignore[index]
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
        errors: Dict[str, str] = {}

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
                errors[f] = repr(e)

        result["analyze"] = {
            "files": analyze_out,
            "errors": errors,
        }
        return _json_ok(result)

    # mode == transform
    operations = args.get("operations", [])
    if operations is None:
        operations_list: List[Dict[str, Any]] = []
    elif isinstance(operations, list):
        operations_list = [op for op in operations if isinstance(op, dict)]
        # keep non-dict errors
        non_dicts = [op for op in operations if not isinstance(op, dict)]
        if non_dicts:
            result.setdefault("transform", {})
            result["transform"].setdefault("op_errors", [])
            result["transform"]["op_errors"].append(
                f"operations contains non-object entries: {non_dicts!r}"
            )
    else:
        return _json_err("operations must be an array")

    transformers, op_errors = _build_transformers(operations_list)

    changed_files: List[str] = []
    unchanged_files: List[str] = []
    backups: Dict[str, str] = {}
    per_file_errors: Dict[str, str] = {}

    for f in files:
        try:
            src = _read_text(f, max_bytes=max_bytes)
            mod = cst.parse_module(src)

            updated = mod
            for t in transformers:
                updated = updated.visit(t)

            out = updated.code
            if out == src:
                unchanged_files.append(f)
                continue

            # backup then overwrite (same policy as replace_in_file_tool)
            backup_path = make_backup_before_overwrite(f)
            backups[f] = backup_path

            _write_text(f, out)
            changed_files.append(f)
        except Exception as e:
            per_file_errors[f] = repr(e)

    result["transform"] = {
        "operations": operations,
        "op_errors": op_errors,
        "changed_files": changed_files,
        "unchanged_files": unchanged_files,
        "backups": backups,
        "errors": per_file_errors,
    }

    return _json_ok(result)
