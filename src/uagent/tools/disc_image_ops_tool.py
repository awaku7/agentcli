from __future__ import annotations

import json
import os
import posixpath
import shutil
import subprocess
import sysconfig
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

from .._pip_auto import install_with_status
from .i18n_helper import make_tool_translator
from .safe_file_ops_extras import ensure_within_workdir, is_path_dangerous

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:disc_image_ops"

TOOL_SPEC: dict[str, Any] = {
    "load_order": -1,
    "type": "function",
    "tool_genre": "file",
    "function": {
        "name": "disc_image_ops",
        "description": _(
            "tool.description",
            default=(
                "Inspect, list, verify, extract, or convert ISO and CHD disc images. "
                "ISO operations use pycdlib; CHD operations use xverter. Optional "
                "Python dependencies are auto-installed according to UAGENT_AUTO_INSTALL."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "iso",
                "chd",
                "disc image",
                "disk image",
                "iso extract",
                "iso list",
                "chd verify",
                "chd convert",
                "rom image",
            ],
        ),
        "x_search_terms_en": [
            "iso",
            "chd",
            "disc image",
            "disk image",
            "iso extract",
            "iso list",
            "chd verify",
            "chd convert",
            "rom image",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["info", "list", "verify", "extract", "convert"],
                    "description": _(
                        "param.action.description",
                        default="Operation to perform.",
                    ),
                },
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Input ISO or CHD path under the current workdir.",
                    ),
                },
                "output": {
                    "type": "string",
                    "default": "",
                    "description": _(
                        "param.output.description",
                        default=(
                            "Destination path for extract/convert. Convert supports ISO to CHD "
                            "or CHD to ISO through xverter; extract uses a directory."
                        ),
                    ),
                },
                "path_type": {
                    "type": "string",
                    "enum": ["auto", "iso9660", "rockridge", "joliet", "udf"],
                    "default": "auto",
                    "description": _(
                        "param.path_type.description",
                        default=(
                            "ISO filename namespace to use. auto prefers UDF, Rock Ridge, "
                            "then Joliet."
                        ),
                    ),
                },
                "deep": {
                    "type": "boolean",
                    "default": False,
                    "description": _(
                        "param.deep.description",
                        default=(
                            "For ISO verify, read every file byte. CHD verify always uses "
                            "xverter integrity verification."
                        ),
                    ),
                },
                "overwrite": {
                    "type": "boolean",
                    "default": False,
                    "description": _(
                        "param.overwrite.description",
                        default=(
                            "Allow replacing existing output files or extracting into a "
                            "non-empty directory."
                        ),
                    ),
                },
                "timeout_seconds": {
                    "type": "integer",
                    "default": 3600,
                    "minimum": 1,
                    "maximum": 86400,
                    "description": _(
                        "param.timeout_seconds.description",
                        default="Maximum time for CHD info/verify/convert operations.",
                    ),
                },
            },
            "required": ["action", "path"],
            "additionalProperties": False,
        },
    },
}


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _ensure_pycdlib() -> bool:
    return install_with_status(
        "pycdlib",
        "pycdlib",
        display_name="pycdlib",
        version_spec=">=1.21.0",
    )


def _ensure_xverter() -> bool:
    return install_with_status(
        "xverter",
        "xverter",
        display_name="xverter",
        version_spec=">=1.5.0",
    )


def _safe_input(path: str) -> str:
    if is_path_dangerous(path):
        raise PermissionError("input path is outside workdir or contains '..'")
    resolved = ensure_within_workdir(path)
    if not os.path.isfile(resolved):
        raise FileNotFoundError(f"input file not found: {path}")
    return resolved


def _safe_output(path: str) -> str:
    if not path:
        raise ValueError("output is required for this action")
    if is_path_dangerous(path):
        raise PermissionError("output path is outside workdir or contains '..'")
    return ensure_within_workdir(path)


