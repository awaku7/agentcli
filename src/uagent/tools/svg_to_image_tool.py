from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Any

from .._pip_auto import install_with_status
from .i18n_helper import make_tool_translator
from .response_util import make_response
from .safe_file_ops_extras import ensure_within_workdir

_ = make_tool_translator(__file__)

BUSY_LABEL = True

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "media",
    "tool_level": 0,
    "x_parallel_safe": False,
    "function": {
        "name": "svg_to_image",
        "description": _(
            "tool.description",
            default=(
                "Convert an SVG file to a raster image and save it as PNG, JPEG, or WebP. "
                "The conversion is performed locally."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "SVG to PNG",
                "SVG to image",
                "convert SVG",
                "rasterize SVG",
                "SVG converter",
                "PNG",
                "JPEG",
                "WebP",
            ],
        ),
        "x_search_terms_en": [
            "SVG to PNG",
            "SVG to image",
            "convert SVG",
            "rasterize SVG",
            "SVG converter",
            "PNG",
            "JPEG",
            "WebP",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "svg": {
                    "type": "string",
                    "description": _(
                        "param.svg.description",
                        default="Path to the source SVG file.",
                    ),
                },
                "output_path": {
                    "type": "string",
                    "description": _(
                        "param.output_path.description",
                        default="Output image path ending in .png, .jpg, .jpeg, or .webp.",
                    ),
                },
                "width": {
                    "type": "integer",
                    "minimum": 1,
                    "description": _(
                        "param.width.description",
                        default="Optional output width in pixels. Keep the SVG intrinsic width when omitted.",
                    ),
                },
                "height": {
                    "type": "integer",
                    "minimum": 1,
                    "description": _(
                        "param.height.description",
                        default="Optional output height in pixels. Keep the SVG intrinsic height when omitted.",
                    ),
                },
                "scale": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                    "default": 1.0,
                    "description": _(
                        "param.scale.description",
                        default="Scale factor applied to the rendered image. Default: 1.0.",
                    ),
                },
                "background": {
                    "type": "string",
                    "description": _(
                        "param.background.description",
                        default="Optional background color, such as white or #ffffff. Keep transparent when omitted.",
                    ),
                },
                "overwrite": {
                    "type": "boolean",
                    "default": False,
                    "description": _(
                        "param.overwrite.description",
                        default="Overwrite the output file if it already exists. Default: false.",
                    ),
                },
                "include_base64": {
                    "type": "boolean",
                    "default": True,
                    "description": _(
                        "param.include_base64.description",
                        default="Include base64 image data for remote clients. Default: true.",
                    ),
                },
            },
            "required": ["svg", "output_path"],
            "additionalProperties": False,
        },
    },
    "is_agent_content": False,
}


def _load_cairosvg():
    try:
        import cairosvg

        return cairosvg
    except ImportError:
        if not install_with_status("CairoSVG", "cairosvg"):
            raise RuntimeError(
                _(
                    "error.renderer_unavailable",
                    default="CairoSVG is not available. Install it with: pip install CairoSVG",
                )
            )
        import cairosvg

        return cairosvg


def _load_pillow():
    try:
        from PIL import Image

        return Image
    except ImportError:
        if not install_with_status("Pillow", "PIL"):
            raise RuntimeError(
                _(
                    "error.pillow_unavailable",
                    default="Pillow is required for JPEG or WebP output. Install it with: pip install Pillow",
                )
            )
        from PIL import Image

        return Image


def _positive_int(value: Any, key: str) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            _(
                "error.positive_integer",
                default="%(key)s must be a positive integer.",
                key=key,
            )
        ) from exc
    if parsed < 1:
        raise ValueError(
            _(
                "error.positive_integer",
                default="%(key)s must be a positive integer.",
                key=key,
            )
        )
    return parsed


def run_tool(args: dict[str, Any]) -> str:
    svg_raw = str(args.get("svg") or "").strip()
    output_raw = str(args.get("output_path") or "").strip()
    if not svg_raw:
        raise ValueError(_("error.svg_required", default="svg is required"))
    if not output_raw:
        raise ValueError(_("error.output_required", default="output_path is required"))

    svg_path = Path(ensure_within_workdir(svg_raw))
    output_path = Path(ensure_within_workdir(output_raw))
    if not svg_path.is_file():
        raise FileNotFoundError(
            _(
                "error.input_not_found",
                default="SVG file was not found: %(path)s",
                path=svg_path,
            )
        )
    if svg_path.suffix.lower() != ".svg":
        raise ValueError(
            _(
                "error.input_extension",
                default="The input file must have a .svg extension.",
            )
        )

    suffix = output_path.suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError(
            _(
                "error.output_extension",
                default="output_path must end in .png, .jpg, .jpeg, or .webp.",
            )
        )
    width = _positive_int(args.get("width"), "width")
    height = _positive_int(args.get("height"), "height")
    try:
        scale = float(args.get("scale", 1.0))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            _("error.scale", default="scale must be greater than 0.")
        ) from exc
    if scale <= 0:
        raise ValueError(_("error.scale", default="scale must be greater than 0."))

    overwrite = bool(args.get("overwrite", False))
    if output_path.exists() and not overwrite:
        raise FileExistsError(
            _(
                "error.file_exists",
                default="Output file already exists: %(path)s",
                path=output_path,
            )
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cairosvg = _load_cairosvg()
    svg_bytes = svg_path.read_bytes()
    render_kwargs: dict[str, Any] = {
        "bytestring": svg_bytes,
        "output_width": round(width * scale) if width else None,
        "output_height": round(height * scale) if height else None,
    }
    background = str(args.get("background") or "").strip()
    if background:
        render_kwargs["background_color"] = background

    png_bytes = cairosvg.svg2png(**render_kwargs)
    if suffix == ".png":
        output_path.write_bytes(png_bytes)
    else:
        Image = _load_pillow()
        with Image.open(io.BytesIO(png_bytes)) as image:
            if suffix in {".jpg", ".jpeg"}:
                if image.mode in {"RGBA", "LA", "P"}:
                    background_image = Image.new("RGB", image.size, "white")
                    if image.mode != "RGB":
                        background_image.paste(image, mask=image.getchannel("A"))
                    image = background_image
                else:
                    image = image.convert("RGB")
                image.save(output_path, format="JPEG", quality=95)
            else:
                image.save(output_path, format="WEBP", quality=95)

    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }[suffix]
    attachment: dict[str, Any] = {
        "type": "image",
        "mime": mime,
        "name": output_path.name,
        "path": str(output_path),
    }
    if bool(args.get("include_base64", True)):
        attachment["data_base64"] = base64.b64encode(output_path.read_bytes()).decode(
            "ascii"
        )

    try:
        from ..runtime.artifact_helpers import register_artifacts

        artifacts = register_artifacts(
            [str(output_path)],
            metadata={"kind": "svg_to_image", "format": suffix.lstrip(".")},
        )
    except Exception:
        artifacts = []

    return make_response(
        True,
        _("ok.converted", default="[OK] SVG converted to image"),
        data={
            "artifacts": artifacts,
            "saved_files": [str(output_path)],
            "attachments": [attachment],
        },
    )


if __name__ == "__main__":
    print(run_tool({"svg": "input.svg", "output_path": "output.png"}))
