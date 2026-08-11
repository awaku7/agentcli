"""Safe, static extraction of VBA modules from macro-enabled workbooks."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from ..._pip_auto import install_with_status


def extract_vba_modules(workbook: Path) -> tuple[tempfile.TemporaryDirectory[str], Path, list[dict[str, Any]]]:
    """Extract VBA source modules without executing the workbook.

    ``oletools`` is optional and is installed on demand only for Excel macro
    files.  The returned TemporaryDirectory must remain alive while the caller
    consumes the extracted source files.
    """
    if not install_with_status(
        "oletools", "oletools", verify_submodule="oletools.olevba"
    ):
        raise RuntimeError(
            "VBA extraction requires oletools; automatic installation failed"
        )

    from oletools.olevba import VBA_Parser

    temp_dir = tempfile.TemporaryDirectory(prefix="code_map_vba_")
    extract_root = Path(temp_dir.name)
    modules: list[dict[str, Any]] = []
    parser = VBA_Parser(str(workbook))
    try:
        if not parser.detect_vba_macros():
            parser.close()
            return temp_dir, extract_root, modules
        for filename, stream_path, vba_filename, code in parser.extract_macros():
            safe_name = Path(vba_filename or filename or "module.bas").name
            suffix = ".cls" if "class" in safe_name.lower() else ".bas"
            if not safe_name.lower().endswith((".bas", ".cls", ".frm")):
                safe_name += suffix
            target = extract_root / safe_name
            counter = 1
            while target.exists():
                target = extract_root / f"{target.stem}_{counter}{target.suffix}"
                counter += 1
            target.write_text(code, encoding="utf-8", errors="replace")
            modules.append(
                {
                    "path": str(target),
                    "module": vba_filename or target.stem,
                    "stream": stream_path,
                    "source": filename,
                }
            )
    finally:
        parser.close()
    return temp_dir, extract_root, modules


def supported_workbook(path: Path) -> bool:
    return path.suffix.lower() in {".xlsm", ".xltm", ".xlsb"}


def supported_office_script(path: Path) -> bool:
    """Return whether a standalone exported Office Script can be scanned."""
    return path.suffix.lower() in {".ts", ".js"}