def _detect_format(path: str) -> str:
    try:
        with open(path, "rb") as fp:
            head = fp.read(8)
            if head == b"MComprHD":
                return "chd"
            fp.seek(16 * 2048 + 1)
            if fp.read(5) == b"CD001":
                return "iso"
    except OSError:
        pass
    suffix = Path(path).suffix.lower()
    if suffix == ".chd":
        return "chd"
    if suffix in {".iso", ".udf"}:
        return "iso"
    raise ValueError("unsupported disc image format; expected ISO or CHD")


def _select_namespace(iso: Any, requested: str) -> tuple[str, str]:
    req = (requested or "auto").strip().lower()
    if req == "auto":
        if iso.has_udf():
            return "udf_path", "udf"
        if iso.has_rock_ridge():
            return "rr_path", "rockridge"
        if iso.has_joliet():
            return "joliet_path", "joliet"
        return "iso_path", "iso9660"
    mapping = {
        "iso9660": ("iso_path", "iso9660"),
        "rockridge": ("rr_path", "rockridge"),
        "joliet": ("joliet_path", "joliet"),
        "udf": ("udf_path", "udf"),
    }
    if req not in mapping:
        raise ValueError(f"invalid path_type: {requested}")
    key, label = mapping[req]
    if key == "rr_path" and not iso.has_rock_ridge():
        raise ValueError("ISO does not contain Rock Ridge names")
    if key == "joliet_path" and not iso.has_joliet():
        raise ValueError("ISO does not contain Joliet names")
    if key == "udf_path" and not iso.has_udf():
        raise ValueError("ISO does not contain UDF names")
    return key, label


