# tools/usb_camera_tool.py
"""Capture photos from USB cameras via ffmpeg (cross-platform)."""

from __future__ import annotations

import json
import platform
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

SYSTEM = platform.system()  # Windows / Linux / Darwin


def _ffmpeg_backend() -> str:
    if SYSTEM == "Windows":
        return "dshow"
    if SYSTEM == "Darwin":
        return "avfoundation"
    return "v4l2"


TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "function": {
        "name": "usb_camera",
        "description": _(
            "tool.description",
            default="Capture a photo from a USB camera via ffmpeg, or list available video devices. Supports Windows (dshow), Linux (v4l2), macOS (avfoundation).",
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
                        default="Device name/path (overrides index). On Linux use /dev/videoN. Use list action to find names.",
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
    backend = _ffmpeg_backend()
    try:
        if SYSTEM == "Windows":
            result = subprocess.run(
                ["ffmpeg", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                capture_output=True,
                timeout=10,
            )
            stderr = _decode_stderr(result.stderr or b"")
            devices: list[dict[str, Any]] = []
            for line in stderr.split("\n"):
                if '"' in line and (
                    "video" in line.lower() or "camera" in line.lower()
                ):
                    idx = line.find('"')
                    end = line.rfind('"')
                    if idx >= 0 and end > idx:
                        name = line[idx + 1 : end]
                        devices.append({"name": name, "backend": backend})
            return devices

        elif SYSTEM == "Darwin":
            result = subprocess.run(
                ["ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
                capture_output=True,
                timeout=10,
            )
            stderr = _decode_stderr(result.stderr or b"")
            devices = []
            for line in stderr.split("\n"):
                m = re.search(r"\[(\d+)\]\s+(.+)", line.strip())
                if m and ("camera" in line.lower() or "video" in line.lower()):
                    devices.append(
                        {
                            "name": m.group(2).strip(),
                            "index": int(m.group(1)),
                            "backend": backend,
                        }
                    )
            return devices

        else:  # Linux
            devices = []
            for vdev in sorted(Path("/dev").glob("video*")):
                devices.append({"name": str(vdev), "backend": backend})
            if not devices:
                # Try ffmpeg
                result = subprocess.run(
                    [
                        "ffmpeg",
                        "-f",
                        "v4l2",
                        "-list_formats",
                        "all",
                        "-i",
                        "/dev/video0",
                    ],
                    capture_output=True,
                    timeout=5,
                )
                stderr = _decode_stderr(result.stderr or b"")
                if "video0" in stderr:
                    devices.append({"name": "/dev/video0", "backend": backend})
            return devices

    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return [{"error": f"ffmpeg not available or timed out: {e}"}]


def _list_caps(devname: str | None, index: int) -> list[dict[str, Any]]:
    try:
        if SYSTEM == "Windows":
            name = devname or (f"USB Camera {index}" if index else "USB Camera")
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-list_options",
                    "true",
                    "-f",
                    "dshow",
                    "-i",
                    f"video={name}",
                ],
                capture_output=True,
                timeout=10,
            )
        elif SYSTEM == "Darwin":
            idx = devname or str(index)
            result = subprocess.run(
                ["ffmpeg", "-f", "avfoundation", "-list_options", "true", "-i", idx],
                capture_output=True,
                timeout=10,
            )
        else:
            dev = devname or f"/dev/video{index}"
            result = subprocess.run(
                ["ffmpeg", "-f", "v4l2", "-list_formats", "all", "-i", dev],
                capture_output=True,
                timeout=10,
            )

        stderr = _decode_stderr(result.stderr or b"")
        caps: list[dict[str, Any]] = []
        current_fmt = None

        for line in stderr.split("\n"):
            s = line.strip()
            if "pixel_format" in s.lower() and "=" in s:
                m = re.search(r"pixel_format=(\S+)", s)
                if m:
                    current_fmt = m.group(1)
            if re.search(r"\d+\s*x\s*\d+", s) and (
                "fps" in s.lower() or re.search(r"\d+\.?\d*\s*fps", s.lower())
            ):
                m = re.search(
                    r"min\s*s=(\d+)x(\d+)\s*fps=([\d.]+)\s*max\s*s=(\d+)x(\d+)\s*fps=([\d.]+)",
                    s,
                )
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
                m = re.search(r"min\s*s=(\d+)x(\d+)\s*fps=([\d.]+)", s)
                if m:
                    entry = {
                        "res": f"{m.group(1)}x{m.group(2)}",
                        "fps": float(m.group(3)),
                    }
                    if current_fmt:
                        entry["pixel_format"] = current_fmt
                    caps.append(entry)
                    continue
                m = re.search(r"max\s*s=(\d+)x(\d+)\s*fps=([\d.]+)", s)
                if m:
                    entry = {
                        "res": f"{m.group(1)}x{m.group(2)}",
                        "fps": float(m.group(3)),
                    }
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
    backend = _ffmpeg_backend()

    if SYSTEM == "Windows":
        if devname:
            video_src = f"video={devname}"
        else:
            video_src = f"video=USB Camera {'' if index == 0 else index}"
    elif SYSTEM == "Darwin":
        video_src = devname or str(index)
    else:
        video_src = devname or f"/dev/video{index}"

    cmd = ["ffmpeg", "-f", backend]
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
            info = {
                "ok": True,
                "saved_path": saved,
                "filename": filename,
                "size_bytes": save_path.stat().st_size,
            }
            if width and height:
                info["width"] = width
                info["height"] = height
            if fps:
                info["fps"] = fps
            return info

        # Fallback: try common names
        alt_names = []
        if SYSTEM == "Windows":
            alt_names = [
                "Integrated Camera",
                "USB Camera",
                "HD Webcam",
                "USB Video Device",
                f"Camera ({index})",
            ]
        elif SYSTEM == "Darwin":
            alt_names = ["0", "1"]
        else:
            for i in range(3):
                alt_names.append(f"/dev/video{i}")

        for alt in alt_names:
            alt_src = f"video={alt}" if SYSTEM == "Windows" else alt
            alt_cmd = ["ffmpeg", "-f", backend]
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
                return {
                    "ok": True,
                    "saved_path": saved,
                    "filename": filename,
                    "size_bytes": save_path.stat().st_size,
                    "device": alt,
                }

        stderr_txt = _decode_stderr(result.stderr or b"")
        return {"ok": False, "error": f"Capture failed. ffmpeg: {stderr_txt[:300]}"}
    except FileNotFoundError:
        return {
            "ok": False,
            "error": "ffmpeg not found. Install ffmpeg and ensure it's in PATH.",
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Camera capture timed out (15s)."}
    except Exception as e:
        return {"ok": False, "error": f"Capture failed: {e}"}


def run_tool(args: dict[str, Any]) -> str:
    action = (args.get("action") or "").strip().lower()
    index = int(args.get("index", 0))
    devname = (args.get("devname") or "").strip() or None

    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
    except FileNotFoundError:
        return json.dumps(
            {
                "ok": False,
                "error": "ffmpeg is not installed or not in PATH. Install ffmpeg.",
            },
            ensure_ascii=False,
        )

    if action == "list":
        return json.dumps(
            {"ok": True, "action": "list", "devices": _list_devices()},
            ensure_ascii=False,
        )

    if action == "list_caps":
        return json.dumps(
            {"ok": True, "action": "list_caps", "caps": _list_caps(devname, index)},
            ensure_ascii=False,
        )

    if action == "capture":
        outdir = (args.get("outdir") or "").strip() or "outputs/usb_camera"
        width = int(args["width"]) if args.get("width") is not None else None
        height = int(args["height"]) if args.get("height") is not None else None
        fps_val = int(args["fps"]) if args.get("fps") is not None else None
        result = _capture(devname, index, width, height, fps_val, outdir)
        result["action"] = "capture"
        return json.dumps(result, ensure_ascii=False)

    return json.dumps(
        {"ok": False, "error": f"Unsupported action: {action}"}, ensure_ascii=False
    )
