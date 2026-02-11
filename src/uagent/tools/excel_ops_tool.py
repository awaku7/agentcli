import pandas as pd
import json
import os
from pathlib import Path
from typing import Any, Dict

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "excel_ops",
        "description": "Excelファイル(.xlsx)の読み書きおよびシート名取得を行います。write で既存ファイルに書き込む場合、書き込み直前に同名のバックアップ（<file_path>.org / <file_path>.org1 / <file_path>.org2 ...）を作成します。",
        "system_prompt": """このツールは次の目的で使われます: Excelファイル(.xlsx)の読み書きおよびシート名取得を行います。write で既存ファイルに書き込む場合、書き込み直前に同名のバックアップ（<file_path>.org / <file_path>.org1 / <file_path>.org2 ...）を作成します。""",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "write", "get_sheet_names"],
                    "description": "実行する操作。\n- 'read': 指定シートを読み込みJSONで返す。\n- 'write': JSONデータを指定シートに書き込む（ファイルがない場合は新規作成）。\n- 'get_sheet_names': シート名一覧を取得する。",
                },
                "file_path": {
                    "type": "string",
                    "description": "Excelファイルの絶対パス。",
                },
                "sheet_name": {
                    "type": "string",
                    "description": "対象のシート名（read/write時）。指定がない場合、readは先頭シート、writeは 'Sheet1' となる。",
                },
                "data": {
                    "type": "string",
                    "description": '書き込むデータ（JSON文字列）。リスト形式の辞書 `[{"col1": "val1"}, ...]` を推奨。',
                },
            },
            "required": ["action", "file_path"],
        },
    },
}


def _next_backup_name(filename: str) -> str:
    base = filename + ".org"
    if not os.path.exists(base):
        return base

    i = 1
    while True:
        cand = f"{base}{i}"
        if not os.path.exists(cand):
            return cand
        i += 1


def _make_backup_if_needed(file_path: str) -> str | None:
    """Create a backup for an existing file.

    - Only when the target exists.
    - Backup name: <file_path>.org / .org1 / ... (no overwrite)
    - Copy bytes as-is.

    Returns backup path if created, otherwise None.
    """
    if not os.path.exists(file_path):
        return None

    backup_path = _next_backup_name(file_path)
    Path(backup_path).parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "rb") as rf, open(backup_path, "wb") as wf:
        wf.write(rf.read())
    return backup_path


def run_tool(args: Dict[str, Any]) -> str:
    """
    Excel操作ツール
    """
    action = args.get("action")
    file_path = args.get("file_path", "").strip()
    sheet_name = args.get("sheet_name")
    data_str = args.get("data")

    if not file_path:
        return "[excel_ops error] file_path is required."

    MAX_RETRIES = 5

    for attempt in range(MAX_RETRIES):
        try:
            if action == "get_sheet_names":
                if not os.path.exists(file_path):
                    return f"[excel_ops error] File not found: {file_path}"

                xl = pd.ExcelFile(file_path)
                return json.dumps({"sheet_names": xl.sheet_names}, ensure_ascii=False)

            elif action == "read":
                if not os.path.exists(file_path):
                    return f"[excel_ops error] File not found: {file_path}"

                target_sheet = sheet_name if sheet_name else 0
                df = pd.read_excel(file_path, sheet_name=target_sheet)

                data_list = df.fillna("").to_dict(orient="records")
                return json.dumps(data_list, ensure_ascii=False, default=str)

            elif action == "write":
                if not data_str:
                    return "[excel_ops error] 'data' is required for write action."

                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    return "[excel_ops error] 'data' must be a valid JSON string."

                if not isinstance(data, list):
                    return "[excel_ops error] 'data' must be a list of dictionaries."

                df = pd.DataFrame(data)
                target_sheet = sheet_name if sheet_name else "Sheet1"

                backup_path = None
                try:
                    backup_path = _make_backup_if_needed(file_path)
                except Exception as e:
                    return f"[excel_ops error] バックアップ作成に失敗しました: {type(e).__name__}: {e}"

                if os.path.exists(file_path):
                    with pd.ExcelWriter(
                        file_path,
                        engine="openpyxl",
                        mode="a",
                        if_sheet_exists="replace",
                    ) as writer:
                        df.to_excel(writer, sheet_name=target_sheet, index=False)
                else:
                    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                        df.to_excel(writer, sheet_name=target_sheet, index=False)

                msg = f"[excel_ops] Successfully wrote {len(df)} rows to {file_path} (Sheet: {target_sheet})"
                if backup_path:
                    msg += f" / バックアップ作成: {backup_path}"
                return msg

            else:
                return f"[excel_ops error] Unknown action: {action}"

        except PermissionError:
            # File is locked. Ask user to retry.
            try:
                from .human_ask_tool import run_tool as human_ask

                msg = (
                    f"Excelファイル ({file_path}) がロックされています（開かれている可能性があります）。\n"
                    "ファイルを閉じてから 'y' を入力してリトライしてください。\n"
                    "（'n' でキャンセル）"
                )
                res_json = human_ask({"message": msg})
                res = json.loads(res_json)
                user_reply = res.get("user_reply", "").strip().lower()

                if user_reply == "y":
                    continue  # Retry
                else:
                    return "[excel_ops error] Operation cancelled by user after PermissionError."

            except Exception as e_inner:
                return f"[excel_ops error] PermissionError occurred and failed to ask user: {e_inner}"

        except Exception as e:
            return f"[excel_ops error] {str(e)}"

    return f"[excel_ops error] Operation failed after {MAX_RETRIES} retries."
