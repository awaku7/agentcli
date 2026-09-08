# tools/zip_ops_tool.py
"""zip_ops_tool

Tool to create/extract/list/view ZIP and TAR archives.

Safety:
- Reject Zip/Tar Slip entries (../, absolute paths, drive letters, etc.) on extract.
- Safe extraction filter logic for both ZIP and TAR (prevent symlink escape, dangerous entries).
- Confirm overwrite on extract via human_ask.
- Zip/Tar bomb protections: limit max files and total uncompressed bytes.
- Reject paths outside workdir (per safe_file_ops_extras).

Notes:
- Uses Python standard zipfile and tarfile modules.
- Supports .zip, .tar, .tar.gz, .tgz, .tar.bz2, .tbz2, .tar.xz, .txz archives transparently.
"""

from __future__ import annotations

import fnmatch
import json
import os
import tarfile
import zipfile
from typing import Any

from .i18n_helper import make_tool_translator
from .safe_file_ops_extras import ensure_within_workdir, is_path_dangerous

BUSY_LABEL = True
STATUS_LABEL = "tool:zip_ops"

_ = make_tool_translator(__file__)

TOOL_SPEC: dict[str, Any] = {
    "load_order": -1,
    "type": "function",
    "tool_genre": "file",
    "function": {
        "name": "zip_ops",
        "description": _(
            "tool.description",
            default="Create, extract, list, or preview ZIP and TAR archives. Protected against path traversal and archive bombs.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "zip_ops",
                "zip ops",
                "zip",
                "tar",
                "tar.gz",
                "tgz",
                "archive",
                "extract zip",
                "compress",
            ],
        ),
        "x_search_terms_en": [
            "zip_ops",
            "zip ops",
            "zip",
            "tar",
            "tar.gz",
            "tgz",
            "archive",
            "extract zip",
            "compress",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "extract", "list", "view"],
                    "description": _(
                        "param.action.description",
                        default="Operation type: create, extract, list, or view.",
                    ),
                },
                "zip_path": {
                    "type": "string",
                    "description": _(
                        "param.zip_path.description",
                        default="Path to the archive file (.zip, .tar, .tar.gz, .tgz, .tar.bz2, .tar.xz, etc.).",
                    ),
                },
                "format": {
                    "type": "string",
                    "enum": ["auto", "zip", "tar", "tar.gz", "tar.bz2", "tar.xz"],
                    "default": "auto",
                    "description": _(
                        "param.format.description",
                        default="Archive format (auto, zip, tar, tar.gz, tar.bz2, tar.xz). Defaults to auto.",
                    ),
                },
                "sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                    "description": _(
                        "param.sources.description",
                        default="Inputs for create (files/directories).",
                    ),
                },
                "dest_dir": {
                    "type": "string",
                    "default": ".",
                    "description": _(
                        "param.dest_dir.description",
                        default="Destination directory for extract.",
                    ),
                },
                "exclude_globs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                    "description": _(
                        "param.exclude_globs.description",
                        default="Exclusions for create (glob patterns matched against basename and relative path).",
                    ),
                },
                "extract_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                    "description": _(
                        "param.extract_files.description",
                        default="Selective extraction: list of file names or glob patterns to extract.",
                    ),
                },
                "relative_to": {
                    "type": "string",
                    "default": "",
                    "description": _(
                        "param.relative_to.description",
                        default="Base directory to compute relative paths inside archive during create.",
                    ),
                },
                "strip_components": {
                    "type": "integer",
                    "default": 0,
                    "description": _(
                        "param.strip_components.description",
                        default="Number of leading directory components to strip on extract.",
                    ),
                },
                "target_file": {
                    "type": "string",
                    "default": "",
                    "description": _(
                        "param.target_file.description",
                        default="Relative path of file inside archive to preview for view action.",
                    ),
                },
                "max_bytes": {
                    "type": "integer",
                    "default": 102400,
                    "description": _(
                        "param.max_bytes.description",
                        default="Maximum bytes to read for view action (default 100KB).",
                    ),
                },
                "overwrite": {
                    "type": "boolean",
                    "default": False,
                    "description": _(
                        "param.overwrite.description",
                        default="Whether to overwrite existing files on extract (requires confirmation).",
                    ),
                },
                "max_files": {
                    "type": "integer",
                    "default": 5000,
                    "description": _(
                        "param.max_files.description",
                        default="Maximum number of files allowed on extract (zip bomb protection).",
                    ),
                },
                "max_total_uncompressed_bytes": {
                    "type": "integer",
                    "default": 500_000_000,
                    "description": _(
                        "param.max_total_uncompressed_bytes.description",
                        default="Maximum total uncompressed bytes allowed on extract (zip bomb protection).",
                    ),
                },
                "dry_run": {
                    "type": "boolean",
                    "default": False,
                    "description": _(
                        "param.dry_run.description",
                        default="For extract: validate only without extracting.",
                    ),
                },
            },
            "required": ["action", "zip_path"],
        },
    },
}


