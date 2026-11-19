"""Small, fixed-contract worker used only inside a verified MXC container."""

from __future__ import annotations

import ast
import base64
import csv
import datetime
import difflib
import ssl
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
import fnmatch
import glob
import hashlib
import io
import json
import math
import mimetypes
import operator
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import threading
import time
import tomllib
import zipfile
from email import policy
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import Any
import xml.etree.ElementTree as ET

MAX_FRAME_BYTES = 1_100_000
MAX_RESULT_BYTES = 900_000
MAX_READ_BYTES = 128_000
MAX_TEXT_BYTES = 1_000_000
_ALLOWED = {
    "create_file",
    "file_exists",
    "read_file",
    "python_exec",
    "list_dir",
    "search_files",
    "file_grep",
    "file_hash",
    "wc",
    "rename_path",
    "delete_files",
    "replace_in_file",
    "diff_files",
    "archive_ops",
    "document_extract",
    "structured_data",
    "sqlite_query",
    "calculate",
    "python_ast",
    "parse_eml",
    "file_type",
    "image_ops",
    "qr_code",
    "binary_edit",
    "security_scan",
    "git_ops",
    "command_exec",
    "get_weather_wttr",
    "get_current_time",
    "geodesic_distance",
    "date_calc",
    "quantities",
    "zipcode_check",
    "reverse_geocode",
    "http_request",
    "apply_patch",
    "svg_to_image",
    "mermaid_render",
    "mmd_to_svg",
    "preprocess_image",
    "path_alias",
    "url_alias",
    "generate_prompt",
}
ROOT = Path.cwd().resolve()
MAX_SCAN_FILES = 5000
MAX_ANALYZE_BYTES = 16 * 1024 * 1024
MAX_TOTAL_SCAN_BYTES = 64 * 1024 * 1024


def _emit(value: Any) -> None:
    encoded = json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))
    if len(encoded.encode("utf-8", errors="replace")) > MAX_RESULT_BYTES:
        encoded = json.dumps(
            {"ok": False, "error": "tool result exceeds the bounded response limit"}
        )
    sys.stdout.write(encoded + "\n")
    sys.stdout.flush()


def _resolve_relative(value: Any) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("path must be a non-empty relative string")
    candidate = Path(value)
    if candidate.is_absolute() or candidate.drive or "\\" in value:
        raise ValueError("absolute paths and Windows path separators are not accepted")
    if ":" in value:
        raise ValueError("alternate data stream paths are not accepted")
    if any(part in {"..", ""} for part in candidate.parts):
        raise ValueError("path traversal is not accepted")
    target = (ROOT / candidate).resolve(strict=False)
    if target != ROOT and ROOT not in target.parents:
        raise ValueError("path escapes the isolated workspace")
    cursor = ROOT
    for part in candidate.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("symbolic links are not accepted")
    return target


def _read_file(args: dict[str, Any]) -> str:
    target = _resolve_relative(args.get("path"))
    if not target.is_file():
        return json.dumps({"error": "not a regular file"})
    start_line = max(1, int(args.get("start_line", 1) or 1))
    max_lines_value = args.get("max_lines")
    max_lines = None if max_lines_value is None else max(1, int(max_lines_value))
    max_bytes = min(
        MAX_READ_BYTES,
        max(1, int(args.get("max_bytes", MAX_READ_BYTES) or MAX_READ_BYTES)),
    )
    with target.open("rb") as stream:
        for _ in range(start_line - 1):
            while True:
                skipped = stream.readline(64 * 1024)
                if not skipped or skipped.endswith(b"\n"):
                    break
                # Keep skipping an unusually long line without buffering it all.
            if not skipped:
                return ""
        raw = stream.read(max_bytes)
    text = raw.decode(str(args.get("encoding") or "utf-8"), errors="replace")
    selected = text.splitlines(keepends=True)
    if max_lines is not None:
        selected = selected[:max_lines]
    return "".join(selected)


def _create_file(args: dict[str, Any]) -> str:
    target = _resolve_relative(args.get("filename"))
    content = args.get("content", "")
    if not isinstance(content, str):
        raise ValueError("content must be a string")
    if len(content.encode("utf-8", errors="replace")) > MAX_TEXT_BYTES:
        raise ValueError("content exceeds the 1 MB write limit")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not bool(args.get("overwrite", False)):
        raise FileExistsError("destination exists; set overwrite=true to replace it")
    if target.exists() and not target.is_file():
        raise ValueError("destination must be a regular file")
    if target.exists() and target.stat().st_size > MAX_TEXT_BYTES:
        raise ValueError("existing file exceeds the 1 MB backup limit")
    if target.exists():
        backup = target.with_name(target.name + ".org")
        index = 1
        while backup.exists() or backup.is_symlink():
            backup = target.with_name(target.name + f".org{index}")
            index += 1
        backup.write_bytes(target.read_bytes())
    encoding = str(args.get("encoding") or "utf-8")
    target.write_text(content, encoding=encoding)
    return f"Created {target.relative_to(ROOT).as_posix()}"


def _workspace_files(root: Path, recursive: bool = True) -> list[Path]:
    import os

    if not root.is_dir():
        return [root] if root.is_file() else []
    found: list[Path] = []
    if recursive:
        for current, dirs, files in os.walk(root, followlinks=False):
            current_path = Path(current)
            dirs[:] = [name for name in dirs if not (current_path / name).is_symlink()]
            for name in files:
                candidate = current_path / name
                if candidate.is_file() and not candidate.is_symlink():
                    found.append(candidate)
                    if len(found) >= MAX_SCAN_FILES:
                        return found
    else:
        found = [p for p in root.iterdir() if p.is_file() and not p.is_symlink()]
    return found


def _list_dir(args: dict[str, Any]) -> str:
    target = _resolve_relative(args.get("path") or ".")
    if not target.is_dir():
        raise NotADirectoryError("path is not a directory")
    entries = []
    truncated = False
    show_hidden = bool(args.get("show_hidden", False))
    for entry in target.iterdir():
        if entry.is_symlink() or (not show_hidden and entry.name.startswith(".")):
            continue
        if len(entries) >= MAX_SCAN_FILES:
            truncated = True
            break
        entries.append(entry)
    entries.sort(key=lambda p: (not p.is_dir(), p.name.lower()))
    limit = min(500, max(1, int(args.get("limit", 50) or 50)))
    page = max(1, int(args.get("page", 1) or 1))
    start = (page - 1) * limit
    selected = [
        entry for entry in entries[start : start + limit] if not entry.is_symlink()
    ]
    return json.dumps(
        {
            "path": "." if target == ROOT else target.relative_to(ROOT).as_posix(),
            "total": len(entries),
            "truncated": truncated,
            "page": page,
            "entries": [
                {
                    "name": p.name,
                    "type": "directory" if p.is_dir() else "file",
                    "size": p.stat().st_size if p.is_file() else None,
                }
                for p in selected
            ],
        },
        ensure_ascii=False,
    )


def _compile_bounded_regex(pattern: str, flags: int = 0) -> re.Pattern[str]:
    if len(pattern) > 500:
        raise ValueError("regular expression exceeds the 500-character limit")
    if re.search(r"\([^)]*(?:[*+]|\{\d+(?:,\d*)?\})[^)]*\)(?:[*+]|\{)", pattern):
        raise ValueError("nested repetition in regular expressions is not supported")
    if re.search(r"\([^)]*\|[^)]*\)(?:[*+]|\{)", pattern):
        raise ValueError("repeated alternation in regular expressions is not supported")
    repeat_count = pattern.count("*") + pattern.count("+")
    if repeat_count > 3:
        raise ValueError(
            "regular expressions with more than three repeats are not supported"
        )
    for quantifier in pattern.split("{")[1:]:
        bounds = quantifier.split("}", 1)[0].split(",")
        if bounds[0].isdigit() and any(part and not part.isdigit() for part in bounds):
            raise ValueError("invalid repetition bound")
        if bounds[0].isdigit() and (
            int(bounds[0]) > 10000
            or any(part.isdigit() and int(part) > 10000 for part in bounds[1:])
        ):
            raise ValueError("regular expression repetition is too large")
    return re.compile(pattern, flags)


def _search_files(args: dict[str, Any]) -> str:
    root = _resolve_relative(args.get("path") or ".")
    if not root.is_dir():
        raise NotADirectoryError("search path is not a directory")
    glob = str(args.get("glob") or "*")
    content_pattern = str(args.get("re_content") or "")
    if len(glob) > 256 or len(content_pattern) > 500:
        raise ValueError("search pattern is too long")
    expression = _compile_bounded_regex(content_pattern) if content_pattern else None
    matches = []
    scanned_bytes = 0
    scan_truncated = False
    for candidate in _workspace_files(root):
        relative = candidate.relative_to(ROOT).as_posix()
        if not (
            fnmatch.fnmatch(candidate.name, glob) or fnmatch.fnmatch(relative, glob)
        ):
            continue
        if expression is not None:
            size = candidate.stat().st_size
            if size > MAX_ANALYZE_BYTES:
                scan_truncated = True
                continue
            if scanned_bytes + size > MAX_TOTAL_SCAN_BYTES:
                scan_truncated = True
                break
            scanned_bytes += size
            found = False
            binary = False
            overlap = ""
            with candidate.open("rb") as stream:
                while chunk := stream.read(64 * 1024):
                    if b"\x00" in chunk:
                        binary = True
                        break
                    text_chunk = overlap + chunk.decode("utf-8", errors="replace")
                    if expression.search(text_chunk):
                        found = True
                    overlap = text_chunk[-500:]
            if binary or not found:
                continue
        matches.append(relative[:512])
    matches.sort()
    limit = min(500, max(1, int(args.get("limit", 50) or 50)))
    page = max(1, int(args.get("page", 1) or 1))
    start = (page - 1) * limit
    return json.dumps(
        {
            "total": len(matches),
            "page": page,
            "files": matches[start : start + limit],
            "scan_truncated": scan_truncated,
        },
        ensure_ascii=False,
    )


def _file_grep(args: dict[str, Any]) -> str:
    pattern = str(args.get("pattern") or "")
    if not pattern or len(pattern) > 500:
        raise ValueError("pattern must contain 1 to 500 characters")
    if bool(args.get("literal", False)):
        pattern = re.escape(pattern)
    flags = re.IGNORECASE if bool(args.get("ignore_case", True)) else 0
    expression = _compile_bounded_regex(pattern, flags)
    root = _resolve_relative(args.get("path") or ".")
    if not root.is_dir():
        raise NotADirectoryError("search path is not a directory")
    glob = str(args.get("glob") or "*")
    if len(glob) > 256:
        raise ValueError("glob pattern is too long")
    context = min(5, max(0, int(args.get("context_lines", 0) or 0)))
    limit = min(100, max(1, int(args.get("limit", 100) or 100)))
    results = []
    scanned_bytes = 0
    scan_truncated = False
    for candidate in _workspace_files(root, recursive=bool(args.get("recur", True))):
        relative = candidate.relative_to(ROOT).as_posix()
        if not (
            fnmatch.fnmatch(candidate.name, glob) or fnmatch.fnmatch(relative, glob)
        ):
            continue
        size = candidate.stat().st_size
        if size > MAX_ANALYZE_BYTES:
            scan_truncated = True
            continue
        if scanned_bytes + size > MAX_TOTAL_SCAN_BYTES:
            scan_truncated = True
            break
        scanned_bytes += size
        with candidate.open("rb") as stream:
            iterator = iter(enumerate(stream, 1))
            previous = deque(maxlen=context)
            pending = deque()
            while True:
                if pending:
                    line_number, raw_line = pending.popleft()
                else:
                    try:
                        line_number, raw_line = next(iterator)
                    except StopIteration:
                        break
                sample = raw_line[:8192].decode("utf-8", errors="replace").rstrip()
                if 0 not in raw_line[:8192] and expression.search(sample):
                    following = []
                    for _ in range(context):
                        try:
                            pair = next(iterator)
                        except StopIteration:
                            break
                        pending.append(pair)
                        following.append(
                            pair[1][:512].decode("utf-8", errors="replace").rstrip()
                        )
                    results.append(
                        {
                            "file": relative[:512],
                            "line": line_number,
                            "text": sample[:2048],
                            "line_truncated": len(raw_line) > 8192,
                            "context": list(previous)
                            + ([sample[:512]] + following if context else []),
                        }
                    )
                    if len(results) >= limit:
                        return json.dumps(
                            {"matches": results, "truncated": True}, ensure_ascii=False
                        )
                if context:
                    previous.append(sample[:512])
    return json.dumps(
        {"matches": results, "truncated": scan_truncated}, ensure_ascii=False
    )


def _file_hash(args: dict[str, Any]) -> str:
    algorithm = str(args.get("algo") or "sha256").lower()
    if algorithm not in {"sha256", "sha1", "md5"}:
        raise ValueError("unsupported hash algorithm")
    paths = args.get("paths")
    if not isinstance(paths, list) or len(paths) > 100:
        raise ValueError("paths must be a list containing at most 100 entries")
    result = []
    total_bytes = 0
    for value in paths:
        target = _resolve_relative(value)
        if not target.is_file() or target.stat().st_size > MAX_ANALYZE_BYTES:
            raise ValueError("each path must be a regular file no larger than 16 MiB")
        total_bytes += target.stat().st_size
        if total_bytes > MAX_TOTAL_SCAN_BYTES:
            raise ValueError("combined hash input exceeds 64 MiB")
        digest = hashlib.new(algorithm)
        with target.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        result.append(
            {"path": target.relative_to(ROOT).as_posix(), "hash": digest.hexdigest()}
        )
    return json.dumps({"algorithm": algorithm, "files": result}, ensure_ascii=False)


def _wc(args: dict[str, Any]) -> str:
    paths = args.get("paths")
    if not isinstance(paths, list) or len(paths) > 100:
        raise ValueError("paths must be a list containing at most 100 entries")
    result = []
    total_bytes = 0
    for value in paths:
        target = _resolve_relative(value)
        size = target.stat().st_size if target.is_file() else -1
        if size < 0 or size > MAX_ANALYZE_BYTES:
            raise ValueError("each path must be a regular file no larger than 16 MiB")
        total_bytes += size
        if total_bytes > MAX_TOTAL_SCAN_BYTES:
            raise ValueError("combined count input exceeds 64 MiB")
        raw = target.read_bytes()
        text = raw.decode("utf-8", errors="replace")
        line_count = sum(1 for _ in re.finditer(r"\r\n|\r|\n", text))
        if text and not text.endswith(("\r", "\n")):
            line_count += 1
        word_count = sum(1 for _ in re.finditer(r"\S+", text))
        result.append(
            {
                "path": target.relative_to(ROOT).as_posix(),
                "lines": line_count,
                "words": word_count,
                "bytes": len(raw),
                "characters": len(text),
            }
        )
    return json.dumps({"files": result}, ensure_ascii=False)


