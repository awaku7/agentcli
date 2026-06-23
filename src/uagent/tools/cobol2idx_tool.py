from __future__ import annotations

import os
import re
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

TOOL_SPEC = {
    "type": "function",
    "tool_genre": "index",
    "function": {
        "name": "cobol2idx",
        "description": _(
            "tool.description",
            default=(
                "Parse a COBOL (.cbl/.cob/.cpy) file into divisions, sections, paragraphs, "
                "data definitions, and copybooks and return a numbered index or a specific "
                "definition section. Use this when you need to read a large COBOL file: "
                "first call with mode='index' to get the table of contents, then call with "
                "mode='section' and the section number to retrieve only the definition you need."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "read cobol file",
                "cobol file index",
                "cobol program structure",
                "cobol division",
                "cobol paragraph",
                "COBOLファイルを読む",
                "COBOL プログラム構造",
                "パラグラフ一覧",
                "セクション一覧",
            ],
        ),
        "x_search_terms_en": [
            "read cobol file",
            "cobol file index",
            "cobol program structure",
            "cobol division",
            "cobol paragraph",
        ],
        "x_parallel_safe": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Path to the COBOL (.cbl/.cob/.cpy) file.",
                    ),
                },
                "mode": {
                    "type": "string",
                    "enum": ["index", "section"],
                    "description": _(
                        "param.mode.description",
                        default=(
                            '"index" returns a numbered table of contents with line numbers. '
                            '"section" returns a specific definition by number.'
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

# COBOL definition patterns
# COBOL is case-insensitive; we normalize to uppercase for matching.
# Patterns detect key structural elements.
_PATTERNS = [
    # PROGRAM-ID. name  or  PROGRAM-ID name
    (r"PROGRAM-ID\.?\s+(\w+)",
     lambda m: ("program", m.group(1))),
    # IDENTIFICATION DIVISION
    (r"IDENTIFICATION\s+DIVISION",
     lambda m: ("division", "IDENTIFICATION DIVISION")),
    # DATA DIVISION
    (r"DATA\s+DIVISION",
     lambda m: ("division", "DATA DIVISION")),
    # PROCEDURE DIVISION [USING ...]
    (r"PROCEDURE\s+DIVISION",
     lambda m: ("division", "PROCEDURE DIVISION")),
    # ENVIRONMENT DIVISION
    (r"ENVIRONMENT\s+DIVISION",
     lambda m: ("division", "ENVIRONMENT DIVISION")),
    # CONFIGURATION SECTION
    (r"CONFIGURATION\s+SECTION\.?\s*$",
     lambda m: ("section", "CONFIGURATION SECTION")),
    # INPUT-OUTPUT SECTION
    (r"INPUT-OUTPUT\s+SECTION\.?\s*$",
     lambda m: ("section", "INPUT-OUTPUT SECTION")),
    # WORKING-STORAGE SECTION
    (r"WORKING-STORAGE\s+SECTION\.?\s*$",
     lambda m: ("section", "WORKING-STORAGE SECTION")),
    # LINKAGE SECTION
    (r"LINKAGE\s+SECTION\.?\s*$",
     lambda m: ("section", "LINKAGE SECTION")),
    # FILE SECTION
    (r"FILE\s+SECTION\.?\s*$",
     lambda m: ("section", "FILE SECTION")),
    # SCREEN SECTION
    (r"SCREEN\s+SECTION\.?\s*$",
     lambda m: ("section", "SCREEN SECTION")),
    # REPORT SECTION
    (r"REPORT\s+SECTION\.?\s*$",
     lambda m: ("section", "REPORT SECTION")),
    # FD file-name
    (r"^FD\s+(\w+)",
     lambda m: ("fd", m.group(1))),
    # SELECT file-name ASSIGN ...
    (r"^SELECT\s+(\w+)",
     lambda m: ("select", m.group(1))),
    # Level 01 / 77 data definitions: 01 data-name, 77 data-name
    (r"^(?:01|77)\s+([\w-]+)",
     lambda m: ("data", m.group(1))),
    # Level 02-66, 78 data definitions
    (r"^(?:0[2-9]|[1-4][0-9]|5[0-9]|6[0-6]|78)\s+([\w-]+)",
     lambda m: ("data", m.group(1))),
    # DECLARATIVES.
    (r"^DECLARATIVES\.?\s*$",
     lambda m: ("declaratives", "DECLARATIVES")),
    # END DECLARATIVES.
    (r"^END\s+DECLARATIVES\.?\s*$",
     lambda m: ("end-declaratives", "END DECLARATIVES")),
    # Paragraph: word[s] followed by a period at the start of Area B (non-data, non-keyword)
    # Must not be a known keyword, and the line should end with just a period
    (r"^(\w[\w-]*)\s*\.\s*$",
     lambda m: ("paragraph", m.group(1))),
    # COPY text-name
    (r"^COPY\s+(\w+)",
     lambda m: ("copy", m.group(1))),
]

# Keywords that should NOT be treated as paragraph names
_PARAGRAPH_EXCLUDE = {
    "ACCEPT", "ADD", "ALL", "ALPHABETIC", "ALSO", "ALTER", "AND", "ARE", "AREA",
    "AS", "ASCENDING", "ASSIGN", "AT", "AUTHOR",
    "BEFORE", "BINARY", "BLANK", "BLOCK", "BOTTOM", "BY",
    "CALL", "CANCEL", "CD", "CF", "CH", "CHARACTER", "CLOCK-UNITS",
    "CLOSE", "COBOL", "CODE", "COLLATING", "COLUMN", "COMMA",
    "COMMON", "COMP", "COMP-1", "COMP-2", "COMP-3", "COMP-4", "COMP-5",
    "COMPUTE", "CONFIGURATION", "CONTAINS", "CONTENT", "CONTINUE",
    "CONTROL", "CONTROLS", "CONVERTING", "COPY", "CORR", "CORRESPONDING",
    "COUNT", "CURRENCY", "CURSOR",
    "DATA", "DATE", "DAY", "DAY-OF-WEEK", "DE", "DEBUG-CONTENTS",
    "DEBUG-ITEM", "DEBUG-LINE", "DEBUG-NAME", "DEBUG-SUB-1",
    "DEBUG-SUB-2", "DEBUG-SUB-3", "DEBUGGING", "DECIMAL-POINT",
    "DECLARATIVES", "DELETE", "DELIMITED", "DELIMITER", "DEPENDING",
    "DESCENDING", "DESTINATION", "DETAIL", "DISABLE", "DISPLAY",
    "DIVIDE", "DIVISION", "DOWN", "DUPLICATES", "DYNAMIC",
    "EGI", "ELSE", "EMI", "ENABLE", "END", "END-ACCEPT",
    "END-ADD", "END-CALL", "END-COMPUTE", "END-DELETE",
    "END-DISPLAY", "END-DIVIDE", "END-EVALUATE", "END-IF",
    "END-MULTIPLY", "END-OF-PAGE", "END-PERFORM", "END-READ",
    "END-RECEIVE", "END-RETURN", "END-REWRITE", "END-SEARCH",
    "END-START", "END-STRING", "END-SUBTRACT", "END-UNSTRING",
    "END-WRITE", "ENTRY", "ENVIRONMENT", "EOP", "EQUAL", "ERROR",
    "ESI", "EVALUATE", "EVERY", "EXCEPTION", "EXIT", "EXTEND",
    "EXTERNAL",
    "FALSE", "FD", "FILE", "FILE-CONTROL", "FILLER", "FINAL",
    "FIRST", "FOOTING", "FOR", "FOREGROUND", "FORMAT", "FROM",
    "FUNCTION",
    "GENERATE", "GET", "GIVING", "GLOBAL", "GO", "GOBACK",
    "GREATER", "GROUP",
    "HEADING", "HIGH-VALUE", "HIGH-VALUES",
    "I-O", "I-O-CONTROL", "IDENTIFICATION", "IF", "IN",
    "INDEX", "INDEXED", "INDICATE", "INITIAL", "INITIALIZE",
    "INITIATE", "INPUT", "INPUT-OUTPUT", "INSPECT", "INSTALLATION",
    "INTO", "INVALID", "IS",
    "JUST", "JUSTIFIED",
    "KEY",
    "LABEL", "LAST", "LEADING", "LEFT", "LENGTH", "LESS", "LIMIT",
    "LIMITS", "LINAGE", "LINAGE-COUNTER", "LINE", "LINE-COUNTER",
    "LINES", "LINKAGE", "LOCK", "LOW-VALUE", "LOW-VALUES",
    "MEMORY", "MERGE", "MESSAGE", "METHOD", "MODE", "MODULES",
    "MOVE", "MULTIPLE", "MULTIPLY",
    "NATIONAL", "NATIVE", "NEGATIVE", "NEXT", "NO", "NOT",
    "NULL", "NULLS", "NUMBER", "NUMERIC",
    "OBJECT-COMPUTER", "OCCURS", "OF", "OFF", "OMITTED", "ON",
    "OPEN", "OPTIONAL", "OR", "ORDER", "ORGANIZATION", "OTHER",
    "OUTPUT", "OVERFLOW", "OVERRIDE",
    "PACKED-DECIMAL", "PADDING", "PAGE", "PAGE-COUNTER", "PERFORM",
    "PF", "PH", "PIC", "PICTURE", "PLUS", "POINTER", "POSITION",
    "POSITIVE", "PRINTING", "PROCEDURE", "PROCEDURES", "PROCEED",
    "PROGRAM", "PROGRAM-ID", "PROMPT", "PURGE",
    "QUEUE", "QUOTE", "QUOTES",
    "RANDOM", "RD", "READ", "READY", "RECEIVE", "RECORD",
    "RECORDING", "RECORDS", "REDEFINES", "REEL", "REFERENCE",
    "REFERENCES", "RELATIVE", "RELEASE", "REMAINDER", "REMOVAL",
    "RENAMES", "REPLACE", "REPLACING", "REPORT", "REPORTING",
    "REPORTS", "RERUN", "RESERVE", "RESET", "RETURN", "REVERSED",
    "REWIND", "REWRITE", "RF", "RH", "RIGHT", "ROUNDED", "RUN",
    "SAME", "SCREEN", "SD", "SEARCH", "SECTION", "SECURE",
    "SEGMENT", "SEGMENT-LIMIT", "SELECT", "SEND", "SENTENCE",
    "SEPARATE", "SEQUENCE", "SEQUENTIAL", "SET", "SIGN",
    "SIZE", "SORT", "SORT-MERGE", "SOURCE", "SOURCE-COMPUTER",
    "SPACE", "SPACES", "SPECIAL-NAMES", "STANDARD", "STANDARD-1",
    "STANDARD-2", "START", "STATUS", "STOP", "STRING",
    "SUB-QUEUE-1", "SUB-QUEUE-2", "SUB-QUEUE-3", "SUBTRACT",
    "SUM", "SUPPRESS", "SYMBOLIC", "SYNC", "SYNCHRONIZED",
    "TABLE", "TALLYING", "TAPE", "TERMINAL", "TERMINATE",
    "TEST", "TEXT", "THAN", "THEN", "THROUGH", "THRU", "TIME",
    "TIMES", "TO", "TOP", "TRAILING", "TRUE", "TRUNCATED",
    "TYPE",
    "UNIT", "UNSTRING", "UNTIL", "UP", "UPON", "USAGE", "USE",
    "USING",
    "VALUE", "VALUES", "VARYING",
    "WHEN", "WITH", "WORDS", "WORKING-STORAGE", "WRITE",
    "ZERO", "ZEROES", "ZEROS",
}


def _is_keyword(word: str) -> bool:
    """Check if a word is a COBOL reserved word."""
    return word.upper() in _PARAGRAPH_EXCLUDE


class _CobolIndexBuilder:
    """Regex-based COBOL source code indexer.

    Scans line by line for divisions, sections, paragraphs, data definitions,
    and other COBOL structural elements. Tracks brace depth (scope) to
    associate paragraphs and data items with their enclosing section/division.
    COBOL is case-insensitive; all matching is done on uppercase text.
    """

    def __init__(self, source: str, filepath: str = ""):
        self.source = source
        self.filepath = filepath
        self.lines = source.split("\n")
        self.entries: list[dict[str, Any]] = []
        self._parse()

    def _prepare_line(self, line: str) -> str:
        """Clean a line for analysis: remove comments (*> and * in col 7)."""
        # Remove inline comment *>
        idx = line.find("*>")
        if idx >= 0:
            line = line[:idx]
        # For fixed format, * in column 7 (index 6) is a comment line
        if len(line) > 6 and line[6] == '*':
            return ""
        # Remove string literals for matching purposes (keep structure)
        return line

    def _normalize(self, line: str) -> str:
        """Normalize a line: uppercase, collapse whitespace, strip."""
        cleaned = self._prepare_line(line)
        return re.sub(r'\s+', ' ', cleaned.upper()).strip()

    def _detect(self, line: str) -> list[tuple[str, str]]:
        normalized = self._normalize(line)
        if not normalized:
            return []

        # Check if it starts with a known keyword that's not a paragraph

        for pat, ext in _PATTERNS:
            m = re.match(pat, normalized)
            if m:
                kind, name = ext(m)
                if kind == "paragraph":
                    # Skip COBOL keywords
                    if _is_keyword(name):
                        continue
                    # Skip data-level numbers as paragraph names
                    if re.match(r'^\d', name):
                        continue
                return [(kind, name)]
        return []

    def _parse(self):
        entries: list[dict] = []
        stack: list[dict] = []

        # Track current division/section context for paragraphs
        current_division = None
        current_section = None

        for i, raw in enumerate(self.lines):
            normalized = self._normalize(raw)
            if not normalized:
                continue

            defs = self._detect(raw)
            for kind, name in defs:
                if kind in ("division",):
                    entry: dict = {
                        "kind": kind,
                        "name": name,
                        "line": i + 1,
                        "end_line": i + 1,
                        "label": name,
                        "members": [],
                    }
                    entries.append(entry)
                    stack.append(entry)
                    current_division = entry
                    current_section = None
                elif kind in ("section",):
                    entry = {
                        "kind": kind,
                        "name": name,
                        "line": i + 1,
                        "end_line": i + 1,
                        "label": name,
                        "members": [],
                    }
                    entries.append(entry)
                    stack.append(entry)
                    current_section = entry
                elif kind in ("program",):
                    entry = {
                        "kind": kind,
                        "name": name,
                        "line": i + 1,
                        "end_line": i + 1,
                        "label": f"PROGRAM-ID {name}",
                    }
                    entries.append(entry)
                elif kind in ("paragraph",):
                    if current_section:
                        lbl = f"{name}."
                        current_section.setdefault("members", []).append({
                            "kind": kind,
                            "name": name,
                            "line": i + 1,
                            "end_line": i + 1,
                            "label": lbl,
                        })
                    elif current_division:
                        lbl = f"{name}."
                        current_division.setdefault("paragraphs", []).append({
                            "kind": kind,
                            "name": name,
                            "line": i + 1,
                            "end_line": i + 1,
                            "label": lbl,
                        })
                elif kind in ("data", "fd", "select", "copy", "declaratives", "end-declaratives"):
                    entries.append({
                        "kind": kind,
                        "name": name,
                        "line": i + 1,
                        "end_line": i + 1,
                        "label": name,
                    })

        self._assign_end_lines(entries)
        self.entries = entries

    def _assign_end_lines(self, entries: list[dict]):
        for idx, e in enumerate(entries):
            if idx + 1 < len(entries):
                e["end_line"] = entries[idx + 1]["line"] - 1
            else:
                e["end_line"] = len(self.lines)
            for midx, m in enumerate(e.get("members", [])):
                if midx + 1 < len(e["members"]):
                    m["end_line"] = e["members"][midx + 1]["line"] - 1
                else:
                    m["end_line"] = e["end_line"]
            # Also handle "paragraphs" key (for division-level paragraphs)
            for midx, m in enumerate(e.get("paragraphs", [])):
                if midx + 1 < len(e["paragraphs"]):
                    m["end_line"] = e["paragraphs"][midx + 1]["line"] - 1
                else:
                    m["end_line"] = e["end_line"]

    def build_index(self) -> str:
        if not self.entries:
            return _("msg.no_entries", default="(no definitions found)")
        lines_out: list[str] = []
        idx = 0
        for e in self.entries:
            idx += 1
            lines_out.append(f"  {idx}. L{e['line']} {e['label']}")
            for m in e.get("members", []):
                idx += 1
                lines_out.append(f"      {idx}. L{m['line']} {m['label']}")
            for m in e.get("paragraphs", []):
                idx += 1
                lines_out.append(f"      {idx}. L{m['line']} {m['label']}")
        return "\n".join(lines_out)

    def get_section(self, n: int) -> str | None:
        flat: list[dict] = []
        for e in self.entries:
            flat.append(e)
            flat.extend(e.get("members", []))
            flat.extend(e.get("paragraphs", []))
        if n < 1 or n > len(flat):
            return None
        e = flat[n - 1]
        start_0 = e["line"] - 1
        end_0 = e.get("end_line", e["line"])
        if end_0 > len(self.lines):
            end_0 = len(self.lines)
        code_lines = self.lines[start_0:end_0]
        while code_lines and not code_lines[-1].strip():
            code_lines.pop()
        return "\n".join(code_lines).rstrip("\n")

    def section_count(self) -> int:
        count = 0
        for e in self.entries:
            count += 1
            count += len(e.get("members", []))
            count += len(e.get("paragraphs", []))
        return count


def run_tool(args: dict[str, Any]) -> str:
    path = args.get("path", "")
    mode = args.get("mode", "index")

    if not path:
        return _("err.path_required", default="Error: 'path' is required.")
    if not os.path.isfile(path):
        return _("err.file_not_found", default="Error: File not found: {path}", path=path)

    try:
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
    except Exception as e:
        return _("err.read_error", default="Error reading file: {e}", e=str(e))

    try:
        builder = _CobolIndexBuilder(source, filepath=path)
    except Exception as e:
        return _("err.parse_error", default="Error parsing file: {e}", e=str(e))

    if mode == "index":
        toc = builder.build_index()
        total = builder.section_count()
        return _(
            "msg.index_output",
            default=(
                "Index for: {path}\n"
                "---\n"
                "{toc}\n"
                "---\n"
                "Total definitions: {total}\n"
                "To retrieve a definition, call cobol2idx with mode='section' and the section number."
            ),
            path=path,
            total=total,
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
        content = builder.get_section(section_num)
        if content is None:
            total = builder.section_count()
            return _(
                "err.section_not_found",
                default="Error: Section {section_num} not found. Valid range: 1..{last}.",
                section_num=section_num,
                last=total,
            )
        return content
    else:
        return _(
            "err.invalid_mode",
            default="Error: Invalid mode '{mode}'. Use 'index' or 'section'.",
            mode=mode,
        )
