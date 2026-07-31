from __future__ import annotations

import os
from typing import Any, List, Dict

from .._pip_auto import install_with_status

if install_with_status("python-docx", "docx"):
    import docx
else:
    docx = None

from .i18n_helper import make_tool_translator
from .index_tool_helpers import resolve_index_path

_ = make_tool_translator(__file__)

TOOL_SPEC = {
    "type": "function",
    "tool_genre": "index",
    "function": {
        "name": "docx2idx",
        "description": _(
            "tool.description",
            default=(
                "Parse a Word document (.docx) into headings and paragraph sections, "
                "returning a numbered index or a specific section. Use this when reading large Word files: "
                "call with mode='index' to get heading table of contents and previews, then call with "
                "mode='section' and section=N to retrieve the content under that heading."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "read docx file",
                "word index",
                "docx parser",
                "word document reader",
                "Wordファイルを読む",
                "DOCXインデックス",
                "見出し目次",
                "セクション分割",
            ],
        ),
        "x_search_terms_en": [
            "read docx file",
            "word index",
            "docx parser",
            "word document reader",
        ],
        "x_parallel_safe": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Path to the Word (.docx) file.",
                    ),
                },
                "mode": {
                    "type": "string",
                    "enum": ["index", "section"],
                    "description": _(
                        "param.mode.description",
                        default=(
                            '"index" returns a numbered table of contents of headings. '
                            '"section" returns paragraph texts under a specific heading.'
                        ),
                    ),
                },
                "section": {
                    "type": "integer",
                    "description": _(
                        "param.section.description",
                        default=(
                            "Section number to retrieve (1-indexed, used only when mode='section'). "
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


class _DocxIndexBuilder:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.sections: List[Dict[str, Any]] = []
        self._parse()

    def _parse(self) -> None:
        if docx is None:
            raise RuntimeError("python-docx library is required to parse .docx files.")

        doc = docx.Document(self.filepath)

        current_heading = "Document Start"
        current_paragraphs: List[str] = []

        for p in doc.paragraphs:
            text = p.text.strip()
            if not text:
                continue

            style_name = (p.style.name or "").lower() if p.style else ""
            is_heading = "heading" in style_name or style_name.startswith("h")

            if is_heading:
                if current_paragraphs or current_heading != "Document Start":
                    combined = " ".join(current_paragraphs)
                    preview = combined[:60] + ("..." if len(combined) > 60 else "")
                    self.sections.append(
                        {
                            "heading": current_heading,
                            "paragraphs": current_paragraphs,
                            "preview": preview,
                        }
                    )
                current_heading = text
                current_paragraphs = []
            else:
                current_paragraphs.append(text)

        if current_paragraphs or current_heading:
            combined = " ".join(current_paragraphs)
            preview = combined[:60] + ("..." if len(combined) > 60 else "")
            self.sections.append(
                {
                    "heading": current_heading,
                    "paragraphs": current_paragraphs,
                    "preview": preview,
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
        builder = _DocxIndexBuilder(resolved)
    except Exception as e:
        return _("err.parse_error", default="Error parsing Word file: {e}").format(e=e)

    if not builder.sections:
        return _(
            "msg.no_sections", default="(no sections or paragraphs found in document)"
        )

    if mode == "index":
        toc_lines = []
        for idx, sec in enumerate(builder.sections, 1):
            h_text = sec["heading"]
            prev = f" - {sec['preview']}" if sec["preview"] else ""
            toc_lines.append(f"Section {idx:2d}: {h_text}{prev}")

        toc = "\n".join(toc_lines)
        return _(
            "msg.index_output",
            default=(
                "Index for: {path}\n---\n{toc}\n---\n"
                "Total sections: {total}\n"
                "To retrieve a section, call docx2idx with mode='section' and section=N."
            ),
        ).format(path=path, toc=toc, total=len(builder.sections))

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

        if section_num < 1 or section_num > len(builder.sections):
            return _(
                "err.section_not_found",
                default="Error: Section {section_num} not found. Valid range: 1..{last}.",
            ).format(section_num=section_num, last=len(builder.sections))

        target = builder.sections[section_num - 1]
        out_lines = [f"=== Section {section_num}: {target['heading']} ==="]
        out_lines.extend(target["paragraphs"])

        return "\n".join(out_lines)

    else:
        return _(
            "err.invalid_mode",
            default="Error: Invalid mode '{mode}'. Use 'index' or 'section'.",
        ).format(mode=mode)