def _rename_path(args: dict[str, Any]) -> str:
    source, destination = _resolve_relative(args.get("src")), _resolve_relative(
        args.get("dst")
    )
    if not source.exists():
        raise FileNotFoundError("source does not exist")
    if destination.exists():
        if not bool(args.get("overwrite", False)):
            raise FileExistsError(
                "destination exists; set overwrite=true to replace it"
            )
        if destination.is_dir():
            raise ValueError("overwriting directories is not supported")
        destination.unlink()
    if not destination.parent.exists():
        if not bool(args.get("mkdirs", False)):
            raise FileNotFoundError("destination parent does not exist")
        destination.parent.mkdir(parents=True, exist_ok=True)
    source.rename(destination)
    return f"Moved {source.relative_to(ROOT).as_posix()} to {destination.relative_to(ROOT).as_posix()}"


def _delete_files(args: dict[str, Any]) -> str:
    if not bool(args.get("confirmed", False)):
        raise PermissionError("confirmed=true is required for deletion")
    raw_items = args.get("filenames")
    if raw_items is None:
        raw_items = args.get("filename")
    if isinstance(raw_items, str):
        items = [raw_items]
    elif isinstance(raw_items, list) and all(
        isinstance(item, str) for item in raw_items
    ):
        items = raw_items
    else:
        raise ValueError("filename(s) must be a string or a list of strings")
    if not items:
        raise ValueError("at least one filename is required")

    matches: set[Path] = set()
    missing: list[str] = []
    for item in items:
        if not item.strip():
            continue
        # Validate relative-path syntax before expanding a glob.
        _resolve_relative(item)
        if any(mark in item for mark in ("*", "?", "[")):
            found = glob.glob(str(ROOT / item), recursive=True)
            candidates = [Path(path) for path in found]
        else:
            candidates = [ROOT / item]
        valid = []
        for candidate in candidates:
            try:
                target = _resolve_relative(candidate.relative_to(ROOT).as_posix())
            except (ValueError, OSError):
                continue
            if target.exists():
                valid.append(target)
        if not valid:
            missing.append(item)
        matches.update(valid)

    if missing and not bool(args.get("skip", False)):
        raise FileNotFoundError(f"no paths matched: {missing[0]}")
    ordered = sorted(matches, key=lambda path: path.as_posix())
    for target in ordered:
        if target == ROOT:
            raise PermissionError("the workspace root cannot be deleted")

    delete_targets: list[Path] = []
    selected_directories: set[Path] = set()
    for target in sorted(ordered, key=lambda path: (len(path.parts), path.as_posix())):
        if any(parent in selected_directories for parent in target.parents):
            continue
        delete_targets.append(target)
        if target.is_dir():
            selected_directories.add(target)

    for target in delete_targets:
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
    return json.dumps(
        {"deleted": [p.relative_to(ROOT).as_posix() for p in delete_targets]}
    )


def _replace_in_file(args: dict[str, Any]) -> str:
    target = _resolve_relative(args.get("path"))
    if not target.is_file() or target.stat().st_size > MAX_TEXT_BYTES:
        raise ValueError("target must be a regular file no larger than 1 MB")
    pattern, replacement = args.get("pattern"), args.get("replacement")
    if not isinstance(pattern, str) or not pattern:
        raise ValueError("pattern must be a non-empty string")
    if not isinstance(replacement, str):
        raise ValueError("replacement must be a string")
    text = target.read_text(encoding="utf-8")
    occurrence = max(0, int(args.get("occurrence", 0) or 0))
    count = (
        text.count(pattern) if occurrence == 0 else min(occurrence, text.count(pattern))
    )
    updated = text.replace(pattern, replacement, -1 if occurrence == 0 else occurrence)
    if len(updated.encode("utf-8")) > MAX_TEXT_BYTES:
        raise ValueError("updated file exceeds the 1 MB workspace write limit")
    if updated != text:
        backup = target.with_name(target.name + ".org")
        index = 1
        while backup.exists() or backup.is_symlink():
            backup = target.with_name(target.name + f".org{index}")
            index += 1
        backup.write_bytes(target.read_bytes())
        target.write_text(updated, encoding="utf-8")
    return json.dumps(
        {"path": target.relative_to(ROOT).as_posix(), "replacements": count}
    )


def _diff_files(args: dict[str, Any]) -> str:
    left, right = _resolve_relative(args.get("path1")), _resolve_relative(
        args.get("path2")
    )
    for path in (left, right):
        if not path.is_file() or path.stat().st_size > MAX_TEXT_BYTES:
            raise ValueError("both paths must be regular files no larger than 1 MB")
    context = min(20, max(0, int(args.get("context_lines", 3) or 0)))
    diff = difflib.unified_diff(
        left.read_text(encoding="utf-8").splitlines(keepends=True),
        right.read_text(encoding="utf-8").splitlines(keepends=True),
        fromfile=left.relative_to(ROOT).as_posix(),
        tofile=right.relative_to(ROOT).as_posix(),
        n=context,
    )
    return "".join(diff)[:MAX_READ_BYTES]


def _bounded_workspace_file(value: Any, maximum: int = MAX_ANALYZE_BYTES) -> Path:
    target = _resolve_relative(value)
    if not target.is_file() or target.stat().st_size > maximum:
        raise ValueError(
            f"expected a regular workspace file no larger than {maximum} bytes"
        )
    return target


def _safe_zip(path: Path) -> zipfile.ZipFile:
    if path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("ZIP archive exceeds the compressed-size limit")
    archive = zipfile.ZipFile(path, "r")
    infos = archive.infolist()
    if len(infos) > 5000 or sum(i.file_size for i in infos) > 50 * 1024 * 1024:
        archive.close()
        raise ValueError("ZIP archive exceeds member or uncompressed-size limits")
    for info in infos:
        mode = (info.external_attr >> 16) & 0xFFFF
        if stat.S_ISLNK(mode) or info.file_size > 16 * 1024 * 1024:
            archive.close()
            raise ValueError("ZIP symlinks and oversized members are not accepted")
        name = info.filename.rstrip("/")
        member = PurePosixPath(name)
        if name and (
            member.is_absolute()
            or ".." in member.parts
            or "\\" in name
            or any(":" in part for part in member.parts)
        ):
            archive.close()
            raise ValueError("unsafe ZIP member path")
    return archive


def _archive_ops(args: dict[str, Any]) -> str:
    action, archive_path = str(args.get("action") or "list"), _resolve_relative(
        args.get("zip_path")
    )
    if action == "create":
        sources = args.get("sources")
        if not isinstance(sources, list) or not sources or len(sources) > 500:
            raise ValueError("sources must contain 1 to 500 workspace paths")
        base = _resolve_relative(args.get("relative_to") or ".")
        files = []
        for item in sources:
            source = _resolve_relative(item)
            candidates = [source] if source.is_file() else _workspace_files(source)
            for file in candidates:
                if not file.is_file() or file.is_symlink():
                    continue
                rel = (
                    file.relative_to(base)
                    if file == base or base in file.parents
                    else Path(file.name)
                )
                files.append((file, rel.as_posix()))
                if len(files) > 500 or file.stat().st_size > 16 * 1024 * 1024:
                    raise ValueError(
                        "ZIP creation exceeds file-count or member-size limit"
                    )
        if not files or sum(p.stat().st_size for p, _ in files) > 50 * 1024 * 1024:
            raise ValueError("ZIP creation is empty or exceeds 50 MiB")
        if len({name.casefold() for _, name in files}) != len(files):
            raise ValueError("duplicate ZIP member names are not allowed")
        if archive_path.exists() and not args.get("overwrite", False):
            raise FileExistsError("destination ZIP exists; set overwrite=true")
        if any(p == archive_path for p, _ in files):
            raise ValueError("output ZIP cannot also be a source file")
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(
            archive_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6
        ) as zf:
            for file, name in files:
                zf.write(file, name)
        return json.dumps(
            {"created": archive_path.relative_to(ROOT).as_posix(), "files": len(files)}
        )
    if action not in {"list", "view", "extract"} or not archive_path.is_file():
        raise ValueError("action must be list/view/create/extract and ZIP must exist")
    with _safe_zip(archive_path) as zf:
        infos = zf.infolist()
        if action == "list":
            return json.dumps(
                {
                    "total": len(infos),
                    "entries": [
                        {
                            "name": i.filename[:512],
                            "size": i.file_size,
                            "compressed_size": i.compress_size,
                            "directory": i.is_dir(),
                        }
                        for i in infos[:500]
                    ],
                },
                ensure_ascii=False,
            )
        if action == "view":
            info = zf.getinfo(str(args.get("target_file") or ""))
            if info.is_dir() or info.file_size > MAX_READ_BYTES:
                raise ValueError("member is a directory or exceeds view limit")
            return zf.read(info).decode(
                str(args.get("encoding") or "utf-8"), errors="replace"
            )
        patterns = args.get("extract_files") or ["*"]
        if not isinstance(patterns, list) or len(patterns) > 100:
            raise ValueError("extract_files must contain at most 100 patterns")
        dest = _resolve_relative(args.get("dest_dir") or ".")
        strip = min(20, max(0, int(args.get("strip_components", 0) or 0)))
        selected = []
        total = 0
        for info in infos:
            if info.is_dir() or not any(
                fnmatch.fnmatch(info.filename, str(p)) for p in patterns
            ):
                continue
            parts = PurePosixPath(info.filename).parts[strip:]
            if not parts:
                continue
            selected.append((info, parts))
            total += info.file_size
        max_files = min(500, max(1, int(args.get("max_files", 500) or 500)))
        max_bytes = min(
            50 * 1024 * 1024,
            max(
                1,
                int(
                    args.get("max_total_uncompressed_bytes", 50 * 1024 * 1024)
                    or 50 * 1024 * 1024
                ),
            ),
        )
        if len(selected) > max_files or total > max_bytes:
            raise ValueError("selected files exceed extraction limits")
        targets = [
            (i, _resolve_relative((dest / Path(*parts)).relative_to(ROOT).as_posix()))
            for i, parts in selected
        ]
        if len({target for _, target in targets}) != len(targets):
            raise ValueError("duplicate extraction destinations are not allowed")
        if args.get("dry_run", False):
            return json.dumps(
                {
                    "would_extract": [
                        t.relative_to(ROOT).as_posix() for _, t in targets
                    ],
                    "total_bytes": total,
                }
            )
        if not args.get("overwrite", False) and any(t.exists() for _, t in targets):
            raise FileExistsError("an extraction destination already exists")
        for info, target in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst, 64 * 1024)
        return json.dumps({"extracted": len(targets), "total_bytes": total})


def _parse_safe_xml(raw: bytes):
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError("document XML parts are limited to 4 MiB")
    upper = raw.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ValueError("DTD/entity declarations are not accepted in document XML")
    return ET.fromstring(raw)


def _document_extract(args: dict[str, Any]) -> str:
    target = _bounded_workspace_file(args.get("path"), 64 * 1024 * 1024)
    ext = target.suffix.lower()
    maximum = min(
        MAX_READ_BYTES,
        max(1000, int(args.get("max_chars", MAX_READ_BYTES) or MAX_READ_BYTES)),
    )
    parts = []
    captured_chars = 0
    truncated = False

    def add_text(value: Any) -> None:
        nonlocal captured_chars, truncated
        value = str(value)
        remaining = maximum - captured_chars
        if len(value) > remaining:
            truncated = True
            value = value[: max(0, remaining)]
        if value:
            parts.append(value)
            captured_chars += len(value)

    if ext in {".docx", ".pptx", ".xlsx", ".odt"}:
        with _safe_zip(target) as zf:
            names = set(zf.namelist())
            if ext == ".docx":
                selected = ["word/document.xml"]
            elif ext == ".odt":
                selected = ["content.xml"]
            elif ext == ".pptx":
                selected = sorted(
                    (n for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
                    key=lambda n: int(re.search(r"slide(\d+)", n).group(1)),
                )
            else:
                selected = sorted(
                    n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)
                )
                shared = []
                if "xl/sharedStrings.xml" in names:
                    sr = _parse_safe_xml(zf.read("xl/sharedStrings.xml"))
                    shared = [
                        "".join(t.text or "" for t in si.iter() if t.tag.endswith("}t"))
                        for si in sr
                    ]
                for sheet in selected:
                    root = _parse_safe_xml(zf.read(sheet))
                    for row in root.iter():
                        if row.tag.endswith("}row"):
                            cells = []
                            for cell in row:
                                if cell.tag.endswith("}c"):
                                    v = next(
                                        (
                                            c.text or ""
                                            for c in cell
                                            if c.tag.endswith("}v")
                                        ),
                                        "",
                                    )
                                    if (
                                        cell.attrib.get("t") == "s"
                                        and v.isdigit()
                                        and int(v) < len(shared)
                                    ):
                                        v = shared[int(v)]
                                    cells.append(v)
                            add_text("\t".join(cells) + "\n")
                selected = []
            for name in selected:
                if name not in names:
                    continue
                root = _parse_safe_xml(zf.read(name))
                if ext == ".pptx":
                    add_text("\n[" + name.rsplit("/", 1)[-1] + "]\n")
                for node in root.iter():
                    if node.tag.endswith("}t") and node.text:
                        add_text(node.text)
                    if node.tag.endswith("}p"):
                        add_text("\n")
    elif ext == ".pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(target, strict=False)
            if reader.is_encrypted:
                raise ValueError("encrypted PDF files are not supported")
            if len(reader.pages) > 200:
                raise ValueError("PDF extraction is limited to 200 pages")
            for page in reader.pages:
                add_text((page.extract_text() or "") + "\n")
        except ImportError:
            try:
                import fitz
            except ImportError as exc:
                raise RuntimeError(
                    "PDF extraction requires pypdf or PyMuPDF in the sandbox"
                ) from exc
            with fitz.open(target) as doc:
                if len(doc) > 200:
                    raise ValueError("PDF extraction is limited to 200 pages")
                for page in doc:
                    add_text(page.get_text() + "\n")
    elif ext in {".eml", ".rtf"}:
        if ext == ".eml":
            msg = BytesParser(policy=policy.default).parsebytes(target.read_bytes())
            parts.extend(
                [
                    f"From: {msg.get('From', '')}\n",
                    f"To: {msg.get('To', '')}\n",
                    f"Subject: {msg.get('Subject', '')}\n\n",
                ]
            )
            for p in msg.walk():
                if p.get_content_type() == "text/plain" and not p.is_multipart():
                    try:
                        add_text(str(p.get_content()))
                    except Exception:
                        pass
        else:
            text = target.read_bytes().decode("latin-1", errors="replace")
            add_text(
                re.sub(
                    r"\\[a-zA-Z]+-?\d* ?|[{}]",
                    "",
                    re.sub(r"\\'[0-9a-fA-F]{2}", " ", text),
                )
            )
    else:
        raise ValueError("supported formats: PDF, DOCX, PPTX, XLSX, ODT, EML, RTF")
    text = "".join(parts)
    return json.dumps(
        {
            "path": target.relative_to(ROOT).as_posix(),
            "format": ext[1:],
            "text": text[:maximum],
            "truncated": truncated,
        },
        ensure_ascii=False,
    )


