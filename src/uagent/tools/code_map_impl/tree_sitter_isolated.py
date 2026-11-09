"""Run Tree-sitter symbol extraction outside the UAG process.

Tree-sitter and its grammars are native extensions. A segfault/access violation
cannot be caught by Python exceptions, so keep a reusable subprocess between
file requests and disable native parsing after a worker failure.
"""

from __future__ import annotations

import atexit
import json
import os
import queue
import subprocess
import sys
import threading
import warnings
from pathlib import Path
from typing import Any

from .tree_sitter_symbols import TREE_SITTER_LANGUAGE_BY_SOURCE

_WORKER_TIMEOUT_SECONDS = 60
_MAX_REQUESTS_PER_WORKER = 128
_LOCK = threading.RLock()
_WORKER: subprocess.Popen[str] | None = None
_RESPONSES: queue.Queue[str | None] | None = None
_BROKEN = False
_REQUESTS = 0


def _worker_command() -> list[str]:
    return [
        sys.executable,
        "-u",
        "-m",
        "uagent.tools.code_map_impl.tree_sitter_worker",
    ]


def _read_worker_output(
    process: subprocess.Popen[str], responses: queue.Queue[str | None]
) -> None:
    try:
        assert process.stdout is not None
        for line in process.stdout:
            responses.put(line)
    except (OSError, UnicodeError, ValueError):
        pass
    finally:
        responses.put(None)


def _start_worker() -> None:
    global _WORKER, _RESPONSES, _REQUESTS
    worker_env = os.environ.copy()
    worker_env["PYTHONIOENCODING"] = "utf-8"
    package_root = str(Path(__file__).resolve().parents[3])
    worker_env["PYTHONPATH"] = os.pathsep.join(
        filter(None, (package_root, worker_env.get("PYTHONPATH", "")))
    )
    process = subprocess.Popen(
        _worker_command(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=worker_env,
        bufsize=1,
    )
    responses: queue.Queue[str | None] = queue.Queue()
    threading.Thread(
        target=_read_worker_output,
        args=(process, responses),
        daemon=True,
        name="uag-tree-sitter-reader",
    ).start()
    _WORKER = process
    _RESPONSES = responses
    _REQUESTS = 0


def _stop_worker() -> None:
    global _WORKER, _RESPONSES
    with _LOCK:
        process = _WORKER
        _WORKER = None
        _RESPONSES = None
        if process is None:
            return
        if process.stdin is not None:
            try:
                process.stdin.close()
            except OSError:
                pass
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        if process.stdout is not None:
            process.stdout.close()


def _disable_worker(reason: str) -> None:
    global _BROKEN
    _stop_worker()
    _BROKEN = True
    warnings.warn(
        f"Tree-sitter subprocess failed ({reason}); "
        "falling back to regex extraction for the rest of this process.",
        RuntimeWarning,
        stacklevel=2,
    )


def extract_tree_sitter_symbols(
    filepath: str, source_language: str
) -> list[dict[str, Any]]:
    """Extract symbols with crash containment; return [] for regex fallback."""
    if source_language not in TREE_SITTER_LANGUAGE_BY_SOURCE:
        return []
    if os.environ.get("UAGENT_CODE_MAP_TREE_SITTER", "1").lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return []

    global _REQUESTS
    with _LOCK:
        if _BROKEN:
            return []
        try:
            if _WORKER is not None and _REQUESTS >= _MAX_REQUESTS_PER_WORKER:
                _stop_worker()
            if _WORKER is None:
                _start_worker()
            assert _WORKER is not None
            assert _WORKER.stdin is not None
            assert _RESPONSES is not None
            request = {"path": filepath, "language": source_language}
            _WORKER.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
            _WORKER.stdin.flush()
            line = _RESPONSES.get(timeout=_WORKER_TIMEOUT_SECONDS)
            if line is None:
                raise RuntimeError(
                    f"worker output stopped (exit code {_WORKER.poll()})"
                )
            result = json.loads(line)
            if not isinstance(result, list):
                raise ValueError("invalid worker response")
            _REQUESTS += 1
            return result
        except (OSError, ValueError, RuntimeError, queue.Empty) as exc:
            _disable_worker(str(exc) or type(exc).__name__)
            return []


atexit.register(_stop_worker)
