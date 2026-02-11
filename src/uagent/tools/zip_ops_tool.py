# tools/zip_ops_tool.py
"""zip_ops_tool

ZIP の作成/展開/一覧を行うツール。

安全:
- extract 時は Zip Slip（../ や絶対パス）を拒否。
- extract 時の上書きは human_ask で確認。
- Zip bomb 対策: 最大ファイル数・最大展開総量を制限。
- workdir 外のパスは拒否（safe_file_ops_extras に準拠）。

注意:
- Windows のパス区切りやエンコーディングを考慮し、zipfile標準を使う。
"""

from __future__ import annotations

import json
import os
import zipfile
from typing import Any, Dict, List

from .safe_file_ops_extras import ensure_within_workdir, is_path_dangerous

BUSY_LABEL = True
STATUS_LABEL = "tool:zip_ops"


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "zip_ops",
        "description": "ZIPファイルの作成/展開/一覧を行います（Zip Slip/Zip Bomb 対策あり）。",
        "system_prompt": (
            "ZIPファイルの作成/展開/一覧を行います（Zip Slip/Zip Bomb 対策あり）。"
            "重要: extract 時は Zip Slip（../ や絶対パス、ドライブレター等）を拒否します。"
            "重要: extract 時の overwrite=True は既存ファイルを上書きする可能性があるため human_ask で確認します。"
            "重要: Zip bomb 対策として、最大ファイル数(max_files)・最大展開総量(max_total_uncompressed_bytes)を超える場合は拒否します。"
            "重要: workdir 外のパスは拒否します（safe_file_ops_extras に準拠）。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "extract", "list"],
                    "description": "操作種別",
                },
                "zip_path": {
                    "type": "string",
                    "description": "zipファイルのパス",
                },
                "sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                    "description": "create時の入力（ファイル/ディレクトリ）",
                },
                "dest_dir": {
                    "type": "string",
                    "default": ".",
                    "description": "extract時の展開先ディレクトリ",
                },
                "exclude_globs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                    "description": "create時の除外（簡易: ベース名一致）",
                },
                "overwrite": {
                    "type": "boolean",
                    "default": False,
                    "description": "extract時、既存ファイルを上書きするか（要確認）",
                },
                "max_files": {
                    "type": "integer",
                    "default": 5000,
                    "description": "extract時の最大ファイル数（Zip bomb対策）",
                },
                "max_total_uncompressed_bytes": {
                    "type": "integer",
                    "default": 500_000_000,
                    "description": "extract時の最大展開総量(bytes)（Zip bomb対策、既定:500MB）",
                },
                "dry_run": {
                    "type": "boolean",
                    "default": False,
                    "description": "extract時、展開せずに検査のみ行う",
                },
            },
            "required": ["action", "zip_path"],
        },
    },
}


def _is_zip_entry_dangerous(name: str) -> bool:
    n = (name or "").replace("\\", "/")
    if not n:
        return True
    if n.startswith("/"):
        return True
    parts = [p for p in n.split("/") if p]
    if any(p == ".." for p in parts):
        return True
    if len(n) >= 2 and n[1] == ":":
        return True
    if n.startswith("//"):
        return True
    return False


def _human_confirm(message: str) -> bool:
    try:
        from .human_ask_tool import run_tool as human_ask

        res_json = human_ask({"message": message})
        res = json.loads(res_json)
        user_reply = (res.get("user_reply") or "").strip().lower()
        return user_reply in ("y", "yes")
    except Exception:
        try:
            resp = input(message + " [y/c/N]: ")
            return resp.strip().lower() == "y"
        except Exception:
            return False


