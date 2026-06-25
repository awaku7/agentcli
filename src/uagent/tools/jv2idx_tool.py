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
        "name": "jv2idx",
        "description": _(
            "tool.description",
            default=(
                "Parse a Java (.java) file into classes, interfaces, enums, records, "
                "methods, constructors, and fields and return a numbered index or a "
                "specific definition section. Use this when you need to read a large "
                ".java file: first call with mode='index' to get the table of contents, "
                "then call with mode='section' and the section number to retrieve only "
                "the definition you need. This saves tokens compared to reading the entire file."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "read java file",
                "java file index",
                "class list",
                "method list",
                "Javaファイルを読む",
                "クラス一覧",
                "メソッド一覧",
            ],
        ),
        "x_search_terms_en": [
            "read java file",
            "java file index",
            "class list",
            "method list",
        ],
        "x_parallel_safe": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Path to the Java (.java) file.",
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

# Java access modifiers and other keywords
_MOD = r"(?:(?:public|private|protected|static|abstract|final|synchronized|native|transient|volatile|strictfp|sealed|non-sealed|default)\s+)*"

# Java keywords that should not be matched as constructors/methods
_KEYWORDS = r"\b(?:for|if|while|switch|catch|return|throw|else|do|try|finally|assert|synchronized)\b"

# Java definition patterns
_PATTERNS = [
    # package declaration
    (r"^\s*package\s+(\w+(?:\.\w+)*)", lambda m: ("package", m.group(1))),
    # class / interface / enum / @interface / record
    (
        r"^\s*" + _MOD + r"(?:class|interface|enum|@interface|record)\s+(\w+)",
        lambda m: ("type", m.group(1)),
    ),
    # constructor: ClassName(...) [throws ...] {  (must NOT be a keyword like for/if/while)
    (
        r"^\s+"
        + _MOD
        + r"(?!for\b|if\b|while\b|switch\b|catch\b|return\b|throw\b|else\b|do\b|try\b|finally\b|assert\b|synchronized\b)(\w+)\s*\([^)]*\)\s*(?:throws\s+\w+(?:\s*,\s*\w+)*\s*)?\{",
        lambda m: ("constructor", m.group(1)),
    ),
    # method: must have a return type before the method name
    (
        r"^\s+"
        + _MOD
        + r"(\w+(?:<[^>]*>)?)\s+(?!for\b|if\b|while\b|switch\b|catch\b|return\b|throw\b|else\b|do\b|try\b|finally\b|assert\b|synchronized\b)(\w+)\s*\([^)]*\)\s*(?:throws\s+\w+(?:\s*,\s*\w+)*\s*)?(?:\{|;|$)",
        lambda m: ("method", m.group(2)),
    ),
    # field: Type name [= ...];  (at class level, requires a modifier keyword to avoid local vars)
    (
        r"^\s+(?:(?:public|private|protected|static|abstract|final|synchronized|native|transient|volatile|strictfp|sealed|non-sealed|default)\s+)+(?!new\b)(\w+(?:<[^>]*>)?(?:\[\])?)\s+(\w+)\s*(?:=|;|$)",
        lambda m: ("field", m.group(2)),
    ),
    # enum constant: NAME(...), or NAME;
    (r"^\s+(\w+)\s*\([^)]*\)\s*,", lambda m: ("enum_const", m.group(1))),
    (r"^\s+(\w+)\s*;", lambda m: ("enum_const", m.group(1))),
]


