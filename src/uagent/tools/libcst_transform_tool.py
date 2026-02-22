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

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


import fnmatch
import json
import os
import re
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
- Specify an array of rules in operations.
- If a file is changed, create .org/.orgN backup immediately before overwrite.

operations examples:
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
                    "description": _("param.mode.description", default="Execution mode: analyze=analyze / transform=transform"),
                },
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _("param.paths.description", default="Array of target files/directories (must be under workdir)."),
                },
                "include_glob": {
                    "type": "string",
                    "description": _("param.include_glob.description", default="Include glob when scanning directories (e.g. **/*.py)."),
                    "default": "**/*.py",
                },
                "exclude_globs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _("param.exclude_globs.description", default="Array of exclude globs (e.g. **/.venv/**, **/__pycache__/**)."),
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
                    "description": _("param.max_files.description", default="Maximum number of files to scan (runaway protection)."),
                    "default": 20000,
                },
                "max_bytes": {
                    "type": "integer",
                    "description": _("param.max_bytes.description", default="Maximum file size (bytes)."),
                    "default": 2_000_000,
                },
                "operations": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": _(
                        "param.operations.description",
                        default="""Transform rules array for mode=transform.

Supported ops:
- rename_symbol: replace identifier (requires old/new)
  - include_attributes=true also targets obj.old
- replace_call: replace function call name (requires old/new)
  - receiver targets only receiver.old(...)
  - if receiver is omitted, targets old(...) and *.old(...)
- rename_import: from X import old -> from X import new (module is optional)
""",
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
    """Build libcst transformers from operations.

    Supported ops:
    - rename_symbol
    - replace_call
    - rename_import
    - wrap_tool_spec_i18n (uagent-specific):
      - Insert tool-local translator prelude:
          from .i18n_helper import make_tool_translator
          _ = make_tool_translator(__file__)
      - Wrap TOOL_SPEC strings using _("key", default=...)
      - Generate/overwrite <tool>_tool.json (en/ja)

    Note: wrap_tool_spec_i18n is intentionally conservative and targets only
    TOOL_SPEC dictionary literals.
    """
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

    # Extract uagent-specific op before building generic transformers
    wrap_ops = [op for op in operations_list if str(op.get("op") or "").strip() == "wrap_tool_spec_i18n"]
    generic_ops = [op for op in operations_list if str(op.get("op") or "").strip() != "wrap_tool_spec_i18n"]

    transformers, op_errors = _build_transformers(generic_ops)

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

            # uagent-specific wrap op (per-file)
            if wrap_ops:
                wrap_op = wrap_ops[0]
                out2, _en_map, _ja_map, _wrap_changed, json_err = _apply_wrap_tool_spec_i18n(
                    py_path=f, src=out, op=wrap_op
                )
                out = out2
                if json_err:
                    per_file_errors[f] = f"wrap_tool_spec_i18n json error: {json_err}"

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


# ------------------------------
# uagent-specific: wrap_tool_spec_i18n


_JP2EN_REPLACEMENTS = [
    ("このツールは次の目的で使われます: ", ""),
    ("このツールは", "This tool"),
    ("次の目的で使われます", "is used for the following purpose"),
    ("指定した", "Specified"),
    ("指定された", "Specified"),
    ("ファイル", "file"),
    ("ディレクトリ", "directory"),
    ("パス", "path"),
    ("文字列", "string"),
    ("配列", "array"),
    ("取得します", "gets"),
    ("作成します", "creates"),
    ("削除します", "deletes"),
    ("変更します", "changes"),
    ("検索します", "searches"),
    ("実行します", "runs"),
    ("返します", "returns"),
    ("行います", "performs"),
    ("省略時", "If omitted"),
    ("既定", "Default"),
    ("デフォルト", "Default"),
    ("必須", "Required"),
]


def _jp_to_en_rule_based(text: str) -> str:
    # External access is not allowed; keep it conservative.
    s = text
    for a, b in _JP2EN_REPLACEMENTS:
        s = s.replace(a, b)
    return s


def _tool_json_path_for_py(py_path: str) -> str:
    p = Path(py_path)
    return str(p.with_suffix(".json"))


def _validate_tool_json_payload(payload: Any) -> Optional[str]:
    if not isinstance(payload, dict):
        return "payload is not an object"
    en = payload.get("en")
    ja = payload.get("ja")
    if not isinstance(en, dict) or not isinstance(ja, dict):
        return "payload must have 'en' and 'ja' objects"
    if set(en.keys()) != set(ja.keys()):
        return "'en' and 'ja' must have the same key set"
    for k, v in en.items():
        if not isinstance(k, str) or not isinstance(v, str):
            return "all 'en' keys/values must be strings"
    for k, v in ja.items():
        if not isinstance(k, str) or not isinstance(v, str):
            return "all 'ja' keys/values must be strings"
    return None


def _safe_write_tool_json_if_missing(
    json_path: str, *, translations_en: Dict[str, str], translations_ja: Dict[str, str]
) -> Tuple[bool, Optional[str]]:
    # Do not modify existing json (existing 6 are kept)
    if Path(json_path).exists():
        # Validate existing JSON as "check"
        try:
            data = json.loads(Path(json_path).read_text(encoding="utf-8"))
        except Exception as e:
            return False, f"existing json invalid: {e!r}"
        err = _validate_tool_json_payload(data)
        if err:
            return False, f"existing json invalid: {err}"
        return False, None

    payload = {"en": dict(translations_en), "ja": dict(translations_ja)}
    err = _validate_tool_json_payload(payload)
    if err:
        return False, f"generated json invalid: {err}"

    Path(json_path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return True, None


def _is_string_literal(expr: cst.BaseExpression) -> Optional[str]:
    # Return python string value if expr is a simple string literal.
    if isinstance(expr, cst.SimpleString):
        try:
            # literal_eval is safest for Python literal
            import ast

            v = ast.literal_eval(expr.value)
            if isinstance(v, str):
                return v
        except Exception:
            return None
    return None


def _make_translate_call(key: str, default_text: str) -> cst.Call:
    return cst.Call(
        func=cst.Name("_"),
        args=[
            cst.Arg(value=cst.SimpleString(json.dumps(key, ensure_ascii=False))),
            cst.Arg(
                keyword=cst.Name("default"),
                value=cst.SimpleString(json.dumps(default_text, ensure_ascii=False)),
            ),
        ],
    )


def _dict_get_value(d: cst.Dict, key: str) -> Optional[cst.BaseExpression]:
    for el in d.elements:
        if not isinstance(el, cst.DictElement):
            continue
        if el.key is None:
            continue
        ks = _is_string_literal(el.key)
        if ks == key:
            return el.value
    return None


def _dict_set_value(d: cst.Dict, key: str, new_value: cst.BaseExpression) -> cst.Dict:
    new_elems: List[cst.DictElement] = []
    replaced = False
    for el in d.elements:
        if not isinstance(el, cst.DictElement) or el.key is None:
            new_elems.append(el)  # type: ignore[arg-type]
            continue
        ks = _is_string_literal(el.key)
        if ks == key:
            new_elems.append(el.with_changes(value=new_value))
            replaced = True
        else:
            new_elems.append(el)
    if not replaced:
        new_elems.append(
            cst.DictElement(
                key=cst.SimpleString(json.dumps(key, ensure_ascii=False)),
                value=new_value,
            )
        )
    return d.with_changes(elements=new_elems)


class _ToolSpecWrapState:
    def __init__(self) -> None:
        self.translations_en: Dict[str, str] = {}
        self.translations_ja: Dict[str, str] = {}
        self.changed: bool = False


class _WrapToolSpecI18nTransformer(cst.CSTTransformer):
    def __init__(self, state: _ToolSpecWrapState) -> None:
        self.state = state

    def leave_Assign(self, original_node: cst.Assign, updated_node: cst.Assign) -> cst.Assign:
        # Match: TOOL_SPEC = { ... }
        if not original_node.targets:
            return updated_node
        tgt0 = original_node.targets[0].target
        if not isinstance(tgt0, cst.Name) or tgt0.value != "TOOL_SPEC":
            return updated_node

        if not isinstance(updated_node.value, cst.Dict):
            return updated_node

        tool_spec = updated_node.value
        func = _dict_get_value(tool_spec, "function")
        if not isinstance(func, cst.Dict):
            return updated_node

        # function.description
        desc_expr = _dict_get_value(func, "description")
        if isinstance(desc_expr, cst.Call) and isinstance(desc_expr.func, cst.Name) and desc_expr.func.value == "_":
            pass
        else:
            ja = _is_string_literal(desc_expr) if isinstance(desc_expr, cst.BaseExpression) else None
            if ja is not None:
                en = _jp_to_en_rule_based(ja)
                self.state.translations_en["tool.description"] = en
                self.state.translations_ja["tool.description"] = ja
                func = _dict_set_value(func, "description", _make_translate_call("tool.description", en))
                self.state.changed = True

        # function.system_prompt (optional)
        sp_expr = _dict_get_value(func, "system_prompt")
        if sp_expr is not None:
            if isinstance(sp_expr, cst.Call) and isinstance(sp_expr.func, cst.Name) and sp_expr.func.value == "_":
                pass
            else:
                ja = _is_string_literal(sp_expr) if isinstance(sp_expr, cst.BaseExpression) else None
                if ja is not None:
                    en = _jp_to_en_rule_based(ja)
                    self.state.translations_en["tool.system_prompt"] = en
                    self.state.translations_ja["tool.system_prompt"] = ja
                    func = _dict_set_value(func, "system_prompt", _make_translate_call("tool.system_prompt", en))
                    self.state.changed = True

        # parameters.properties.*.description
        params = _dict_get_value(func, "parameters")
        if isinstance(params, cst.Dict):
            props = _dict_get_value(params, "properties")
            if isinstance(props, cst.Dict):
                new_prop_elems: List[cst.DictElement] = []
                for el in props.elements:
                    if not isinstance(el, cst.DictElement) or el.key is None:
                        new_prop_elems.append(el)  # type: ignore[arg-type]
                        continue
                    pname = _is_string_literal(el.key)
                    if not pname or not isinstance(el.value, cst.Dict):
                        new_prop_elems.append(el)
                        continue
                    pdef = el.value
                    pdesc = _dict_get_value(pdef, "description")
                    if pdesc is None:
                        new_prop_elems.append(el)
                        continue
                    if isinstance(pdesc, cst.Call) and isinstance(pdesc.func, cst.Name) and pdesc.func.value == "_":
                        new_prop_elems.append(el)
                        continue
                    ja = _is_string_literal(pdesc) if isinstance(pdesc, cst.BaseExpression) else None
                    if ja is None:
                        new_prop_elems.append(el)
                        continue
                    en = _jp_to_en_rule_based(ja)
                    key = f"param.{pname}.description"
                    self.state.translations_en[key] = en
                    self.state.translations_ja[key] = ja
                    pdef2 = _dict_set_value(pdef, "description", _make_translate_call(key, en))
                    new_prop_elems.append(el.with_changes(value=pdef2))
                    self.state.changed = True

                props2 = props.with_changes(elements=new_prop_elems)
                params2 = _dict_set_value(params, "properties", props2)
                func = _dict_set_value(func, "parameters", params2)

        tool_spec2 = _dict_set_value(tool_spec, "function", func)
        return updated_node.with_changes(value=tool_spec2)


def _module_has_import_make_tool_translator(mod: cst.Module) -> bool:
    for stmt in mod.body:
        if isinstance(stmt, cst.SimpleStatementLine):
            for small in stmt.body:
                if isinstance(small, cst.ImportFrom):
                    try:
                        mod_name = cst.Module([]).code_for_node(small.module).strip() if small.module else None  # type: ignore[arg-type]
                    except Exception:
                        mod_name = None
                    if mod_name == ".i18n_helper":
                        for nm in small.names:
                            if (
                                isinstance(nm, cst.ImportAlias)
                                and isinstance(nm.name, cst.Name)
                                and nm.name.value == "make_tool_translator"
                            ):
                                return True
    return False


def _module_has_assign_translator(mod: cst.Module) -> bool:
    # Look for: _ = make_tool_translator(__file__)
    for stmt in mod.body:
        if not isinstance(stmt, cst.SimpleStatementLine):
            continue
        for small in stmt.body:
            if not isinstance(small, cst.Assign):
                continue
            if not small.targets:
                continue
            t0 = small.targets[0].target
            if not isinstance(t0, cst.Name) or t0.value != "_":
                continue
            if (
                isinstance(small.value, cst.Call)
                and isinstance(small.value.func, cst.Name)
                and small.value.func.value == "make_tool_translator"
            ):
                return True
    return False


def _insert_translator_prelude(mod: cst.Module) -> Tuple[cst.Module, bool]:
    need_import = not _module_has_import_make_tool_translator(mod)
    need_assign = not _module_has_assign_translator(mod)
    if not need_import and not need_assign:
        return mod, False

    import_stmt = cst.parse_statement("from .i18n_helper import make_tool_translator\n")
    assign_stmt = cst.parse_statement("_ = make_tool_translator(__file__)\n")
    empty_stmt = cst.EmptyLine()

    # Insert after future import if exists, else at top
    new_body: List[cst.BaseStatement] = []
    inserted = False
    for stmt in mod.body:
        new_body.append(stmt)
        if not inserted and isinstance(stmt, cst.SimpleStatementLine) and stmt.body:
            try:
                code = cst.Module([]).code_for_node(stmt).strip()
            except Exception:
                code = ""
            if "from __future__ import annotations" in code:
                if need_import:
                    new_body.append(import_stmt)
                if need_assign:
                    new_body.append(assign_stmt)
                new_body.append(empty_stmt)
                inserted = True

    if inserted:
        return mod.with_changes(body=new_body), True

    # no future import
    head: List[cst.BaseStatement] = []
    if need_import:
        head.append(import_stmt)
    if need_assign:
        head.append(assign_stmt)
    head.append(empty_stmt)
    head.extend(mod.body)
    return mod.with_changes(body=head), True


def _apply_wrap_tool_spec_i18n(
    *, py_path: str, src: str, op: Dict[str, Any]
) -> Tuple[str, Dict[str, str], Dict[str, str], bool, Optional[str]]:
    # Return: (new_src, en, ja, changed, json_error)
    try:
        mod = cst.parse_module(src)
        mod2, prelude_changed = _insert_translator_prelude(mod)

        state = _ToolSpecWrapState()
        mod3 = mod2.visit(_WrapToolSpecI18nTransformer(state))

        changed = prelude_changed or state.changed
        out = mod3.code

        generate_json = bool(op.get("generate_json", True))
        json_err: Optional[str] = None
        if generate_json:
            json_path = _tool_json_path_for_py(py_path)
            _created, json_err = _safe_write_tool_json_if_missing(
                json_path,
                translations_en=state.translations_en,
                translations_ja=state.translations_ja,
            )

        return out, state.translations_en, state.translations_ja, changed, json_err
    except Exception as e:
        return src, {}, {}, False, repr(e)
