from __future__ import annotations

from pathlib import Path
from typing import Any

from .i18n_helper import make_tool_translator
from .mermaid_render_tool import run_tool as _render_mermaid
from .safe_file_ops_extras import ensure_within_workdir

_ = make_tool_translator(__file__)

BUSY_LABEL = True

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "media",
    "tool_level": 0,
    "x_parallel_safe": False,
    "function": {
        "name": "mmd_to_svg",
        "description": _(
            "tool.description",
            default=(
                "Convert a Mermaid Markdown (.mmd) file to an SVG diagram locally. "
                "Japanese and other supported scripts are handled when suitable fonts are available."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "mmd to svg",
                "Mermaid Markdown to SVG",
                "Mermaid file converter",
                "Mermaid SVG",
                "convert .mmd",
            ],
        ),
        "x_search_terms_en": [
            "mmd to svg",
            "Mermaid Markdown to SVG",
            "Mermaid file converter",
            "Mermaid SVG",
            "convert .mmd",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "mmd": {
                    "type": "string",
                    "description": _(
                        "param.mmd.description",
                        default="Path to the input Mermaid Markdown (.mmd) file.",
                    ),
                },
                "output_path": {
                    "type": "string",
                    "description": _(
                        "param.output_path.description",
                        default="Output SVG path. It must end in .svg.",
                    ),
                },
                "theme": {
                    "type": "string",
                    "enum": ["default", "forest", "dark", "neutral"],
                    "default": "default",
                    "description": _(
                        "param.theme.description",
                        default="Mermaid theme.",
                    ),
                },
                "include_base64": {
                    "type": "boolean",
                    "default": True,
                    "description": _(
                        "param.include_base64.description",
                        default="Include base64 SVG data for remote clients. Default: true.",
                    ),
                },
            },
            "required": ["mmd", "output_path"],
            "additionalProperties": False,
        },
    },
    "is_agent_content": False,
}


def run_tool(args: dict[str, Any]) -> str:
    mmd_raw = str(args.get("mmd") or "").strip()
    output_raw = str(args.get("output_path") or "").strip()
    if not mmd_raw:
        raise ValueError(_("error.mmd_required", default="mmd is required"))
    if not output_raw:
        raise ValueError(_("error.output_required", default="output_path is required"))

    mmd_path = Path(ensure_within_workdir(mmd_raw))
    output_path = Path(ensure_within_workdir(output_raw))
    if not mmd_path.is_file():
        raise FileNotFoundError(
            _(
                "error.input_not_found",
                default="Mermaid Markdown file was not found: %(path)s",
                path=mmd_path,
            )
        )
    if mmd_path.suffix.lower() not in {".mmd", ".mermaid"}:
        raise ValueError(
            _(
                "error.input_extension",
                default="The input file must have a .mmd or .mermaid extension.",
            )
        )
    if output_path.suffix.lower() != ".svg":
        raise ValueError(
            _(
                "error.output_extension",
                default="output_path must end in .svg.",
            )
        )

    return _render_mermaid(
        {
            "input_path": str(mmd_path),
            "output_path": str(output_path),
            "theme": str(args.get("theme") or "default"),
            "include_base64": bool(args.get("include_base64", True)),
        }
    )


if __name__ == "__main__":
    print(run_tool({"mmd": "diagram.mmd", "output_path": "diagram.svg"}))
