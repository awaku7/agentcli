from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Dict

from .i18n_helper import make_tool_translator

try:
    import msoffcrypto
except Exception:  # pragma: no cover
    msoffcrypto = None  # type: ignore[assignment]

_ = make_tool_translator(__file__)

BUSY_LABEL = True


def _import_exstruct():
    # Local import to avoid requiring dependency at import time.
    import exstruct  # type: ignore

    return exstruct


def _prompt_for_password(path: str) -> str | None:
    try:
        from .human_ask_tool import run_tool as human_ask
    except Exception:
        return None

    message = _(
        "prompt.password",
        default="Enter the password for this file:\
{path}",
    ).format(path=path)
    try:
        res_json = human_ask({"message": message, "is_password": True})
        res = json.loads(res_json)
    except Exception:
        return None

    pwd = str(res.get("user_reply") or "").strip()
    return pwd or None


def _resolve_input_file(
    file_path: str, password: str | None = None
) -> tuple[str, str | None]:
    if msoffcrypto is None:
        return file_path, None

    with open(file_path, "rb") as fin:
        office = msoffcrypto.OfficeFile(fin)
        encrypted = False
        try:
            encrypted = bool(office.is_encrypted())
        except Exception:
            encrypted = False

        if not encrypted:
            return file_path, None

        if not password:
            password = _prompt_for_password(file_path)
        if not password:
            raise RuntimeError("password is required for encrypted workbook files")

        office.load_key(password=password)
        fd, temp_path = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        try:
            with open(temp_path, "wb") as fout:
                office.decrypt(fout)
        except Exception:
            try:
                os.unlink(temp_path)
            except Exception:
                pass
            raise
        return temp_path, temp_path


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
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "exstruct",
                "exstruct",
                "structured data",
                "excel structure",
                "export json",
                "export yaml",
            ],
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
                "password": {
                    "type": "string",
                    "description": _(
                        "param.password.description",
                        default=(
                            "Optional password for encrypted .xlsx files. If omitted and the file is encrypted, "
                            "the tool will prompt once for a password."
                        ),
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
    password = str(args.get("password") or "").strip() or None

    if action not in ("extract", "export_file"):
        raise ValueError("Invalid action")
    if not file_path:
        raise ValueError("file_path is required")

    # exstruct (current) API reference (confirmed in this environment):
    # - extract(file_path, mode='standard', *, alpha_col=False) -> WorkbookData
    # - export(data, path, fmt=None, *, pretty=False, indent=None) -> None
    # - set_table_detection_params(...)

    mode = str(args.get("mode") or "standard")
    alpha_col = bool(args.get("alpha_col", False))

    # Compatibility: these flags are not controllable via extract() in current exstruct.
    # We accept them but do not enforce them.
    _ = bool(args.get("include_shapes", False))
    _ = args.get("include_cell_links")

    pretty = bool(args.get("pretty", False))
    fmt = str(args.get("format") or "json").lower()

    output_path = str(args.get("output_path") or "").strip()
    table_score_threshold = args.get("table_score_threshold")
    density_min = args.get("density_min")

    # Apply table detection params when provided
    try:
        if table_score_threshold is not None or density_min is not None:
            exstruct.set_table_detection_params(
                table_score_threshold=table_score_threshold,
                density_min=density_min,
            )
    except Exception:
        # Best-effort: ignore if API changes
        pass

    resolved_file_path = file_path
    temp_path: str | None = None
    try:
        resolved_file_path, temp_path = _resolve_input_file(
            file_path, password=password
        )

        data = exstruct.extract(
            resolved_file_path,
            mode=mode,
            alpha_col=alpha_col,
        )

        if action == "extract":
            # Return as JSON/YAML string without touching filesystem.
            # export() requires a path, so we serialize in-process.
            try:
                as_dict = data.model_dump()  # pydantic v2
            except Exception:
                try:
                    as_dict = data.dict()  # pydantic v1
                except Exception:
                    # Fallback: stringify
                    return str(data)

            if fmt == "yaml" or fmt == "yml":
                try:
                    import yaml  # type: ignore

                    return yaml.safe_dump(
                        as_dict,
                        allow_unicode=True,
                        sort_keys=False,
                    )
                except Exception as e:
                    raise RuntimeError(
                        "YAML output requested but PyYAML is not available or failed. "
                        f"Install pyyaml or use format=json. Details: {e}"
                    )

            return json.dumps(
                as_dict,
                ensure_ascii=False,
                indent=2 if pretty else None,
            )

        # export_file: save via exstruct.export (this matches latest API).
        if not output_path:
            raise ValueError("output_path is required for export_file")

        # Backup behavior is handled by the agent framework for tools that write.
        # Here we write directly via exstruct.export.
        exstruct.export(
            data,
            output_path,
            fmt=fmt,
            pretty=pretty,
        )

        return json.dumps({"ok": True, "output_path": output_path}, ensure_ascii=False)
    finally:
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except Exception:
                pass