def _detect_format(path: str, format_hint: str = "auto") -> str:
    fmt = (format_hint or "auto").strip().lower()
    if fmt and fmt != "auto":
        return fmt

    low = path.lower()
    if low.endswith((".tar.gz", ".tgz")):
        return "tar.gz"
    elif low.endswith((".tar.bz2", ".tbz2", ".tbz")):
        return "tar.bz2"
    elif low.endswith((".tar.xz", ".txz")):
        return "tar.xz"
    elif low.endswith(".tar"):
        return "tar"
    elif low.endswith(".zip"):
        return "zip"
    return "zip"


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


def _strip_path_components(name: str, count: int) -> str | None:
    if count <= 0:
        return name
    parts = [p for p in name.replace("\\", "/").split("/") if p]
    if len(parts) <= count:
        return None
    return "/".join(parts[count:])


def _matches_any_glob(name: str, patterns: list[str]) -> bool:
    if not patterns:
        return True
    norm_name = name.replace("\\", "/")
    base_name = os.path.basename(norm_name)
    for pat in patterns:
        pat_norm = str(pat).replace("\\", "/")
        if fnmatch.fnmatch(norm_name, pat_norm) or fnmatch.fnmatch(base_name, pat_norm):
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


def _run_list(safe_zip_path: str, fmt: str, _) -> str:
    if not os.path.exists(safe_zip_path):
        return json.dumps(
            {
                "ok": False,
                "error": _(
                    "error.zip_not_found", default="zip not found: {zip_path}"
                ).format(zip_path=safe_zip_path),
            },
            ensure_ascii=False,
        )

    try:
        files: list[dict[str, Any]] = []
        if fmt == "zip":
            with zipfile.ZipFile(safe_zip_path, "r") as z:
                for i in z.infolist():
                    files.append(
                        {
                            "name": i.filename,
                            "file_size": i.file_size,
                            "compress_size": i.compress_size,
                            "is_dir": i.is_dir(),
                        }
                    )
        else:
            mode = "r:*"
            with tarfile.open(safe_zip_path, mode) as t:
                for m in t.getmembers():
                    files.append(
                        {
                            "name": m.name,
                            "file_size": m.size,
                            "compress_size": m.size,
                            "is_dir": m.isdir(),
                        }
                    )
        return json.dumps(
            {
                "ok": True,
                "action": "list",
                "zip_path": safe_zip_path,
                "format": fmt,
                "entries": files,
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {
                "ok": False,
                "error": _(
                    "error.zip_list_failed",
                    default="zip list failed: {etype}: {error}",
                ).format(etype=type(e).__name__, error=e),
            },
            ensure_ascii=False,
        )


def _run_view(
    safe_zip_path: str,
    target_file: str,
    max_bytes: int,
    fmt: str,
    _,
) -> str:
    if not os.path.exists(safe_zip_path):
        return json.dumps(
            {
                "ok": False,
                "error": _(
                    "error.zip_not_found", default="zip not found: {zip_path}"
                ).format(zip_path=safe_zip_path),
            },
            ensure_ascii=False,
        )

    if not target_file:
        return json.dumps(
            {
                "ok": False,
                "error": _(
                    "error.target_file_required",
                    default="target_file is required for view action",
                ),
            },
            ensure_ascii=False,
        )

    target_norm = target_file.replace("\\", "/").lstrip("/")

    try:
        content_bytes = b""
        total_size = 0
        found = False

        if fmt == "zip":
            with zipfile.ZipFile(safe_zip_path, "r") as z:
                for info in z.infolist():
                    curr_norm = info.filename.replace("\\", "/").lstrip("/")
                    if curr_norm == target_norm:
                        found = True
                        total_size = info.file_size
                        with z.open(info, "r") as f:
                            content_bytes = f.read(max_bytes)
                        break
        else:
            with tarfile.open(safe_zip_path, "r:*") as t:
                for member in t.getmembers():
                    curr_norm = member.name.replace("\\", "/").lstrip("./").lstrip("/")
                    if curr_norm == target_norm:
                        found = True
                        total_size = member.size
                        f = t.extractfile(member)
                        if f is not None:
                            content_bytes = f.read(max_bytes)
                        break

        if not found:
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "error.file_not_found_in_archive",
                        default="file not found in archive: {target_file}",
                    ).format(target_file=target_file),
                },
                ensure_ascii=False,
            )

        truncated = len(content_bytes) < total_size
        encoding = "utf-8"
        try:
            content_str = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                content_str = content_bytes.decode("cp932")
                encoding = "cp932"
            except UnicodeDecodeError:
                content_str = content_bytes.decode("latin-1", errors="replace")
                encoding = "latin-1"

        return json.dumps(
            {
                "ok": True,
                "action": "view",
                "zip_path": safe_zip_path,
                "target_file": target_norm,
                "size": total_size,
                "bytes_read": len(content_bytes),
                "truncated": truncated,
                "encoding": encoding,
                "content": content_str,
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {
                "ok": False,
                "error": _(
                    "error.zip_view_failed",
                    default="zip view failed: {etype}: {error}",
                ).format(etype=type(e).__name__, error=e),
            },
            ensure_ascii=False,
        )


def _run_create(
    safe_zip_path: str,
    sources: list[Any],
    exclude_globs: list[Any],
    relative_to: str,
    fmt: str,
    _,
) -> str:
    if not sources:
        return json.dumps(
            {
                "ok": False,
                "error": _(
                    "error.sources_required_for_create",
                    default="sources is required for create",
                ),
            },
            ensure_ascii=False,
        )

    safe_sources: list[str] = []
    for s in sources:
        s_str = str(s)
        if is_path_dangerous(s_str):
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "error.dangerous_source_rejected",
                        default="dangerous source rejected: {source}",
                    ).format(source=s_str),
                },
                ensure_ascii=False,
            )
        try:
            safe_sources.append(ensure_within_workdir(s_str))
        except Exception as e:
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "error.source_not_allowed",
                        default="source not allowed: {error}",
                    ).format(error=e),
                },
                ensure_ascii=False,
            )

    safe_rel_base = ""
    if relative_to:
        if is_path_dangerous(relative_to):
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "error.dangerous_source_rejected",
                        default="dangerous source rejected: {source}",
                    ).format(source=relative_to),
                },
                ensure_ascii=False,
            )
        try:
            safe_rel_base = ensure_within_workdir(relative_to)
        except Exception as e:
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "error.source_not_allowed",
                        default="source not allowed: {error}",
                    ).format(error=e),
                },
                ensure_ascii=False,
            )

    exclude_patterns = [str(x) for x in exclude_globs if str(x).strip()]

    def should_exclude(rel_path: str, base_name: str) -> bool:
        if not exclude_patterns:
            return False
        for pat in exclude_patterns:
            pat_norm = pat.replace("\\", "/")
            if fnmatch.fnmatch(base_name, pat_norm) or fnmatch.fnmatch(
                rel_path.replace("\\", "/"), pat_norm
            ):
                return True
        return False

    def compute_arcname(path: str) -> str:
        if safe_rel_base:
            arc = os.path.relpath(path, safe_rel_base)
        else:
            arc = os.path.relpath(path, os.getcwd())
        return arc.replace("\\", "/")

    try:
        os.makedirs(os.path.dirname(safe_zip_path) or ".", exist_ok=True)
        added: list[str] = []

        if fmt == "zip":
            with zipfile.ZipFile(
                safe_zip_path, "w", compression=zipfile.ZIP_DEFLATED
            ) as z:
                for src in safe_sources:
                    if os.path.isdir(src):
                        for dirpath, _dirnames, filenames in os.walk(src):
                            for fn in filenames:
                                fp = os.path.join(dirpath, fn)
                                arcname = compute_arcname(fp)
                                if should_exclude(arcname, fn):
                                    continue
                                z.write(fp, arcname)
                                added.append(arcname)
                    else:
                        fn = os.path.basename(src)
                        arcname = compute_arcname(src)
                        if should_exclude(arcname, fn):
                            continue
                        z.write(src, arcname)
                        added.append(arcname)
        else:
            tar_mode = "w"
            if fmt == "tar.gz":
                tar_mode = "w:gz"
            elif fmt == "tar.bz2":
                tar_mode = "w:bz2"
            elif fmt == "tar.xz":
                tar_mode = "w:xz"

            with tarfile.open(safe_zip_path, tar_mode) as t:
                for src in safe_sources:
                    if os.path.isdir(src):
                        for dirpath, _dirnames, filenames in os.walk(src):
                            for fn in filenames:
                                fp = os.path.join(dirpath, fn)
                                arcname = compute_arcname(fp)
                                if should_exclude(arcname, fn):
                                    continue
                                t.add(fp, arcname=arcname, recursive=False)
                                added.append(arcname)
                    else:
                        fn = os.path.basename(src)
                        arcname = compute_arcname(src)
                        if should_exclude(arcname, fn):
                            continue
                        t.add(src, arcname=arcname, recursive=False)
                        added.append(arcname)

        return json.dumps(
            {
                "ok": True,
                "action": "create",
                "zip_path": safe_zip_path,
                "format": fmt,
                "added": added,
                "count": len(added),
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {
                "ok": False,
                "error": _(
                    "error.zip_create_failed",
                    default="zip create failed: {etype}: {error}",
                ).format(etype=type(e).__name__, error=e),
            },
            ensure_ascii=False,
        )


def _run_extract(
    safe_zip_path: str,
    dest_dir: str,
    extract_files: list[Any],
    strip_components: int,
    overwrite: bool,
    max_files: int,
    max_total_uncompressed_bytes: int,
    dry_run: bool,
    fmt: str,
    _,
) -> str:
    if not os.path.exists(safe_zip_path):
        return json.dumps(
            {
                "ok": False,
                "error": _(
                    "error.zip_not_found", default="zip not found: {zip_path}"
                ).format(zip_path=safe_zip_path),
            },
            ensure_ascii=False,
        )

    if is_path_dangerous(dest_dir):
        return json.dumps(
            {
                "ok": False,
                "error": _(
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
                "error": _(
                    "error.dest_dir_not_allowed",
                    default="dest_dir not allowed: {error}",
                ).format(error=e),
            },
            ensure_ascii=False,
        )

    extract_patterns = [str(x) for x in extract_files if str(x).strip()]

    try:
        entries_to_process: list[dict[str, Any]] = []

        if fmt == "zip":
            with zipfile.ZipFile(safe_zip_path, "r") as z:
                raw_infos = z.infolist()
                if len(raw_infos) > max_files:
                    return json.dumps(
                        {
                            "ok": False,
                            "error": _(
                                "error.too_many_files_in_zip",
                                default="too many files in zip: {count} > max_files({max_files})",
                            ).format(count=len(raw_infos), max_files=max_files),
                        },
                        ensure_ascii=False,
                    )

                total_uncompressed = sum(int(i.file_size) for i in raw_infos)
                if total_uncompressed > max_total_uncompressed_bytes:
                    return json.dumps(
                        {
                            "ok": False,
                            "error": _(
                                "error.zip_too_large_to_extract",
                                default="zip too large to extract: total_uncompressed={total_uncompressed} > max_total_uncompressed_bytes({max_total_uncompressed_bytes})",
                            ).format(
                                total_uncompressed=total_uncompressed,
                                max_total_uncompressed_bytes=max_total_uncompressed_bytes,
                            ),
                        },
                        ensure_ascii=False,
                    )

                dangerous = [
                    i.filename for i in raw_infos if _is_zip_entry_dangerous(i.filename)
                ]
                if dangerous:
                    return json.dumps(
                        {
                            "ok": False,
                            "error": _(
                                "error.dangerous_zip_entries_rejected",
                                default="dangerous zip entries rejected",
                            ),
                            "entries": dangerous,
                        },
                        ensure_ascii=False,
                    )

                for info in raw_infos:
                    if info.is_dir():
                        continue
                    orig_name = info.filename
                    if extract_patterns and not _matches_any_glob(
                        orig_name, extract_patterns
                    ):
                        continue

                    out_name = _strip_path_components(orig_name, strip_components)
                    if not out_name:
                        continue
                    if _is_zip_entry_dangerous(out_name):
                        continue

                    entries_to_process.append(
                        {
                            "orig_name": orig_name,
                            "out_name": out_name,
                            "info": info,
                            "size": info.file_size,
                        }
                    )
        else:
            with tarfile.open(safe_zip_path, "r:*") as t:
                raw_members = t.getmembers()
                if len(raw_members) > max_files:
                    return json.dumps(
                        {
                            "ok": False,
                            "error": _(
                                "error.too_many_files_in_zip",
                                default="too many files in zip: {count} > max_files({max_files})",
                            ).format(count=len(raw_members), max_files=max_files),
                        },
                        ensure_ascii=False,
                    )

                total_uncompressed = sum(int(m.size) for m in raw_members)
                if total_uncompressed > max_total_uncompressed_bytes:
                    return json.dumps(
                        {
                            "ok": False,
                            "error": _(
                                "error.zip_too_large_to_extract",
                                default="zip too large to extract: total_uncompressed={total_uncompressed} > max_total_uncompressed_bytes({max_total_uncompressed_bytes})",
                            ).format(
                                total_uncompressed=total_uncompressed,
                                max_total_uncompressed_bytes=max_total_uncompressed_bytes,
                            ),
                        },
                        ensure_ascii=False,
                    )

                dangerous = [
                    m.name
                    for m in raw_members
                    if _is_zip_entry_dangerous(m.name) or m.issym() or m.islnk()
                ]
                if dangerous:
                    return json.dumps(
                        {
                            "ok": False,
                            "error": _(
                                "error.dangerous_zip_entries_rejected",
                                default="dangerous zip entries rejected",
                            ),
                            "entries": dangerous,
                        },
                        ensure_ascii=False,
                    )

                for member in raw_members:
                    if member.isdir():
                        continue
                    orig_name = member.name.lstrip("./")
                    if extract_patterns and not _matches_any_glob(
                        orig_name, extract_patterns
                    ):
                        continue

                    out_name = _strip_path_components(orig_name, strip_components)
                    if not out_name:
                        continue
                    if _is_zip_entry_dangerous(out_name):
                        continue

                    entries_to_process.append(
                        {
                            "orig_name": member.name,
                            "out_name": out_name,
                            "member": member,
                            "size": member.size,
                        }
                    )

        if overwrite:
            msg = _(
                "confirm.extract_overwrite",
                default=(
                    "zip_ops(extract) may overwrite existing files.\n"
                    "zip: {zip_path}\n"
                    "dest: {dest_dir}\n"
                    "entries: {entries}\n\n"
                    "Enter y to proceed, or c to cancel."
                ),
            ).format(
                zip_path=safe_zip_path,
                dest_dir=safe_dest,
                entries=len(entries_to_process),
            )
            if not _human_confirm(msg):
                return json.dumps(
                    {
                        "ok": False,
                        "error": _(
                            "error.cancelled_by_user",
                            default="cancelled by user",
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
                    "entries": len(entries_to_process),
                    "total_uncompressed": sum(e["size"] for e in entries_to_process),
                },
                ensure_ascii=False,
            )

        os.makedirs(safe_dest, exist_ok=True)
        extracted: list[str] = []

        if fmt == "zip":
            with zipfile.ZipFile(safe_zip_path, "r") as z:
                for item in entries_to_process:
                    out_path = os.path.join(
                        safe_dest, item["out_name"].replace("/", os.sep)
                    )
                    ensure_within_workdir(out_path)
                    os.makedirs(os.path.dirname(out_path) or safe_dest, exist_ok=True)

                    if os.path.exists(out_path) and not overwrite:
                        continue

                    with (
                        z.open(item["info"], "r") as src_f,
                        open(out_path, "wb") as dst_f,
                    ):
                        dst_f.write(src_f.read())
                    extracted.append(item["out_name"])
        else:
            with tarfile.open(safe_zip_path, "r:*") as t:
                for item in entries_to_process:
                    out_path = os.path.join(
                        safe_dest, item["out_name"].replace("/", os.sep)
                    )
                    ensure_within_workdir(out_path)
                    os.makedirs(os.path.dirname(out_path) or safe_dest, exist_ok=True)

                    if os.path.exists(out_path) and not overwrite:
                        continue

                    src_f = t.extractfile(item["member"])
                    if src_f is not None:
                        with open(out_path, "wb") as dst_f:
                            dst_f.write(src_f.read())
                        extracted.append(item["out_name"])

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
                "error": _(
                    "error.zip_extract_failed",
                    default="zip extract failed: {etype}: {error}",
                ).format(etype=type(e).__name__, error=e),
            },
            ensure_ascii=False,
        )


def run_tool(args: dict[str, Any]) -> str:
    _ = make_tool_translator(__file__)
    action = str(args.get("action") or "").strip().lower()
    zip_path = str(args.get("zip_path") or "").strip()
    format_arg = str(args.get("format") or "auto").strip().lower()
    sources = args.get("sources", []) or []
    dest_dir = str(args.get("dest_dir") or ".")
    exclude_globs = args.get("exclude_globs", []) or []
    extract_files = args.get("extract_files", []) or []
    relative_to = str(args.get("relative_to") or "").strip()
    strip_components = int(args.get("strip_components", 0) or 0)
    target_file = str(args.get("target_file") or "").strip()
    max_bytes = int(args.get("max_bytes", 102400) or 102400)
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

    if action not in ("create", "extract", "list", "view"):
        return json.dumps(
            {
                "ok": False,
                "error": _(
                    "error.invalid_action", default="invalid action: {action}"
                ).format(action=action),
            },
            ensure_ascii=False,
        )

    if not zip_path:
        return json.dumps(
            {
                "ok": False,
                "error": _("error.zip_path_required", default="zip_path is required"),
            },
            ensure_ascii=False,
        )

    if is_path_dangerous(zip_path):
        return json.dumps(
            {
                "ok": False,
                "error": _(
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
                "error": _(
                    "error.zip_path_not_allowed",
                    default="zip_path not allowed: {error}",
                ).format(error=e),
            },
            ensure_ascii=False,
        )

    fmt = _detect_format(safe_zip_path, format_arg)

    if action == "list":
        return _run_list(safe_zip_path, fmt, _)
    elif action == "view":
        return _run_view(safe_zip_path, target_file, max_bytes, fmt, _)
    elif action == "create":
        return _run_create(safe_zip_path, sources, exclude_globs, relative_to, fmt, _)
    elif action == "extract":
        return _run_extract(
            safe_zip_path,
            dest_dir,
            extract_files,
            strip_components,
            overwrite,
            max_files,
            max_total_uncompressed_bytes,
            dry_run,
            fmt,
            _,
        )
    return json.dumps({"ok": False, "error": "unknown action"}, ensure_ascii=False)
