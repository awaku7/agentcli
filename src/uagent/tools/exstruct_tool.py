# tools/exstruct_tool.py
from __future__ import annotations

import json
from typing import Any, Dict

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True


def _import_exstruct():
    # Local import to avoid requiring dependency at import time.
    import exstruct  # type: ignore

    return exstruct


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "exstruct",
        "description": _(
            "tool.description",
            default=(
                "Use exstruct to extract structured data from an Excel (.xlsx) and return/save as JSON/YAML. "
                "If export_file.output_path already exists, a backup (<output_path>.org / <output_path>.org1 / ...) is created immediately before saving."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default="This tool performs the operation described by the tool name 'exstruct'.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["extract", "export_file"],
                    "description": _(
                        "param.action.description",
                        default=(
                            "Operation to perform. extract=return extracted content as a string / export_file=save to a file."
                        ),
                    ),
                },
                "file_path": {
                    "type": "string",
                    "description": _(
                        "param.file_path.description",
                        default="Path to the input Excel file (absolute path recommended).",
                    ),
                },
                "mode": {
                    "type": "string",
                    "enum": ["light", "standard", "verbose"],
                    "description": _(
                        "param.mode.description",
                        default="Extraction mode. Defaults to standard.",
                    ),
                },
                "include_shapes": {
                    "type": "boolean",
                    "description": _(
                        "param.include_shapes.description",
                        default="Whether to include shapes in the output. Default is false.",
                    ),
                },
                "include_cell_links": {
                    "type": "boolean",
                    "description": _(
                        "param.include_cell_links.description",
                        default="Whether to include cell hyperlinks. Defaults to mode behavior.",
                    ),
                },
                "pretty": {
                    "type": "boolean",
                    "description": _(
                        "param.pretty.description",
                        default="Pretty print output. Default is false.",
                    ),
                },
                "format": {
                    "type": "string",
                    "enum": ["json", "yaml"],
                    "description": _(
                        "param.format.description",
                        default="Output format. Default is json.",
                    ),
                },
                "output_path": {
                    "type": "string",
                    "description": _(
                        "param.output_path.description",
                        default="Output path for export_file.",
                    ),
                },
                "sheets_dir": {
                    "type": "string",
                    "description": _(
                        "param.sheets_dir.description",
                        default="Directory to save per-sheet files.",
                    ),
                },
                "print_areas_dir": {
                    "type": "string",
                    "description": _(
                        "param.print_areas_dir.description",
                        default="Directory to save per-print-area files.",
                    ),
                },
                "auto_page_breaks_dir": {
                    "type": "string",
                    "description": _(
                        "param.auto_page_breaks_dir.description",
                        default="Directory to save auto page break areas (COM only).",
                    ),
                },
                "table_score_threshold": {
                    "type": "number",
                    "description": _(
                        "param.table_score_threshold.description",
                        default="Table detection threshold.",
                    ),
                },
                "density_min": {
                    "type": "number",
                    "description": _(
                        "param.density_min.description",
                        default="Table density threshold.",
                    ),
                },
            },
            "required": ["action", "file_path"],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    exstruct = _import_exstruct()

    action = str(args.get("action") or "").strip()
    file_path = str(args.get("file_path") or "").strip()

    if action not in ("extract", "export_file"):
        raise ValueError("Invalid action")
    if not file_path:
        raise ValueError("file_path is required")

    mode = args.get("mode")
    include_shapes = bool(args.get("include_shapes", False))
    include_cell_links = args.get("include_cell_links")
    pretty = bool(args.get("pretty", False))
    fmt = str(args.get("format") or "json")

    output_path = args.get("output_path")
    sheets_dir = args.get("sheets_dir")
    print_areas_dir = args.get("print_areas_dir")
    auto_page_breaks_dir = args.get("auto_page_breaks_dir")
    table_score_threshold = args.get("table_score_threshold")
    density_min = args.get("density_min")

    if action == "extract":
        out = exstruct.extract(
            file_path,
            mode=mode,
            include_shapes=include_shapes,
            include_cell_links=include_cell_links,
            pretty=pretty,
            format=fmt,
            table_score_threshold=table_score_threshold,
            density_min=density_min,
        )
        return str(out)

    # export_file
    out = exstruct.export_file(
        file_path,
        mode=mode,
        include_shapes=include_shapes,
        include_cell_links=include_cell_links,
        pretty=pretty,
        format=fmt,
        output_path=output_path,
        sheets_dir=sheets_dir,
        print_areas_dir=print_areas_dir,
        auto_page_breaks_dir=auto_page_breaks_dir,
        table_score_threshold=table_score_threshold,
        density_min=density_min,
    )

    return json.dumps({"ok": True, "output_path": out}, ensure_ascii=False)