def _bounded_value(
    value: Any,
    *,
    budget: list[int] | None = None,
    seen: frozenset[int] = frozenset(),
    depth: int = 0,
) -> Any:
    if budget is None:
        budget = [200]
    budget[0] -= 1
    if budget[0] < 0:
        return "[truncated]"
    if depth > 12:
        return "[depth limit]"
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, str):
        return value[:512]
    if isinstance(value, (list, tuple)):
        if id(value) in seen:
            return "[recursive reference]"
        nested_seen = seen | {id(value)}
        return [
            _bounded_value(item, budget=budget, seen=nested_seen, depth=depth + 1)
            for item in value[:50]
        ]
    if isinstance(value, dict):
        if id(value) in seen:
            return "[recursive reference]"
        nested_seen = seen | {id(value)}
        result = {}
        for key, item in list(value.items())[:50]:
            result[str(key)[:256]] = _bounded_value(
                item, budget=budget, seen=nested_seen, depth=depth + 1
            )
            if budget[0] <= 0:
                break
        return result
    return str(value)[:512]


def _structured_data(args: dict[str, Any]) -> str:
    target = _bounded_workspace_file(args.get("path"), 4 * 1024 * 1024)
    raw = target.read_bytes()
    if b"\x00" in raw:
        raise ValueError("binary data is not supported")
    text = raw.decode(str(args.get("encoding") or "utf-8-sig"), errors="strict")
    fmt, mode = str(args.get("format") or target.suffix.lstrip(".")).lower(), str(
        args.get("mode") or "summary"
    )
    if fmt == "json":
        value = json.loads(text)
        pointer = str(args.get("pointer") or "")
        if pointer:
            if not pointer.startswith("/"):
                raise ValueError("pointer must be an RFC 6901 JSON pointer")
            for key in pointer[1:].split("/"):
                key = key.replace("~1", "/").replace("~0", "~")
                value = value[int(key)] if isinstance(value, list) else value[key]
        if mode == "summary":
            info = {"type": type(value).__name__}
            if isinstance(value, dict):
                info["keys"] = [str(key)[:256] for key in list(value)[:100]]
            if isinstance(value, list):
                info.update(length=len(value), preview=_bounded_value(value[:10]))
            if not isinstance(value, (dict, list)):
                info["value"] = _bounded_value(value)
            return json.dumps(info, ensure_ascii=False, default=str)
        return json.dumps(
            _bounded_value(value), ensure_ascii=False, indent=2, default=str
        )
    if fmt == "csv":
        start = max(0, int(args.get("start_row", 0) or 0))
        count = min(50, max(1, int(args.get("max_rows", 100) or 100)))
        selected = []
        truncated = False
        rows_total = 0
        csv.field_size_limit(MAX_ANALYZE_BYTES)
        for index, row in enumerate(csv.reader(io.StringIO(text, newline=""))):
            rows_total = index + 1
            if start <= index < start + count:
                if len(row) > 20 or any(len(cell) > 128 for cell in row):
                    truncated = True
                selected.append([cell[:128] for cell in row[:20]])
        return json.dumps(
            {
                "rows_total": rows_total,
                "start_row": start,
                "rows": selected,
                "truncated": truncated or start + len(selected) < rows_total,
            },
            ensure_ascii=False,
        )
    if fmt == "toml":
        value = tomllib.loads(text)
        if mode == "summary" and isinstance(value, dict):
            value = {"keys": [str(key)[:256] for key in list(value)[:100]]}
        return json.dumps(_bounded_value(value), ensure_ascii=False, default=str)
    if fmt in {"yaml", "yml"}:
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError("YAML support requires PyYAML in the sandbox") from exc
        value = yaml.safe_load(text)
        if mode == "summary" and isinstance(value, dict):
            value = {"keys": [str(key)[:256] for key in list(value)[:100]]}
        elif mode == "summary" and isinstance(value, list):
            value = {"length": len(value), "preview": _bounded_value(value[:10])}
        return json.dumps(_bounded_value(value), ensure_ascii=False, default=str)
    if fmt == "xml":
        if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
            raise ValueError("DTD/entity declarations are not allowed")
        root = ET.fromstring(text)
        return json.dumps(
            {
                "root": root.tag[:256],
                "attributes": _bounded_value(root.attrib),
                "children": [
                    {
                        "tag": c.tag[:256],
                        "attributes": _bounded_value(c.attrib),
                        "text": (c.text or "")[:500],
                    }
                    for c in list(root)[:100]
                ],
                "children_total": len(root),
            },
            ensure_ascii=False,
        )
    raise ValueError("format must be json, csv, xml, or toml")


def _sqlite_query(args: dict[str, Any]) -> str:
    path = _bounded_workspace_file(args.get("path"), 64 * 1024 * 1024)
    query = args.get("query")
    if not isinstance(query, str) or not query.strip() or len(query) > 10000:
        raise ValueError("query must be 1 to 10000 characters")
    lowered = query.lstrip().lower()
    if not lowered.startswith(
        (
            "select",
            "with",
            "explain",
            "pragma table_info",
            "pragma table_list",
            "pragma quick_check",
        )
    ):
        raise PermissionError(
            "only read-only SELECT/CTE/EXPLAIN and safe inspection PRAGMAs are allowed"
        )
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=2)
    try:
        connection.execute("PRAGMA query_only=ON")
        start = time.monotonic()
        connection.set_progress_handler(
            lambda: int(time.monotonic() - start > 1.0), 1000
        )
        cursor = connection.execute(query)
        all_columns = [column[0] for column in cursor.description or ()]
        columns = all_columns[:50]
        limit = min(20, max(1, int(args.get("limit", 20) or 20)))
        rows = []
        truncated = len(all_columns) > 50
        for index in range(limit + 1):
            row = cursor.fetchone()
            if row is None:
                break
            if index == limit:
                truncated = True
                break
            rows.append([_bounded_value(value) for value in row[:50]])
        return json.dumps(
            {
                "columns": [str(column)[:256] for column in columns],
                "rows": rows,
                "truncated": truncated,
            },
            ensure_ascii=False,
            default=str,
        )
    finally:
        connection.close()


_CALC_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_CALC_FUNCS = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "floor": math.floor,
    "ceil": math.ceil,
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
}


def _calculate(args: dict[str, Any]) -> str:
    expression = args.get("expression")
    if (
        not isinstance(expression, str)
        or not expression.strip()
        or len(expression) > 500
    ):
        raise ValueError("expression must be 1 to 500 characters")
    tree = ast.parse(expression, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > 100:
        raise ValueError("expression is too complex")

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
            if abs(node.value) > 1e100:
                raise ValueError("number is out of range")
            return node.value
        if isinstance(node, ast.Name) and node.id in {"pi", "e"}:
            return math.pi if node.id == "pi" else math.e
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        if isinstance(node, ast.BinOp) and type(node.op) in _CALC_OPS:
            a, b = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow) and abs(b) > 100:
                raise ValueError("exponent is out of range")
            result = _CALC_OPS[type(node.op)](a, b)
            if not math.isfinite(result) or abs(result) > 1e100:
                raise ValueError("result is out of range")
            return result
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _CALC_FUNCS
            and not node.keywords
        ):
            vals = [visit(arg) for arg in node.args]
            if len(vals) > 20:
                raise ValueError("too many arguments")
            result = _CALC_FUNCS[node.func.id](*vals)
            if not math.isfinite(result) or abs(result) > 1e100:
                raise ValueError("result is out of range")
            return result
        raise ValueError("unsupported arithmetic syntax")

    return json.dumps(
        {"expression": expression, "result": visit(tree.body)}, allow_nan=False
    )


def _python_ast(args: dict[str, Any]) -> str:
    path = _bounded_workspace_file(args.get("path"), MAX_TEXT_BYTES)
    tree = ast.parse(
        path.read_text(encoding=str(args.get("encoding") or "utf-8"), errors="replace"),
        filename=path.name,
    )
    definitions, imports = [], []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definitions.append(
                {
                    "kind": type(node).__name__,
                    "name": node.name,
                    "line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno),
                }
            )
        elif isinstance(node, ast.Import):
            imports.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append("." * node.level + (node.module or ""))
    definitions.sort(key=lambda d: (d["line"], d["name"]))
    return json.dumps(
        {
            "path": path.relative_to(ROOT).as_posix(),
            "definitions": definitions[:1000],
            "imports": sorted(set(imports))[:500],
        },
        ensure_ascii=False,
    )


def _parse_eml(args: dict[str, Any]) -> str:
    path = _bounded_workspace_file(args.get("path"))
    msg = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    maximum = min(MAX_READ_BYTES, max(0, int(args.get("max_body_length", 5000) or 0)))
    body = []
    for part in msg.walk():
        if part.get_content_type() == "text/plain" and not part.is_multipart():
            try:
                body.append(str(part.get_content()))
            except Exception:
                pass
    return json.dumps(
        {
            "from": str(msg.get("From", "")),
            "to": str(msg.get("To", "")),
            "subject": str(msg.get("Subject", "")),
            "date": str(msg.get("Date", "")),
            "body": "\n".join(body)[:maximum],
        },
        ensure_ascii=False,
    )


def _file_type(args: dict[str, Any]) -> str:
    path = _bounded_workspace_file(args.get("path"), 128 * 1024 * 1024)
    with path.open("rb") as stream:
        sample = stream.read(4096)
    signatures = [
        (b"%PDF-", "application/pdf", "PDF"),
        (b"\x89PNG\r\n\x1a\n", "image/png", "PNG image"),
        (b"\xff\xd8\xff", "image/jpeg", "JPEG image"),
        (b"GIF87a", "image/gif", "GIF image"),
        (b"GIF89a", "image/gif", "GIF image"),
        (b"PK\x03\x04", "application/zip", "ZIP archive"),
        (b"SQLite format 3\x00", "application/vnd.sqlite3", "SQLite database"),
        (b"\x1f\x8b", "application/gzip", "GZIP archive"),
    ]
    mime, desc = "application/octet-stream", "binary data"
    for sig, typ, label in signatures:
        if sample.startswith(sig):
            mime, desc = typ, label
            break
    else:
        try:
            sample.decode("utf-8")
            mime, desc = "text/plain", "UTF-8 text"
        except UnicodeDecodeError:
            mime = mimetypes.guess_type(path.name)[0] or mime
            desc = "inferred from extension"
    return json.dumps(
        {
            "path": path.relative_to(ROOT).as_posix(),
            "mime": mime,
            "description": desc,
            "extension_mime": mimetypes.guess_type(path.name)[0],
            "size": path.stat().st_size,
        }
    )


def _image_ops(args: dict[str, Any]) -> str:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("image operations require Pillow in the sandbox") from exc
    source = _bounded_workspace_file(args.get("path"), 32 * 1024 * 1024)
    action = str(args.get("action") or "info")
    with Image.open(source) as image:
        width, height = image.size
        if width <= 0 or height <= 0 or width * height > 40_000_000:
            raise ValueError("image exceeds the 40 megapixel limit")
        if action == "info":
            return json.dumps(
                {
                    "path": source.relative_to(ROOT).as_posix(),
                    "format": image.format,
                    "width": width,
                    "height": height,
                    "mode": image.mode,
                }
            )
        if action == "grayscale":
            result = image.convert("L")
        elif action == "resize":
            new_width = int(args.get("width", 0) or 0)
            new_height = int(args.get("height", 0) or 0)
            if (
                new_width < 0
                or new_height < 0
                or new_width > 10000
                or new_height > 10000
            ):
                raise ValueError("resize dimensions must be between 1 and 10000")
            if not new_width and not new_height:
                raise ValueError("resize requires width or height")
            if not new_width:
                new_width = max(1, round(width * new_height / height))
            if not new_height:
                new_height = max(1, round(height * new_width / width))
            if new_width * new_height > 40_000_000:
                raise ValueError("resized image exceeds 40 megapixels")
            result = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        elif action == "rotate":
            angle = float(args.get("angle", 0))
            if not math.isfinite(angle) or abs(angle) > 360:
                raise ValueError("rotation angle must be between -360 and 360 degrees")
            result = image.rotate(angle, expand=True)
            if result.width * result.height > 40_000_000:
                raise ValueError("rotated image exceeds 40 megapixels")
        else:
            raise ValueError("image action must be info, resize, grayscale, or rotate")
        output = _resolve_relative(args.get("output_path"))
        if output == source:
            raise ValueError("image output must differ from its input path")
        if output.exists() and not args.get("overwrite", False):
            raise FileExistsError("output exists; set overwrite=true to replace it")
        extension = output.suffix.lower()
        formats = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}
        if extension not in formats:
            raise ValueError("image output extension must be PNG, JPEG, or WebP")
        if formats[extension] == "JPEG" and result.mode not in {"RGB", "L"}:
            result = _flatten_for_jpeg(result)
        output.parent.mkdir(parents=True, exist_ok=True)
        result.save(output, format=formats[extension])
    if output.stat().st_size > 32 * 1024 * 1024:
        output.unlink()
        raise ValueError("image output exceeds 32 MiB")
    return json.dumps(
        {
            "saved": output.relative_to(ROOT).as_posix(),
            "width": result.width,
            "height": result.height,
        }
    )


def _qr_code(args: dict[str, Any]) -> str:
    text = args.get("text")
    if not isinstance(text, str) or not text or len(text.encode("utf-8")) > 2000:
        raise ValueError("QR text must contain 1 to 2000 UTF-8 bytes")
    output = _resolve_relative(args.get("output_path"))
    if output.suffix.lower() != ".png":
        raise ValueError("QR output path must end in .png")
    if output.exists() and not args.get("overwrite", False):
        raise FileExistsError("output exists; set overwrite=true to replace it")
    if _ensure_package("qrcode") is None:
        raise RuntimeError(
            "QR generation requires qrcode and Pillow in the sandbox; "
            "automatic installation failed"
        )
    try:
        import qrcode
        from qrcode.constants import (
            ERROR_CORRECT_H,
            ERROR_CORRECT_L,
            ERROR_CORRECT_M,
            ERROR_CORRECT_Q,
        )
    except ImportError as exc:
        raise RuntimeError(
            "QR generation requires qrcode and Pillow in the sandbox"
        ) from exc
    levels = {
        "L": ERROR_CORRECT_L,
        "M": ERROR_CORRECT_M,
        "Q": ERROR_CORRECT_Q,
        "H": ERROR_CORRECT_H,
    }
    level = str(args.get("ecc") or "M").upper()
    if level not in levels:
        raise ValueError("ecc must be L, M, Q, or H")
    box = min(20, max(1, int(args.get("box_size", 10) or 10)))
    border = min(10, max(0, int(args.get("border", 4) or 0)))
    qr = qrcode.QRCode(error_correction=levels[level], box_size=box, border=border)
    qr.add_data(text)
    qr.make(fit=True)
    image = qr.make_image(
        fill_color=str(args.get("fill_color") or "black"),
        back_color=str(args.get("back_color") or "white"),
    )
    if image.width * image.height > 40_000_000:
        raise ValueError("generated QR image exceeds 40 megapixels")
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG")
    if output.stat().st_size > 32 * 1024 * 1024:
        output.unlink()
        raise ValueError("generated QR image exceeds 32 MiB")
    return json.dumps(
        {
            "saved": output.relative_to(ROOT).as_posix(),
            "width": image.width,
            "height": image.height,
        }
    )


