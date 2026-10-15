"""Small, fixed-contract worker used only inside a verified MXC container."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

MAX_FRAME_BYTES = 1_100_000
MAX_RESULT_BYTES = 900_000
MAX_TEXT_BYTES = 1_000_000
_ALLOWED = {"create_file", "file_exists", "read_file", "python_exec"}
ROOT = Path.cwd().resolve()


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
        MAX_TEXT_BYTES,
        max(1, int(args.get("max_bytes", MAX_TEXT_BYTES) or MAX_TEXT_BYTES)),
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
