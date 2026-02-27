from __future__ import annotations

import binascii
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from .context import get_callbacks
from .human_ask_tool import run_tool as human_ask
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


Mode = Literal["write", "replace", "splice", "apply_patch"]


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "binary_edit",
        "description": _(
            "tool.description",
            default=(
                "Edit a local file as raw bytes (binary). Supports offset write, search/replace, splice (insert/delete), "
                "and applying a simple JSON patch. Dangerous: this tool can corrupt files."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "This tool is used for the following purpose: edit a local file as raw bytes (binary).\n\n"
                "SECURITY / SAFETY:\n"
                "- This tool modifies local files and can corrupt them.\n"
                "- Always request confirmation with human_ask before writing.\n"
                "- Do not operate on paths outside the current workdir when running under the host agent's safety policies.\n"
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Target file path."},
                "mode": {
                    "type": "string",
                    "enum": ["write", "replace", "splice", "apply_patch"],
                    "description": "Edit mode.",
                },
                "dry_run": {
                    "type": "boolean",
                    "default": False,
                    "description": "If true, do not modify the file; only report what would change.",
                },
                "max_bytes": {
                    "type": "integer",
                    "default": 200000000,
                    "description": "Reject files larger than this size (bytes).",
                },
                "offset": {
                    "type": "integer",
                    "description": "Byte offset (0-based). Required for write/splice.",
                },
                "data_hex": {
                    "type": "string",
                    "description": "Hex string of bytes to write/insert (e.g. 'DEADBEEF' or 'DE AD BE EF').",
                },
                "search_hex": {
                    "type": "string",
                    "description": "Hex string to search for (replace mode).",
                },
                "replace_hex": {
                    "type": "string",
                    "description": "Hex string to replace with (replace mode). Must be same length as search_hex unless allow_resize=true (not supported).",
                },
                "occurrence": {
                    "type": "integer",
                    "default": 1,
                    "description": "Which occurrence to replace (1-based). 0 means replace all occurrences (still requires same length).",
                },
                "splice_op": {
                    "type": "string",
                    "enum": ["insert", "delete"],
                    "description": "Splice operation (splice mode).",
                },
                "delete_len": {
                    "type": "integer",
                    "description": "Number of bytes to delete (splice delete).",
                },
                "patch_json": {
                    "type": "string",
                    "description": "JSON string patch (apply_patch mode).",
                },
            },
            "required": ["path", "mode"],
            "additionalProperties": False,
        },
    },
    "is_agent_content": False,
}


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _normalize_hex(s: str) -> str:
    s2 = (s or "").strip()
    s2 = s2.replace(" ", "").replace("\t", "").replace("\r", "").replace("\n", "")
    if s2.lower().startswith("0x"):
        s2 = s2[2:]
    if s2 == "":
        return ""
    if len(s2) % 2 != 0:
        raise ValueError("hex length must be even")
    # validate
    try:
        bytes.fromhex(s2)
    except ValueError as e:
        raise ValueError(f"invalid hex: {e}")
    return s2


def _hex_to_bytes(s: str) -> bytes:
    s2 = _normalize_hex(s)
    return bytes.fromhex(s2) if s2 else b""


def _format_preview_bytes(b: bytes, limit: int = 64) -> str:
    bb = b[:limit]
    hx = binascii.hexlify(bb).decode("ascii")
    if len(b) > limit:
        return hx + "..."
    return hx


@dataclass
class OpResult:
    op: str
    changed: bool
    detail: str


def _confirm_or_cancel(message: str) -> None:
    res_json = human_ask({"message": message, "is_password": False})
    res = json.loads(res_json)
    ans = (res.get("user_reply") or "").strip().lower()
    if ans not in ("y", "yes"):
        raise SystemExit("[binary_edit] cancelled")


def _ensure_file_ok(path: Path, *, max_bytes: int) -> Tuple[int, str]:
    if not path.exists():
        raise SystemExit(f"[binary_edit] file not found: {path}")
    if not path.is_file():
        raise SystemExit(f"[binary_edit] not a file: {path}")
    size = path.stat().st_size
    if size > int(max_bytes):
        raise SystemExit(
            f"[binary_edit] file too large: {size} bytes (limit={max_bytes})"
        )
    sha = _sha256_file(path)
    return size, sha


def _read_all(path: Path) -> bytearray:
    return bytearray(path.read_bytes())


def _write_all(path: Path, data: bytearray) -> None:
    path.write_bytes(bytes(data))


