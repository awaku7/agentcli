from __future__ import annotations

# Based on md2idx (https://github.com/oubakiou/md2idx) — a Markdown section splitter
# designed for LLM context efficiency. Original concept by oubakiou.

import os
import re
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

TOOL_SPEC = {
    "type": "function",
    "tool_genre": "basic",
    "function": {
        "name": "md2idx",
        "description": _(
            "tool.description",
            default=(
                "Split a Markdown file into heading-level sections and return a numbered index "
                "or a specific section. Use this when you need to read a large Markdown document: "
                "first call with mode='index' to get the table of contents, then call with "
                "mode='section' and the section number to retrieve only the content you need. "
                "This saves tokens compared to reading the entire file."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "read markdown file",
                "markdown table of contents",
                "markdown index",
                "markdown section",
                "large document reader",
                "md2idx",
                "markdownを読む",
                "マークダウン目次",
                "セクション分割",
                "大きなドキュメント",
                "見出し一覧",
            ],
        ),
        "x_search_terms_en": [
            "read markdown file",
            "markdown table of contents",
            "markdown index",
            "markdown section",
            "large document reader",
            "md2idx",
        ],
        "x_parallel_safe": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Path to the Markdown file.",
                    ),
                },
                "mode": {
                    "type": "string",
                    "enum": ["index", "section"],
                    "description": _(
                        "param.mode.description",
                        default=(
                            '"index" returns a numbered table of contents. '
                            '"section" returns a specific section by number.'
                        ),
                    ),
                },
                "section": {
                    "type": "integer",
                    "description": _(
                        "param.section.description",
                        default=(
                            "Section number to retrieve (used only when mode='section'). "
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


def _strip_inline_markup(text: str) -> str:
    """Remove inline Markdown formatting for cleaner index display."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    text = re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    return text


class _MdSectionParser:
    """Zero-dependency Markdown section parser.

    Detects ATX headings (# ...) and setext headings (=== / ---).
    Skips fenced code blocks. Handles preamble before first heading.
    """

    def __init__(self, text: str):
        self.text = text
        self.lines = text.split("\n")
        self.headings: list[dict[str, Any]] = []
        self._parse()

    @staticmethod
    def _is_fence_line(line: str, fence_stack: list[str]) -> bool:
        stripped = line.strip()
        for delim in ("```", "~~~"):
            if stripped.startswith(delim):
                count = 0
                for ch in stripped:
                    if ch == delim[0]:
                        count += 1
                    else:
                        break
                if count >= 3:
                    if fence_stack and fence_stack[-1] == delim:
                        fence_stack.pop()
                    else:
                        fence_stack.append(delim)
                    return True
        return False

    @staticmethod
    def _is_setext_underline(line: str) -> int:
        """Return heading level (1 or 2) if line is a setext underline, else 0."""
        stripped = line.strip()
        if not stripped:
            return 0
        if re.fullmatch(r"=+\s*", stripped):
            return 1
        if re.fullmatch(r"-+\s*", stripped):
            return 2
        return 0

    @staticmethod
    def _is_atx_heading(stripped: str) -> tuple[int, str] | None:
        m = re.match(r"^(#{1,6})\s+(.+?)(?:\s+#+)?\s*$", stripped)
        if m:
            return (len(m.group(1)), m.group(2))
        return None

    def _parse(self):
        fence_stack: list[str] = []
        in_fence = False
        headings: list[dict[str, Any]] = []
        prev_line: str | None = None
        prev_line_nonempty: bool = False

        for i, line in enumerate(self.lines):
            stripped = line.strip()

            if self._is_fence_line(line, fence_stack):
                in_fence = bool(fence_stack)
                prev_line = line
                prev_line_nonempty = bool(stripped)
                continue

            if in_fence:
                prev_line = line
                prev_line_nonempty = bool(stripped)
                continue

            # Setext heading: underline must follow a non-empty, non-heading line
            setext_level = self._is_setext_underline(line)
            if setext_level > 0 and prev_line_nonempty and prev_line is not None:
                prev_stripped = prev_line.strip()
                if not self._is_setext_underline(prev_line):
                    heading_text = prev_stripped
                    headings.append({
                        "level": setext_level,
                        "text": heading_text,
                        "line": i - 1,
                        "end_line": i,
                    })
                    prev_line = line
                    prev_line_nonempty = False
                    continue

            # ATX heading detection
            atx = self._is_atx_heading(stripped)
            if atx:
                level, heading_text = atx
                headings.append({
                    "level": level,
                    "text": heading_text,
                    "line": i,
                    "end_line": i,
                })
                prev_line = line
                prev_line_nonempty = bool(stripped)
                continue

            prev_line = line
            prev_line_nonempty = bool(stripped)

        self.headings = headings

    def build_index(self) -> str:
        if not self.headings:
            return "0. (no headings)"
        lines = []
        for idx, h in enumerate(self.headings):
            prefix = "#" * h["level"]
            clean_text = _strip_inline_markup(h["text"])
            lines.append(f"{prefix} {idx + 1}. {clean_text}")
        return "\n".join(lines)

    def build_sections(self) -> list[str]:
        if not self.headings:
            text = self.text.strip()
            return [text] if text else [""]

        sections: list[str] = []
        first_line = self.headings[0]["line"]
        preamble_lines = self.lines[:first_line]
        preamble = "\n".join(preamble_lines).strip()
        sections.append(preamble)

        for i, h in enumerate(self.headings):
            start = h["line"]
            if i + 1 < len(self.headings):
                end = self.headings[i + 1]["line"]
            else:
                end = len(self.lines)
            body = "\n".join(self.lines[start:end]).strip()
            sections.append(body)

        return sections

    def get_section(self, number: int) -> str | None:
        sections = self.build_sections()
        if 0 <= number < len(sections):
            return sections[number]
        return None

    def section_count(self) -> int:
        return len(self.headings) + 1


def run_tool(args: dict[str, Any]) -> str:
    path = args.get("path", "")
    mode = args.get("mode", "index")

    if not path:
        return _("err.path_required", default="Error: 'path' is required.")

    if not os.path.isfile(path):
        return _("err.file_not_found", default="Error: File not found: {path}", path=path)

    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        return _("err.read_error", default="Error reading file: {e}", e=str(e))

    try:
        parser = _MdSectionParser(text)
    except Exception as e:
        return _("err.parse_error", default="Error parsing Markdown: {e}", e=str(e))

    if mode == "index":
        toc = parser.build_index()
        total = parser.section_count()
        last = total - 1
        return _(
            "msg.index_output",
            default=(
                "Table of contents for: {path}\n"
                "(0 = preamble before first heading, 1..{last} = heading sections)\n"
                "---\n"
                "{toc}\n"
                "---\n"
                "Total sections: {total}\n"
                "To retrieve a section, call md2idx with mode='section' and the section number."
            ),
            path=path,
            total=total,
            last=last,
            toc=toc,
        )

    elif mode == "section":
        section_num = args.get("section")
        if section_num is None:
            return _("err.section_required", default="Error: 'section' (integer) is required when mode='section'.")

        try:
            section_num = int(section_num)
        except (TypeError, ValueError):
            return _("err.section_invalid", default="Error: 'section' must be an integer.", section_num=repr(section_num))

        content = parser.get_section(section_num)
        if content is None:
            total = parser.section_count()
            return _(
                "err.section_not_found",
                default="Error: Section {section_num} not found. Valid range: 0..{last}.",
                section_num=section_num,
                last=total - 1,
            )

        return content

    else:
        return _("err.invalid_mode", default="Error: Invalid mode '{mode}'. Use 'index' or 'section'.", mode=mode)