def _binary_edit(args: dict[str, Any]) -> str:
    target = _resolve_relative(args.get("path"))
    mode = str(args.get("mode") or "replace")
    if mode not in {"write", "replace", "splice"}:
        raise ValueError("mode must be write, replace, or splice")
    if target.exists():
        if not target.is_file() or target.stat().st_size > 64 * 1024 * 1024:
            raise ValueError("target must be a regular file no larger than 64 MiB")
        original = target.read_bytes()
    else:
        if mode != "write":
            raise FileNotFoundError("replace/splice target does not exist")
        original = b""
    try:
        data = bytes.fromhex(str(args.get("data_hex") or ""))
        search = bytes.fromhex(str(args.get("search_hex") or ""))
        replacement = bytes.fromhex(str(args.get("replace_hex") or ""))
    except ValueError as exc:
        raise ValueError("binary data must be valid hexadecimal") from exc
    if max(len(data), len(search), len(replacement)) > 1_000_000:
        raise ValueError("individual binary payloads are limited to 1 MiB")
    offset = max(0, int(args.get("offset", 0) or 0))
    if mode == "write":
        if offset > len(original):
            raise ValueError("write offset cannot create a sparse file")
        updated = original[:offset] + data + original[offset + len(data) :]
        changed = len(data)
    elif mode == "replace":
        if not search:
            raise ValueError("replace requires non-empty search_hex")
        if len(replacement) != len(search):
            raise ValueError(
                "binary replace must preserve byte length; use splice to resize"
            )
        occurrence = max(0, int(args.get("occurrence", 1) or 0))
        found = original.count(search)
        if occurrence == 0:
            updated = original.replace(search, replacement)
            changed = found
        else:
            if found < occurrence:
                raise ValueError("requested occurrence was not found")
            start = -1
            cursor = 0
            for _ in range(occurrence):
                start = original.find(search, cursor)
                cursor = start + len(search)
            updated = original[:start] + replacement + original[start + len(search) :]
            changed = 1
    else:
        if offset > len(original):
            raise ValueError("splice offset is beyond end of file")
        splice_op = str(args.get("splice_op") or "insert")
        if splice_op == "insert":
            updated = original[:offset] + data + original[offset:]
            changed = len(data)
        elif splice_op == "delete":
            delete_length = max(0, int(args.get("delete_len", 0) or 0))
            if delete_length > len(original) - offset:
                raise ValueError("splice deletion extends beyond end of file")
            updated = original[:offset] + original[offset + delete_length :]
            changed = delete_length
        else:
            raise ValueError("splice_op must be insert or delete")
    if len(updated) > 64 * 1024 * 1024:
        raise ValueError("edited file would exceed 64 MiB")
    if args.get("dry_run", False):
        return json.dumps(
            {
                "path": target.relative_to(ROOT).as_posix(),
                "changed_bytes": changed,
                "old_size": len(original),
                "new_size": len(updated),
                "dry_run": True,
            }
        )
    if updated != original:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            backup = target.with_name(target.name + ".org")
            index = 1
            while backup.exists() or backup.is_symlink():
                backup = target.with_name(target.name + f".org{index}")
                index += 1
            backup.write_bytes(original)
        target.write_bytes(updated)
    return json.dumps(
        {
            "path": target.relative_to(ROOT).as_posix(),
            "changed_bytes": changed,
            "old_size": len(original),
            "new_size": len(updated),
            "dry_run": False,
        }
    )


_SECURITY_PATTERNS = (
    (
        "private_key",
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----"
        ),
    ),
    ("aws_access_key", re.compile(r"\bAKIA[A-Z0-9]{16}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    (
        "credential_assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?[^'\"\s;,]{8,}"
        ),
    ),
)


def _security_scan(args: dict[str, Any]) -> str:
    root = _resolve_relative(args.get("path") or ".")
    if not root.is_dir():
        raise NotADirectoryError("scan path is not a directory")
    limit = min(100, max(1, int(args.get("limit", 100) or 100)))
    glob = str(args.get("glob") or "*")
    if len(glob) > 256:
        raise ValueError("glob pattern is too long")
    findings = []
    scanned = 0
    truncated = False
    for path in _workspace_files(root):
        relative = path.relative_to(ROOT).as_posix()
        if not (fnmatch.fnmatch(path.name, glob) or fnmatch.fnmatch(relative, glob)):
            continue
        size = path.stat().st_size
        if size > MAX_ANALYZE_BYTES:
            continue
        if scanned + size > MAX_TOTAL_SCAN_BYTES:
            truncated = True
            break
        scanned += size
        with path.open("rb") as stream:
            for line_number, raw_line in enumerate(stream, 1):
                sample = raw_line[:8192].decode("utf-8", errors="replace")
                if "\x00" in sample:
                    break
                for kind, expression in _SECURITY_PATTERNS:
                    if expression.search(sample):
                        findings.append(
                            {
                                "path": relative[:512],
                                "line": line_number,
                                "kind": kind,
                                "value_redacted": True,
                            }
                        )
                        if len(findings) >= limit:
                            return json.dumps(
                                {
                                    "findings": findings,
                                    "scanned_bytes": scanned,
                                    "truncated": True,
                                },
                                ensure_ascii=False,
                            )
    return json.dumps(
        {"findings": findings, "scanned_bytes": scanned, "truncated": truncated},
        ensure_ascii=False,
    )


_GIT_READ_COMMANDS = frozenset(
    {
        "status",
        "diff",
        "log",
        "branch",
        "rev-parse",
        "rev-list",
        "show",
        "ls-files",
        "grep",
        "tag",
        "reflog",
        "blame",
        "ls-tree",
        "cat-file",
    }
)
_GIT_MUTATING_COMMANDS = frozenset(
    {
        "init",
        "add",
        "commit",
        "switch",
        "checkout",
        "reset",
        "restore",
        "merge",
        "rebase",
        "stash",
        "rm",
    }
)
_GIT_FORBIDDEN_ARGS = (
    "-c",
    "--config",
    "--config-env",
    "--git-dir",
    "--work-tree",
    "--exec-path",
    "--output",
    "--no-index",
    "--ext-diff",
    "--textconv",
    "--filters",
    "--pathspec-from-file",
    "--template",
    "--separate-git-dir",
    "--reference",
    "--upload-pack",
    "--receive-pack",
    "--remote",
    "--show-signature",
    "--gpg-sign",
    "--local-user",
)


def _validate_workspace_git_metadata() -> None:
    metadata = ROOT / ".git"
    if metadata.is_symlink():
        raise PermissionError("symbolic .git entries are not allowed in the workspace")
    if metadata.is_file():
        first_line = metadata.read_text(encoding="utf-8", errors="replace").splitlines()
        if not first_line or not first_line[0].lower().startswith("gitdir:"):
            raise ValueError("invalid workspace .git file")
        value = first_line[0].split(":", 1)[1].strip()
        git_dir = Path(value)
        if not git_dir.is_absolute():
            git_dir = ROOT / git_dir
        resolved = git_dir.resolve(strict=False)
        if resolved != ROOT and ROOT not in resolved.parents:
            raise PermissionError(
                "Git metadata must stay inside the isolated workspace"
            )
        metadata = resolved
    if metadata.is_dir():
        common = metadata / "commondir"
        if common.is_file():
            value = common.read_text(encoding="utf-8", errors="replace").strip()
            path = Path(value)
            resolved = (
                (metadata / path).resolve(strict=False)
                if not path.is_absolute()
                else path.resolve(strict=False)
            )
            if resolved != ROOT and ROOT not in resolved.parents:
                raise PermissionError(
                    "shared Git metadata must stay inside the isolated workspace"
                )
        if (metadata / "objects" / "info" / "alternates").exists():
            raise PermissionError("external Git object alternates are not allowed")


def _git_ops(args: dict[str, Any]) -> str:
    command = str(args.get("command") or "").strip().lower()
    if command not in _GIT_READ_COMMANDS | _GIT_MUTATING_COMMANDS:
        raise ValueError("Git command is not in the local/offline allowlist")
    git_args = args.get("args", [])
    if not isinstance(git_args, list) or len(git_args) > 40:
        raise ValueError("Git args must be a list of at most 40 strings")
    normalized = []
    for item in git_args:
        if (
            not isinstance(item, str)
            or len(item) > 1000
            or any(ord(ch) < 32 for ch in item)
        ):
            raise ValueError(
                "Git arguments must be bounded text without control characters"
            )
        if chr(92) in item or "://" in item or item.lower().startswith("git@"):
            raise PermissionError(
                "absolute paths and remote Git URLs are not available in Sandbox"
            )
        if item.startswith("/") or Path(item).is_absolute() or Path(item).drive:
            raise PermissionError(
                "Git paths must be relative to the isolated workspace"
            )
        if any(part == ".." for part in item.split("/")):
            raise PermissionError("Git path traversal is not accepted")
        lowered = item.lower()
        if any(
            lowered == forbidden or lowered.startswith(forbidden + "=")
            for forbidden in _GIT_FORBIDDEN_ARGS
        ):
            raise PermissionError(
                "Git option can escape the local/offline execution policy"
            )
        normalized.append(item)
    if command == "tag" and any(arg in {"-s", "-u", "-v"} for arg in normalized):
        raise PermissionError(
            "GPG signing/verification is not available in Sandbox Git"
        )
    if command == "commit" and any(arg.startswith("-S") for arg in normalized):
        raise PermissionError("GPG signing is not available in Sandbox Git")
    if command in _GIT_MUTATING_COMMANDS and not bool(args.get("confirmed", False)):
        raise PermissionError("confirmed=true is required for workspace Git mutations")
    if (
        command == "branch"
        and any(
            not arg.startswith("-")
            or arg
            in {"-d", "-D", "-m", "-M", "-c", "-C", "--delete", "--move", "--copy"}
            for arg in normalized
        )
        and not args.get("confirmed", False)
    ):
        raise PermissionError("confirmed=true is required to mutate branches")
    if (
        command == "tag"
        and any(
            not arg.startswith("-")
            or arg in {"-d", "--delete", "-a", "-s", "-f", "--force"}
            for arg in normalized
        )
        and not args.get("confirmed", False)
    ):
        raise PermissionError("confirmed=true is required to mutate tags")
    if (
        command == "reflog"
        and any(arg in {"delete", "expire"} for arg in normalized)
        and not args.get("confirmed", False)
    ):
        raise PermissionError("confirmed=true is required to mutate reflogs")
    if "--" in normalized:
        separator = normalized.index("--")
        for path_arg in normalized[separator + 1 :]:
            _resolve_relative(path_arg)
    _validate_workspace_git_metadata()
    executable = shutil.which("git")
    if not executable:
        raise RuntimeError("Git executable is not installed in the MXC sandbox")
    executable_link = Path(executable).absolute()
    executable_path = executable_link.resolve(strict=True)
    if any(
        path == ROOT or ROOT in path.parents
        for path in (executable_link, executable_path)
    ):
        raise PermissionError(
            "Git executable must be installed outside the session workspace"
        )
    executable = str(executable_path)
    env = {
        "PATH": os.environ.get("PATH", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "WINDIR": os.environ.get("WINDIR", ""),
        "HOME": str(ROOT),
        "USERPROFILE": str(ROOT),
        "TEMP": str(ROOT),
        "TMP": str(ROOT),
        "TMPDIR": str(ROOT),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_PAGER": "cat",
        "PAGER": "cat",
        "GIT_EDITOR": "false",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_CEILING_DIRECTORIES": str(ROOT),
        "GIT_CONFIG_COUNT": "7",
        "GIT_CONFIG_KEY_0": "core.fsmonitor",
        "GIT_CONFIG_VALUE_0": "false",
        "GIT_CONFIG_KEY_1": "core.pager",
        "GIT_CONFIG_VALUE_1": "cat",
        "GIT_CONFIG_KEY_2": "diff.external",
        "GIT_CONFIG_VALUE_2": "",
        "GIT_CONFIG_KEY_3": "credential.helper",
        "GIT_CONFIG_VALUE_3": "",
        "GIT_CONFIG_KEY_4": "core.hooksPath",
        "GIT_CONFIG_VALUE_4": os.devnull,
        "GIT_CONFIG_KEY_5": "commit.gpgSign",
        "GIT_CONFIG_VALUE_5": "false",
        "GIT_CONFIG_KEY_6": "tag.gpgSign",
        "GIT_CONFIG_VALUE_6": "false",
        "GIT_AUTHOR_NAME": "MXC Sandbox",
        "GIT_AUTHOR_EMAIL": "sandbox@localhost",
        "GIT_COMMITTER_NAME": "MXC Sandbox",
        "GIT_COMMITTER_EMAIL": "sandbox@localhost",
    }
    argv = [executable, command, *normalized]
    if command in {"diff", "show", "log"}:
        argv.extend(["--no-ext-diff", "--no-textconv"])
    try:
        process = subprocess.Popen(
            argv,
            cwd=ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
    except OSError as exc:
        raise RuntimeError(
            f"could not start sandbox Git: {type(exc).__name__}"
        ) from exc
    collected: dict[str, Any] = {}

    def drain(stream, key: str, limit: int) -> None:
        pieces = []
        size = 0
        truncated_output = False
        while True:
            chunk = stream.read(8192)
            if not chunk:
                break
            remaining = limit - size
            if remaining > 0:
                pieces.append(chunk[:remaining])
                size += min(len(chunk), remaining)
            if len(chunk) > remaining:
                truncated_output = True
        collected[key] = b"".join(pieces).decode("utf-8", errors="replace")
        collected[key + "_truncated"] = truncated_output

    stdout_thread = threading.Thread(
        target=drain, args=(process.stdout, "stdout", MAX_READ_BYTES), daemon=True
    )
    stderr_thread = threading.Thread(
        target=drain, args=(process.stderr, "stderr", 16_384), daemon=True
    )
    stdout_thread.start()
    stderr_thread.start()
    timed_out = False
    try:
        return_code = process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        return_code = process.wait()
    stdout_thread.join(timeout=2)
    stderr_thread.join(timeout=2)
    stdout = collected.get("stdout", "")
    stderr = collected.get("stderr", "")
    for host_path in (str(ROOT), str(ROOT).replace("\\", "/")):
        stdout = stdout.replace(host_path, ".")
        stderr = stderr.replace(host_path, ".")
    return json.dumps(
        {
            "command": command,
            "returncode": return_code,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": timed_out,
            "output_truncated": collected.get("stdout_truncated", False)
            or collected.get("stderr_truncated", False),
        },
        ensure_ascii=False,
    )


_WEATHER_MAX_BYTES = 1024 * 1024
_WEATHER_TIMEOUT_SECONDS = 10

_WMO_WEATHER_DESCRIPTIONS = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def _fetch_weather_json(url: str) -> Any:
    """Fetch one JSON document from a public weather API, size-bounded."""
    request = urllib.request.Request(
        url, headers={"User-Agent": "uagent-sandbox-weather"}
    )
    with urllib.request.urlopen(request, timeout=_WEATHER_TIMEOUT_SECONDS) as response:
        raw = response.read(_WEATHER_MAX_BYTES + 1)
    if len(raw) > _WEATHER_MAX_BYTES:
        raise ValueError("weather response is too large")
    return json.loads(raw.decode("utf-8"))


def _weather_description(entry: dict[str, Any]) -> str:
    for key in ("lang_ja", "weatherDesc"):
        values = entry.get(key)
        if isinstance(values, list) and values and isinstance(values[0], dict):
            text = str(values[0].get("value") or "").strip()
            if text:
                return text
    return "Unknown"


def _weather_from_wttr(*, city: str, lat: Any, lon: Any) -> str:
    location = f"{lat},{lon}" if lat is not None and lon is not None else city
    url = "https://wttr.in/" + urllib.parse.quote(location, safe=",") + "?format=j1"
    data = _fetch_weather_json(url)
    if not isinstance(data, dict):
        raise ValueError("unexpected wttr.in response")
    current = (data.get("current_condition") or [{}])[0]
    display_city = city or f"{lat},{lon}"
    areas = data.get("nearest_area") or []
    if areas:
        names = areas[0].get("areaName") or []
        if names and isinstance(names[0], dict) and names[0].get("value"):
            display_city = str(names[0]["value"])
    lines = [
        f"### Weather for {display_city}",
        f"- **Temp**: {current.get('temp_C', '?')}°C"
        f" (feels like {current.get('FeelsLikeC', '?')}°C)",
        f"- **Condition**: {_weather_description(current)}",
        f"- **Humidity**: {current.get('humidity', '?')}%",
    ]
    days = data.get("weather") or []
    if days:
        lines.append("\n--- Forecast ---")
        for day in days[:7]:
            desc = ""
            hourly = day.get("hourly") or []
            if len(hourly) > 2:
                desc = _weather_description(hourly[2])
            lines.append(
                f"- **{day.get('date', '')}**: {day.get('mintempC', '?')}°C"
                f" / {day.get('maxtempC', '?')}°C ({desc})"
            )
    return "\n".join(lines)


def _weather_from_open_meteo(*, city: str, lat: Any, lon: Any) -> str:
    display_city = city
    if lat is None or lon is None:
        geo = _fetch_weather_json(
            "https://geocoding-api.open-meteo.com/v1/search?name="
            + urllib.parse.quote(city)
            + "&count=1&language=en&format=json"
        )
        results = (geo or {}).get("results") or []
        if not results:
            raise ValueError("city not found")
        lat = float(results[0]["latitude"])
        lon = float(results[0]["longitude"])
        display_city = str(results[0].get("name") or city)
    elif not display_city:
        display_city = f"{lat},{lon}"
    data = _fetch_weather_json(
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={float(lat)}&longitude={float(lon)}"
        "&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code"
        "&daily=temperature_2m_max,temperature_2m_min,weather_code"
        "&timezone=auto"
    )
    current = (data or {}).get("current") or {}

    def describe(code: Any) -> str:
        if isinstance(code, bool) or not isinstance(code, (int, float)):
            return "Unknown"
        return _WMO_WEATHER_DESCRIPTIONS.get(int(code), "Unknown")

    lines = [
        "[via Open-Meteo fallback]",
        f"### Weather for {display_city}",
        f"- **Temp**: {current.get('temperature_2m', '?')}°C"
        f" (feels like {current.get('apparent_temperature', '?')}°C)",
        f"- **Condition**: {describe(current.get('weather_code'))}",
        f"- **Humidity**: {current.get('relative_humidity_2m', '?')}%",
    ]
    daily = (data or {}).get("daily") or {}
    dates = daily.get("time") or []
    if dates:
        lines.append("\n--- Forecast ---")
        maxs = daily.get("temperature_2m_max") or []
        mins = daily.get("temperature_2m_min") or []
        codes = daily.get("weather_code") or []
        for idx, date in enumerate(dates[:7]):
            desc = describe(codes[idx]) if idx < len(codes) else "Unknown"
            low = mins[idx] if idx < len(mins) else "?"
            high = maxs[idx] if idx < len(maxs) else "?"
            lines.append(f"- **{date}**: {low}°C / {high}°C ({desc})")
    return "\n".join(lines)


def _get_weather_wttr(args: dict[str, Any]) -> str:
    """Current weather + short forecast from public APIs (no credentials).

    Mirrors the host get_weather_wttr tool: wttr.in first, Open-Meteo
    as fallback. Runs entirely inside the sandbox; the only network
    access is to those two public weather endpoints.
    """
    lat = args.get("lat")
    lon = args.get("lon")
    city = args.get("city")
    if city is not None and (
        not isinstance(city, str) or len(city) > 200 or any(ord(c) < 32 for c in city)
    ):
        raise ValueError("city must be a string of at most 200 characters")
    city = (city or "").strip()
    for value, low, high, label in ((lat, -90, 90, "lat"), (lon, -180, 180, "lon")):
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not (low <= float(value) <= high)
        ):
            raise ValueError(f"{label} must be a number between {low} and {high}")
    if (lat is None) != (lon is None) and not city:
        raise ValueError("Provide a city name, or lat+lon coordinates.")
    if lat is None and lon is None and not city:
        raise ValueError("Provide a city name, or lat+lon coordinates.")
    try:
        return _weather_from_wttr(city=city, lat=lat, lon=lon)
    except Exception:
        pass
    try:
        return _weather_from_open_meteo(city=city, lat=lat, lon=lon)
    except Exception as exc:
        raise ValueError(
            f"weather lookup failed on both providers ({type(exc).__name__})"
        ) from exc


# ---------------------------------------------------------------------------
# Ported host tools. These mirror the host tools' argument and output
# contracts but run entirely inside the sandbox. They use only the standard
# library plus optional packages when those are already importable in the
# sandbox environment; nothing is ever installed from inside.
# ---------------------------------------------------------------------------


_SANDBOX_SITE_PACKAGES: Path | None = None


def _sandbox_site_packages() -> Path:
    global _SANDBOX_SITE_PACKAGES
    if _SANDBOX_SITE_PACKAGES is None:
        target = ROOT / ".uag" / "site-packages"
        _SANDBOX_SITE_PACKAGES = target
        if str(target) not in sys.path:
            sys.path.insert(0, str(target))
    return _SANDBOX_SITE_PACKAGES


def _ensure_package(module_name: str, pip_name: str | None = None) -> Any | None:
    """Import a module, installing it into the workspace on first use.

    The sandbox cannot write to the Python environment (it is mounted
    read-only), so optional packages are installed with pip --target into
    <workspace>/.uag/site-packages, which persists with the workspace.
    Returns the imported module, or None when it stays unavailable.
    """
    import importlib

    try:
        return importlib.import_module(module_name)
    except ImportError:
        pass
    target = _sandbox_site_packages()
    try:
        return importlib.import_module(module_name)
    except ImportError:
        pass
    try:
        target.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-input",
                "--disable-pip-version-check",
                "--target",
                str(target),
                pip_name or module_name,
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if completed.returncode != 0:
            return None
    except Exception:
        return None
    importlib.invalidate_caches()
    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None


def _fetch_capped(
    request: urllib.request.Request,
    *,
    timeout: float,
    cap: int,
    opener: Any = None,
) -> tuple[bytes, Any]:
    open_fn = opener.open if opener is not None else urllib.request.urlopen
    with open_fn(request, timeout=timeout) as response:
        return response.read(cap + 1)[:cap], response


def _get_current_time(args: dict[str, Any]) -> str:
    del args
    now = datetime.datetime.now().astimezone()
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    res = [
        f"ISO8601 (Local): {now.isoformat()}",
        f"ISO8601 (UTC):   {utc_now.isoformat()}",
        f"Weekday:         {now.strftime('%A')}",
        f"Timezone Name:   {now.tzname()}",
        f"UTC Offset:      {now.strftime('%z')}",
        f"Year:            {now.year}",
        f"Month:           {now.month}",
        f"Day:             {now.day}",
        f"Hour:            {now.hour}",
        f"Minute:          {now.minute}",
        f"Second:          {now.second}",
        "NTP Sync:        N/A",
    ]
    return "[get_current_time]\n" + "\n".join(res)


def _nominatim_reverse(lat: float, lon: float, language: str) -> dict[str, Any]:
    params = {"lat": str(lat), "lon": str(lon), "format": "json"}
    params["accept-language"] = language or "en"
    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"https://nominatim.openstreetmap.org/reverse?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": "uagent-sandbox/1.0"})
    raw, _response = _fetch_capped(request, timeout=10, cap=1_000_000)
    return json.loads(raw.decode("utf-8"))


