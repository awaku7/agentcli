# tools/generate_qr_code_tool.py

from __future__ import annotations

import os
from typing import Any

import qrcode

from .i18n_helper import make_tool_translator
from .safe_file_ops_extras import ensure_within_workdir
from .response_util import make_response
from .openers import open_image_with_default_app
from .context import get_callbacks
from ..env_utils import env_get
import sys

_ = make_tool_translator(__file__)

BUSY_LABEL = True

TOOL_SPEC: dict[str, Any] = {
    "load_order": 10,
    "type": "function",
    "function": {
        "name": "generate_qr_code",
        "description": _(
            "tool.description",
            default="Generate a QR code image (PNG) from text or URL. Customizable colors and size.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["qr", "qrcode", "generate qr", "make qr", "qr code"],
        ),
        "x_search_terms_en": ["qr", "qrcode", "generate qr", "make qr", "qr code"],
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": _(
                        "param.text.description",
                        default="The text or URL to encode into the QR code.",
                    ),
                },
                "filename": {
                    "type": "string",
                    "description": _(
                        "param.filename.description",
                        default="The output filename (e.g., 'qrcode.png'). Must end with .png.",
                    ),
                },
                "error_correction": {
                    "type": "string",
                    "enum": ["L", "M", "Q", "H"],
                    "description": _(
                        "param.error_correction.description",
                        default="Error correction: L/M/Q/H (default: M).",
                    ),
                },
                "box_size": {
                    "type": "integer",
                    "description": _(
                        "param.box_size.description",
                        default="Size of each box (pixel width/height). Default: 10.",
                    ),
                },
                "border": {
                    "type": "integer",
                    "description": _(
                        "param.border.description",
                        default="Border width (number of boxes). Default: 4.",
                    ),
                },
                "fill_color": {
                    "type": "string",
                    "description": _(
                        "param.fill_color.description",
                        default="Color of the QR code modules (e.g., 'black', '#000000'). Default: 'black'.",
                    ),
                },
                "back_color": {
                    "type": "string",
                    "description": _(
                        "param.back_color.description",
                        default="BG color (default: white).",
                    ),
                },
                "overwrite": {
                    "type": "boolean",
                    "description": _(
                        "param.overwrite.description",
                        default="Overwrite if exists (default: false).",
                    ),
                },
            },
            "required": ["text", "filename"],
            "additionalProperties": False,
        },
    },
}


def _backup_path(path: str) -> str:
    base = path + ".org"
    if not os.path.exists(base):
        return base
    i = 1
    while True:
        cand = f"{path}.org{i}"
        if not os.path.exists(cand):
            return cand
        i += 1


def run_tool(args: dict[str, Any]) -> str:
    text = str(args.get("text", ""))
    filename = str(args.get("filename", "")).strip()
    error_correction_str = str(args.get("error_correction", "M")).upper()
    box_size = args.get("box_size", 10)
    border = args.get("border", 4)
    fill_color = str(args.get("fill_color", "black"))
    back_color = str(args.get("back_color", "white"))
    overwrite = bool(args.get("overwrite", False))

    if not text:
        raise ValueError(_("error.text_required", default="text is required"))
    if not filename:
        raise ValueError(_("error.filename_required", default="filename is required"))
    if not filename.lower().endswith(".png"):
        raise ValueError(_("error.must_be_png", default="filename must end with .png"))

    # Map error correction levels
    ec_map = {
        "L": qrcode.constants.ERROR_CORRECT_L,
        "M": qrcode.constants.ERROR_CORRECT_M,
        "Q": qrcode.constants.ERROR_CORRECT_Q,
        "H": qrcode.constants.ERROR_CORRECT_H,
    }
    error_correction = ec_map.get(
        error_correction_str, qrcode.constants.ERROR_CORRECT_M
    )

    safe_path = ensure_within_workdir(filename)
    existed_before = os.path.exists(safe_path)

    if existed_before and not overwrite:
        raise FileExistsError(
            _(
                "error.file_exists",
                default="File already exists: %(path)s",
                path=safe_path,
            )
        )

    backup_path = None
    if existed_before and overwrite:
        backup_path = _backup_path(safe_path)
        with open(safe_path, "rb") as fsrc, open(backup_path, "wb") as fdst:
            fdst.write(fsrc.read())

    # Generate QR Code
    qr = qrcode.QRCode(
        version=None,  # auto-fit
        error_correction=error_correction,
        box_size=box_size,
        border=border,
    )
    qr.add_data(text)
    qr.make(fit=True)

    img = qr.make_image(fill_color=fill_color, back_color=back_color)

    os.makedirs(os.path.dirname(safe_path) or ".", exist_ok=True)
    img.save(safe_path)

    msg = (
        _("status.created", default="Created QR code: %(path)s", path=safe_path)
        if not existed_before
        else _(
            "status.overwritten", default="Overwrote QR code: %(path)s", path=safe_path
        )
    )

    cb = get_callbacks()

    attachments = [
        {
            "type": "image",
            "mime": "image/png",
            "name": os.path.basename(safe_path),
            "path": safe_path,
        }
    ]

    data = {
        "text": text,
        "filename": filename,
        "saved_files": [safe_path],
        "attachments": attachments,
        "created": not existed_before,
        "overwritten": bool(existed_before and overwrite),
        "backup_path": backup_path,
    }

    open_flag = (env_get("UAGENT_IMAGE_OPEN") or "").strip().lower()
    should_open = not bool(getattr(cb, "is_gui", False)) and open_flag not in (
        "0",
        "false",
        "no",
        "off",
    )
    if should_open:
        if open_image_with_default_app(safe_path):
            print(
                _(
                    "log.opened_default_app",
                    default="[INFO] Opened image file with the default app.",
                ),
                file=sys.stderr,
            )

    return make_response(True, msg, data=data)


if __name__ == "__main__":
    # Quick standalone check
    test_args = {
        "text": "https://github.com",
        "filename": "test_qrcode.png",
        "overwrite": True,
    }
    print(run_tool(test_args))