class _JvIndexBuilder:
    """Regex-based Java source code indexer."""

    def __init__(self, source: str, filepath: str = ""):
        self.source = source
        self.filepath = filepath
        self.lines = source.split("\n")
        self.entries: list[dict[str, Any]] = []
        self._parse()

    def _clean_line(self, line: str) -> str:
        """Remove // and /* */ comments from a line (keeps strings intact)."""
        in_str = False
        sc = None
        result = []
        i = 0
        while i < len(line):
            ch = line[i]
            if in_str:
                result.append(ch)
                if ch == "\\" and i + 1 < len(line):
                    result.append(line[i + 1])
                    i += 2
                    continue
                if ch == sc:
                    in_str = False
                i += 1
                continue
            if ch in ('"', "'"):
                in_str = True
                sc = ch
                result.append(ch)
                i += 1
                continue
            if ch == "/" and i + 1 < len(line):
                if line[i + 1] == "/":
                    break
                if line[i + 1] == "*":
                    return "".join(result)
            result.append(ch)
            i += 1
        return "".join(result)

    def _guess_brace_depth(self, raw: str) -> int:
        """Count { and } changes, ignoring strings."""
        cleaned = self._clean_line(raw)
        depth = 0
        in_str = False
        sc = None
        for ch in cleaned:
            if in_str:
                if ch == sc:
                    in_str = False
                continue
            if ch in ('"', "'"):
                in_str = True
                sc = ch
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
        return depth

    def _detect_definitions(self, line: str) -> list[tuple[str, str]]:
        cleaned = self._clean_line(line)
        if not cleaned.strip():
            return []

        results = []
        for pattern, extractor in _PATTERNS:
            m = re.match(pattern, cleaned)
            if m:
                kind, name = extractor(m)
                results.append((kind, name))
                break
        return results

    def _parse(self):
        entries: list[dict] = []
        stack: list[dict] = []
        stack_start_depth: list[int] = []
        brace_depth = 0

        for i, raw in enumerate(self.lines):
            stripped = raw.strip()
            if not stripped:
                bd = self._guess_brace_depth(raw)
                brace_depth += bd
                continue

            # Track brace depth for scope closing
            bd = self._guess_brace_depth(raw)
            old_depth = brace_depth
            brace_depth += bd

            # Detect definitions
            defs = self._detect_definitions(raw)
            for kind, name in defs:
                if kind in ("package", "type"):
                    entry = {
                        "kind": kind,
                        "name": name,
                        "line": i + 1,
                        "end_line": i + 1,
                        "level": len(stack),
                        "label": f"{kind} {name}",
                        "members": [],
                    }
                    entries.append(entry)
                    stack.append(entry)
                    stack_start_depth.append(old_depth)
                elif kind in ("method", "constructor", "field", "enum_const"):
                    if stack:
                        container = stack[-1]
                        label = (
                            f"{name}()" if kind in ("method", "constructor") else name
                        )
                        member = {
                            "kind": kind,
                            "name": name,
                            "line": i + 1,
                            "end_line": i + 1,
                            "level": len(stack),
                            "label": label,
                        }
                        container.setdefault("members", []).append(member)

            # Pop stack when scope ends
            while stack_start_depth and brace_depth <= stack_start_depth[-1] and bd < 0:
                if stack:
                    popped = stack.pop()
                    popped["end_line"] = i
                stack_start_depth.pop()

        self._assign_end_lines(entries)
        self.entries = entries

    def _assign_end_lines(self, entries: list[dict]):
        for idx, e in enumerate(entries):
            if idx + 1 < len(entries):
                next_line = entries[idx + 1]["line"]
            else:
                next_line = len(self.lines)
            e["end_line"] = next_line - 1
            for midx, m in enumerate(e.get("members", [])):
                if midx + 1 < len(e["members"]):
                    m_end = e["members"][midx + 1]["line"] - 1
                else:
                    m_end = e["end_line"]
                m["end_line"] = m_end

    def build_index(self) -> str:
        if not self.entries:
            return _("msg.no_entries", default="(no definitions found)")
        lines_out: list[str] = []
        idx = 0
        for entry in self.entries:
            idx += 1
            lines_out.append(f"  {idx}. L{entry['line']} {entry['label']}")
            for member in entry.get("members", []):
                idx += 1
                lines_out.append(f"      {idx}. L{member['line']} {member['label']}")
        return "\n".join(lines_out)

    def _source_lines(self, entry: dict) -> str:
        start = entry["line"]
        end = entry.get("end_line", entry["line"]) + 1
        if end > len(self.lines):
            end = len(self.lines)
        code_lines = self.lines[start:end]
        while code_lines and not code_lines[-1].strip():
            code_lines.pop()
        return "\n".join(code_lines)

    def get_section(self, number: int) -> str | None:
        if number < 1:
            return None
        flat: list[dict] = []
        for entry in self.entries:
            flat.append(entry)
            flat.extend(entry.get("members", []))
        if number > len(flat):
            return None
        return self._source_lines(flat[number - 1])

    def section_count(self) -> int:
        count = 0
        for entry in self.entries:
            count += 1
            count += len(entry.get("members", []))
        return count


def run_tool(args: dict[str, Any]) -> str:
    path = args.get("path", "")
    mode = args.get("mode", "index")

    if not path:
        return _("err.path_required", default="Error: 'path' is required.")
    if not os.path.isfile(path):
        return _(
            "err.file_not_found", default="Error: File not found: {path}", path=path
        )

    try:
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
    except Exception as e:
        return _("err.read_error", default="Error reading file: {e}", e=str(e))

    try:
        builder = _JvIndexBuilder(source, filepath=path)
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
                "To retrieve a definition, call jv2idx with mode='section' and the section number."
            ),
            path=path,
            total=total,
            toc=toc,
        )
    elif mode == "section":
        section_num = args.get("section")
        if section_num is None:
            return _(
                "err.section_required",
                default="Error: 'section' (integer) is required when mode='section'.",
            )
        try:
            section_num = int(section_num)
        except (TypeError, ValueError):
            return _(
                "err.section_invalid",
                default="Error: 'section' must be an integer.",
                section_num=repr(section_num),
            )
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
