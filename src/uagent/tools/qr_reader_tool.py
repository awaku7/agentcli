"""Launch a standalone QR reader window with camera and image-file support."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from .i18n_helper import make_tool_translator
from .response_util import make_response

_ = make_tool_translator(__file__)

TOOL_SPEC: dict[str, Any] = {
    "load_order": 20,
    "type": "function",
    "tool_genre": "media",
    "function": {
        "name": "read_qr_code",
        "description": _(
            "tool.description",
            default=(
                "Open a standalone QR reader window. Scan with a camera or choose an image file, then "
                "click Send to UAG to return the decoded text to the current conversation."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["read QR", "scan QR code", "QR reader", "decode QR"],
        ),
        "x_search_terms_en": ["read QR", "scan QR code", "QR reader", "decode QR"],
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
}

_LAUNCH_LOCK = threading.Lock()
_READER_PROCESS: subprocess.Popen[str] | None = None


def _tkinter_available() -> bool:
    try:
        import tkinter  # noqa: F401
    except ImportError:
        return False
    return True


def _dependencies_available() -> bool:
    try:
        import cv2  # noqa: F401
        from PIL import Image, ImageTk  # noqa: F401
    except ImportError:
        return False
    return True


def _ensure_dependencies() -> bool:
    if _dependencies_available():
        return True
    import importlib

    from .. import _pip_auto

    # A tool hot-reload can leave the dependency policy module cached from
    # before this tool's package was added to the central allowlist.
    if not _pip_auto._install_allowed("opencv-python-headless"):
        _pip_auto = importlib.reload(_pip_auto)
    install_with_status = _pip_auto.install_with_status

    try:
        import cv2  # noqa: F401
    except ImportError:
        if not install_with_status(
            "opencv-python-headless", "cv2", display_name="OpenCV QR reader"
        ):
            return False
    try:
        from PIL import Image, ImageTk  # noqa: F401
    except ImportError:
        if not install_with_status("pillow", "PIL", display_name="Pillow"):
            return False
    return _dependencies_available()


def run_tool(args: dict[str, Any]) -> str:
    """Open the reader window and return its decoded text to UAG on confirmation."""
    global _READER_PROCESS
    del args  # This tool intentionally has no parameters.

    with _LAUNCH_LOCK:
        if _READER_PROCESS is not None and _READER_PROCESS.poll() is None:
            return make_response(
                True,
                _("status.already_open", default="QR reader is already open."),
                data={"already_open": True},
            )

        if not _tkinter_available():
            return make_response(
                False,
                _(
                    "error.tkinter",
                    default="QR reader needs a Python build with Tk support.",
                ),
            )

        if not _ensure_dependencies():
            return make_response(
                False,
                _(
                    "error.dependencies",
                    default=(
                        "QR reader needs OpenCV and Pillow. Install with: "
                        "pip install opencv-python-headless pillow"
                    ),
                ),
            )

        ui_script = Path(__file__).with_name("qr_reader_ui.py")
        creationflags = (
            getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        )
        try:
            process = subprocess.Popen(
                [sys.executable, str(ui_script)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                creationflags=creationflags,
                start_new_session=(os.name != "nt"),
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            _READER_PROCESS = process
        except Exception as exc:
            return make_response(
                False,
                _(
                    "error.launch",
                    default="Could not open QR reader: %(error)s",
                    error=f"{type(exc).__name__}: {exc}",
                ),
            )

    try:
        stdout, _stderr = process.communicate()
    except Exception as exc:
        return make_response(
            False,
            _(
                "error.read_result",
                default="Could not receive QR reader output: %(error)s",
                error=f"{type(exc).__name__}: {exc}",
            ),
        )
    finally:
        with _LAUNCH_LOCK:
            if _READER_PROCESS is process:
                _READER_PROCESS = None

    if process.returncode:
        return make_response(
            False,
            _(
                "error.ui_exit",
                default="QR reader closed with an error (exit code %(code)s).",
                code=process.returncode,
            ),
        )
    if not stdout or not stdout.strip():
        return make_response(
            True,
            _(
                "status.cancelled",
                default="QR reading was cancelled; no text was sent.",
            ),
            data={"cancelled": True},
        )

    try:
        payload = json.loads(stdout)
        text = payload.get("text") if isinstance(payload, dict) else None
    except (json.JSONDecodeError, AttributeError):
        text = None
    if not isinstance(text, str) or not text:
        return make_response(
            False,
            _("error.invalid_result", default="QR reader returned no valid text."),
        )
    if len(text.encode("utf-8")) > 65_536:
        return make_response(
            False,
            _(
                "error.result_too_large",
                default="QR contents exceed the maximum size allowed for UAG input.",
            ),
        )

    return make_response(
        True,
        _(
            "status.imported",
            default="QR contents were imported as untrusted text.",
        ),
        data={"text": text, "source": "qr_code", "untrusted": True},
    )
