from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

TOOL_SPEC: dict[str, Any] = {
    "tool_level": 1,
    "tool_genre": "office",
    "type": "function",
    "function": {
        "name": "mermaid_to_excel",
        "description": _(
            "tool.description",
            default="Convert a supported Mermaid flowchart into editable Excel shapes without pywin32.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["mermaid", "excel", "xlsx", "shapes", "flowchart"],
        ),
        "x_search_terms_en": ["mermaid", "excel", "xlsx", "shapes", "flowchart"],
        "parameters": {
            "type": "object",
            "properties": {
                "mermaid": {
                    "type": "string",
                    "description": _(
                        "param.mermaid.description",
                        default="Mermaid source text.",
                    ),
                },
                "source_path": {
                    "type": "string",
                    "description": _(
                        "param.source_path.description",
                        default="Optional Mermaid file path.",
                    ),
                },
                "output_path": {
                    "type": "string",
                    "description": _(
                        "param.output_path.description",
                        default="Output .xlsx path.",
                    ),
                },
            },
            "required": ["output_path"],
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    mermaid = str(args.get("mermaid", "") or "")
    source_path = str(args.get("source_path", "") or "").strip()
    output_path = str(args.get("output_path", "") or "").strip()

    if source_path:
        mermaid = Path(source_path).read_text(encoding="utf-8")
    if not mermaid.strip():
        raise ValueError(
            _(
                "error.source_required",
                default="mermaid or source_path is required",
            )
        )
    if not output_path:
        raise ValueError(
            _("error.output_required", default="output_path is required")
        )
    if not output_path.lower().endswith(".xlsx"):
        raise ValueError(
            _(
                "error.output_extension",
                default="output_path must end with .xlsx",
            )
        )

    # The implementation is kept pywin32-free and uses OOXML directly.
    from .mermaid_excel_impl.drawingml import generate_drawing_xml
    from .mermaid_excel_impl.layout import layout_graph
    from .mermaid_excel_impl.parser import parse_mermaid
    from .mermaid_excel_impl.xlsx import write_xlsx

    graph = parse_mermaid(mermaid)
    positions = layout_graph(graph)
    drawing_xml = generate_drawing_xml(graph, positions)
    write_xlsx(output_path, drawing_xml)

    return json.dumps(
        {
            "ok": True,
            "output_path": str(Path(output_path).resolve()),
            "nodes": len(graph.nodes),
            "edges": len(graph.edges),
        },
        ensure_ascii=False,
    )
