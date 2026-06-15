# tools/usb_camera_tool.py
"""Capture photos from USB cameras via ffmpeg."""

from __future__ import annotations

import json
import re
import subprocess
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
                    "enum": ["capture", "list", "list_caps"],
                    "description": _(
                        "param.action.description",
                        default="Action: capture (take a photo), list (show devices), or list_caps (show capabilities like resolutions and FPS for a device).",
                    ),
                },
                "index": {
                    "type": "integer",
                    "description": _(
                        "param.index.description",
                        default="Video device index (0 = first). Default: 0.",
                    ),
                    "default": 0,
                },
                "devname": {
                    "type": "string",
                    "description": _(
                        "param.devname.description",
                        default="DirectShow device name (overrides index). Use list action to find names.",
                    ),
                },
                "width": {
                    "type": "integer",
                    "description": _(
                        "param.width.description",
                        default="Capture width in pixels (e.g. 1920). Uses default if omitted.",
                    ),
                },
                "height": {
                    "type": "integer",
                    "description": _(
                        "param.height.description",
                        default="Capture height in pixels (e.g. 1080). Uses default if omitted.",
                    ),
                },
                "fps": {
                    "type": "integer",
                    "description": _(
                        "param.fps.description",
                        default="Frames per second (e.g. 30). Uses default if omitted.",
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


def _decode_stderr(raw: bytes) -> str:
    try:
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return raw.decode("cp932", errors="replace")


def _list_devices() -> list[dict[str, Any]]:
    try:
        result = subprocess.run(
            ["ffmpeg", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
            capture_output=True, timeout=10,
        )
        stderr = _decode_stderr(result.stderr or b"")
        devices: list[dict[str, Any]] = []
        for line in stderr.split("\n"):
            if '"' in line and ("video" in line.lower() or "camera" in line.lower()):
                idx = line.find('"')
                end = line.rfind('"')
                if idx >= 0 and end > idx:
                    name = line[idx + 1:end]
                    kind = "video" if "video" in line.lower() else "unknown"
                    devices.append({"name": name, "kind": kind})
        return devices
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return [{"error": f"ffmpeg not available or timed out: {e}"}]


def _list_caps(devname: str | None, index: int) -> list[dict[str, Any]]:
    name = devname or (f"USB Camera {index}" if index else "USB Camera")
    video_src = f"video={name}"
    try:
        result = subprocess.run(
            ["ffmpeg", "-list_options", "true", "-f", "dshow", "-i", video_src],
            capture_output=True, timeout=10,
        )
        stderr = _decode_stderr(result.stderr or b"")
        caps: list[dict[str, Any]] = []
        current_fmt = None
        for line in stderr.split("\n"):
            s = line.strip()
            if "pixel_format" in s.lower() and "=" in s:
                m = re.search(r'pixel_format=(\S+)', s)
                if m:
                    current_fmt = m.group(1)
            if re.search(r'\d+\s*x\s*\d+', s) and ("fps" in s.lower() or re.search(r'\d+\.?\d*\s*fps', s.lower())):
                m = re.search(r'min\s*s=(\d+)x(\d+)\s*fps=([\d.]+)\s*max\s*s=(\d+)x(\d+)\s*fps=([\d.]+)', s)
                if m:
                    entry = {
                        "min_res": f"{m.group(1)}x{m.group(2)}",
                        "min_fps": float(m.group(3)),
                        "max_res": f"{m.group(4)}x{m.group(5)}",
                        "max_fps": float(m.group(6)),
                    }
                    if current_fmt:
                        entry["pixel_format"] = current_fmt
                    caps.append(entry)
                    continue
                m = re.search(r'min\s*s=(\d+)x(\d+)\s*fps=([\d.]+)', s)
                if m:
                    entry = {"res": f"{m.group(1)}x{m.group(2)}", "fps": float(m.group(3))}
                    if current_fmt:
                        entry["pixel_format"] = current_fmt
                    caps.append(entry)
                    continue
                m = re.search(r'max\s*s=(\d+)x(\d+)\s*fps=([\d.]+)', s)
                if m:
                    entry = {"res": f"{m.group(1)}x{m.group(2)}", "fps": float(m.group(3))}
                    if current_fmt:
                        entry["pixel_format"] = current_fmt
                    caps.append(entry)
                    continue
        return caps
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return [{"error": f"Could not query capabilities: {e}"}]


def _capture(
    devname: str | None,
    index: int,
    width: int | None,
    height: int | None,
    fps: int | None,
    outdir: str,
) -> dict[str, Any]:
    out_path = Path(outdir)
    out_path.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"usb_cam_{ts}.jpg"
    save_path = out_path / filename

    if devname:
        video_src = f"video={devname}"
    else:
        video_src = f"video=USB Camera {'' if index == 0 else index}"

    cmd = ["ffmpeg", "-f", "dshow"]
    if width and height:
        cmd += ["-video_size", f"{width}x{height}"]
    if fps:
        cmd += ["-framerate", str(fps)]
    cmd += ["-i", video_src, "-vframes", "1", "-y", str(save_path)]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=15)
        if save_path.exists() and save_path.stat().st_size > 0:
            saved = str(save_path.resolve())
            try:
                open_image_with_default_app(saved)
            except Exception:
                pass
            info = {"ok": True, "saved_path": saved, "filename": filename, "size_bytes": save_path.stat().st_size}
            if width and height:
                info["width"] = width
                info["height"] = height
            if fps:
                info["fps"] = fps
            return info

        for alt_name in ["Integrated Camera", "USB Camera", "HD Webcam", "USB Video Device", f"Camera ({index})"]:
            alt_src = f"video={alt_name}"
            alt_cmd = ["ffmpeg", "-f", "dshow"]
            if width and height:
                alt_cmd += ["-video_size", f"{width}x{height}"]
            if fps:
                alt_cmd += ["-framerate", str(fps)]
            alt_cmd += ["-i", alt_src, "-vframes", "1", "-y", str(save_path)]
            subprocess.run(alt_cmd, capture_output=True, timeout=15)
            if save_path.exists() and save_path.stat().st_size > 0:
                saved = str(save_path.resolve())
                try:
                    open_image_with_default_app(saved)
                except Exception:
                    pass
                return {"ok": True, "saved_path": saved, "filename": filename, "size_bytes": save_path.stat().st_size, "device": alt_name}

        stderr_txt = _decode_stderr(result.stderr or b"")
        return {"ok": False, "error": f"Capture failed. ffmpeg: {stderr_txt[:300]}"}
    except FileNotFoundError:
        return {"ok": False, "error": "ffmpeg not found. Install ffmpeg and ensure it's in PATH."}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Camera capture timed out (15s)."}
    except Exception as e:
        return {"ok": False, "error": f"Capture failed: {e}"}


def run_tool(args: dict[str, Any]) -> str:
    action = (args.get("action") or "").strip().lower()
    index = int(args.get("index", 0))
    devname = (args.get("devname") or "").strip() or None

    # Check ffmpeg availability early
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
    except FileNotFoundError:
        return json.dumps({"ok": False, "error": "ffmpeg is not installed or not in PATH. Install ffmpeg to use this tool."}, ensure_ascii=False)

    if action == "list":
        devices = _list_devices()
        return json.dumps({"ok": True, "action": "list", "devices": devices}, ensure_ascii=False)

    if action == "list_caps":
        caps = _list_caps(devname, index)
        return json.dumps({"ok": True, "action": "list_caps", "caps": caps}, ensure_ascii=False)

    if action == "capture":
        outdir = (args.get("outdir") or "").strip() or "outputs/usb_camera"
        width = int(args["width"]) if args.get("width") is not None else None
        height = int(args["height"]) if args.get("height") is not None else None
        fps_val = int(args["fps"]) if args.get("fps") is not None else None
        result = _capture(devname, index, width, height, fps_val, outdir)
        result["action"] = "capture"
        return json.dumps(result, ensure_ascii=False)

    return json.dumps({"ok": False, "error": f"Unsupported action: {action}"}, ensure_ascii=False)
