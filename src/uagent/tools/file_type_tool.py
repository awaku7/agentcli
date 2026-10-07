# tools/file_type_tool.py
"""file_type_tool

Determines the MIME type/format of a file using extension and magic bytes.

Safety: read-only. Rejects dangerous paths.
Output: JSON
"""

from __future__ import annotations
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

import importlib as _importlib
import importlib.metadata as _metadata
import json
import mimetypes
import os as _os
import subprocess as _subprocess
import sys as _sys
import threading as _threading
from pathlib import Path
from typing import Any
from .safe_file_ops_extras import ensure_within_workdir

BUSY_LABEL = True
STATUS_LABEL = "tool:file_type"


# Magic byte signatures: (offset, signature_bytes, mime_type, description)
_MAGIC_PATTERNS: list[tuple[int, bytes, str, str]] = [
    (0, b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a", "image/png", "PNG image"),
    (0, b"\xff\xd8\xff", "image/jpeg", "JPEG image"),
    (0, b"\x47\x49\x46\x38\x37\x61", "image/gif", "GIF image"),
    (0, b"\x47\x49\x46\x38\x39\x61", "image/gif", "GIF image"),
    (0, b"\x52\x49\x46\x46", "image/webp", "WebP image"),
    (0, b"\x42\x4d", "image/bmp", "BMP image"),
    (0, b"\x00\x00\x01\x00", "image/x-icon", "ICO icon"),
    (0, b"\x3c\x73\x76\x67", "image/svg+xml", "SVG image"),
    (0, b"\x1a\x45\xdf\xa3", "video/webm", "WebM video"),
    (0, b"\x00\x00\x00\x1c\x66\x74\x79\x70\x6d\x70\x34\x32", "video/mp4", "MP4 video"),
    (0, b"\x00\x00\x00\x1c\x66\x74\x79\x70\x69\x73\x6f\x6d", "video/mp4", "MP4 video"),
    (0, b"\x00\x00\x00\x18\x66\x74\x79\x70\x6d\x70\x34\x32", "video/mp4", "MP4 video"),
    (0, b"\x00\x00\x00\x14\x66\x74\x79\x70\x69\x73\x6f\x6d", "video/mp4", "MP4 video"),
    (0, b"\x00\x00\x01\xba", "video/mpeg", "MPEG video"),
    (0, b"\x00\x00\x01\xb3", "video/mpeg", "MPEG video"),
    (
        0,
        b"\x00\x00\x00\x1c\x66\x74\x79\x70\x71\x74\x20\x20",
        "video/quicktime",
        "QuickTime video",
    ),
    (
        0,
        b"\x00\x00\x00\x0c\x66\x74\x79\x70\x4d\x53\x4e\x56",
        "video/x-ms-wmv",
        "WMV video",
    ),
    (0, b"\x00\x00\x00\x0c\x66\x74\x79\x70\x33\x67\x70", "video/3gpp", "3GPP video"),
    (8, b"\x41\x56\x49\x20\x20\x20\x20", "video/x-msvideo", "AVI video"),
    (0, b"\x25\x50\x44\x46", "application/pdf", "PDF document"),
    (0, b"\x50\x4b\x03\x04", "application/zip", "ZIP archive"),
    (0, b"\x50\x4b\x05\x06", "application/zip", "ZIP archive (empty)"),
    (0, b"\x50\x4b\x07\x08", "application/zip", "ZIP archive (spanned)"),
    (0, b"\x1f\x8b\x08", "application/gzip", "GZip compressed"),
    (0, b"\x42\x5a\x68", "application/x-bzip2", "BZip2 compressed"),
    (0, b"\x28\xb5\x2f\xfd", "application/zstd", "Zstandard compressed"),
    (0, b"\x37\x7a\xbc\xaf\x27\x1c", "application/x-7z-compressed", "7-Zip archive"),
    (0, b"\x52\x61\x72\x21\x1a\x07\x00", "application/vnd.rar", "RAR archive"),
    (
        0,
        b"\x64\x38\x3a\x61\x6e\x6e\x6f\x75\x6e\x63\x65",
        "application/x-bittorrent",
        "BitTorrent file",
    ),
    (0, b"\xef\xbb\xbf", "text/plain; charset=utf-8-bom", "UTF-8 BOM text"),
    (0, b"\xff\xfe", "text/plain; charset=utf-16-le", "UTF-16 LE text"),
    (0, b"\xfe\xff", "text/plain; charset=utf-16-be", "UTF-16 BE text"),
    (257, b"\x75\x73\x74\x61\x72\x00", "application/x-tar", "POSIX tar archive"),
    (257, b"\x75\x73\x74\x61\x72\x20\x20\x00", "application/x-tar", "GNU tar archive"),
    (0, b"\x23\x21", "text/x-script", "Script (shebang)"),
    (0, b"\xca\xfe\xba\xbe", "application/java-vm", "Java class file"),
    (0, b"\x4d\x5a", "application/x-msdownload", "Portable Executable"),
    (0, b"\x7f\x45\x4c\x46", "application/x-elf", "ELF binary"),
    (0, b"\x25\x21\x50\x53", "application/postscript", "PostScript document"),
    (0, b"\x00\x01\x00\x00\x00", "application/x-font-ttf", "TrueType font"),
    (0, b"\x4f\x54\x54\x4f\x00", "application/x-font-opentype", "OpenType font"),
    (0, b"\x77\x4f\x46\x46", "application/font-woff", "WOFF font"),
    (0, b"\x77\x4f\x46\x32", "font/woff2", "WOFF2 font"),
]


def _distribution_is_installed(name: str) -> bool:
    try:
        _metadata.distribution(name)
        return True
    except _metadata.PackageNotFoundError:
        return False
    except Exception:
        return False


def _remove_windows_python_magic_conflict() -> bool:
    """On Windows, replace the conflicting generic package with the bundled DLL build."""
    if _os.name != "nt" or not _distribution_is_installed("python-magic"):
        return True

    # Respect the configured auto-install policy before changing the environment.
    try:
        from .._pip_auto import _may_install

        if not _may_install("python-magic-bin", display_name="python-magic-bin"):
            return False
    except Exception:
        return False

    try:
        print(
            _(
                "status.magic_conflict_removal",
                default="Removing conflicting python-magic on Windows.",
            ),
            file=_sys.stderr,
        )
        removed = _subprocess.run(
            [_sys.executable, "-m", "pip", "uninstall", "-y", "python-magic"],
            stdout=_sys.stderr,
            stderr=_sys.stderr,
            timeout=120,
            check=False,
        )
        if removed.returncode != 0:
            return False

        # Both distributions provide the same `magic` import package. Reinstall
        # the Windows build after uninstalling the generic distribution because
        # pip may have removed files shared by both distributions.
        installed = _subprocess.run(
            [
                _sys.executable,
                "-m",
                "pip",
                "install",
                "--force-reinstall",
                "--no-deps",
                "python-magic-bin",
            ],
            stdout=_sys.stderr,
            stderr=_sys.stderr,
            timeout=120,
            check=False,
        )
        if installed.returncode != 0:
            return False
    except Exception as exc:
        print(
            _(
                "err.magic_conflict_replace",
                default="Could not replace python-magic: %(error)s",
            )
            % {"error": exc},
            file=_sys.stderr,
        )
        return False

    # Drop any already-imported files from the generic distribution.
    for module_name in list(_sys.modules):
        if module_name == "magic" or module_name.startswith("magic."):
            _sys.modules.pop(module_name, None)
    _importlib.invalidate_caches()
    return True


def _ensure_python_magic() -> Any:
    """Import python-magic; on Windows replace the generic package with python-magic-bin."""
    if _os.name == "nt" and _distribution_is_installed("python-magic"):
        if not _remove_windows_python_magic_conflict():
            return None

    try:
        import magic as _magic

        # Verify that the selected binding can actually access libmagic.
        _magic.from_file(__file__)
        return _magic
    except Exception:
        pass
    try:
        from .._pip_auto import install_with_status

        # On Windows use python-magic-bin (includes bundled DLL)
        if _os.name == "nt":
            pkg = "python-magic-bin"
        else:
            pkg = "python-magic"
        if install_with_status(pkg, "magic"):
            import magic as _magic

            return _magic
    except Exception:
        pass
    return None


_PYTHON_MAGIC: Any = None
_PYTHON_MAGIC_INITIALIZED = False
_PYTHON_MAGIC_LOCK = _threading.Lock()


def _detect_by_magic(path: str) -> dict[str, Any] | None:
    global _PYTHON_MAGIC, _PYTHON_MAGIC_INITIALIZED
    with _PYTHON_MAGIC_LOCK:
        if not _PYTHON_MAGIC_INITIALIZED:
            _PYTHON_MAGIC = _ensure_python_magic()
            _PYTHON_MAGIC_INITIALIZED = True

    # Prefer python-magic (libmagic binding) when available
    if _PYTHON_MAGIC is not None:
        try:
            mime = _PYTHON_MAGIC.from_file(path, mime=True)
            desc = _PYTHON_MAGIC.from_file(path)
            return {"mime_type": mime, "description": desc, "source": "python-magic"}
        except Exception:
            pass

    # Fallback: built-in magic byte dictionary
    try:
        with open(path, "rb") as f:
            header = f.read(512)
    except Exception:
        return None
    for offset, sig, mime, desc in _MAGIC_PATTERNS:
        end = offset + len(sig)
        if len(header) >= end and header[offset:end] == sig:
            return {"mime_type": mime, "description": desc, "source": "builtin"}
    return None


def _format_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {unit}" if isinstance(size, float) else f"{size} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "x_parallel_safe": True,
    "tool_level": 1,
    "tool_genre": "file",
    "function": {
        "name": "file_type",
        "description": _(
            "tool.description",
            default="Identify one or more files by inspecting their contents with libmagic (python-magic or Windows python-magic-bin), magic bytes, and filename heuristics. Returns the detected MIME type, format description, extension-based MIME guess, encoding, and file size. Read-only.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "file type",
                "mime type",
                "file format",
                "detect type",
                "file info",
                "magic bytes",
            ],
        ),
        "x_search_terms_en": [
            "file type",
            "mime type",
            "file format",
            "detect type",
            "file info",
            "magic bytes",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _(
                        "param.paths.description",
                        default="One or more file paths to identify.",
                    ),
                    "minItems": 1,
                }
            },
            "required": ["paths"],
            "additionalProperties": False,
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    paths: list[str] = args.get("paths", [])
    if not paths or not isinstance(paths, list):
        return json.dumps(
            {"ok": False, "error": _("err.no_paths", default="No paths provided.")},
            ensure_ascii=False,
        )
    mimetypes.init()
    results: list[dict[str, Any]] = []
    for p in paths:
        entry: dict[str, Any] = {"path": p}
        try:
            resolved = ensure_within_workdir(p)
        except (ValueError, PermissionError):
            results.append(
                {
                    "path": p,
                    "ok": False,
                    "error": _("err.outside_workdir", default="path outside workdir"),
                }
            )
            continue
        if not _os.path.isfile(resolved):
            results.append(
                {
                    "path": p,
                    "ok": False,
                    "error": _("err.not_found", default="file not found"),
                }
            )
            continue
        entry["ok"] = True
        entry["resolved"] = resolved
        try:
            size = _os.path.getsize(resolved)
            entry["size_bytes"] = size
            entry["size_human"] = _format_size(size)
        except Exception as e:
            entry["size_error"] = str(e)
        ext = Path(resolved).suffix.lower()
        mime_guessed, encoding = mimetypes.guess_type(resolved, strict=False)
        entry["extension"] = ext
        if mime_guessed:
            entry["mime_guess"] = mime_guessed
        if encoding:
            entry["encoding"] = encoding
        magic = _detect_by_magic(resolved)
        if magic:
            entry["magic_mime"] = magic["mime_type"]
            entry["magic_desc"] = magic["description"]
        results.append(entry)
    return json.dumps({"ok": True, "files": results}, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    import sys

    test_paths = sys.argv[1:] if len(sys.argv) > 1 else ["."]
    print(run_tool({"paths": test_paths}))
