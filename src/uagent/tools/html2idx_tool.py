from __future__ import annotations

import os
from typing import Any, List, Dict

from .._pip_auto import install_with_status

BeautifulSoup = None
_bs4_initialized = False


def _ensure_bs4() -> bool:
    global BeautifulSoup, _bs4_initialized
    if _bs4_initialized:
        return BeautifulSoup is not None
    _bs4_initialized = True
    if not install_with_status("beautifulsoup4", "bs4"):
        return False
    try:
        from bs4 import BeautifulSoup as _BeautifulSoup

        BeautifulSoup = _BeautifulSoup
    except Exception:
        BeautifulSoup = None
    return BeautifulSoup is not None


from .i18n_helper import make_tool_translator
from .index_tool_helpers import read_index_source, resolve_index_path

_ = make_tool_translator(__file__)

TOOL_SPEC = {
    "type": "function",
    "tool_genre": "index",
    "function": {
        "name": "html2idx",
        "description": _(
            "tool.description",
            default=(
                "Parse an HTML or XML file (.html/.xml) into headings, sections, and structural elements, "
                "returning a numbered index or a specific section. Use this when reading large HTML/XML files: "
                "call with mode='index' to get heading/element tree previews, then call with "
                "mode='section' and section=N to retrieve the text content of that section."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "read html file",
                "html index",
                "xml parser",
                "html section",
                "Read HTML files",
                "HTML index",
                "XML parser",
                "Split into sections",
            ],
        ),
        "x_search_terms_en": [
            "read html file",
            "html index",
            "xml parser",
            "html section",
        ],
        "x_parallel_safe": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Path to the HTML/XML file.",
                    ),
                },
                "mode": {
                    "type": "string",
                    "enum": ["index", "section"],
                    "description": _(
                        "param.mode.description",
                        default=(
                            '"index" returns a numbered table of contents of headings and sections. '
                            '"section" returns the text content of a specific element section.'
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


class _HtmlIndexBuilder:
    def __init__(self, source: str):
        self.source = source
        self.elements: List[Dict[str, Any]] = []
        self._parse()

    def _parse(self) -> None:
        if BeautifulSoup is None:
            raise RuntimeError(
                "beautifulsoup4 library is required to parse HTML/XML files."
            )

        soup = BeautifulSoup(self.source, "html.parser")

        # Find headings (h1..h6) or section/article tags
        headers = soup.find_all(
            ["h1", "h2", "h3", "h4", "h5", "h6", "section", "article"]
        )

        if not headers:
            # Fallback to body or root text
            body_text = soup.get_text(separator=" ", strip=True)
            self.elements.append(
                {
                    "tag": "body",
                    "title": "Document Body",
                    "preview": body_text[:60] + ("..." if len(body_text) > 60 else ""),
                    "full_text": body_text,
                }
            )
            return

        for tag in headers:
            tag_name = tag.name.upper()
            text = tag.get_text(separator=" ", strip=True)
            if not text:
                continue
            title = text[:80].replace("\n", " ")
            preview = text[:60].replace("\n", " ") + ("..." if len(text) > 60 else "")

            self.elements.append(
                {
                    "tag": tag_name,
                    "title": title,
                    "preview": preview,
                    "full_text": text,
                }
            )


def run_tool(args: dict[str, Any]) -> str:
    if not _ensure_bs4():
        return _("err.bs4_missing", default="Error: beautifulsoup4 is not installed or could not be imported.")
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
        source = read_index_source(resolved)
        builder = _HtmlIndexBuilder(source)
    except Exception as e:
        return _("err.parse_error", default="Error parsing HTML file: {e}").format(e=e)

    if not builder.elements:
        return _("msg.no_elements", default="(no HTML/XML sections found)")

    if mode == "index":
        toc_lines = []
        for idx, elem in enumerate(builder.elements, 1):
            t_name = elem["tag"]
            title = elem["title"]
            toc_lines.append(f"Section {idx:2d} [{t_name}]: {title}")

        toc = "\n".join(toc_lines)
        return _(
            "msg.index_output",
            default=(
                "Index for: {path}\n---\n{toc}\n---\n"
                "Total sections: {total}\n"
                "To retrieve a section, call html2idx with mode='section' and section=N."
            ),
        ).format(path=path, toc=toc, total=len(builder.elements))

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

        if section_num < 1 or section_num > len(builder.elements):
            return _(
                "err.section_not_found",
                default="Error: Section {section_num} not found. Valid range: 1..{last}.",
            ).format(section_num=section_num, last=len(builder.elements))

        target = builder.elements[section_num - 1]
        return (
            f"=== Section {section_num} [{target['tag']}]: {target['title']} ===\n"
            + target["full_text"]
        )

    else:
        return _(
            "err.invalid_mode",
            default="Error: Invalid mode '{mode}'. Use 'index' or 'section'.",
        ).format(mode=mode)
