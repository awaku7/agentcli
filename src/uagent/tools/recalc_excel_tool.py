from __future__ import annotations

import fnmatch
import json
import os
from typing import Any

from .i18n_helper import make_tool_translator

try:
    import msoffcrypto
except Exception:  # pragma: no cover
    msoffcrypto = None  # type: ignore[assignment]
from .safe_file_ops_extras import ensure_within_workdir, make_backup_before_overwrite

_ = make_tool_translator(__file__)

BUSY_LABEL = True

TOOL_SPEC: dict[str, Any] = {
    "tool_level": 1,
    "tool_genre": "office",
    "type": "function",
    "function": {
        "name": "recalc_excel",
        "description": _(
            "tool.description",
            default="Recalculate Excel formulas by automating Microsoft Excel (Windows COM) and save updated cached values. Supports a single .",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "recalc_excel",
                "recalc excel",
                "recalculate",
                "excel formula",
                "windows com",
                "cache values",
            ],
        ),
        "x_search_terms_en": [
            "recalc_excel",
            "recalc excel",
            "recalculate",
            "excel formula",
            "windows com",
            "cache values",
        ],
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
                "password": {
                    "type": "string",
                    "description": _(
                        "param.password.description",
                        default="Password (prompts if needed).",
                    ),
                },
                "include_glob": {
                    "type": "string",
                    "description": _(
                        "param.include_glob.description",
                        default="Glob pattern used when path is a directory. Default: '*.xlsx'.",
                    ),
                },
                "recur": {
                    "type": "boolean",
                    "description": _(
                        "param.recur.description",
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
) -> list[str]:
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
    items: list[str] = []
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


def _prompt_for_password(path: str) -> str | None:
    try:
        from .human_ask_tool import run_tool as human_ask
    except Exception:
        return None

    message = _(
        "prompt.password",
        default="Enter the password for this file:\n{path}",
    ).format(path=path)
    try:
        res_json = human_ask({"message": message, "is_password": True})
        res = json.loads(res_json)
    except Exception:
        return None

    pwd = str(res.get("user_reply") or "").strip()
    return pwd or None


def _is_encrypted_office_xlsx(path: str) -> bool:
    if msoffcrypto is None:
        return False
    try:
        with open(path, "rb") as fin:
            office = msoffcrypto.OfficeFile(fin)
            try:
                return bool(office.is_encrypted())
            except Exception:
                return False
    except Exception:
        return False


def run_tool(args: dict[str, Any]) -> str:
    target_path = str(args.get("path", "") or "").strip()
    include_glob = str(args.get("include_glob", "*.xlsx") or "*.xlsx")

    recursive_raw = args.get("recur", False)
    backup_raw = args.get("backup", False)
    dry_run_raw = args.get("dry_run", False)
    visible_raw = args.get("visible", False)
    max_files_raw = args.get("max_files", 200)
    password = str(args.get("password") or "").strip() or None

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
    result: dict[str, Any] = {
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

        prompted_password: str | None = None

        for fp in targets:
            wb = None
            backup_path = None
            try:
                if backup_raw and os.path.exists(fp):
                    backup_path = make_backup_before_overwrite(fp)

                open_password = password
                if _is_encrypted_office_xlsx(fp):
                    if not open_password:
                        if prompted_password is None:
                            prompted_password = _prompt_for_password(fp)
                        open_password = prompted_password
                    if not open_password:
                        raise RuntimeError(
                            "password is required for encrypted workbook files"
                        )

                if open_password:
                    wb = excel.Workbooks.Open(
                        fp, UpdateLinks=0, ReadOnly=False, Password=open_password
                    )
                else:
                    wb = excel.Workbooks.Open(fp, UpdateLinks=0, ReadOnly=False)

                excel.CalculateFullRebuild()
                try:
                    excel.CalculateUntilAsyncQueriesDone()
                except Exception:
                    pass
                wb.Save()
                result["processed"].append({"path": fp, "backup": backup_path})
            except Exception as e:
                result["failed"].append(
                    {"path": fp, "error": f"{type(e).__name__}: {e}"}
                )
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
