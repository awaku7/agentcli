"""Small, fixed-contract worker used only inside a verified MXC container."""

from __future__ import annotations

import ast
import csv
import difflib
from collections import deque
import fnmatch
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
    "delete_file",
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


def _delete_file(args: dict[str, Any]) -> str:
    if not bool(args.get("confirmed", False)):
        raise PermissionError("confirmed=true is required for deletion")
    target = _resolve_relative(args.get("filename"))
    if target == ROOT:
        raise PermissionError("the workspace root cannot be deleted")
    if not target.exists():
        if bool(args.get("skip", False)):
            return "Path does not exist; nothing deleted"
        raise FileNotFoundError("path does not exist")
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    return f"Deleted {target.relative_to(ROOT).as_posix()}"


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
            result = result.convert("RGB")
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


def _dispatch(request: Any) -> Any:
    if not isinstance(request, dict) or request.get("name") not in _ALLOWED:
        raise ValueError("tool is not in the local sandbox allowlist")
    name = request["name"]
    args = request.get("args", {})
    if not isinstance(args, dict):
        raise ValueError("tool arguments must be an object")
    if name == "python_exec":
        raise RuntimeError(
            "python_exec must use a one-shot MXC container, not the persistent worker"
        )
    if name == "create_file":
        return _create_file(args)
    handlers = {
        "list_dir": _list_dir,
        "search_files": _search_files,
        "file_grep": _file_grep,
        "file_hash": _file_hash,
        "wc": _wc,
        "rename_path": _rename_path,
        "delete_file": _delete_file,
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
