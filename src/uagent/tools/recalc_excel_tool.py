from __future__ import annotations

import fnmatch
import json
import os
from typing import Any, Dict, List

from .i18n_helper import make_tool_translator
from .safe_file_ops_extras import ensure_within_workdir, make_backup_before_overwrite

_ = make_tool_translator(__file__)

BUSY_LABEL = True

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "recalc_excel",
        "description": _(
            "tool.description",
            default=(
                "Recalculate Excel formulas by automating Microsoft Excel (Windows COM) and save updated cached values. "
                "Supports a single .xlsx file or a directory scan. By default, no backup "
                "is created before saving only when backup=true is specified."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "Use this tool when formula cached values in .xlsx are stale (e.g., openpyxl data_only reads old values). "
                "This tool opens workbook(s) in Microsoft Excel via COM, performs full recalculation, and saves."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Target .xlsx file path or directory path.",
                    ),
                },
                "include_glob": {
                    "type": "string",
                    "description": _(
                        "param.include_glob.description",
                        default="Glob pattern used when path is a directory. Default: '*.xlsx'.",
                    ),
                },
                "recursive": {
                    "type": "boolean",
                    "description": _(
                        "param.recursive.description",
                        default="Whether to scan directory recursively. Default: false.",
                    ),
                },
                "backup": {
                    "type": "boolean",
                    "description": _(
                        "param.backup.description",
                        default="Create backup before save. Default: false.",
                    ),
                },
                "dry_run": {
                    "type": "boolean",
                    "description": _(
                        "param.dry_run.description",
                        default="If true, only list targets and do not recalculate/save. Default: false.",
                    ),
                },
                "visible": {
                    "type": "boolean",
                    "description": _(
                        "param.visible.description",
                        default="Show Excel window during automation. Default: false.",
                    ),
                },
                "max_files": {
                    "type": "integer",
                    "description": _(
                        "param.max_files.description",
                        default="Maximum number of files to process when scanning a directory. Default: 200.",
                    ),
                },
            },
            "required": ["path"],
        },
    },
}


def _collect_targets(
    target_path: str, include_glob: str, recursive: bool, max_files: int
) -> List[str]:
    safe_target = ensure_within_workdir(target_path)
    if not os.path.exists(safe_target):
        raise FileNotFoundError(
            _("err.path_not_found", default="Path not found: {path}").format(
                path=safe_target
            )
        )

    if os.path.isfile(safe_target):
        if not safe_target.lower().endswith(".xlsx"):
            raise ValueError(
                _(
                    "err.file_ext",
                    default="Only .xlsx is supported for file mode: {path}",
                ).format(path=safe_target)
            )
        if os.path.basename(safe_target).startswith("~$"):
            return []
        return [safe_target]

    if max_files <= 0:
        raise ValueError(_("err.max_files_positive", default="max_files must be >= 1"))

    pattern = include_glob or "*.xlsx"
    items: List[str] = []
    if recursive:
        for root, _dirs, files in os.walk(safe_target):
            for name in files:
                if not fnmatch.fnmatch(name, pattern):
                    continue
                full = os.path.join(root, name)
                if not full.lower().endswith(".xlsx"):
                    continue
                if os.path.basename(full).startswith("~$"):
                    continue
                items.append(full)
                if len(items) >= max_files:
                    return items
    else:
        for name in os.listdir(safe_target):
            full = os.path.join(safe_target, name)
            if not os.path.isfile(full):
                continue
            if not fnmatch.fnmatch(name, pattern):
                continue
            if not full.lower().endswith(".xlsx"):
                continue
            if os.path.basename(full).startswith("~$"):
                continue
            items.append(full)
            if len(items) >= max_files:
                return items
    return items


def run_tool(args: Dict[str, Any]) -> str:
    target_path = str(args.get("path", "") or "").strip()
    include_glob = str(args.get("include_glob", "*.xlsx") or "*.xlsx")

    recursive_raw = args.get("recursive", False)
    backup_raw = args.get("backup", False)
    dry_run_raw = args.get("dry_run", False)
    visible_raw = args.get("visible", False)
    max_files_raw = args.get("max_files", 200)

    if not target_path:
        raise ValueError(_("err.path_required", default="path is required"))
    if not isinstance(recursive_raw, bool):
        raise ValueError(_("err.recursive_bool", default="recursive must be a boolean"))
    if not isinstance(backup_raw, bool):
        raise ValueError(_("err.backup_bool", default="backup must be a boolean"))
    if not isinstance(dry_run_raw, bool):
        raise ValueError(_("err.dry_run_bool", default="dry_run must be a boolean"))
    if not isinstance(visible_raw, bool):
        raise ValueError(_("err.visible_bool", default="visible must be a boolean"))

    try:
        max_files = int(max_files_raw)
    except Exception as e:
        raise ValueError(
            _("err.max_files_int", default="max_files must be an integer")
        ) from e

    targets = _collect_targets(target_path, include_glob, recursive_raw, max_files)
    result: Dict[str, Any] = {
        "path": ensure_within_workdir(target_path),
        "count": len(targets),
        "targets": targets,
        "dry_run": bool(dry_run_raw),
        "backup": bool(backup_raw),
        "processed": [],
        "failed": [],
    }

    if dry_run_raw:
        return json.dumps(result, ensure_ascii=False)

    if os.name != "nt":
        raise RuntimeError(
            _(
                "err.windows_only",
                default="recalc_excel is supported only on Windows (Microsoft Excel COM automation).",
            )
        )

    try:
        import pythoncom  # type: ignore
        import win32com.client as win32  # type: ignore
    except Exception as e:
        raise RuntimeError(
            _(
                "err.pywin32_required",
                default="pywin32 is required (and Microsoft Excel must be installed).",
            )
        ) from e

    pythoncom.CoInitialize()
    excel = None
    try:
        excel = win32.DispatchEx("Excel.Application")
        excel.Visible = bool(visible_raw)
        excel.DisplayAlerts = False
        try:
            excel.AskToUpdateLinks = False
        except Exception:
            pass

        for fp in targets:
            wb = None
            backup_path = None
            try:
                if backup_raw and os.path.exists(fp):
                    backup_path = make_backup_before_overwrite(fp)

                wb = excel.Workbooks.Open(fp, UpdateLinks=0, ReadOnly=False)
                excel.CalculateFullRebuild()
                try:
                    excel.CalculateUntilAsyncQueriesDone()
                except Exception:
                    pass
                wb.Save()
                result["processed"].append({"path": fp, "backup": backup_path})
            except Exception as e:
                result["failed"].append({"path": fp, "error": f"{type(e).__name__}: {e}"})
            finally:
                if wb is not None:
                    try:
                        wb.Close(SaveChanges=True)
                    except Exception:
                        pass
    finally:
        if excel is not None:
            try:
                excel.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()

    return json.dumps(result, ensure_ascii=False)