def _reverse_geocode(args: dict[str, Any]) -> str:
    lat = args.get("lat")
    lon = args.get("lon")
    if lat is None or lon is None:
        return json.dumps(
            {"ok": False, "error": "Both lat and lon are required."},
            ensure_ascii=False,
        )
    try:
        flat = float(lat)
        flon = float(lon)
    except (TypeError, ValueError):
        return json.dumps(
            {"ok": False, "error": "lat and lon must be numbers."},
            ensure_ascii=False,
        )
    language = str(args.get("language") or "")
    try:
        data = _nominatim_reverse(flat, flon, language)
    except urllib.error.HTTPError as exc:
        return json.dumps(
            {"ok": False, "error": f"HTTP Error {exc.code}: {exc.reason}"},
            ensure_ascii=False,
        )
    except urllib.error.URLError as exc:
        return json.dumps(
            {"ok": False, "error": f"URL Error: {exc.reason}"},
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps(
            {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
            ensure_ascii=False,
        )
    if "error" in data:
        return json.dumps({"ok": False, "error": data["error"]}, ensure_ascii=False)
    result = {
        "ok": True,
        "display_name": data.get("display_name", ""),
        "lat": data.get("lat", str(flat)),
        "lon": data.get("lon", str(flon)),
        "address": data.get("address", {}),
        "osm_type": data.get("osm_type", ""),
        "osm_id": data.get("osm_id"),
    }
    return json.dumps(result, ensure_ascii=False)


def _geodesic_distance(args: dict[str, Any]) -> str:
    def _coordinate(value: Any, label: str, low: float, high: float) -> float:
        number = float(value)
        if not low <= number <= high:
            raise ValueError(f"{label} must be between {low} and {high}")
        return number

    try:
        lat_a = _coordinate(args.get("lat_a"), "lat_a", -90, 90)
        lon_a = _coordinate(args.get("lon_a"), "lon_a", -180, 180)
        lat_b = _coordinate(args.get("lat_b"), "lat_b", -90, 90)
        lon_b = _coordinate(args.get("lon_b"), "lon_b", -180, 180)
    except (TypeError, ValueError) as exc:
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
    phi1, phi2 = math.radians(lat_a), math.radians(lat_b)
    dphi = math.radians(lat_b - lat_a)
    dlambda = math.radians(lon_b - lon_a)
    hav = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    distance_km = 6371.0088 * 2 * math.atan2(math.sqrt(hav), math.sqrt(1 - hav))
    bearing = (
        math.degrees(
            math.atan2(
                math.sin(dlambda) * math.cos(phi2),
                math.cos(phi1) * math.sin(phi2)
                - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda),
            )
        )
        + 360
    ) % 360
    output: dict[str, Any] = {
        "ok": True,
        "point_a": {"lat": lat_a, "lon": lon_a},
        "point_b": {"lat": lat_b, "lon": lon_b},
        "distance_km": round(distance_km, 6),
        "distance_m": round(distance_km * 1000, 3),
        "initial_bearing_degrees": round(bearing, 3),
        "method": "Haversine",
    }
    if args.get("resolve_addresses"):
        language = str(args.get("language") or "")
        for key, la, lo in (
            ("address_a", lat_a, lon_a),
            ("address_b", lat_b, lon_b),
        ):
            try:
                data = _nominatim_reverse(la, lo, language)
                output[key] = data.get("display_name", "")
            except Exception:
                output[key] = ""
    return json.dumps(output, ensure_ascii=False)


def _date_calc(args: dict[str, Any]) -> str:
    if _ensure_package("dateutil", "python-dateutil") is None:
        return json.dumps(
            {
                "ok": False,
                "error": "[date_calc] python-dateutil is not available "
                "in the sandbox environment and could not be installed "
                "automatically.",
            },
            ensure_ascii=False,
        )
    from dateutil.relativedelta import relativedelta

    base_date_str = args.get("base_date")
    country = str(args.get("country", "JP") or "JP")
    check_h = args.get("check_holiday", True)
    try:
        if base_date_str:
            if len(str(base_date_str)) == 10:
                base_date = datetime.datetime.strptime(str(base_date_str), "%Y-%m-%d")
            else:
                base_date = datetime.datetime.fromisoformat(str(base_date_str))
        else:
            base_date = datetime.datetime.now()
    except Exception as exc:
        return json.dumps(
            {"ok": False, "error": f"[date_calc]\nError parsing base_date: {exc}"},
            ensure_ascii=False,
        )
    try:
        delta = relativedelta(
            years=int(args.get("years", 0) or 0),
            months=int(args.get("months", 0) or 0),
            weeks=int(args.get("weeks", 0) or 0),
            days=int(args.get("days", 0) or 0),
        )
    except Exception as exc:
        return json.dumps(
            {"ok": False, "error": f"[date_calc] invalid delta: {exc}"},
            ensure_ascii=False,
        )
    result_date = base_date + delta
    holiday_info = None
    if check_h:
        holiday_info = _holiday_info(result_date, country)
    info_suffix = f" ({holiday_info})" if holiday_info else ""
    res = [
        f"Base Date:   {base_date.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Operation:   years={args.get('years', 0)}, months={args.get('months', 0)}, "
        f"weeks={args.get('weeks', 0)}, days={args.get('days', 0)}",
        f"Country:     {country.upper()}",
        f"Result Date: {result_date.strftime('%Y-%m-%d %H:%M:%S')}{info_suffix}",
        f"ISO8601:     {result_date.isoformat()}",
        f"Weekday:     {result_date.strftime('%A')}",
    ]
    if holiday_info:
        res.append(f"Holiday Info: {holiday_info}")
    else:
        res.append("Holiday Info: Weekday")
    return "[date_calc]\n" + "\n".join(res)


def _holiday_info(dt: datetime.datetime, country_code: str) -> str | None:
    holidays = _ensure_package("holidays")
    if holidays is None:
        return None
    try:
        if country_code.upper() == "JP":
            hols = holidays.Japan(language="ja")
        else:
            hols = holidays.country_holidays(country_code.upper())
    except Exception:
        return f"Error: Country code '{country_code}' not supported."
    holiday_name = hols.get(dt)
    weekend_name = None
    if dt.weekday() == 5:
        weekend_name = "Saturday"
    elif dt.weekday() == 6:
        weekend_name = "Sunday"
    if holiday_name and weekend_name:
        return f"Holiday ({holiday_name}) and {weekend_name}"
    if holiday_name:
        return f"Holiday ({holiday_name})"
    if weekend_name:
        return weekend_name
    return None


_QUANTITY_UNSAFE = re.compile(
    r"(?:__|\b(?:import|exec|eval|lambda|globals|locals|open)\b|[\[\]{};`])",
    re.IGNORECASE,
)
_QUANTITY_TO_SUFFIX = re.compile(r"\s+(?:to|in)\s+(.+?)\s*$", re.IGNORECASE)


def _quantities(args: dict[str, Any]) -> str:
    def _error(message: str, **extra: Any) -> str:
        result: dict[str, Any] = {"ok": False, "error": message}
        result.update(extra)
        return json.dumps(result, ensure_ascii=False)

    expression = str(args.get("expression") or "").strip()
    if not expression:
        return _error("No quantity expression was provided.")
    if _QUANTITY_UNSAFE.search(expression):
        return _error("The quantity expression contains unsupported syntax.")
    target = str(args.get("to_unit") or "").strip()
    source = expression
    if target:
        source = expression.strip()
    else:
        match = _QUANTITY_TO_SUFFIX.search(expression)
        if match:
            source = expression[: match.start()].strip()
            target = match.group(1).strip()
    if _QUANTITY_UNSAFE.search(target):
        return _error("The target unit contains unsupported syntax.")
    pint = _ensure_package("pint")
    if pint is None:
        return _error(
            "Pint is not available in the sandbox environment and "
            "could not be installed automatically. Use the calculate "
            "tool for plain arithmetic."
        )
    try:
        raw_precision = args.get("precision")
        precision = 6 if raw_precision is None else int(raw_precision)
    except (TypeError, ValueError):
        precision = 6
    precision = max(0, min(precision, 15))
    try:
        registry = pint.UnitRegistry(autoconvert_offset_to_baseunit=True)
        quantity = registry.parse_expression(source)
        if target:
            quantity = quantity.to(target)
        magnitude = quantity.magnitude
        if isinstance(magnitude, complex):
            magnitude_text = str(magnitude)
        else:
            magnitude_text = f"{float(magnitude):.{precision}f}".rstrip("0").rstrip(".")
            if magnitude_text in {"-0", ""}:
                magnitude_text = "0"
        output = {
            "ok": True,
            "expression": expression,
            "result": f"{magnitude_text} {quantity.units:~P}",
            "magnitude": quantity.magnitude,
            "unit": str(quantity.units),
        }
        return json.dumps(output, ensure_ascii=False, default=str)
    except Exception as exc:
        return _error(
            f"Unable to evaluate the quantity expression: {exc}",
            expression=expression,
        )


_ZIPCODE_BASE_URL = "https://jpzip.nadai.dev"


def _zipcode_fetch_json(path: str) -> dict[str, Any] | None:
    url = f"{_ZIPCODE_BASE_URL}{path}"
    request = urllib.request.Request(url)
    request.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
    try:
        raw, _response = _fetch_capped(request, timeout=10, cap=4_000_000)
        return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    except Exception:
        return None


def _zipcode_check(args: dict[str, Any]) -> str:
    zipcode = str(args.get("zipcode") or "").strip()
    prefecture = str(args.get("prefecture") or "").strip()
    if zipcode and prefecture:
        return json.dumps(
            {
                "ok": False,
                "error": "Provide either zipcode or prefecture, not both.",
            },
            ensure_ascii=False,
        )
    if zipcode:
        z = zipcode.replace("-", "").replace(" ", "").strip()
        if not z.isdigit() or len(z) != 7:
            return json.dumps(
                {
                    "ok": False,
                    "error": f"Invalid zipcode format: '{zipcode}'. "
                    "Must be 7 digits.",
                },
                ensure_ascii=False,
            )
        data = _zipcode_fetch_json(f"/p/{z[:3]}.json")
        if data is None:
            return json.dumps(
                {
                    "ok": False,
                    "error": f"No data found for zipcode prefix {z[:3]}.",
                },
                ensure_ascii=False,
            )
        entry = data.get(z)
        if entry is None:
            return json.dumps(
                {"ok": False, "error": f"Zipcode {z} not found."},
                ensure_ascii=False,
            )
        entry = dict(entry)
        entry.pop("prefecture_code", None)
        return json.dumps(
            {"ok": True, "zipcode": z, "address": entry},
            ensure_ascii=False,
            indent=2,
        )
    if prefecture:
        meta = _zipcode_fetch_json("/meta.json")
        if meta is None:
            return json.dumps(
                {"ok": False, "error": "Failed to fetch metadata."},
                ensure_ascii=False,
            )
        matched: dict[str, Any] = {}
        found_code = None
        for group in "0123456789":
            group_data = _zipcode_fetch_json(f"/g/{group}.json")
            if group_data is None:
                continue
            for code, entry in group_data.items():
                p_name = entry.get("prefecture", "")
                p_kana = entry.get("prefecture_kana", "")
                p_roma = entry.get("prefecture_roma", "")
                p_code = entry.get("prefecture_code", "")
                match = (
                    prefecture in (p_name, p_kana)
                    or (p_roma and prefecture.lower() == p_roma.lower())
                    or prefecture in p_name
                    or prefecture in p_kana
                )
                if not match:
                    continue
                if found_code is None:
                    found_code = p_code
                if p_code != found_code:
                    continue
                city_key = f"{entry.get('city', '')}|{entry.get('city_code', '')}"
                if city_key not in matched:
                    matched[city_key] = {
                        "city": entry.get("city", ""),
                        "city_kana": entry.get("city_kana", ""),
                        "city_roma": entry.get("city_roma", ""),
                        "city_code": entry.get("city_code", ""),
                    }
        if not matched:
            return json.dumps(
                {
                    "ok": False,
                    "error": f"No cities found for prefecture '{prefecture}'.",
                },
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "ok": True,
                "prefecture": prefecture,
                "count": len(matched),
                "cities": sorted(
                    matched.values(), key=lambda c: c.get("city_code", "")
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    return json.dumps(
        {
            "ok": False,
            "error": "Provide either 'zipcode' (7 digits) or 'prefecture' "
            "(e.g. Tokyo).",
            "usage": {
                "example_zipcode": {"zipcode": "1000001"},
                "example_prefecture": {"prefecture": "Tokyo"},
            },
        },
        ensure_ascii=False,
    )


def _http_request(args: dict[str, Any]) -> str:
    method = str(args.get("method") or "GET").upper()
    allowed = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
    if method not in allowed:
        return json.dumps(
            {"ok": False, "error": f"unsupported HTTP method: {method}"},
            ensure_ascii=False,
        )
    url = str(args.get("url") or "")
    query = args.get("query")
    if isinstance(query, dict) and query:
        parts = urllib.parse.urlsplit(url)
        pairs: list[tuple[str, str]] = []
        for key, value in query.items():
            if isinstance(value, (list, tuple)):
                pairs.extend((str(key), str(item)) for item in value)
            else:
                pairs.append((str(key), str(value)))
        extra = urllib.parse.urlencode(pairs)
        merged = f"{parts.query}&{extra}" if parts.query else extra
        url = urllib.parse.urlunsplit(
            (parts.scheme, parts.netloc, parts.path, merged, parts.fragment)
        )
    if not url.startswith(("http://", "https://")):
        return json.dumps(
            {"ok": False, "error": "url must start with http:// or https://"},
            ensure_ascii=False,
        )
    headers_arg = args.get("headers") or {}
    if not isinstance(headers_arg, dict):
        return json.dumps(
            {"ok": False, "error": "headers must be an object"},
            ensure_ascii=False,
        )
    headers = {str(k): str(v) for k, v in headers_arg.items()}
    headers.setdefault("User-Agent", "uagent-http-request/1.0")
    bearer = str(args.get("bearer_token") or "")
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    username = args.get("username")
    password = args.get("password")
    if username is not None or password is not None:
        raw_auth = f"{username or ''}:{password or ''}".encode("utf-8")
        headers["Authorization"] = "Basic " + base64.b64encode(raw_auth).decode("ascii")
    body_value = args.get("body")
    body_text = args.get("body_text")
    data: bytes | None = None
    if body_text is not None:
        data = str(body_text).encode("utf-8")
    elif body_value is not None:
        if isinstance(body_value, (dict, list)):
            data = json.dumps(body_value, ensure_ascii=False).encode("utf-8")
        elif isinstance(body_value, bool):
            data = ("true" if body_value else "false").encode("utf-8")
        else:
            data = str(body_value).encode("utf-8")
    if data is not None:
        headers.setdefault(
            "Content-Type", str(args.get("content_type") or "application/json")
        )
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    verify_ssl = args.get("ssl", True)
    if not isinstance(verify_ssl, bool):
        verify_ssl = str(verify_ssl).lower() in {"1", "true", "yes", "on"}
    context = None
    if url.startswith("https://") and not verify_ssl:
        context = ssl._create_unverified_context()
    try:
        # Network tools run under the sandbox's long response budget
        # (300 seconds); keep the request timeout inside it with room
        # for response processing.
        timeout = max(1, min(int(args.get("timeout") or 30), 240))
    except (TypeError, ValueError):
        timeout = 30
    try:
        max_bytes = max(1, min(int(args.get("max_bytes") or 2_000_000), 10_000_000))
    except (TypeError, ValueError):
        max_bytes = 2_000_000
    handlers: list[Any] = []
    if context is not None:
        handlers.append(urllib.request.HTTPSHandler(context=context))
    opener = urllib.request.build_opener(*handlers)
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(max_bytes + 1)
            truncated = len(raw) > max_bytes
            raw = raw[:max_bytes]
            response_headers = {str(k): str(v) for k, v in response.headers.items()}
            charset = response.headers.get_content_charset()
            try:
                text = raw.decode(charset or "utf-8", errors="replace")
            except Exception:
                text = raw.decode("latin-1", errors="replace")
            result: dict[str, Any] = {
                "ok": True,
                "status_code": int(getattr(response, "status", 200)),
                "url": str(getattr(response, "url", url)),
                "headers": response_headers,
                "body": text,
                "truncated": truncated,
            }
            if args.get("parse_json"):
                try:
                    result["response_json"] = json.loads(text)
                except Exception:
                    pass
            # The worker result budget (MAX_RESULT_BYTES, enforced by
            # _emit) is smaller than the advertised body cap, and a
            # parsed copy in response_json doubles the payload. Shrink
            # to fit so the caller keeps status and headers instead of
            # losing the whole result: drop response_json first, then
            # truncate the body.
            budget = MAX_RESULT_BYTES - 100_000
            encoded = json.dumps(result, ensure_ascii=False)
            if len(encoded.encode("utf-8", errors="replace")) > budget:
                result.pop("response_json", None)
                encoded = json.dumps(result, ensure_ascii=False)
            while (
                len(encoded.encode("utf-8", errors="replace")) > budget
                and result["body"]
            ):
                result["body"] = result["body"][: len(result["body"]) // 2]
                result["truncated"] = True
                encoded = json.dumps(result, ensure_ascii=False)
            return encoded
    except urllib.error.HTTPError as exc:
        try:
            raw = exc.read(max_bytes)
            text = raw.decode("utf-8", errors="replace")
        except Exception:
            text = ""
        return json.dumps(
            {
                "ok": False,
                "status_code": int(exc.code),
                "error": f"HTTP Error {exc.code}: {exc.reason}",
                "body": text,
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps(
            {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
            ensure_ascii=False,
        )


def _parse_patch_sections(patch_text: str) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    hunk: dict[str, Any] | None = None
    src_left = 0
    dst_left = 0
    for line in patch_text.splitlines():
        # Inside a hunk body, consume lines by the advertised counts
        # first: a removed line whose content starts with "-- " reads
        # as "--- " and must not be mistaken for a new file header
        # (same for "+++ " and added content).
        if (
            hunk is not None
            and (src_left > 0 or dst_left > 0)
            and line[:1]
            in {
                " ",
                "-",
                "+",
                "\\",
            }
        ):
            hunk["lines"].append(line)
            if line[:1] == " ":
                src_left -= 1
                dst_left -= 1
            elif line[:1] == "-":
                src_left -= 1
            elif line[:1] == "+":
                dst_left -= 1
            continue
        if line.startswith("--- "):
            current = {
                "old": line[4:].split("\t")[0].strip(),
                "new": None,
                "hunks": [],
            }
            sections.append(current)
            hunk = None
            src_left = 0
            dst_left = 0
            continue
        if line.startswith("+++ ") and current is not None:
            current["new"] = line[4:].split("\t")[0].strip()
            continue
        match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
        if match and current is not None:
            hunk = {
                "old_start": int(match.group(1)),
                "old_count": int(match.group(2)) if match.group(2) else 1,
                "new_start": int(match.group(3)),
                "new_count": int(match.group(4)) if match.group(4) else 1,
                "lines": [],
            }
            src_left = hunk["old_count"]
            dst_left = hunk["new_count"]
            current["hunks"].append(hunk)
            continue
        if hunk is not None and line[:1] in {" ", "-", "+", "\\"}:
            hunk["lines"].append(line)
    return [s for s in sections if s["new"] is not None]


def _strip_patch_path(token: str, strip: int) -> str | None:
    if token == "/dev/null":
        return None
    parts = token.split("/")
    # Git-style diffs prefix the old/new paths with a/ and b/; that prefix
    # is normalized away first (as the host parser does), then the
    # documented strip count applies to what remains.
    if parts and parts[0] in {"a", "b"}:
        parts = parts[1:]
    if strip > 0:
        parts = parts[strip:]
    return "/".join(parts)


def _apply_patch(args: dict[str, Any]) -> str:
    patch_text = str(args.get("patch_text") or "")
    if not patch_text.strip():
        return json.dumps(
            {"ok": False, "error": "patch_text is required"}, ensure_ascii=False
        )
    # The host tool (and the confirmation policy) treats an omitted
    # dry_run as a safe preview; match that default.
    dry_run = bool(args.get("dry_run", True))
    revert = bool(args.get("revert"))
    ignore_ws = bool(args.get("ignore_whitespace"))
    try:
        strip = max(0, min(int(args.get("strip", 0)), 5))
    except (TypeError, ValueError):
        strip = 0
    encoding = str(args.get("encoding") or "utf-8")

    def _norm(text: str) -> str:
        return " ".join(text.split()) if ignore_ws else text

    results: list[dict[str, Any]] = []
    for section in _parse_patch_sections(patch_text):
        old_rel = _strip_patch_path(str(section["old"]), strip)
        new_rel = _strip_patch_path(str(section["new"]), strip)
        if revert:
            old_rel, new_rel = new_rel, old_rel
        target_rel = new_rel if new_rel is not None else old_rel
        if target_rel is None:
            results.append({"ok": False, "error": "patch section has no path"})
            continue
        try:
            target = _resolve_relative(target_rel)
        except Exception as exc:
            results.append({"path": target_rel, "ok": False, "error": str(exc)})
            continue
        creating = old_rel is None
        deleting = new_rel is None
        if creating:
            if target.exists():
                results.append(
                    {
                        "path": target_rel,
                        "ok": False,
                        "error": "file already exists",
                    }
                )
                continue
            original: list[str] = []
            ends_with_newline = True
            crlf = False
        else:
            if not target.is_file():
                results.append(
                    {"path": target_rel, "ok": False, "error": "file not found"}
                )
                continue
            raw_text = target.read_bytes().decode(encoding, errors="strict")
            crlf = "\r\n" in raw_text
            ends_with_newline = raw_text.endswith(("\n", "\r")) or raw_text == ""
            original = raw_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
            if ends_with_newline and original and original[-1] == "":
                original = original[:-1]
            elif raw_text == "":
                original = []
        lines = list(original)
        offset = 0
        failed = ""
        for hunk in section["hunks"]:
            src_lines: list[str] = []
            dst_lines: list[str] = []
            src_marked: set[int] = set()
            dst_marked: set[int] = set()
            prev_src = prev_dst = False
            for entry in hunk["lines"]:
                tag, content = entry[:1], entry[1:]
                if tag == "\\":
                    # "\ No newline at end of file" marks the line above.
                    if prev_src and src_lines:
                        src_marked.add(len(src_lines) - 1)
                    if prev_dst and dst_lines:
                        dst_marked.add(len(dst_lines) - 1)
                    continue
                if revert:
                    feeds_src = tag in {" ", "+"}
                    feeds_dst = tag in {" ", "-"}
                else:
                    feeds_src = tag in {" ", "-"}
                    feeds_dst = tag in {" ", "+"}
                if feeds_src:
                    src_lines.append(content)
                if feeds_dst:
                    dst_lines.append(content)
                prev_src, prev_dst = feeds_src, feeds_dst
            if revert:
                anchor = hunk["new_start"]
                src_count = hunk["new_count"]
            else:
                anchor = hunk["old_start"]
                src_count = hunk["old_count"]
            # A zero-length source range names the line AFTER which the
            # new lines are inserted, not the line they replace.
            base = (anchor if src_count == 0 else anchor - 1) + offset
            found = -1
            if src_lines:
                # Search outward from the expected position so a shifted
                # hunk lands on the nearest matching occurrence, not the
                # first one in the file.
                candidates = []
                for distance in range(0, len(lines) + 1):
                    if distance == 0:
                        candidates.append(base)
                    else:
                        candidates.append(base - distance)
                        candidates.append(base + distance)
            else:
                candidates = [base]
            seen: set[int] = set()
            for pos in candidates:
                if pos in seen or pos < 0 or pos > len(lines):
                    continue
                seen.add(pos)
                window = lines[pos : pos + len(src_lines)]
                if len(window) != len(src_lines):
                    continue
                if all(_norm(a) == _norm(b) for a, b in zip(window, src_lines)):
                    found = pos
                    break
            if found < 0:
                failed = "hunk context not found"
                break
            touches_eof = found + len(src_lines) == len(lines)
            lines[found : found + len(src_lines)] = dst_lines
            if touches_eof:
                # The destination side of this hunk decides whether the
                # file ends with a newline; interior hunks leave the
                # original state alone.
                if dst_lines:
                    ends_with_newline = (len(dst_lines) - 1) not in dst_marked
                else:
                    ends_with_newline = bool(lines)
            offset += len(dst_lines) - len(src_lines)
        if failed:
            results.append({"path": target_rel, "ok": False, "error": failed})
            continue
        action = "created" if creating else "deleted" if deleting else "modified"
        if not dry_run:
            if deleting:
                if lines:
                    results.append(
                        {
                            "path": target_rel,
                            "ok": False,
                            "error": "delete patch leaves content behind",
                        }
                    )
                    continue
                target.unlink()
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                text_out = "\n".join(lines)
                if ends_with_newline and lines:
                    text_out += "\n"
                if crlf and args.get("preserve_line_endings", True):
                    text_out = text_out.replace("\n", "\r\n")
                target.write_bytes(text_out.encode(encoding))
        results.append(
            {
                "path": target_rel,
                "ok": True,
                "action": action,
                "hunks": len(section["hunks"]),
            }
        )
    ok = all(item.get("ok") for item in results) and bool(results)
    return json.dumps(
        {"ok": ok, "dry_run": dry_run, "files": results},
        ensure_ascii=False,
    )


def _media_attachment(
    out_rel: str, data: bytes, mime: str, *, include: bool
) -> list[dict[str, Any]]:
    # Mirror the host render tools: the Web UI consumes top-level
    # "attachments" entries with data_base64 when include_base64 is set.
    if not include:
        return []
    return [
        {
            "type": "image" if mime.startswith("image/") else "file",
            "mime": mime,
            "name": Path(out_rel).name,
            "path": out_rel,
            "data_base64": base64.b64encode(data).decode("ascii"),
        }
    ]


def _attach_within_budget(
    payload: dict[str, Any], attachments: list[dict[str, Any]]
) -> None:
    # A large render's base64 attachment can push the serialized
    # result past MAX_RESULT_BYTES, in which case the dispatcher
    # would discard the whole result. Keep the metadata (the file
    # itself stays in the workspace) and note the omission instead.
    if not attachments:
        return
    candidate = dict(payload)
    candidate["attachments"] = attachments
    serialized = json.dumps(candidate, ensure_ascii=False).encode("utf-8")
    if len(serialized) <= MAX_RESULT_BYTES - 1024:
        payload["attachments"] = attachments
    else:
        payload["attachment_omitted"] = (
            "attachment exceeds the sandbox response limit; "
            "the file is available at output_path"
        )


def _flatten_for_jpeg(image: Any) -> Any:
    """Composite an alpha-bearing image onto white for JPEG output,
    matching the host tools (a direct RGB conversion turns
    transparent pixels black)."""
    from PIL import Image

    if image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    ):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[3])
        return background
    return image.convert("RGB")


def _svg_to_image(args: dict[str, Any]) -> str:
    svg_rel = str(args.get("svg") or "").strip()
    out_rel = str(args.get("output_path") or "").strip()
    if not svg_rel:
        return json.dumps({"ok": False, "error": "svg is required"}, ensure_ascii=False)
    if not out_rel:
        return json.dumps(
            {"ok": False, "error": "output_path is required"},
            ensure_ascii=False,
        )
    svg_path = _resolve_relative(svg_rel)
    if not svg_path.is_file():
        return json.dumps(
            {"ok": False, "error": f"SVG file was not found: {svg_rel}"},
            ensure_ascii=False,
        )
    if svg_path.suffix.lower() != ".svg":
        return json.dumps(
            {"ok": False, "error": "input file must end in .svg"},
            ensure_ascii=False,
        )
    output_path = _resolve_relative(out_rel)
    if output_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        return json.dumps(
            {
                "ok": False,
                "error": "output_path must end in .png, .jpg, .jpeg, or .webp",
            },
            ensure_ascii=False,
        )
    if output_path.exists() and not bool(args.get("overwrite")):
        return json.dumps(
            {"ok": False, "error": f"output already exists: {out_rel}"},
            ensure_ascii=False,
        )
    cairosvg = _ensure_package("cairosvg")
    if cairosvg is None:
        return json.dumps(
            {
                "ok": False,
                "error": "CairoSVG is not available in the sandbox "
                "environment and could not be installed automatically.",
            },
            ensure_ascii=False,
        )
    render_kwargs: dict[str, Any] = {
        "bytestring": svg_path.read_bytes(),
    }
    if args.get("width"):
        render_kwargs["output_width"] = int(args["width"])
    if args.get("height"):
        render_kwargs["output_height"] = int(args["height"])
    if args.get("scale"):
        render_kwargs["scale"] = float(args["scale"])
    if args.get("background"):
        render_kwargs["background_color"] = str(args["background"])
    try:
        png_bytes = cairosvg.svg2png(**render_kwargs)
    except Exception as exc:
        return json.dumps(
            {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
            ensure_ascii=False,
        )
    suffix = output_path.suffix.lower()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if suffix == ".png":
        output_path.write_bytes(png_bytes)
    else:
        try:
            from PIL import Image
        except ImportError:
            return json.dumps(
                {
                    "ok": False,
                    "error": "Pillow is required to write non-PNG output.",
                },
                ensure_ascii=False,
            )
        image = Image.open(io.BytesIO(png_bytes))
        if suffix in {".jpg", ".jpeg"}:
            image = _flatten_for_jpeg(image)
        image.save(output_path)
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }[suffix]
    payload: dict[str, Any] = {
        "ok": True,
        "output_path": out_rel,
        "format": suffix.lstrip("."),
        "bytes": output_path.stat().st_size,
    }
    attachments = _media_attachment(
        out_rel,
        output_path.read_bytes(),
        mime,
        include=bool(args.get("include_base64", True)),
    )
    _attach_within_budget(payload, attachments)
    return json.dumps(payload, ensure_ascii=False)


def _mermaid_render_core(source: str, theme: str) -> tuple[Any, str]:
    mermaidx = _ensure_package("mermaidx")
    if mermaidx is None:
        raise ImportError("mermaidx is not available")
    diagram = mermaidx.render(source, theme=theme or "default")
    return diagram, diagram.svg()


def _mermaid_render(args: dict[str, Any]) -> str:
    source = str(args.get("source") or "")
    input_rel = str(args.get("input_path") or "")
    if bool(source) == bool(input_rel):
        return json.dumps(
            {
                "ok": False,
                "error": "specify exactly one of source or input_path",
            },
            ensure_ascii=False,
        )
    out_rel = str(args.get("output_path") or "")
    if not out_rel:
        return json.dumps(
            {"ok": False, "error": "output_path is required"},
            ensure_ascii=False,
        )
    output_path = _resolve_relative(out_rel)
    if output_path.suffix.lower() not in {".png", ".svg", ".pdf"}:
        return json.dumps(
            {
                "ok": False,
                "error": "output_path must end in .png, .svg, or .pdf",
            },
            ensure_ascii=False,
        )
    if input_rel:
        input_path = _resolve_relative(input_rel)
        if not input_path.is_file():
            return json.dumps(
                {"ok": False, "error": f"input file not found: {input_rel}"},
                ensure_ascii=False,
            )
        source = input_path.read_text(encoding="utf-8")
    try:
        diagram, svg = _mermaid_render_core(source, str(args.get("theme") or ""))
    except ImportError:
        return json.dumps(
            {
                "ok": False,
                "error": "mermaidx is not available in the sandbox "
                "environment and could not be installed automatically.",
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps(
            {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
            ensure_ascii=False,
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = output_path.suffix.lower()
    try:
        if suffix == ".svg":
            output_path.write_text(svg, encoding="utf-8")
        elif suffix == ".png":
            resvg_py = _ensure_package("resvg_py", "resvg-py")
            if resvg_py is None:
                return json.dumps(
                    {
                        "ok": False,
                        "error": "resvg_py is not available in the sandbox "
                        "environment for PNG output and could not be "
                        "installed automatically; use .svg instead.",
                    },
                    ensure_ascii=False,
                )
            rendered = resvg_py.svg_to_bytes(
                svg_string=svg,
                background=str(args.get("background") or "white"),
            )
            output_path.write_bytes(bytes(rendered))
        else:
            diagram.save(str(output_path), format="pdf")
    except Exception as exc:
        return json.dumps(
            {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
            ensure_ascii=False,
        )
    mime = {
        ".png": "image/png",
        ".svg": "image/svg+xml",
        ".pdf": "application/pdf",
    }[suffix]
    payload: dict[str, Any] = {
        "ok": True,
        "output_path": out_rel,
        "format": suffix.lstrip("."),
        "bytes": output_path.stat().st_size,
    }
    attachments = _media_attachment(
        out_rel,
        output_path.read_bytes(),
        mime,
        include=bool(args.get("include_base64", True)),
    )
    _attach_within_budget(payload, attachments)
    return json.dumps(payload, ensure_ascii=False)


def _mmd_to_svg(args: dict[str, Any]) -> str:
    mmd_rel = str(args.get("mmd") or "").strip()
    out_rel = str(args.get("output_path") or "").strip()
    if not mmd_rel:
        return json.dumps({"ok": False, "error": "mmd is required"}, ensure_ascii=False)
    if not out_rel:
        return json.dumps(
            {"ok": False, "error": "output_path is required"},
            ensure_ascii=False,
        )
    mmd_path = _resolve_relative(mmd_rel)
    if not mmd_path.is_file():
        return json.dumps(
            {"ok": False, "error": f"Mermaid file was not found: {mmd_rel}"},
            ensure_ascii=False,
        )
    if mmd_path.suffix.lower() not in {".mmd", ".mermaid"}:
        return json.dumps(
            {"ok": False, "error": "input file must end in .mmd or .mermaid"},
            ensure_ascii=False,
        )
    output_path = _resolve_relative(out_rel)
    if output_path.suffix.lower() != ".svg":
        return json.dumps(
            {"ok": False, "error": "output_path must end in .svg"},
            ensure_ascii=False,
        )
    source = mmd_path.read_text(encoding="utf-8")
    try:
        _diagram, svg = _mermaid_render_core(source, str(args.get("theme") or ""))
    except ImportError:
        return json.dumps(
            {
                "ok": False,
                "error": "mermaidx is not available in the sandbox "
                "environment and could not be installed automatically.",
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps(
            {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
            ensure_ascii=False,
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")
    payload: dict[str, Any] = {
        "ok": True,
        "output_path": out_rel,
        "format": "svg",
        "bytes": output_path.stat().st_size,
    }
    attachments = _media_attachment(
        out_rel,
        output_path.read_bytes(),
        "image/svg+xml",
        include=bool(args.get("include_base64", True)),
    )
    _attach_within_budget(payload, attachments)
    return json.dumps(payload, ensure_ascii=False)


def _preprocess_image(args: dict[str, Any]) -> str:
    img_rel = str(args.get("img") or "").strip()
    if not img_rel:
        return json.dumps(
            {"ok": False, "error": "[preprocess_image] image_path is required"},
            ensure_ascii=False,
        )
    img_path = _resolve_relative(img_rel)
    if not img_path.is_file():
        return json.dumps(
            {
                "ok": False,
                "error": f"[preprocess_image] image file not found: {img_rel}",
            },
            ensure_ascii=False,
        )
    try:
        from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    except ImportError:
        return json.dumps(
            {"ok": False, "error": "Pillow is not available in the sandbox."},
            ensure_ascii=False,
        )

    def _bool(value: Any, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).lower() in {"1", "true", "yes", "on"}

    mode = str(args.get("mode") or "ocr").strip().lower()
    grayscale = _bool(args.get("grayscale"), True)
    denoise = _bool(args.get("denoise"), True)
    binarize = _bool(args.get("binarize"), False)
    edge_enhance = _bool(args.get("edge_enhance"), False)
    deskew = _bool(args.get("deskew"), False)
    try:
        contrast = float(args.get("contrast") or 1.0)
    except (TypeError, ValueError):
        contrast = 1.0

    def _binarize(img: Any) -> Any:
        gray = ImageOps.grayscale(img)
        return gray.point(lambda p: 255 if p > 160 else 0)

    # The mode pipeline runs first (mirroring the host tool's
    # _apply_mode); the optional flags then compose on top of it.
    image = Image.open(img_path)
    image.load()
    ops: list[str] = []
    if mode == "ocr":
        image = ImageOps.grayscale(image)
        ops.append("grayscale")
        image = image.filter(ImageFilter.MedianFilter(size=3))
        ops.append("denoise")
        image = image.filter(ImageFilter.SHARPEN)
        ops.append("sharpen")
        image = image.point(lambda p: 255 if p > 180 else 0)
        ops.append("adaptive_threshold")
    elif mode == "document":
        image = ImageOps.grayscale(image)
        ops.append("grayscale")
        image = image.filter(ImageFilter.MedianFilter(size=3))
        ops.append("denoise")
        image = ImageOps.autocontrast(image)
        ops.append("contrast")
    elif mode == "diagram":
        image = ImageOps.grayscale(image)
        ops.append("grayscale")
        image = image.filter(ImageFilter.EDGE_ENHANCE_MORE)
        ops.append("edge_enhance")
        image = image.point(lambda p: 255 if p > 170 else 0)
        ops.append("threshold")
    elif mode == "photo":
        image = image.filter(ImageFilter.MedianFilter(size=3))
        ops.append("denoise")
        image = ImageOps.autocontrast(image)
        ops.append("contrast")
    elif mode == "custom":
        ops.append("custom")
    else:
        return json.dumps(
            {
                "ok": False,
                "error": f"invalid mode: {mode!r}. "
                "Use ocr/document/diagram/photo/custom.",
            },
            ensure_ascii=False,
        )

    if mode == "custom":
        if grayscale:
            image = ImageOps.grayscale(image)
            ops.append("grayscale")
        if denoise:
            image = image.filter(ImageFilter.MedianFilter(size=3))
            ops.append("denoise")
        if edge_enhance:
            image = image.filter(ImageFilter.EDGE_ENHANCE_MORE)
            ops.append("edge_enhance")
        if binarize:
            image = _binarize(image)
            ops.append("binarize")
        if abs(contrast - 1.0) > 1e-9:
            image = ImageEnhance.Contrast(image).enhance(contrast)
            ops.append(f"contrast={contrast}")
        if deskew:
            ops.append("deskew")
    else:
        if binarize:
            image = _binarize(image)
            ops.append("binarize")
        if edge_enhance:
            image = image.filter(ImageFilter.EDGE_ENHANCE_MORE)
            ops.append("edge_enhance")
        if deskew:
            ops.append("deskew")
        if abs(contrast - 1.0) > 1e-9:
            image = ImageEnhance.Contrast(image).enhance(contrast)
            ops.append(f"contrast={contrast}")

    resize = str(args.get("resize") or "").strip().lower()
    if resize:
        target: tuple[int, int] | None = None
        if resize.endswith("x") and resize[:-1].isdigit():
            factor = float(resize[:-1])
            target = (
                max(1, int(image.width * factor)),
                max(1, int(image.height * factor)),
            )
        elif "x" in resize:
            w_text, h_text = resize.split("x", 1)
            if w_text.strip().isdigit() and h_text.strip().isdigit():
                target = (max(1, int(w_text)), max(1, int(h_text)))
        if target is None:
            return json.dumps(
                {
                    "ok": False,
                    "error": f"invalid resize value: {resize!r}. "
                    "Use '2x' or '1600x1200'.",
                },
                ensure_ascii=False,
            )
        image = image.resize(target, Image.LANCZOS)
        ops.append(f"resize={target[0]}x{target[1]}")

    output_dir = _resolve_relative(
        str(args.get("output_dir") or "outputs/image_preprocess")
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = str(args.get("prefix") or "preprocess_image").strip() or "preprocess_image"
    # The prefix is caller-controlled: validate the complete destination
    # before saving so a prefix with separators or an absolute path can
    # never write outside the workspace.
    joined = (output_dir.relative_to(ROOT) / f"{prefix}_{img_path.stem}.png").as_posix()
    try:
        output_path = _resolve_relative(joined)
    except ValueError as exc:
        return json.dumps(
            {"ok": False, "error": f"invalid output path: {exc}"},
            ensure_ascii=False,
        )
    image.save(output_path, format="PNG")
    return json.dumps(
        {
            "ok": True,
            "output": output_path.relative_to(ROOT).as_posix(),
            "applied": ops,
            "width": image.width,
            "height": image.height,
        },
        ensure_ascii=False,
    )


def _alias_store_path(
    filename: str, *, create: bool = False, root: Path | None = None
) -> Path:
    store_dir = (root if root is not None else ROOT) / ".uag"
    if create:
        store_dir.mkdir(parents=True, exist_ok=True)
    return store_dir / filename


def _load_aliases(filename: str, root: Path | None = None) -> dict[int, str]:
    path = _alias_store_path(filename, root=root)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    result: dict[int, str] = {}
    if isinstance(data, dict):
        for key, value in data.items():
            try:
                slot = int(key)
            except (TypeError, ValueError):
                continue
            if 0 <= slot <= 9 and isinstance(value, str):
                result[slot] = value
    return result


def _save_aliases(filename: str, aliases: dict[int, str]) -> None:
    path = _alias_store_path(filename, create=True)
    payload = {str(slot): aliases[slot] for slot in sorted(aliases)}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _alias_slot(args: dict[str, Any]) -> int | None:
    try:
        slot = int(args.get("slot"))
    except (TypeError, ValueError):
        return None
    return slot if 0 <= slot <= 9 else None


def _path_alias(args: dict[str, Any]) -> str:
    def _result(**fields: Any) -> str:
        return json.dumps(fields, ensure_ascii=False)

    action = str(args.get("action") or "").strip().lower()
    aliases = _load_aliases("path_aliases.json")

    def label(slot: int) -> str:
        return f"@A{{{slot}}}"

    if action == "list":
        visible = {slot: str(ROOT / aliases[slot]) for slot in sorted(aliases)}
        if 0 not in visible:
            visible[0] = str(ROOT)
        return _result(
            ok=True,
            aliases={label(slot): visible[slot] for slot in sorted(visible)},
        )
    if action == "delete":
        slot = _alias_slot(args)
        if slot is None:
            return _result(ok=False, error="slot must be an integer from 0 to 9")
        if slot not in aliases:
            return _result(ok=False, error=f"alias not registered: {label(slot)}")
        del aliases[slot]
        _save_aliases("path_aliases.json", aliases)
        return _result(ok=True, deleted=label(slot))
    if action == "set":
        slot = _alias_slot(args)
        if slot is None:
            return _result(ok=False, error="slot must be an integer from 0 to 9")
        raw_path = str(args.get("path") or "").strip()
        if not raw_path:
            return _result(ok=False, error="path is required")
        if slot in aliases and not bool(args.get("overwrite", False)):
            return _result(ok=False, error=f"alias already registered: {label(slot)}")
        try:
            path = _resolve_relative(raw_path)
        except Exception:
            return _result(
                ok=False,
                error="path must be inside the sandbox workspace",
            )
        if not path.is_dir():
            return _result(ok=False, error="path must be an existing directory")
        relative = path.relative_to(ROOT)
        aliases[slot] = "" if str(relative) == "." else relative.as_posix()
        _save_aliases("path_aliases.json", aliases)
        return _result(ok=True, alias=label(slot))
    return _result(ok=False, error="action must be set, list, or delete")


def _url_alias(args: dict[str, Any]) -> str:
    def _result(**fields: Any) -> str:
        return json.dumps(fields, ensure_ascii=False)

    action = str(args.get("action") or "").strip().lower()
    aliases = _load_aliases("url_aliases.json")

    def label(slot: int) -> str:
        return f"@B{{{slot}}}"

    if action == "list":
        return _result(
            ok=True,
            aliases={label(slot): aliases[slot] for slot in sorted(aliases)},
        )
    if action == "delete":
        slot = _alias_slot(args)
        if slot is None:
            return _result(ok=False, error="slot must be an integer from 0 to 9")
        if slot not in aliases:
            return _result(ok=False, error=f"alias not registered: {label(slot)}")
        del aliases[slot]
        _save_aliases("url_aliases.json", aliases)
        return _result(ok=True, deleted=label(slot))
    if action == "set":
        slot = _alias_slot(args)
        if slot is None:
            return _result(ok=False, error="slot must be an integer from 0 to 9")
        raw_url = str(args.get("url") or "").strip()
        if not raw_url:
            return _result(ok=False, error="url is required")
        if not raw_url.startswith(("http://", "https://")):
            return _result(ok=False, error="url must start with http:// or https://")
        if slot in aliases and not bool(args.get("overwrite", False)):
            return _result(ok=False, error=f"alias already registered: {label(slot)}")
        aliases[slot] = raw_url
        _save_aliases("url_aliases.json", aliases)
        return _result(ok=True, alias=label(slot))
    return _result(ok=False, error="action must be set, list, or delete")


def _generate_prompt(args: dict[str, Any]) -> str:
    raw_path = str(args.get("path") or args.get("filename") or "").strip()
    if not raw_path:
        return "[generate_prompt error] path/filename is not specified"
    template = str(args.get("template") or "")
    if not template:
        return "[generate_prompt error] template is not specified"
    try:
        path = _resolve_relative(raw_path)
    except Exception as exc:
        return f"[generate_prompt error] {type(exc).__name__}: {exc}"
    if not path.is_file():
        return f"[generate_prompt error] not a file: {raw_path}"
    content = path.read_text(encoding="utf-8", errors="replace")
    lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
    vars_map: dict[str, Any] = {
        "content": content,
        "lines": lines,
        "bytes": path.stat().st_size,
        "basename": path.name,
        "path": str(path),
    }
    try:
        return template.format(**vars_map)
    except Exception as exc:
        return f"[generate_prompt error] {type(exc).__name__}: {exc}"


# Alias expansion happens inside the sandbox dispatch boundary: the host
# resolves @A{...} / @B{...} tokens against its own ~/.uag store before
# routing, which cannot see aliases registered here, so sandbox-routed
# calls skip the host resolver and expand here against the workspace
# store instead. The field sets mirror the host's path_alias_shared.
_PATH_FIELD_NAMES = {
    "path",
    "file",
    "filename",
    "file_path",
    "filepath",
    "current_file",
    "output_path",
    "input_path",
    "db_path",
    "json_path",
    "log_path",
    "pcap_path",
    "img",
    "image",
    "mask_path",
    "zip_path",
    "dest_dir",
    "destination",
    "output_dir",
    "outdir",
    "root",
    "root_path",
    "root_dir",
    "cwd",
    "new_dir",
    "source",
    "sources",
    "relative_path",
    "file_pattern",
    "download_dir",
    "trace_path",
    "record_video_dir",
    "storage_state",
    "skill_dir",
    "sheets_dir",
    "print_areas_dir",
    "auto_page_breaks_dir",
    "exclude_dirs",
    "path1",
    "path2",
    "render_path",
}
_URL_FIELD_NAMES = {
    "url",
    "url_pattern",
    "url_contains",
    "base_url",
    "business_url",
    "location",
    "redirect_uri",
}
_SANDBOX_ALIAS_RE = re.compile(r"^@A\{([0-9])\}(?:[\\/](.*))?$")
_SANDBOX_URL_ALIAS_RE = re.compile(r"^@B\{([0-9])\}(.*)$")


def _resolve_sandbox_path_alias(value: str, root: Path | None = None) -> str:
    match = _SANDBOX_ALIAS_RE.match(value)
    if not match:
        return value
    slot = int(match.group(1))
    aliases = _load_aliases("path_aliases.json", root)
    root_rel = aliases.get(slot)
    if root_rel is None and slot == 0:
        root_rel = ""
    if root_rel is None:
        raise ValueError(f"unknown path alias: @A{{{slot}}}")
    relative = match.group(2) or ""
    parts: list[str] = []
    for part in relative.replace("\\", "/").split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                raise ValueError("path escapes alias root")
            parts.pop()
        else:
            parts.append(part)
    joined = "/".join(p for p in [root_rel, *parts] if p)
    return joined if joined else "."


def _resolve_sandbox_url_alias(value: str, root: Path | None = None) -> str:
    match = _SANDBOX_URL_ALIAS_RE.match(value)
    if not match:
        return value
    slot = int(match.group(1))
    aliases = _load_aliases("url_aliases.json", root)
    base = aliases.get(slot)
    if base is None:
        raise ValueError(f"unknown URL alias: @B{{{slot}}}")
    suffix = match.group(2)
    if suffix and not suffix.startswith(("/", "?", "#")):
        raise ValueError("URL alias suffix must start with '/', '?' or '#'")
    return base.rstrip("/") + suffix


def _expand_sandbox_aliases(
    value: Any, field_name: str | None = None, root: Path | None = None
) -> Any:
    if isinstance(value, str):
        if field_name in _PATH_FIELD_NAMES:
            return _resolve_sandbox_path_alias(value, root)
        if field_name in _URL_FIELD_NAMES:
            return _resolve_sandbox_url_alias(value, root)
        return value
    if isinstance(value, list):
        if field_name in _PATH_FIELD_NAMES:
            return [
                (
                    _resolve_sandbox_path_alias(item, root)
                    if isinstance(item, str)
                    else item
                )
                for item in value
            ]
        if field_name in _URL_FIELD_NAMES:
            return [
                (
                    _resolve_sandbox_url_alias(item, root)
                    if isinstance(item, str)
                    else item
                )
                for item in value
            ]
        return [_expand_sandbox_aliases(item, root=root) for item in value]
    if isinstance(value, dict):
        return {
            key: _expand_sandbox_aliases(item, str(key), root)
            for key, item in value.items()
        }
    return value


def expand_aliases_in_args(args: dict[str, Any], workspace_root: Any) -> dict[str, Any]:
    """Expand @A{}/@B{} alias tokens in tool args against the alias
    stores of an explicit workspace. Used by the host backend for the
    one-shot exec tools, which never pass through this worker's
    dispatch loop."""
    return _expand_sandbox_aliases(args, root=Path(workspace_root))


def _dispatch(request: Any) -> Any:
    if not isinstance(request, dict) or request.get("name") not in _ALLOWED:
        raise ValueError("tool is not in the local sandbox allowlist")
    name = request["name"]
    args = request.get("args", {})
    if not isinstance(args, dict):
        raise ValueError("tool arguments must be an object")
    if name in {"python_exec", "command_exec"}:
        raise RuntimeError(
            f"{name} must use a one-shot MXC container, not the persistent worker"
        )
    args = _expand_sandbox_aliases(args)
    if name == "create_file":
        return _create_file(args)
    handlers = {
        "list_dir": _list_dir,
        "search_files": _search_files,
        "file_grep": _file_grep,
        "file_hash": _file_hash,
        "wc": _wc,
        "rename_path": _rename_path,
        "delete_files": _delete_files,
        "replace_in_file": _replace_in_file,
        "diff_files": _diff_files,
        "archive_ops": _archive_ops,
        "document_extract": _document_extract,
        "structured_data": _structured_data,
        "sqlite_query": _sqlite_query,
        "calculate": _calculate,
        "python_ast": _python_ast,
        "parse_eml": _parse_eml,
        "file_type": _file_type,
        "image_ops": _image_ops,
        "qr_code": _qr_code,
        "binary_edit": _binary_edit,
        "security_scan": _security_scan,
        "git_ops": _git_ops,
        "get_weather_wttr": _get_weather_wttr,
        "get_current_time": _get_current_time,
        "geodesic_distance": _geodesic_distance,
        "date_calc": _date_calc,
        "quantities": _quantities,
        "zipcode_check": _zipcode_check,
        "reverse_geocode": _reverse_geocode,
        "http_request": _http_request,
        "apply_patch": _apply_patch,
        "svg_to_image": _svg_to_image,
        "mermaid_render": _mermaid_render,
        "mmd_to_svg": _mmd_to_svg,
        "preprocess_image": _preprocess_image,
        "path_alias": _path_alias,
        "url_alias": _url_alias,
        "generate_prompt": _generate_prompt,
    }
    if name in handlers:
        return handlers[name](args)
    if name == "file_exists":
        target = _resolve_relative(args.get("path"))
        return json.dumps(
            {
                "exists": target.exists(),
                "is_file": target.is_file(),
                "is_dir": target.is_dir(),
            }
        )
    return _read_file(args)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _emit({"ready": True})
    for line in sys.stdin.buffer:
        if len(line) > MAX_FRAME_BYTES:
            _emit(
                {
                    "ok": False,
                    "error": "tool request exceeds the IPC size limit",
                    "terminate": True,
                }
            )
            return 2
        try:
            request = json.loads(line.decode("utf-8"))
            result = _dispatch(request)
            _emit({"ok": True, "result": result})
        except Exception as exc:
            _emit({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
