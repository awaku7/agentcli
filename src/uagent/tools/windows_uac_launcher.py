"""Restricted Windows UAC launcher for the network privileged helper."""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Sequence

_FIXED_MODULE = "uagent.tools.network_privileged_helper"


def build_helper_command(
    request_path: str,
    result_path: str,
    *,
    module: str = _FIXED_MODULE,
) -> list[str]:
    if module != _FIXED_MODULE:
        raise ValueError("only the fixed privileged helper module is allowed")
    return [
        sys.executable,
        "-m",
        _FIXED_MODULE,
        "--request",
        request_path,
        "--result",
        result_path,
    ]


def create_request_paths(directory: str | None = None) -> tuple[Path, Path]:
    root = Path(directory) if directory else Path(tempfile.mkdtemp(prefix="uag-network-"))
    root.mkdir(parents=True, exist_ok=True)
    return root / "request.json", root / "result.json"


def write_request(path: str | Path, request: dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    temporary.replace(target)
    return target


def read_result(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    value = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("helper result must be an object")
    return value


def wait_for_result(path: str | Path, timeout: float = 30.0, interval: float = 0.1) -> dict[str, Any]:
    target = Path(path)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if target.is_file():
            return read_result(target)
        time.sleep(interval)
    raise TimeoutError("privileged helper result timed out")


def shell_execute_runas(args: Sequence[str]) -> int:
    if os.name != "nt":
        raise RuntimeError("Windows UAC is only available on Windows")
    if not args or args[0] != sys.executable or len(args) < 3 or args[1:3] != ["-m", _FIXED_MODULE]:
        raise ValueError("only the fixed privileged helper may be elevated")
    parameters = subprocess.list2cmdline(list(args[1:]))
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        sys.executable,
        parameters,
        None,
        1,
    )
    if result <= 32:
        raise RuntimeError(f"UAC elevation failed with code {result}")
    return int(result)