def _op_write(data: bytearray, *, offset: int, patch: bytes) -> OpResult:
    if offset < 0:
        raise SystemExit("[binary_edit] offset must be >= 0")
    end = offset + len(patch)
    if end > len(data):
        raise SystemExit(
            f"[binary_edit] write out of range: offset={offset}, len={len(patch)}, file_size={len(data)}"
        )
    before = bytes(data[offset:end])
    if before == patch:
        return OpResult("write", False, "bytes already match")
    data[offset:end] = patch
    return OpResult(
        "write",
        True,
        f"offset=0x{offset:X} len={len(patch)} before={_format_preview_bytes(before)} after={_format_preview_bytes(patch)}",
    )


def _find_nth(hay: bytes, needle: bytes, occurrence: int) -> List[int]:
    if needle == b"":
        raise SystemExit("[binary_edit] search pattern is empty")
    idxs: List[int] = []
    start = 0
    while True:
        i = hay.find(needle, start)
        if i < 0:
            break
        idxs.append(i)
        start = i + 1
        if occurrence > 0 and len(idxs) >= occurrence:
            break
    return idxs


def _op_replace(
    data: bytearray,
    *,
    search: bytes,
    repl: bytes,
    occurrence: int,
) -> OpResult:
    if len(search) != len(repl):
        raise SystemExit(
            "[binary_edit] replace requires same length (size-changing replace is not supported)"
        )

    hay = bytes(data)

    if occurrence == 0:
        idxs = _find_nth(hay, search, occurrence=-1)  # all
    else:
        idxs = _find_nth(hay, search, occurrence=occurrence)

    if not idxs:
        return OpResult("replace", False, "pattern not found")

    # If occurrence != 0, we only have one index.
    changed_count = 0
    for i in idxs:
        before = bytes(data[i : i + len(search)])
        if before == repl:
            continue
        data[i : i + len(search)] = repl
        changed_count += 1

    if changed_count == 0:
        return OpResult("replace", False, "already replaced")

    return OpResult(
        "replace",
        True,
        f"replaced {changed_count} occurrence(s); len={len(search)}",
    )


def _op_splice_insert(data: bytearray, *, offset: int, ins: bytes) -> OpResult:
    if offset < 0:
        raise SystemExit("[binary_edit] offset must be >= 0")
    if offset > len(data):
        raise SystemExit(
            f"[binary_edit] insert out of range: offset={offset}, file_size={len(data)}"
        )
    if ins == b"":
        return OpResult("splice_insert", False, "nothing to insert")
    data[offset:offset] = ins
    return OpResult(
        "splice_insert",
        True,
        f"offset=0x{offset:X} insert_len={len(ins)} data={_format_preview_bytes(ins)}",
    )


def _op_splice_delete(data: bytearray, *, offset: int, delete_len: int) -> OpResult:
    if offset < 0:
        raise SystemExit("[binary_edit] offset must be >= 0")
    if delete_len <= 0:
        raise SystemExit("[binary_edit] delete_len must be > 0")
    end = offset + delete_len
    if end > len(data):
        raise SystemExit(
            f"[binary_edit] delete out of range: offset={offset}, delete_len={delete_len}, file_size={len(data)}"
        )
    before = bytes(data[offset:end])
    del data[offset:end]
    return OpResult(
        "splice_delete",
        True,
        f"offset=0x{offset:X} delete_len={delete_len} deleted={_format_preview_bytes(before)}",
    )


