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
from .i18n_helper import make_tool_translator

BUSY_LABEL = True
STATUS_LABEL = "tool:zip_ops"


t = make_tool_translator(__file__)

# Translator usage: t(key, default=...)


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "zip_ops",
        "description": t(
            "tool.description",
            default="Create/extract/list ZIP files (with Zip Slip/Zip Bomb protections).",
        ),
        "system_prompt": t(
            "tool.system_prompt",
            default="Create/extract/list ZIP files (with Zip Slip/Zip Bomb protections). Important: during extract, Zip Slip paths (../, absolute paths, drive letters, etc.) are rejected. Important: overwrite=True for extract may overwrite existing files and will ask for confirmation via human_ask. Important: Zip bomb protections reject archives exceeding max_files and max_total_uncompressed_bytes. Important: paths outside workdir are rejected (per safe_file_ops_extras).",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "extract", "list"],
                    "description": t(
                        "param.action.description", default="Operation type."
                    ),
                },
                "zip_path": {
                    "type": "string",
                    "description": t(
                        "param.zip_path.description", default="Path to the zip file."
                    ),
                },
                "sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                    "description": t(
                        "param.sources.description",
                        default="Inputs for create (files/directories).",
                    ),
                },
                "dest_dir": {
                    "type": "string",
                    "default": ".",
                    "description": t(
                        "param.dest_dir.description",
                        default="Destination directory for extract.",
                    ),
                },
                "exclude_globs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                    "description": t(
                        "param.exclude_globs.description",
                        default="Exclusions for create (simple: basename match).",
                    ),
                },
                "overwrite": {
                    "type": "boolean",
                    "default": False,
                    "description": t(
                        "param.overwrite.description",
                        default="Whether to overwrite existing files on extract (requires confirmation).",
                    ),
                },
                "max_files": {
                    "type": "integer",
                    "default": 5000,
                    "description": t(
                        "param.max_files.description",
                        default="Maximum number of files allowed on extract (zip bomb protection).",
                    ),
                },
                "max_total_uncompressed_bytes": {
                    "type": "integer",
                    "default": 500_000_000,
                    "description": t(
                        "param.max_total_uncompressed_bytes.description",
                        default="Maximum total uncompressed bytes allowed on extract (zip bomb protection).",
                    ),
                },
                "dry_run": {
                    "type": "boolean",
                    "default": False,
                    "description": t(
                        "param.dry_run.description",
                        default="For extract: validate only without extracting.",
                    ),
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
            {
                "ok": False,
                "error": t(
                    "error.invalid_action", default="invalid action: {action}"
                ).format(action=action),
            },
            ensure_ascii=False,
        )

    if not zip_path:
        return json.dumps(
            {
                "ok": False,
                "error": t("error.zip_path_required", default="zip_path is required"),
            },
            ensure_ascii=False,
        )

    if is_path_dangerous(zip_path):
        return json.dumps(
            {
                "ok": False,
                "error": t(
                    "error.dangerous_zip_path_rejected",
                    default="dangerous zip_path rejected: {zip_path}",
                ).format(zip_path=zip_path),
            },
            ensure_ascii=False,
        )

    try:
        safe_zip_path = ensure_within_workdir(zip_path)
    except Exception as e:
        return json.dumps(
            {
                "ok": False,
                "error": t(
                    "error.zip_path_not_allowed",
                    default="zip_path not allowed: {error}",
                ).format(error=e),
            },
            ensure_ascii=False,
        )

    if action == "list":
        if not os.path.exists(safe_zip_path):
            return json.dumps(
                {
                    "ok": False,
                    "error": t(
                        "error.zip_not_found", default="zip not found: {zip_path}"
                    ).format(zip_path=safe_zip_path),
                },
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
                {
                    "ok": False,
                    "error": t(
                        "error.zip_list_failed",
                        default="zip list failed: {etype}: {error}",
                    ).format(etype=type(e).__name__, error=e),
                },
                ensure_ascii=False,
            )

    if action == "create":
        if not sources:
            return json.dumps(
                {
                    "ok": False,
                    "error": t(
                        "error.sources_required_for_create",
                        default="sources is required for create",
                    ),
                },
                ensure_ascii=False,
            )

        safe_sources: List[str] = []
        for s in sources:
            s = str(s)
            if is_path_dangerous(s):
                return json.dumps(
                    {
                        "ok": False,
                        "error": t(
                            "error.dangerous_source_rejected",
                            default="dangerous source rejected: {source}",
                        ).format(source=s),
                    },
                    ensure_ascii=False,
                )
            try:
                safe_sources.append(ensure_within_workdir(s))
            except Exception as e:
                return json.dumps(
                    {
                        "ok": False,
                        "error": t(
                            "error.source_not_allowed",
                            default="source not allowed: {error}",
                        ).format(error=e),
                    },
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
                {
                    "ok": False,
                    "error": t(
                        "error.zip_create_failed",
                        default="zip create failed: {etype}: {error}",
                    ).format(etype=type(e).__name__, error=e),
                },
                ensure_ascii=False,
            )

    # extract
    if not os.path.exists(safe_zip_path):
        return json.dumps(
            {
                "ok": False,
                "error": t(
                    "error.zip_not_found", default="zip not found: {zip_path}"
                ).format(zip_path=safe_zip_path),
            },
            ensure_ascii=False,
        )

    if is_path_dangerous(dest_dir):
        return json.dumps(
            {
                "ok": False,
                "error": t(
                    "error.dangerous_dest_dir_rejected",
                    default="dangerous dest_dir rejected: {dest_dir}",
                ).format(dest_dir=dest_dir),
            },
            ensure_ascii=False,
        )

    try:
        safe_dest = ensure_within_workdir(dest_dir)
    except Exception as e:
        return json.dumps(
            {
                "ok": False,
                "error": t(
                    "error.dest_dir_not_allowed",
                    default="dest_dir not allowed: {error}",
                ).format(error=e),
            },
            ensure_ascii=False,
        )

    try:
        with zipfile.ZipFile(safe_zip_path, "r") as z:
            infos = z.infolist()

            if len(infos) > max_files:
                return json.dumps(
                    {
                        "ok": False,
                        "error": t(
                            "error.too_many_files_in_zip",
                            default="too many files in zip: {count} > max_files({max_files})",
                        ).format(count=len(infos), max_files=max_files),
                    },
                    ensure_ascii=False,
                )

            total_uncompressed = sum(int(i.file_size) for i in infos)
            if total_uncompressed > max_total_uncompressed_bytes:
                return json.dumps(
                    {
                        "ok": False,
                        "error": (
                            t(
                                "error.zip_too_large_to_extract",
                                default="zip too large to extract: total_uncompressed={total_uncompressed} > max_total_uncompressed_bytes({max_total_uncompressed_bytes})",
                            ).format(
                                total_uncompressed=total_uncompressed,
                                max_total_uncompressed_bytes=max_total_uncompressed_bytes,
                            )
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
                        "error": t(
                            "error.dangerous_zip_entries_rejected",
                            default="dangerous zip entries rejected",
                        ),
                        "entries": dangerous,
                    },
                    ensure_ascii=False,
                )

            if overwrite:
                msg = t(
                    "confirm.extract_overwrite",
                    default="zip_ops(extract) may overwrite existing files.\nzip: {zip_path}\ndest: {dest_dir}\nentries: {entries}\n\nEnter y to proceed, or c to cancel.",
                ).format(zip_path=safe_zip_path, dest_dir=safe_dest, entries=len(infos))
                if not _human_confirm(msg):
                    return json.dumps(
                        {
                            "ok": False,
                            "error": t(
                                "error.cancelled_by_user", default="cancelled by user"
                            ),
                        },
                        ensure_ascii=False,
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
            {
                "ok": False,
                "error": t(
                    "error.zip_extract_failed",
                    default="zip extract failed: {etype}: {error}",
                ).format(etype=type(e).__name__, error=e),
            },
            ensure_ascii=False,
        )