def run_tool(args: Dict[str, Any]) -> str:
    action = str(args.get("action") or "")
    zip_path = str(args.get("zip_path") or "")
    sources = args.get("sources", []) or []
    dest_dir = str(args.get("dest_dir") or ".")
    exclude_globs = args.get("exclude_globs", []) or []
    overwrite = bool(args.get("overwrite", False))
    max_files = args.get("max_files")
    if max_files is None:
        max_files = 5000
    else:
        max_files = int(max_files)

    max_total_uncompressed_bytes = args.get("max_total_uncompressed_bytes")
    if max_total_uncompressed_bytes is None:
        max_total_uncompressed_bytes = 500_000_000
    else:
        max_total_uncompressed_bytes = int(max_total_uncompressed_bytes)
    dry_run = bool(args.get("dry_run", False))

    if action not in ("create", "extract", "list"):
        return json.dumps(
            {"ok": False, "error": f"invalid action: {action}"}, ensure_ascii=False
        )

    if not zip_path:
        return json.dumps(
            {"ok": False, "error": "zip_path is required"}, ensure_ascii=False
        )

    if is_path_dangerous(zip_path):
        return json.dumps(
            {"ok": False, "error": f"dangerous zip_path rejected: {zip_path}"},
            ensure_ascii=False,
        )

    try:
        safe_zip_path = ensure_within_workdir(zip_path)
    except Exception as e:
        return json.dumps(
            {"ok": False, "error": f"zip_path not allowed: {e}"}, ensure_ascii=False
        )

    if action == "list":
        if not os.path.exists(safe_zip_path):
            return json.dumps(
                {"ok": False, "error": f"zip not found: {safe_zip_path}"},
                ensure_ascii=False,
            )
        try:
            with zipfile.ZipFile(safe_zip_path, "r") as z:
                infos = z.infolist()
                files = [
                    {
                        "name": i.filename,
                        "file_size": i.file_size,
                        "compress_size": i.compress_size,
                    }
                    for i in infos
                ]
            return json.dumps(
                {
                    "ok": True,
                    "action": "list",
                    "zip_path": safe_zip_path,
                    "entries": files,
                },
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps(
                {"ok": False, "error": f"zip list failed: {type(e).__name__}: {e}"},
                ensure_ascii=False,
            )

    if action == "create":
        if not sources:
            return json.dumps(
                {"ok": False, "error": "sources is required for create"},
                ensure_ascii=False,
            )

        safe_sources: List[str] = []
        for s in sources:
            s = str(s)
            if is_path_dangerous(s):
                return json.dumps(
                    {"ok": False, "error": f"dangerous source rejected: {s}"},
                    ensure_ascii=False,
                )
            try:
                safe_sources.append(ensure_within_workdir(s))
            except Exception as e:
                return json.dumps(
                    {"ok": False, "error": f"source not allowed: {e}"},
                    ensure_ascii=False,
                )

        exclude_set = set(str(x) for x in exclude_globs)

        try:
            os.makedirs(os.path.dirname(safe_zip_path) or ".", exist_ok=True)
            with zipfile.ZipFile(
                safe_zip_path, "w", compression=zipfile.ZIP_DEFLATED
            ) as z:
                added: List[str] = []
                for src in safe_sources:
                    if os.path.isdir(src):
                        for dirpath, _, filenames in os.walk(src):
                            for fn in filenames:
                                if fn in exclude_set:
                                    continue
                                fp = os.path.join(dirpath, fn)
                                arcname = os.path.relpath(fp, os.getcwd()).replace(
                                    "\\", "/"
                                )
                                z.write(fp, arcname)
                                added.append(arcname)
                    else:
                        if os.path.basename(src) in exclude_set:
                            continue
                        arcname = os.path.relpath(src, os.getcwd()).replace("\\", "/")
                        z.write(src, arcname)
                        added.append(arcname)

            return json.dumps(
                {
                    "ok": True,
                    "action": "create",
                    "zip_path": safe_zip_path,
                    "added": added,
                    "count": len(added),
                },
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps(
                {"ok": False, "error": f"zip create failed: {type(e).__name__}: {e}"},
                ensure_ascii=False,
            )

    # extract
    if not os.path.exists(safe_zip_path):
        return json.dumps(
            {"ok": False, "error": f"zip not found: {safe_zip_path}"},
            ensure_ascii=False,
        )

    if is_path_dangerous(dest_dir):
        return json.dumps(
            {"ok": False, "error": f"dangerous dest_dir rejected: {dest_dir}"},
            ensure_ascii=False,
        )

    try:
        safe_dest = ensure_within_workdir(dest_dir)
    except Exception as e:
        return json.dumps(
            {"ok": False, "error": f"dest_dir not allowed: {e}"}, ensure_ascii=False
        )

    try:
        with zipfile.ZipFile(safe_zip_path, "r") as z:
            infos = z.infolist()

            if len(infos) > max_files:
                return json.dumps(
                    {
                        "ok": False,
                        "error": f"too many files in zip: {len(infos)} > max_files({max_files})",
                    },
                    ensure_ascii=False,
                )

            total_uncompressed = sum(int(i.file_size) for i in infos)
            if total_uncompressed > max_total_uncompressed_bytes:
                return json.dumps(
                    {
                        "ok": False,
                        "error": (
                            f"zip too large to extract: total_uncompressed={total_uncompressed} "
                            f"> max_total_uncompressed_bytes({max_total_uncompressed_bytes})"
                        ),
                    },
                    ensure_ascii=False,
                )

            dangerous = [
                i.filename for i in infos if _is_zip_entry_dangerous(i.filename)
            ]
            if dangerous:
                return json.dumps(
                    {
                        "ok": False,
                        "error": "dangerous zip entries rejected",
                        "entries": dangerous,
                    },
                    ensure_ascii=False,
                )

            if overwrite:
                msg = (
                    "zip_ops(extract) は既存ファイルを上書きする可能性があります。\n"
                    f"zip: {safe_zip_path}\n"
                    f"dest: {safe_dest}\n"
                    f"entries: {len(infos)}\n\n"
                    "実行してよければ y、キャンセルなら c を入力してください。"
                )
                if not _human_confirm(msg):
                    return json.dumps(
                        {"ok": False, "error": "cancelled by user"}, ensure_ascii=False
                    )

            if dry_run:
                return json.dumps(
                    {
                        "ok": True,
                        "action": "extract",
                        "dry_run": True,
                        "zip_path": safe_zip_path,
                        "dest_dir": safe_dest,
                        "entries": len(infos),
                        "total_uncompressed": total_uncompressed,
                    },
                    ensure_ascii=False,
                )

            os.makedirs(safe_dest, exist_ok=True)

            extracted: List[str] = []
            for i in infos:
                out_path = os.path.join(safe_dest, i.filename.replace("/", os.sep))
                os.makedirs(os.path.dirname(out_path) or safe_dest, exist_ok=True)

                if os.path.exists(out_path) and not overwrite:
                    continue

                with z.open(i, "r") as src_f, open(out_path, "wb") as dst_f:
                    dst_f.write(src_f.read())
                extracted.append(i.filename)

            return json.dumps(
                {
                    "ok": True,
                    "action": "extract",
                    "dry_run": False,
                    "zip_path": safe_zip_path,
                    "dest_dir": safe_dest,
                    "extracted": extracted,
                    "count": len(extracted),
                },
                ensure_ascii=False,
            )
    except Exception as e:
        return json.dumps(
            {"ok": False, "error": f"zip extract failed: {type(e).__name__}: {e}"},
            ensure_ascii=False,
        )