def _parse_patch_json(patch_json: str) -> List[Dict[str, Any]]:
    try:
        obj = json.loads(patch_json)
    except Exception as e:
        raise SystemExit(f"[binary_edit] invalid patch_json: {type(e).__name__}: {e}")

    if not isinstance(obj, dict):
        raise SystemExit("[binary_edit] patch_json must be a JSON object")

    ops = obj.get("operations")
    if not isinstance(ops, list) or not ops:
        raise SystemExit("[binary_edit] patch_json.operations must be a non-empty list")

    out: List[Dict[str, Any]] = []
    for i, op in enumerate(ops):
        if not isinstance(op, dict):
            raise SystemExit(f"[binary_edit] operations[{i}] must be an object")
        out.append(op)
    return out


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()

    path_s = str(args.get("path") or "").strip()
    if not path_s:
        raise SystemExit("[binary_edit] path is required")

    mode: Mode = args.get("mode")  # type: ignore[assignment]
    if mode not in ("write", "replace", "splice", "apply_patch"):
        raise SystemExit("[binary_edit] invalid mode")

    dry_run = bool(args.get("dry_run", False))
    max_bytes = int(args.get("max_bytes", 200_000_000))

    p = Path(path_s)
    before_size, before_sha = _ensure_file_ok(p, max_bytes=max_bytes)

    # Load
    data = _read_all(p)

    # Execute
    results: List[OpResult] = []

    if mode == "write":
        if "offset" not in args:
            raise SystemExit("[binary_edit] offset is required for write")
        offset = int(args.get("offset"))
        patch = _hex_to_bytes(str(args.get("data_hex") or ""))
        if patch == b"":
            raise SystemExit("[binary_edit] data_hex is required for write")
        results.append(_op_write(data, offset=offset, patch=patch))

    elif mode == "replace":
        search = _hex_to_bytes(str(args.get("search_hex") or ""))
        repl = _hex_to_bytes(str(args.get("replace_hex") or ""))
        if not search:
            raise SystemExit("[binary_edit] search_hex is required")
        if not repl and repl != b"":
            raise SystemExit("[binary_edit] replace_hex is required")
        occurrence = int(args.get("occurrence", 1))
        results.append(_op_replace(data, search=search, repl=repl, occurrence=occurrence))

    elif mode == "splice":
        if "offset" not in args:
            raise SystemExit("[binary_edit] offset is required for splice")
        offset = int(args.get("offset"))
        splice_op = str(args.get("splice_op") or "").strip().lower()
        if splice_op not in ("insert", "delete"):
            raise SystemExit("[binary_edit] splice_op must be 'insert' or 'delete'")
        if splice_op == "insert":
            ins = _hex_to_bytes(str(args.get("data_hex") or ""))
            if not ins:
                raise SystemExit("[binary_edit] data_hex is required for splice insert")
            results.append(_op_splice_insert(data, offset=offset, ins=ins))
        else:
            if "delete_len" not in args:
                raise SystemExit("[binary_edit] delete_len is required for splice delete")
            delete_len = int(args.get("delete_len"))
            results.append(_op_splice_delete(data, offset=offset, delete_len=delete_len))

    elif mode == "apply_patch":
        patch_json = str(args.get("patch_json") or "")
        if not patch_json.strip():
            raise SystemExit("[binary_edit] patch_json is required")
        ops = _parse_patch_json(patch_json)
        for op in ops:
            op_type = str(op.get("op") or "").strip().lower()
            if op_type == "write":
                offset = int(op.get("offset"))
                patch = _hex_to_bytes(str(op.get("data_hex") or ""))
                if not patch:
                    raise SystemExit("[binary_edit] patch op write requires data_hex")
                results.append(_op_write(data, offset=offset, patch=patch))
            elif op_type == "insert":
                offset = int(op.get("offset"))
                ins = _hex_to_bytes(str(op.get("data_hex") or ""))
                if not ins:
                    raise SystemExit("[binary_edit] patch op insert requires data_hex")
                results.append(_op_splice_insert(data, offset=offset, ins=ins))
            elif op_type == "delete":
                offset = int(op.get("offset"))
                delete_len = int(op.get("delete_len"))
                results.append(_op_splice_delete(data, offset=offset, delete_len=delete_len))
            elif op_type == "replace":
                search = _hex_to_bytes(str(op.get("search_hex") or ""))
                repl = _hex_to_bytes(str(op.get("replace_hex") or ""))
                occurrence = int(op.get("occurrence", 1))
                results.append(_op_replace(data, search=search, repl=repl, occurrence=occurrence))
            else:
                raise SystemExit(f"[binary_edit] unknown patch op: {op_type}")

    any_changed = any(r.changed for r in results)
    after_size = len(data)

    # Confirm (always for non-dry-run)
    if not dry_run:
        # Stronger wording for resize operations
        resized = after_size != before_size
        ops_summary = "\n".join([f"- {r.op}: {r.detail}" for r in results]) or "(no ops)"
        msg = (
            "[binary_edit] This tool will modify a local file.\n\n"
            f"Path: {os.path.abspath(str(p))}\n"
            f"Mode: {mode}\n"
            f"Dry-run: {dry_run}\n"
            f"Before: size={before_size} sha256={before_sha}\n"
            f"After : size={after_size} (predicted)\n\n"
            "Operations:\n"
            f"{ops_summary}\n\n"
        )
        if resized:
            msg += (
                "WARNING: This operation changes file size (insert/delete). This may corrupt executable/binary formats.\n"
            )
        msg += "Proceed? Reply with y to write, or n/cancel to abort."
        _confirm_or_cancel(msg)

    if dry_run:
        payload = {
            "ok": True,
            "dry_run": True,
            "path": str(p),
            "mode": mode,
            "before_size": before_size,
            "after_size": after_size,
            "sha256_before": before_sha,
            "would_write": bool(any_changed),
            "operations": [r.__dict__ for r in results],
        }
        return json.dumps(payload, ensure_ascii=False)

    # Write
    if any_changed:
        _write_all(p, data)

    after_sha = _sha256_file(p)

    payload = {
        "ok": True,
        "dry_run": False,
        "path": str(p),
        "mode": mode,
        "before_size": before_size,
        "after_size": after_size,
        "sha256_before": before_sha,
        "sha256_after": after_sha,
        "changed": bool(any_changed),
        "operations": [r.__dict__ for r in results],
    }
    return json.dumps(payload, ensure_ascii=False)
