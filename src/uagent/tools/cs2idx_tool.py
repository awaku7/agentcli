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
        "name": "cs2idx",
        "description": _(
            "tool.description",
            default=(
                "Parse a C# (.cs) file into classes, interfaces, structs, enums, "
                "methods, and properties and return a numbered index or a specific "
                "definition section. Use this when you need to read a large .cs file: "
                "first call with mode='index' to get the table of contents, then call "
                "with mode='section' and the section number to retrieve only the "
                "definition you need. This saves tokens compared to reading the entire file."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "read csharp file",
                "read cs file",
                "csharp file index",
                "class list",
                "method list",
                "C#ファイルを読む",
                "クラス一覧",
                "メソッド一覧",
            ],
        ),
        "x_search_terms_en": [
            "read csharp file",
            "read cs file",
            "csharp file index",
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
                        default="Path to the C# (.cs) file.",
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

# Modifier prefix pattern (optional)
_MOD = r"(?:(?:public|private|protected|internal|static|virtual|override|abstract|sealed|partial|readonly|unsafe|new)\s+)*"

# C# definition patterns
_PATTERNS = [
    # namespace
    (r"^\s*namespace\s+(\w+(?:\.\w+)*)",
     lambda m: ("namespace", m.group(1))),
    # class / struct / record / interface / enum
    (r"^\s*" + _MOD + r"(?:class|struct|record|interface|enum)\s+(\w+)",
     lambda m: ("type", m.group(1))),
    # constructor: ClassName(...) or ClassName(...) : this(...) / base(...)
    (r"^\s+" + _MOD + r"(\w+)\s*\([^)]*\)\s*(?::\s*(?:this|base)\s*\([^)]*\))?\s*(?:\{|$)",
     lambda m: ("constructor", m.group(1))),
    # destructor: ~ClassName(...)
    (r"^\s+~(\w+)\s*\(",
     lambda m: ("destructor", f"~{m.group(1)}")),
    # operator overload: public static ReturnType operator +(...
    (r"^\s+" + _MOD + r"(\w+(?:<[^>]*>)?)\s+operator\s+([^\s(]+)\s*\(",
     lambda m: ("operator", f"operator {m.group(2)}")),
    # explicit / implicit operator
    (r"^\s+(?:explicit|implicit)\s+operator\s+(\w+(?:<[^>]*>)?)\s*\(",
     lambda m: ("operator", f"operator {m.group(1)}")),
    # property: Type Name { get; set; } or Type Name => ...
    (r"^\s+" + _MOD + r"(\w+(?:<[^>]*>)?)\s+(\w+)\s*\{\s*(?:get|set|init)",
     lambda m: ("property", m.group(2))),
    # property with expression body: Type Name => ...
    (r"^\s+" + _MOD + r"(\w+(?:<[^>]*>)?)\s+(\w+)\s*=>",
     lambda m: ("property", m.group(2))),
    # method: ReturnType MethodName(...) {  or  ReturnType MethodName(...) =>
    (r"^\s+" + _MOD + r"(\w+(?:<[^>]*>)?)\s+(\w+)\s*\([^)]*\)\s*(?::\s*\w+(?:<[^>]*>)?(?:\s*,\s*\w+(?:<[^>]*>)?)*\s*)?(?:where\s+\w+\s*:.*?)?(?:\{|=>|$)",
     lambda m: ("method", m.group(2))),
    # delegate
    (r"^\s+" + _MOD + r"delegate\s+(\w+(?:<[^>]*>)?)\s+(\w+)\s*\(",
     lambda m: ("delegate", m.group(2))),
    # event
    (r"^\s+" + _MOD + r"event\s+(\w+(?:<[^>]*>)?)\s+(\w+)",
     lambda m: ("event", m.group(2))),
    # enum member: Name = value,
    (r"^\s+(\w+)\s*=",
     lambda m: ("enum_member", m.group(1))),
    # indexer: ReturnType this[int index] { get; set; }
    (r"^\s+" + _MOD + r"(\w+(?:<[^>]*>)?)\s+this\s*\[",
     lambda m: ("indexer", "this[]")),
]


class _CsIndexBuilder:
    """Regex-based C# source code indexer."""

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
                    break  # rest is comment
                if line[i + 1] == "*":
                    return "".join(result)  # naive: block comment to end of line
            result.append(ch)
            i += 1
        return "".join(result)

    def _detect_definitions(self, line: str) -> list[tuple[str, str]]:
        """Return list of (kind, name) for definitions found on this line."""
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

    def _guess_brace_depth(self, raw: str) -> int:
        """Count { and } changes, ignoring strings and comments."""
        cleaned = self._clean_line(raw)
        # Remove interpolated strings roughly
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

    def _parse(self):
        entries: list[dict] = []
        stack: list[dict] = []  # type/namespace stack
        brace_depth = 0
        # Track brace depth per stack entry
        stack_start_depth: list[int] = []
        in_xml_doc = False

        for i, raw in enumerate(self.lines):
            stripped = raw.strip()

            # Track XML doc comments
            if stripped.startswith("///") or stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
                continue

            # Detect definitions on this line
            defs = self._detect_definitions(raw)
            for kind, name in defs:
                if kind in ("namespace", "type"):
                    parent = stack[-1] if stack else None
                    entry = {
                        "kind": kind,
                        "name": name,
                        "line": i + 1,
                        "end_line": i + 1,
                        "level": len(stack),
                        "label": f"{kind} {name}",
                        "members": [],
                        "parent": parent,
                    }
                    entries.append(entry)
                    stack.append(entry)
                    stack_start_depth.append(brace_depth)
                elif kind in ("method", "property", "constructor", "destructor",
                              "operator", "delegate", "event", "indexer", "enum_member"):
                    # Attach to innermost type/namespace if inside one
                    if stack:
                        container = stack[-1]
                        member = {
                            "kind": kind,
                            "name": name,
                            "line": i + 1,
                            "end_line": i + 1,
                            "level": len(stack),
                            "label": f"{name}()" if kind in ("method", "constructor", "destructor", "operator") else f"{name}" if kind in ("property", "delegate", "event", "indexer") else f"{name}",
                        }
                        container.setdefault("members", []).append(member)
                else:
                    if stack:
                        container = stack[-1]
                        member = {
                            "kind": kind,
                            "name": name,
                            "line": i + 1,
                            "end_line": i + 1,
                            "level": len(stack),
                            "label": name,
                        }
                        container.setdefault("members", []).append(member)

            # Track brace depth for scope closing
            bd = self._guess_brace_depth(raw)
            old_depth = brace_depth
            brace_depth += bd

            # Pop stack when scope ends (depth returns to or below the level where the entry started)
            while stack_start_depth and brace_depth <= stack_start_depth[-1] and bd < 0:
                if stack:
                    popped = stack.pop()
                    popped["end_line"] = i
                stack_start_depth.pop()

        # Assign end_line approximations
        self._assign_end_lines(entries)
        self.entries = entries

    def _assign_end_lines(self, entries: list[dict]):
        """Walk entries and assign end_line from next sibling entry or EOF."""
        # For top-level entries, use next top-level entry's line as boundary
        for idx, e in enumerate(entries):
            if idx + 1 < len(entries):
                next_line = entries[idx + 1]["line"]
            else:
                next_line = len(self.lines)
            e["end_line"] = next_line - 1
            # For members, use their own entry's end_line as boundary
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
        return _("err.file_not_found", default="Error: File not found: {path}", path=path)

    try:
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
    except Exception as e:
        return _("err.read_error", default="Error reading file: {e}", e=str(e))

    try:
        builder = _CsIndexBuilder(source, filepath=path)
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
                "To retrieve a definition, call cs2idx with mode='section' and the section number."
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
            return _("err.section_not_found", default="Error: Section {section_num} not found. Valid range: 1..{last}.", section_num=section_num, last=total)
        return content
    else:
        return _("err.invalid_mode", default="Error: Invalid mode '{mode}'. Use 'index' or 'section'.", mode=mode)
