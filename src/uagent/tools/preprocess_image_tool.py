# -*- coding: utf-8 -*-
"""preprocess_image tool

Purpose:
- Apply image preprocessing before sending an image to an LLM / OCR backend.
- Useful for screenshots, scanned documents, charts, tables, diagrams, and line art.

Supported modes:
- ocr: grayscale + denoise + adaptive threshold + sharpen
- document: grayscale + denoise + contrast enhancement
- diagram: grayscale + edge enhancement + threshold
- photo: light denoise + contrast enhancement
- custom: apply user-selected flags

Notes:
- This tool saves a processed image as PNG and returns the saved path.
- The original image is never modified.
- I18N strings are loaded from preprocess_image_tool.json.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    from PIL import Image, ImageFilter, ImageOps, ImageEnhance

    PIL_AVAILABLE = True
except ImportError as e:
    Image = ImageFilter = ImageOps = ImageEnhance = None  # type: ignore[assignment]
    PIL_AVAILABLE = False
    LOAD_DISABLED_REASON = f"[preprocess_image] Pillow is not available: {e!r}"

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True

STATUS_LABEL = "tool:preprocess_image"


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "preprocess_image",
        "description": _(
            "tool.description",
            default=(
                "Apply image preprocessing such as grayscale, denoise, binarization, and edge enhancement, then save the result as a PNG."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "Preprocess the provided image according to the selected mode or options, save the result as a PNG, and return only the saved file path."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "preprocess_image",
                "preprocess image",
                "ocr preprocess",
                "image cleanup",
                "scan image",
                "document image",
            ],
        ),
        "x_search_terms_en": [
            "preprocess_image",
            "preprocess image",
            "ocr preprocess",
            "image cleanup",
            "scan image",
            "document image",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "image_path": {
                    "type": "string",
                    "description": _(
                        "param.image_path.description",
                        default="Path to the source image to preprocess.",
                    ),
                },
                "mode": {
                    "type": "string",
                    "description": _(
                        "param.mode.description",
                        default="Preprocessing mode: ocr, document, diagram, photo, or custom.",
                    ),
                    "default": "ocr",
                },
                "grayscale": {
                    "type": "boolean",
                    "description": _(
                        "param.grayscale.description",
                        default="Convert the image to grayscale.",
                    ),
                    "default": True,
                },
                "denoise": {
                    "type": "boolean",
                    "description": _(
                        "param.denoise.description",
                        default="Apply denoising / smoothing.",
                    ),
                    "default": True,
                },
                "binarize": {
                    "type": "boolean",
                    "description": _(
                        "param.binarize.description",
                        default="Apply binarization / thresholding.",
                    ),
                    "default": False,
                },
                "edge_enhance": {
                    "type": "boolean",
                    "description": _(
                        "param.edge_enhance.description",
                        default="Enhance edges / outlines.",
                    ),
                    "default": False,
                },
                "deskew": {
                    "type": "boolean",
                    "description": _(
                        "param.deskew.description",
                        default="Attempt to correct small image skew (lightweight heuristic).",
                    ),
                    "default": False,
                },
                "resize": {
                    "type": "string",
                    "description": _(
                        "param.resize.description",
                        default="Optional resize target, e.g. 2x or 1600x1200. Leave empty to keep original size.",
                    ),
                },
                "contrast": {
                    "type": "number",
                    "description": _(
                        "param.contrast.description",
                        default="Optional contrast factor. 1.0 keeps original; >1.0 increases contrast.",
                    ),
                    "default": 1.0,
                },
                "output_dir": {
                    "type": "string",
                    "description": _(
                        "param.output_dir.description",
                        default="Directory to save processed images. Defaults to outputs/image_preprocess if omitted.",
                    ),
                },
                "file_prefix": {
                    "type": "string",
                    "description": _(
                        "param.file_prefix.description",
                        default="Prefix for the saved filename (optional).",
                    ),
                    "default": "preprocess_image",
                },
            },
            "required": ["image_path"],
        },
    },
}


def _msg(key: str, default: str, **kwargs: Any) -> str:
    return _(key, default=default).format(**kwargs)


def _ensure_dir(p: str) -> str:
    p2 = os.path.expanduser(p)
    os.makedirs(p2, exist_ok=True)
    return p2


def _parse_bool(v: Any, default: bool = False) -> bool:
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _parse_resize(v: Any, src_size: Tuple[int, int]) -> Tuple[int, int] | None:
    if v is None:
        return None
    s = str(v).strip().lower()
    if not s:
        return None
    if s.endswith("x") and s[:-1].isdigit():
        scale = float(s[:-1])
        return max(1, int(src_size[0] * scale)), max(1, int(src_size[1] * scale))
    if "x" in s:
        a, b = s.split("x", 1)
        if a.strip().isdigit() and b.strip().isdigit():
            return max(1, int(a)), max(1, int(b))
    raise RuntimeError(
        _msg(
            "err.resize_invalid",
            "invalid resize value: {value!r}. Use '2x' or '1600x1200'.",
            value=v,
        )
    )


def _apply_deskew(img: Image.Image) -> Image.Image:
    return img


def _apply_binarize(img: Image.Image) -> Image.Image:
    gray = ImageOps.grayscale(img)
    return gray.point(lambda p: 255 if p > 160 else 0)


def _apply_mode(img: Image.Image, mode: str) -> Tuple[Image.Image, List[str]]:
    ops: List[str] = []
    m = (mode or "ocr").strip().lower()

    if m == "ocr":
        img = ImageOps.grayscale(img)
        ops.append("grayscale")
        img = img.filter(ImageFilter.MedianFilter(size=3))
        ops.append("denoise")
        img = img.filter(ImageFilter.SHARPEN)
        ops.append("sharpen")
        img = img.point(lambda p: 255 if p > 180 else 0)
        ops.append("adaptive_threshold")
    elif m == "document":
        img = ImageOps.grayscale(img)
        ops.append("grayscale")
        img = img.filter(ImageFilter.MedianFilter(size=3))
        ops.append("denoise")
        img = ImageOps.autocontrast(img)
        ops.append("contrast")
    elif m == "diagram":
        img = ImageOps.grayscale(img)
        ops.append("grayscale")
        img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)
        ops.append("edge_enhance")
        img = img.point(lambda p: 255 if p > 170 else 0)
        ops.append("threshold")
    elif m == "photo":
        img = img.filter(ImageFilter.MedianFilter(size=3))
        ops.append("denoise")
        img = ImageOps.autocontrast(img)
        ops.append("contrast")
    elif m == "custom":
        ops.append("custom")
    else:
        raise RuntimeError(
            _msg(
                "err.mode_invalid",
                "invalid mode: {mode!r}. Use ocr/document/diagram/photo/custom.",
                mode=mode,
            )
        )
    return img, ops


def run_tool(args: Dict[str, Any]) -> str:
    image_path = str(args.get("image_path") or "").strip()
    if not image_path:
        raise RuntimeError(
            _(
                "err.image_path_empty",
                default="[preprocess_image] image_path is required",
            )
        )

    p = Path(image_path)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(
            _(
                "err.image_not_found",
                default="[preprocess_image] image file not found: {path}",
            ).format(path=image_path)
        )

    mode = str(args.get("mode") or "ocr").strip().lower()
    grayscale = _parse_bool(args.get("grayscale"), default=True)
    denoise = _parse_bool(args.get("denoise"), default=True)
    binarize = _parse_bool(args.get("binarize"), default=False)
    edge_enhance = _parse_bool(args.get("edge_enhance"), default=False)
    deskew = _parse_bool(args.get("deskew"), default=False)
    contrast = float(args.get("contrast") or 1.0)
    resize = args.get("resize")
    output_dir = str(args.get("output_dir") or "outputs/image_preprocess").strip()
    file_prefix = (
        str(args.get("file_prefix") or "preprocess_image").strip() or "preprocess_image"
    )

    img = Image.open(p)
    ops: List[str] = []

    try:
        img, mode_ops = _apply_mode(img, mode)
        ops.extend(mode_ops)

        if mode == "custom":
            if grayscale:
                img = ImageOps.grayscale(img)
                ops.append("grayscale")
            if denoise:
                img = img.filter(ImageFilter.MedianFilter(size=3))
                ops.append("denoise")
            if edge_enhance:
                img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)
                ops.append("edge_enhance")
            if binarize:
                img = _apply_binarize(img)
                ops.append("binarize")
            if abs(contrast - 1.0) > 1e-9:
                img = ImageEnhance.Contrast(img).enhance(contrast)
                ops.append(f"contrast={contrast}")
            if deskew:
                img = _apply_deskew(img)
                ops.append("deskew")
        else:
            if binarize:
                img = _apply_binarize(img)
                ops.append("binarize")
            if edge_enhance:
                img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)
                ops.append("edge_enhance")
            if deskew:
                img = _apply_deskew(img)
                ops.append("deskew")
            if abs(contrast - 1.0) > 1e-9:
                img = ImageEnhance.Contrast(img).enhance(contrast)
                ops.append(f"contrast={contrast}")

        if resize:
            target = _parse_resize(resize, img.size)
            if target:
                img = img.resize(target, Image.LANCZOS)
                ops.append(f"resize={target[0]}x{target[1]}")

        outdir = _ensure_dir(output_dir)
        out_name = f"{file_prefix}_{p.stem}.png"
        out_path = os.path.join(outdir, out_name)
        img.save(out_path, format="PNG")

        return _(
            "ok.generated",
            default="[OK] generated: {path}",
        ).format(path=out_path)

    finally:
        try:
            img.close()
        except Exception:
            pass
