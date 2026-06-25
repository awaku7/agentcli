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
        "name": "php2idx",
        "description": _(
            "tool.description",
            default=(
                "Parse a PHP (.php) file into namespaces, classes, interfaces, traits, enums, "
                "functions, methods, constants, and properties and return a numbered index or a "
                "specific definition section. Use this when you need to read a large .php file: "
                "first call with mode='index' to get the table of contents, then call with "
                "mode='section' and the section number to retrieve only the definition you need."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "read php file",
                "php file index",
                "class list",
                "method list",
                "PHPファイルを読む",
                "クラス一覧",
                "メソッド一覧",
            ],
        ),
        "x_search_terms_en": [
            "read php file",
            "php file index",
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
                        default="Path to the PHP (.php) file.",
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

# PHP definition patterns
# Order matters: more specific patterns first, generic fallbacks later.
_PATTERNS = [
    # namespace Foo\Bar;
    (r"^\s*namespace\s+([\w\\\\]+)\s*;", lambda m: ("namespace", m.group(1))),
    # (abstract|final|readonly)* class Foo
    (
        r"^\s*(?:(?:abstract|final|readonly)\s+)*class\s+(\w+)",
        lambda m: ("class", m.group(1)),
    ),
    # interface Foo
    (r"^\s*interface\s+(\w+)", lambda m: ("interface", m.group(1))),
    # trait Foo
    (r"^\s*trait\s+(\w+)", lambda m: ("trait", m.group(1))),
    # enum Foo (PHP 8.1+)
    (r"^\s*enum\s+(\w+)", lambda m: ("enum", m.group(1))),
    # define('NAME', ...) or define("NAME", ...)
    (r"^\s*define\s*\(\s*['\"]([\w_]+)['\"]", lambda m: ("define", m.group(1))),
    # global function: function &?foo(...)
    (r"^\s*function\s+(?:&\s*)?(\w+)\s*\(", lambda m: ("function", m.group(1))),
    # method inside class/trait/interface: indented function
    (
        r"^\s+(?:(?:public|private|protected|static|abstract|final)\s+)*(?:function)\s+(?:&\s*)?(\w+)\s*\(",
        lambda m: ("method", m.group(1)),
    ),
    # class constant: (public|private|protected|static)* const FOO
    (
        r"^\s+(?:(?:public|private|protected|static)\s+)*const\s+(\w+)",
        lambda m: ("const", m.group(1)),
    ),
    # typed property: (public|private|protected|static|readonly)* (?<type>)? $prop
    # Capture the property name without the leading $ to avoid double-$ in labels.
    (
        r"^\s+(?:(?:public|private|protected|static|readonly)\s+)*(?:[\w\[\]\\\\]+\s+)?\$(\w+)\s*(?:=|;|$)",
        lambda m: ("property", m.group(1)),
    ),
]


class _PhpIndexBuilder:
    """Regex-based PHP source code indexer.

    Scans line by line for namespace, class, interface, trait, enum, function,
    method, constant, and property definitions. Tracks brace depth to associate
    methods/constants/properties with their enclosing class-like structure.

    Line numbers stored in entries are 1-based. Internal lines list is 0-based.
    """

    def __init__(self, source: str, filepath: str = ""):
        self.source = source
        self.filepath = filepath
        self.lines = source.split("\n")
        self.entries: list[dict[str, Any]] = []
        self._parse()

    def _clean_line(self, line: str) -> str:
        """Remove comments (//, #, /* */) from a line, keeping strings intact."""
        in_str = False
        sc = None
        result: list[str] = []
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
            if ch in ('"', "'", "`"):
                in_str = True
                sc = ch
                result.append(ch)
                i += 1
                continue
            if ch == "/" and i + 1 < len(line):
                if line[i + 1] == "/":
                    break  # rest is // comment
                if line[i + 1] == "*":
                    # block comment start -- skip rest of line
                    return "".join(result)
            if ch == "#":
                # Perl-style comment (rest of line)
                break
            result.append(ch)
            i += 1
        return "".join(result)

    def _guess_brace_depth(self, raw: str) -> int:
        """Count { and } changes in a line, ignoring strings and comments."""
        cleaned = self._clean_line(raw)
        depth = 0
        in_str = False
        sc = None
        for ch in cleaned:
            if in_str:
                if ch == sc:
                    in_str = False
                continue
            if ch in ('"', "'", "`"):
                in_str = True
                sc = ch
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
        return depth

    def _detect(self, line: str) -> list[tuple[str, str]]:
        cleaned = self._clean_line(line)
        if not cleaned.strip():
            return []
        for pat, ext in _PATTERNS:
            m = re.match(pat, cleaned)
            if m:
                try:
                    r = ext(m)
                    return [r] if r else []
                except Exception:
                    return []
        return []

    def _parse(self):
        entries: list[dict] = []
        stack: list[dict] = []
        stack_dep: list[int] = []
        depth = 0

        for i, raw in enumerate(self.lines):
            stripped = raw.strip()
            if not stripped:
                depth += self._guess_brace_depth(raw)
                continue

            bd = self._guess_brace_depth(raw)
            od = depth
            depth += bd

            defs = self._detect(raw)
            for kind, name in defs:
                if kind in ("namespace",):
                    e: dict = {
                        "kind": kind,
                        "name": name,
                        "line": i + 1,
                        "end_line": i + 1,
                        "label": name,
                        "members": [],
                    }
                    entries.append(e)
                    stack.append(e)
                    stack_dep.append(od)
                elif kind in ("class", "interface", "trait", "enum"):
                    e = {
                        "kind": kind,
                        "name": name,
                        "line": i + 1,
                        "end_line": i + 1,
                        "label": f"{kind} {name}",
                        "members": [],
                    }
                    entries.append(e)
                    stack.append(e)
                    stack_dep.append(od)
                elif kind == "function":
                    entries.append(
                        {
                            "kind": "function",
                            "name": name,
                            "line": i + 1,
                            "end_line": i + 1,
                            "label": f"{name}()",
                        }
                    )
                elif kind in ("method", "const", "property") and stack:
                    c = stack[-1]
                    label = (
                        f"{name}()"
                        if kind == "method"
                        else f"${name}" if kind == "property" else name
                    )
                    c.setdefault("members", []).append(
                        {
                            "kind": kind,
                            "name": name,
                            "line": i + 1,
                            "end_line": i + 1,
                            "label": label,
                        }
                    )
                elif kind == "define":
                    entries.append(
                        {
                            "kind": "define",
                            "name": name,
                            "line": i + 1,
                            "end_line": i + 1,
                            "label": name,
                        }
                    )

            # Pop stack when brace depth returns to enclosing level
            while stack_dep and depth <= stack_dep[-1] and bd < 0:
                if stack:
                    stack.pop()["end_line"] = i
                stack_dep.pop()

        self._assign_end_lines(entries)
        self.entries = entries

    def _assign_end_lines(self, entries: list[dict]):
        total_lines = len(self.lines)  # number of lines = 1-based last line number
        for idx, e in enumerate(entries):
            if idx + 1 < len(entries):
                e["end_line"] = entries[idx + 1]["line"] - 1
            else:
                # Last top-level entry: end at the last line of the file
                e["end_line"] = total_lines
            for midx, m in enumerate(e.get("members", [])):
                if midx + 1 < len(e["members"]):
                    m["end_line"] = e["members"][midx + 1]["line"] - 1
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
        return "\n".join(lines_out)

    def get_section(self, n: int) -> str | None:
        """Return source code for the n-th definition (1-based).

        Line numbers stored in entries are 1-based; self.lines is 0-based.
        We convert: lines[start_0based : end_0based] where
          start_0based = entry['line'] - 1
          end_0based   = entry['end_line']   (since end_line is 1-based and
                          Python slice excludes the end index)
        """
        flat: list[dict] = []
        for e in self.entries:
            flat.append(e)
            flat.extend(e.get("members", []))
        if n < 1 or n > len(flat):
            return None
        e = flat[n - 1]
        start_0 = e["line"] - 1
        end_0 = e.get("end_line", e["line"])  # 1-based; slice end is exclusive
        if end_0 > len(self.lines):
            end_0 = len(self.lines)
        code_lines = self.lines[start_0:end_0]
        while code_lines and not code_lines[-1].strip():
            code_lines.pop()
        return "\n".join(code_lines).rstrip("\n")

    def section_count(self) -> int:
        return sum(1 + len(e.get("members", [])) for e in self.entries)


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
        builder = _PhpIndexBuilder(source, filepath=path)
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
                "To retrieve a definition, call php2idx with mode='section' and the section number."
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
