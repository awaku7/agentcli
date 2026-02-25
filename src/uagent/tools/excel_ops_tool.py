# tools/excel_ops_tool.py
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "excel_ops",
        "description": _(
            "tool.description",
            default=(
                "Read/write an Excel (.xlsx) file and get sheet names. When writing to an existing file, "
                "a backup with the same name (<file_path>.org / <file_path>.org1 / ...) is created immediately before writing."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default="This tool performs the operation described by the tool name 'excel_ops'.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "write", "get_sheet_names"],
                    "description": _(
                        "param.action.description",
                        default=(
                            "Operation to perform.\n"
                            "- 'read': read the specified sheet and return JSON.\n"
                            "- 'write': write JSON data to the specified sheet (create file if missing).\n"
                            "- 'get_sheet_names': get a list of sheet names."
                        ),
                    ),
                },
                "file_path": {
                    "type": "string",
                    "description": _(
                        "param.file_path.description",
                        default="Absolute path to the Excel file.",
                    ),
                },
                "sheet_name": {
                    "type": "string",
                    "description": _(
                        "param.sheet_name.description",
                        default=(
                            "Target sheet name (for read/write). If omitted, read uses the first sheet and write uses 'Sheet1'."
                        ),
                    ),
                },
                "data": {
                    "type": "string",
                    "description": _(
                        "param.data.description",
                        default="Data to write (JSON string).",
                    ),
                },
            },
            "required": ["action", "file_path"],
        },
    },
}


def _backup_path(path: str) -> str:
    base = path + ".org"
    if not os.path.exists(base):
        return base
    i = 1
    while True:
        cand = f"{path}.org{i}"
        if not os.path.exists(cand):
            return cand
        i += 1


def run_tool(args: Dict[str, Any]) -> str:
    action = args.get("action")
    file_path = str(args.get("file_path", "") or "").strip()
    sheet_name = args.get("sheet_name")
    data_str = args.get("data")

    if action not in ("read", "write", "get_sheet_names"):
        raise ValueError("Invalid action")

    if not file_path:
        raise ValueError("file_path is required")

    # Lazy import openpyxl to keep tool import light.
    import openpyxl

    if action == "get_sheet_names":
        wb = openpyxl.load_workbook(file_path)
        try:
            return json.dumps(wb.sheetnames, ensure_ascii=False)
        finally:
            wb.close()

    if action == "read":
        wb = openpyxl.load_workbook(file_path, data_only=True)
        try:
            target = sheet_name or wb.sheetnames[0]
            ws = wb[target]
            # Return as list of rows (list of values)
            rows: List[List[Any]] = []
            for row in ws.iter_rows(values_only=True):
                rows.append(list(row))
            return json.dumps(rows, ensure_ascii=False)
        finally:
            wb.close()

    # write
    if os.path.exists(file_path):
        backup = _backup_path(file_path)
        with open(file_path, "rb") as fsrc, open(backup, "wb") as fdst:
            fdst.write(fsrc.read())

    if os.path.exists(file_path):
        wb = openpyxl.load_workbook(file_path)
    else:
        wb = openpyxl.Workbook()

    try:
        target = sheet_name or "Sheet1"
        if target in wb.sheetnames:
            ws = wb[target]
            # clear
            ws.delete_rows(1, ws.max_row)
        else:
            ws = wb.create_sheet(title=target)

        if data_str is None:
            data_str = "[]"
        data = json.loads(str(data_str))

        if isinstance(data, list) and data and isinstance(data[0], dict):
            # write header
            keys = list(data[0].keys())
            ws.append(keys)
            for obj in data:
                ws.append([obj.get(k) for k in keys])
        elif isinstance(data, list):
            for row in data:
                if isinstance(row, list):
                    ws.append(row)
                else:
                    ws.append([row])
        else:
            ws.append([data])

        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
        wb.save(file_path)
        return file_path
    finally:
        wb.close()
