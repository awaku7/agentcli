# tools/usb_camera_tool.py
"""Capture photos from USB cameras via ffmpeg."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .i18n_helper import make_tool_translator
from .openers import open_image_with_default_app

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:usb_camera"

TOOL_SPEC: dict[str, Any] = {
    "tool_level": 0,
    "tool_genre": "iot",
    "type": "function",
    "function": {
        "name": "usb_camera",
        "description": _(
            "tool.description",
            default="Capture a photo from a USB camera via ffmpeg, or list available video devices.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "usb camera",
                "webcam",
                "capture photo",
                "take picture",
                "video device",
                "camera",
                "USBカメラ",
                "写真撮影",
            ],
        ),
        "x_search_terms_en": [
            "usb camera",
            "webcam",
            "capture photo",
            "take picture",
            "video device",
            "camera",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["capture", "list"],
                    "description": _(
                        "param.action.description",
                        default="Action: capture (take a photo) or list (show available devices).",
                    ),
                },
                "index": {
                    "type": "integer",
                    "description": _(
                        "param.index.description",
                        default="Video device index (0 = first USB camera). Used with action=capture. Default: 0.",
                    ),
                    "default": 0,
                },
                "devname": {
                    "type": "string",
                    "description": _(
                        "param.devname.description",
                        default="DirectShow device name (overrides index if set). Use list action to find names.",
                    ),
                },
                "outdir": {
                    "type": "string",
                    "description": _(
                        "param.outdir.description",
                        default="Output directory for captured images. Default: outputs/usb_camera.",
                    ),
                },
            },
            "required": ["action"],
        },
    },
}


def _list_devices() -> list[dict[str, Any]]:
    """List available DirectShow video devices via ffmpeg."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
            capture_output=True, timeout=10,
        )
        raw = result.stderr or b""
        try:
            stderr = raw.decode("utf-8", errors="replace")
        except Exception:
            stderr = raw.decode("cp932", errors="replace")
        devices: list[dict[str, Any]] = []
        for line in stderr.split("\n"):
            if '"' in line and ("video" in line.lower() or "camera" in line.lower()):
                idx = line.find('"')
                end = line.rfind('"')
                if idx >= 0 and end > idx:
                    name = line[idx + 1:end]
                    direct = line.lower().startswith("  ")
                    kind = "video" if "video" in line.lower() else "unknown"
                    devices.append({"name": name, "kind": kind, "directshow": True})
        return devices
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return [{"error": f"ffmpeg not available or timed out: {e}"}]


def _capture(
    devname: str | None,
    index: int,
    outdir: str,
) -> dict[str, Any]:
    """Capture a single frame from a USB camera."""
    out_path = Path(outdir)
    out_path.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"usb_cam_{ts}.jpg"
    save_path = out_path / filename

    if devname:
        video_src = f"video={devname}"
    else:
        # Try DirectShow with index via dshow
        video_src = f"video=USB Camera {'' if index == 0 else index}"

    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-f", "dshow",
                "-i", video_src,
                "-vframes", "1",
                "-y",
                str(save_path),
            ],
            capture_output=True, timeout=15,
        )
        if save_path.exists() and save_path.stat().st_size > 0:
            saved = str(save_path.resolve())
            # Try to open the image
            try:
                open_image_with_default_app(saved)
            except Exception:
                pass
            return {
                "ok": True,
                "saved_path": saved,
                "filename": filename,
                "size_bytes": save_path.stat().st_size,
            }
        else:
            # Fallback: try directshow with alternative naming
            # Try common camera names
            for alt_name in [
                "Integrated Camera",
                "USB Camera",
                "HD Webcam",
                "USB Video Device",
                f"Camera ({index})",
            ]:
                alt_src = f"video={alt_name}"
                alt_result = subprocess.run(
                    ["ffmpeg", "-f", "dshow", "-i", alt_src, "-vframes", "1", "-y", str(save_path)],
                    capture_output=True, timeout=15,
                )
                if save_path.exists() and save_path.stat().st_size > 0:
                    saved = str(save_path.resolve())
                    try:
                        open_image_with_default_app(saved)
                    except Exception:
                        pass
                    return {
                        "ok": True,
                        "saved_path": saved,
                        "filename": filename,
                        "size_bytes": save_path.stat().st_size,
                        "device": alt_name,
                    }

            return {
                "ok": False,
                "error": f"Could not capture from device. ffmpeg stderr: {(result.stderr or b'')[:200]}",
            }
    except FileNotFoundError:
        return {"ok": False, "error": "ffmpeg not found. Install ffmpeg and ensure it's in PATH."}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Camera capture timed out (15s)."}
    except Exception as e:
        return {"ok": False, "error": f"Capture failed: {e}"}


def run_tool(args: dict[str, Any]) -> str:
    action = (args.get("action") or "").strip().lower()
    
    if action == "list":
        devices = _list_devices()
        return json.dumps({"ok": True, "action": "list", "devices": devices}, ensure_ascii=False)
    
    if action == "capture":
        index = int(args.get("index", 0))
        devname = (args.get("devname") or "").strip() or None
        outdir = (args.get("outdir") or "").strip() or "outputs/usb_camera"
        result = _capture(devname, index, outdir)
        result["action"] = "capture"
        return json.dumps(result, ensure_ascii=False)
    
    return json.dumps(
        {"ok": False, "error": f"Unsupported action: {action}"},
        ensure_ascii=False,
    )