def _iso_entries(iso: Any, path_key: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for dirname, dirlist, filelist in iso.walk(**{path_key: "/"}):
        for name in dirlist:
            full = posixpath.join(dirname.rstrip("/"), str(name)) or "/"
            if not full.startswith("/"):
                full = "/" + full
            entries.append({"path": full, "type": "directory"})
        for name in filelist:
            full = posixpath.join(dirname.rstrip("/"), str(name))
            if not full.startswith("/"):
                full = "/" + full
            size = None
            try:
                rec = iso.get_record(**{path_key: full})
                size = int(getattr(rec, "data_length", 0) or 0)
            except Exception:
                pass
            item: dict[str, Any] = {"path": full, "type": "file"}
            if size is not None:
                item["size"] = size
            entries.append(item)
    entries.sort(key=lambda item: (item["path"].casefold(), item["type"]))
    return entries


def _safe_member_relative(path: str) -> Path:
    raw = str(path).replace("\\", "/").lstrip("/")
    parts = [part for part in PurePosixPath(raw).parts if part not in {"", "."}]
    if not parts or any(part == ".." for part in parts):
        raise ValueError(f"unsafe image member path: {path}")
    if any(":" in part for part in parts):
        raise ValueError(f"unsafe image member path: {path}")
    return Path(*parts)


def _confirm_overwrite(message: str) -> bool:
    try:
        from .human_ask_tool import run_tool as human_ask

        result = json.loads(human_ask({"message": message}))
        reply = str(result.get("user_reply", "") or "").strip().lower()
        return reply in {"y", "yes"}
    except Exception:
        try:
            reply = input(message + " [y/N]: ")
            return reply.strip().lower() in {"y", "yes"}
        except Exception:
            return False


def _prepare_extract_dir(path: str, overwrite: bool) -> str:
    output = _safe_output(path)
    target = Path(output)
    if target.exists() and not target.is_dir():
        raise FileExistsError(f"extract output exists and is not a directory: {path}")
    if target.exists() and any(target.iterdir()):
        if not overwrite:
            raise FileExistsError(
                "extract output directory is not empty; set overwrite=true to continue"
            )
        if not _confirm_overwrite(
            _(
                "confirm.extract_overwrite",
                default="disc_image_ops may overwrite files under: %(path)s",
                path=target,
            )
        ):
            raise PermissionError("overwrite was not confirmed")
    target.mkdir(parents=True, exist_ok=True)
    return str(target)


def _paths_alias(source: str, output: str) -> bool:
    src = Path(source).resolve()
    dst = Path(output).resolve()
    if src == dst:
        return True
    if dst.exists():
        try:
            return os.path.samefile(src, dst)
        except OSError:
            pass
    return False


def _prepare_output_file(
    path: str,
    overwrite: bool,
    *,
    source: str = "",
) -> str:
    output = _safe_output(path)
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    if source and _paths_alias(source, str(target)):
        raise ValueError("source and output must refer to different files")
    if target.exists() and target.is_dir():
        raise IsADirectoryError(f"output is a directory: {path}")
    if target.exists():
        if not overwrite:
            raise FileExistsError(
                "output already exists; set overwrite=true to replace it"
            )
        if not _confirm_overwrite(
            _(
                "confirm.file_overwrite",
                default="disc_image_ops may overwrite: %(path)s",
                path=target,
            )
        ):
            raise PermissionError("overwrite was not confirmed")
    return str(target)


def _temporary_output_path(target: str) -> Path:
    dest = Path(target)
    return dest.with_name(
        f".{dest.stem}.{uuid.uuid4().hex}.tmp{dest.suffix}"
    )


def _run_xverter_convert_atomic(
    source: str,
    target: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    temp = _temporary_output_path(target)
    try:
        result = _run_xverter(
            ["convert", source, "-o", str(temp)],
            timeout_seconds,
        )
        if result.get("ok"):
            if not temp.is_file():
                result["ok"] = False
                result["stderr"] = (
                    str(result.get("stderr", ""))
                    + "xverter reported success but did not create output"
                )
            else:
                os.replace(str(temp), target)
        return result
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def _iso_info(path: str, path_type: str) -> dict[str, Any]:
    if not _ensure_pycdlib():
        raise RuntimeError("pycdlib is unavailable and could not be auto-installed")
    import pycdlib

    iso = pycdlib.PyCdlib()
    opened = False
    try:
        iso.open(path)
        opened = True
        path_key, namespace = _select_namespace(iso, path_type)
        entries = _iso_entries(iso, path_key)
        volume_id = ""
        try:
            raw = getattr(iso.pvd, "volume_identifier", b"")
            if isinstance(raw, bytes):
                volume_id = raw.decode("ascii", errors="replace").rstrip(" \x00")
            else:
                volume_id = str(raw).rstrip(" \x00")
        except Exception:
            pass
        return {
            "ok": True,
            "format": "iso",
            "backend": "pycdlib",
            "path": path,
            "size": os.path.getsize(path),
            "volume_id": volume_id,
            "namespace": namespace,
            "has_udf": bool(iso.has_udf()),
            "has_rock_ridge": bool(iso.has_rock_ridge()),
            "has_joliet": bool(iso.has_joliet()),
            "entry_count": len(entries),
            "file_count": sum(1 for item in entries if item["type"] == "file"),
            "directory_count": sum(
                1 for item in entries if item["type"] == "directory"
            ),
        }
    finally:
        if opened:
            iso.close()


def _iso_list(path: str, path_type: str) -> dict[str, Any]:
    if not _ensure_pycdlib():
        raise RuntimeError("pycdlib is unavailable and could not be auto-installed")
    import pycdlib

    iso = pycdlib.PyCdlib()
    opened = False
    try:
        iso.open(path)
        opened = True
        path_key, namespace = _select_namespace(iso, path_type)
        return {
            "ok": True,
            "format": "iso",
            "backend": "pycdlib",
            "path": path,
            "namespace": namespace,
            "entries": _iso_entries(iso, path_key),
        }
    finally:
        if opened:
            iso.close()


def _iso_verify(path: str, path_type: str, deep: bool) -> dict[str, Any]:
    if not _ensure_pycdlib():
        raise RuntimeError("pycdlib is unavailable and could not be auto-installed")
    import pycdlib

    iso = pycdlib.PyCdlib()
    bytes_read = 0
    opened = False
    try:
        iso.open(path)
        opened = True
        path_key, namespace = _select_namespace(iso, path_type)
        entries = _iso_entries(iso, path_key)
        if deep:
            for item in entries:
                if item["type"] != "file":
                    continue
                with iso.open_file_from_iso(**{path_key: item["path"]}) as fp:
                    while True:
                        chunk = fp.read(1024 * 1024)
                        if not chunk:
                            break
                        bytes_read += len(chunk)
        return {
            "ok": True,
            "format": "iso",
            "backend": "pycdlib",
            "path": path,
            "namespace": namespace,
            "deep": deep,
            "entry_count": len(entries),
            "bytes_read": bytes_read,
        }
    finally:
        if opened:
            iso.close()


def _iso_extract(
    path: str, output: str, path_type: str, overwrite: bool
) -> dict[str, Any]:
    if not _ensure_pycdlib():
        raise RuntimeError("pycdlib is unavailable and could not be auto-installed")
    import pycdlib

    dest = _prepare_extract_dir(output, overwrite)
    dest_root = Path(dest).resolve()
    iso = pycdlib.PyCdlib()
    extracted: list[str] = []
    opened = False
    try:
        iso.open(path)
        opened = True
        path_key, namespace = _select_namespace(iso, path_type)
        for item in _iso_entries(iso, path_key):
            rel = _safe_member_relative(item["path"])
            target = (dest_root / rel).resolve()
            try:
                target.relative_to(dest_root)
            except ValueError as exc:
                raise ValueError(f"unsafe image member path: {item['path']}") from exc
            if item["type"] == "directory":
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and not overwrite:
                raise FileExistsError(f"extracted file already exists: {target}")
            iso.get_file_from_iso(local_path=str(target), **{path_key: item["path"]})
            extracted.append(rel.as_posix())
        return {
            "ok": True,
            "format": "iso",
            "backend": "pycdlib",
            "path": path,
            "namespace": namespace,
            "output": dest,
            "extracted_count": len(extracted),
            "extracted": extracted,
        }
    finally:
        if opened:
            iso.close()


def _xverter_executable() -> str:
    found = shutil.which("xverter")
    if found:
        return found
    scripts = Path(sysconfig.get_path("scripts") or "")
    names = (
        ["xverter.exe", "xverter-script.py", "xverter"]
        if os.name == "nt"
        else ["xverter"]
    )
    for name in names:
        candidate = scripts / name
        if candidate.is_file():
            return str(candidate)
    raise FileNotFoundError(
        "xverter console entry point was not found after installation"
    )


def _run_xverter(argv: list[str], timeout_seconds: int) -> dict[str, Any]:
    if not _ensure_xverter():
        raise RuntimeError("xverter is unavailable and could not be auto-installed")
    exe = _xverter_executable()
    env = os.environ.copy()
    env.setdefault("XVERTER_NO_HINTS", "1")
    proc = subprocess.run(
        [exe, *argv],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        env=env,
        check=False,
    )
    result = {
        "ok": proc.returncode == 0,
        "backend": "xverter",
        "returncode": proc.returncode,
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
    }
    if not result["ok"]:
        result["error"] = _(
            "err.backend_failed",
            default="The disc image backend operation failed.",
        )
    return result


def _chd_action(
    action: str,
    path: str,
    output: str,
    overwrite: bool,
    timeout_seconds: int,
) -> dict[str, Any]:
    if action == "info":
        result = _run_xverter(["info", path], timeout_seconds)
    elif action == "verify":
        result = _run_xverter(["verify", path, "--no-lookup"], timeout_seconds)
    elif action in {"extract", "convert"}:
        if not output:
            raise ValueError("output is required for CHD extract/convert")
        if action == "extract":
            target = _prepare_extract_dir(output, overwrite)
            target_arg = target + os.sep
        else:
            target = _prepare_output_file(output, overwrite, source=path)
            if Path(target).suffix.lower() not in {".iso", ".chd"}:
                raise ValueError("convert output must end in .iso or .chd")
            target_arg = target
        if action == "convert":
            result = _run_xverter_convert_atomic(path, target_arg, timeout_seconds)
        else:
            result = _run_xverter(["convert", path, "-o", target_arg], timeout_seconds)
        result["output"] = target
    else:
        raise ValueError(f"unsupported CHD action: {action}")
    result["format"] = "chd"
    result["path"] = path
    result["action"] = action
    return result


def _convert_iso_to_chd(
    path: str, output: str, overwrite: bool, timeout_seconds: int
) -> dict[str, Any]:
    target = _prepare_output_file(output, overwrite, source=path)
    if Path(target).suffix.lower() != ".chd":
        raise ValueError("ISO convert output must end in .chd")
    result = _run_xverter_convert_atomic(path, target, timeout_seconds)
    result.update(
        {"format": "iso", "path": path, "action": "convert", "output": target}
    )
    return result


def run_tool(args: dict[str, Any]) -> str:
    try:
        action = str(args.get("action", "") or "").strip().lower()
        path_raw = str(args.get("path", "") or "").strip()
        output_raw = str(args.get("output", "") or "").strip()
        path_type = str(args.get("path_type", "auto") or "auto").strip().lower()
        deep = bool(args.get("deep", False))
        overwrite = bool(args.get("overwrite", False))
        timeout_seconds = int(args.get("timeout_seconds", 3600) or 3600)
        timeout_seconds = max(1, min(timeout_seconds, 86400))

        if action not in {"info", "list", "verify", "extract", "convert"}:
            raise ValueError(f"invalid action: {action}")
        if not path_raw:
            raise ValueError("path is required")

        path = _safe_input(path_raw)
        fmt = _detect_format(path)

        if fmt == "iso":
            if action == "info":
                return _json(_iso_info(path, path_type))
            if action == "list":
                return _json(_iso_list(path, path_type))
            if action == "verify":
                return _json(_iso_verify(path, path_type, deep))
            if action == "extract":
                return _json(_iso_extract(path, output_raw, path_type, overwrite))
            return _json(
                _convert_iso_to_chd(path, output_raw, overwrite, timeout_seconds)
            )

        if action == "list":
            raise ValueError(
                "list is currently supported for ISO images only; "
                "use info for CHD metadata"
            )
        return _json(_chd_action(action, path, output_raw, overwrite, timeout_seconds))
    except subprocess.TimeoutExpired as exc:
        return _json(
            {
                "ok": False,
                "timeout": True,
                "error": _(
                    "err.timeout",
                    default="Disc image operation timed out after %(seconds)s seconds.",
                    seconds=exc.timeout,
                ),
                "error_type": type(exc).__name__,
            }
        )
    except Exception as exc:
        if isinstance(exc, PermissionError):
            message = _(
                "err.permission",
                default="The disc image operation was not permitted.",
            )
        elif isinstance(exc, FileExistsError):
            message = _(
                "err.output_exists",
                default="The output already exists.",
            )
        elif isinstance(exc, IsADirectoryError):
            message = _(
                "err.output_type",
                default="A file output was required, but a directory was specified.",
            )
        elif isinstance(exc, FileNotFoundError):
            message = _(
                "err.not_found",
                default="A required input file or dependency was not found.",
            )
        elif isinstance(exc, ValueError):
            message = _(
                "err.invalid",
                default="A disc image option, path, or format is invalid.",
            )
        elif isinstance(exc, RuntimeError):
            message = _(
                "err.dependency",
                default="A required disc image dependency is unavailable.",
            )
        else:
            message = _(
                "err.operation_failed",
                default="The disc image operation failed.",
            )
        return _json(
            {
                "ok": False,
                "error": message,
                "error_type": type(exc).__name__,
            }
        )
