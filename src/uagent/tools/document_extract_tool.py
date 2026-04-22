from __future__ import annotations

from pathlib import Path
from typing import Any
from uagent.util import _

try:
    from docx import Document
except Exception:  # pragma: no cover
    Document = None

try:
    import odf
    from odf import teletype
    from odf.opendocument import load as odf_load
    from odf.table import Table, TableCell, TableRow
    from odf.text import H, P
except Exception:  # pragma: no cover
    odf = None
    teletype = None
    odf_load = None
    Table = TableCell = TableRow = H = P = None

try:
    from striprtf.striprtf import rtf_to_text
except Exception:  # pragma: no cover
    rtf_to_text = None


TOOL_SPEC = {
    "name": "document_extract",
    "description": _(
        "tool.description",
        default=(
            "Extract text and basic structure from Word-like documents (.docx, .rtf, .odt). "
            "Choose output_format=text or output_format=json. The tool always returns JSON."
        ),
    ),
    "system_prompt": _(
        "tool.system_prompt",
        default=(
            "Read .docx, .rtf, or .odt documents and return JSON only. "
            "If output_format=text, place the extracted text in the JSON response. "
            "If output_format=json, include structured sections and tables when available."
        ),
    ),
    "parameters": [
        {
            "name": "path",
            "type": "string",
            "required": True,
            "description": _(
                "param.path.description",
                default="Path to the input document (.docx, .rtf, .odt).",
            ),
        },
        {
            "name": "output_format",
            "type": "string",
            "required": False,
            "default": "json",
            "description": _(
                "param.output_format.description",
                default="Output format: text or json.",
            ),
        },
    ],
}


def _docx_extract(path: Path) -> dict[str, Any]:
    if Document is None:
        raise RuntimeError("python-docx is not available")
    doc = Document(str(path))
    paragraphs: list[str] = []
    sections: list[dict[str, Any]] = []
    tables: list[list[list[str]]] = []

    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        style_name = getattr(getattr(p, "style", None), "name", "") or ""
        level = None
        if style_name.lower().startswith("heading "):
            try:
                level = int(style_name.split()[-1])
            except Exception:
                level = None
        sections.append(
            {
                "type": "heading" if level is not None else "paragraph",
                "level": level,
                "text": text,
            }
        )
        paragraphs.append(text)

    for table in doc.tables:
        rows: list[list[str]] = []
        for row in table.rows:
            rows.append([cell.text.replace("
", "
").strip() for cell in row.cells])
        tables.append(rows)

    return {
        "file_type": "docx",
        "text": "

".join(paragraphs),
        "sections": sections,
        "tables": tables,
    }


def _rtf_extract(path: Path) -> dict[str, Any]:
    if rtf_to_text is None:
        raise RuntimeError("striprtf is not available")
    raw = path.read_bytes()
    text = rtf_to_text(raw.decode("utf-8", errors="ignore"))
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return {
        "file_type": "rtf",
        "text": "
".join(lines),
        "sections": [{"type": "paragraph", "text": line} for line in lines],
        "tables": [],
    }


def _odt_extract(path: Path) -> dict[str, Any]:
    if odf_load is None:
        raise RuntimeError("odfpy is not available")
    doc = odf_load(str(path))
    paragraphs: list[str] = []
    tables: list[list[list[str]]] = []

    for node in doc.getElementsByType(P):
        text = teletype.extractText(node) if teletype is not None else ""
        if text.strip():
            paragraphs.append(text)
    for node in doc.getElementsByType(H):
        text = teletype.extractText(node) if teletype is not None else ""
        if text.strip():
            paragraphs.append(text)
    for table in doc.getElementsByType(Table):
        rows: list[list[str]] = []
        for row in table.getElementsByType(TableRow):
            cells: list[str] = []
            for cell in row.getElementsByType(TableCell):
                cell_text = ""
                for p in cell.getElementsByType(P):
                    t = teletype.extractText(p) if teletype is not None else ""
                    if t:
                        cell_text += t
                cells.append(cell_text)
            rows.append(cells)
        tables.append(rows)
    return {
        "file_type": "odt",
        "text": "\n".join(paragraphs),
        "sections": [{"type": "paragraph", "text": p} for p in paragraphs],
        "tables": tables,
    }


def run(path: str, output_format: str = "json") -> dict[str, Any]:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix not in {".docx", ".rtf", ".odt"}:
        return {
            "ok": False,
            "error": f"unsupported file type: {suffix}",
            "warnings": [],
        }

    try:
        if suffix == ".docx":
            data = _docx_extract(p)
        elif suffix == ".rtf":
            data = _rtf_extract(p)
        else:
            data = _odt_extract(p)
    except Exception as e:
        return {"ok": False, "error": str(e), "warnings": []}

    text = data.get("text", "")
    if output_format == "text":
        data = {**data, "output_format": "text", "text": text}
    else:
        data = {**data, "output_format": "json"}

    return {"ok": True, "warnings": [], **data}
