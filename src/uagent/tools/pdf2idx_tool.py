from __future__ import annotations

import os
from typing import Any, List, Dict

from .._pip_auto import install_with_status

if install_with_status("pdfplumber", "pdfplumber", version_spec=">=0.11.9"):
    import pdfplumber
else:
    pdfplumber = None

from .i18n_helper import make_tool_translator
from .index_tool_helpers import resolve_index_path

_ = make_tool_translator(__file__)

TOOL_SPEC = {
    "type": "function",
    "tool_genre": "index",
    "function": {
        "name": "pdf2idx",
        "description": _(
            "tool.description",
            default=(
                "Parse a PDF document (.pdf) into page summaries and text previews, "
                "returning a numbered index or a specific page section. Use this when reading large PDF files: "
                "call with mode='index' to get the list of pages with preview text, then call with "
                "mode='section' and section=N to retrieve the full text content of that page."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "read pdf file",
                "pdf index",
                "pdf parser",
                "pdf page reader",
                "pdf section",
                "PDFファイルを読む",
                "PDFインデックス",
                "ページ目次",
                "ページ抽出",
                "セクション分割",
            ],
        ),
        "x_search_terms_en": [
            "read pdf file",
            "pdf index",
            "pdf parser",
            "pdf page reader",
            "pdf section",
        ],
        "x_parallel_safe": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Path to the PDF (.pdf) file.",
                    ),
                },
                "mode": {
                    "type": "string",
                    "enum": ["index", "section"],
                    "description": _(
                        "param.mode.description",
                        default=(
                            '"index" returns a numbered table of contents listing pages with previews. '
                            '"section" returns the full text content of a specific page.'
                        ),
                    ),
                },
                "section": {
                    "type": "integer",
                    "description": _(
                        "param.section.description",
                        default=(
                            "Page number to retrieve (1-indexed, used only when mode='section'). "
                            "Get the number from the index output."
                        ),
                    ),
                },
            },
            "required": ["path", "mode"],
            "additionalProperties": False,
        },
    },
}


class _PdfIndexBuilder:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.pages: List[Dict[str, Any]] = []
        self._parse()

    def _parse(self) -> None:
        if pdfplumber is None:
            raise RuntimeError("pdfplumber library is required to parse PDF files.")

        with pdfplumber.open(self.filepath) as pdf:
            for idx, page in enumerate(pdf.pages, 1):
                try:
                    text = page.extract_text() or ""
                except Exception:
                    text = ""

                clean_text = text.strip()
                first_line = ""
                preview = ""

                if clean_text:
                    lines = [
                        line.strip() for line in clean_text.splitlines() if line.strip()
                    ]
                    if lines:
                        first_line = lines[0]
                        combined = " / ".join(lines)
                        preview = combined[:60] + ("..." if len(combined) > 60 else "")

                self.pages.append(
                    {
                        "page_num": idx,
                        "first_line": first_line,
                        "preview": preview,
                        "full_text": clean_text,
                    }
                )


def run_tool(args: dict[str, Any]) -> str:
    path = args.get("path")
    if not path:
        return _("err.path_required", default="Error: 'path' is required.")

    mode = args.get("mode", "index")
    section = args.get("section")

    try:
        resolved = resolve_index_path(path)
    except Exception as e:
        return _("err.read_error", default="Error reading file: {e}").format(e=e)

    if not os.path.isfile(resolved):
        return _("err.file_not_found", default="Error: File not found: {path}").format(
            path=path
        )

    try:
        builder = _PdfIndexBuilder(resolved)
    except Exception as e:
        return _("err.parse_error", default="Error parsing PDF file: {e}").format(e=e)

    if not builder.pages:
        return _("msg.no_pages", default="(no pages found in PDF)")

    if mode == "index":
        toc_lines = []
        for p in builder.pages:
            p_num = p["page_num"]
            prev = p["preview"] or "(empty page)"
            toc_lines.append(f"Page {p_num:3d}: {prev}")

        toc = "\n".join(toc_lines)
        return _(
            "msg.index_output",
            default=(
                "Index for: {path}\n---\n{toc}\n---\n"
                "Total pages: {total}\n"
                "To retrieve a page, call pdf2idx with mode='section' and section=N."
            ),
        ).format(path=path, toc=toc, total=len(builder.pages))

    elif mode == "section":
        if section is None:
            return _(
                "err.section_required",
                default="Error: 'section' (integer) is required when mode='section'.",
            )
        try:
            section_num = int(section)
        except (ValueError, TypeError):
            return _(
                "err.section_invalid", default="Error: 'section' must be an integer."
            )

        if section_num < 1 or section_num > len(builder.pages):
            return _(
                "err.section_not_found",
                default="Error: Page {section_num} not found. Valid range: 1..{last}.",
            ).format(section_num=section_num, last=len(builder.pages))

        target = builder.pages[section_num - 1]
        out_lines = [f"=== Page {target['page_num']} ==="]
        if target["full_text"]:
            out_lines.append(target["full_text"])
        else:
            out_lines.append("(empty page / non-extractable text)")

        return "\n".join(out_lines)

    else:
        return _(
            "err.invalid_mode",
            default="Error: Invalid mode '{mode}'. Use 'index' or 'section'.",
        ).format(mode=mode)
