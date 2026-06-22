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
        "name": "cpp2idx",
        "description": _(
            "tool.description",
            default=(
                "Parse a C/C++ (.c/.cpp/.h/.hpp) file into classes, structs, namespaces, "
                "functions, methods, and macros and return a numbered index or a specific "
                "definition section. Use this when you need to read a large C/C++ file: "
                "first call with mode='index' to get the table of contents, then call "
                "with mode='section' and the section number to retrieve only the definition "
                "you need. This saves tokens compared to reading the entire file."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "read c file",
                "read cpp file",
                "c header file",
                "c++ file index",
                "function list",
                "class list",
                "C言語ファイルを読む",
                "C++ファイルを読む",
                "関数一覧",
                "クラス一覧",
            ],
        ),
        "x_search_terms_en": [
            "read c file",
            "read cpp file",
            "c header file",
            "c++ file index",
            "function list",
            "class list",
        ],
        "x_parallel_safe": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Path to the C/C++ (.c/.cpp/.h/.hpp) file.",
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

# C/C++ keywords to exclude
_KEYWORDS = r"\b(?:for|if|while|switch|catch|return|throw|else|do|try|finally|case|default|break|continue|goto|sizeof|delete|new)\b"

# C/C++ modifiers
_MOD = r"(?:(?:virtual|override|final|static|const|constexpr|mutable|volatile|extern|explicit|inline|register)\s+)*"

# C/C++ definition patterns
_PATTERNS = [
    # #include / #define / #ifdef / #pragma etc.
    (r"^\s*#\s*(?:include|define|ifdef|ifndef|endif|pragma|error|warning|undef|if|else|elif)\b.*",
     lambda m: ("preproc", m.group(0).strip()[:50])),
    # namespace
    (r"^\s*namespace\s+(\w+(?:::\w+)*)\s*(?:\{|$)",
     lambda m: ("namespace", m.group(1))),
    # extern "C" { ... }
    (r"^\s*extern\s+\"C\"\s*\{",
     lambda m: ("extern_c", "extern \"C\"")),
    # template declaration (just note it, attach to next def)
    (r"^\s*template\s*<[^>]*>\s*$",
     lambda m: ("template", "")),
    # class / struct / union
    (r"^\s*(?:" + _MOD + r")?(?:class|struct|union)\s+(\w+(?:\s*:\s*(?:public|private|protected)\s+\w+(?:<[^>]*>)?(?:\s*,\s*(?:public|private|protected)\s+\w+(?:<[^>]*>)?)*)?)\s*(?:\{|$)",
     lambda m: ("type", m.group(1).split()[0])),
    # enum (also enum class in C++11)
    (r"^\s*(?:enum\s+(?:class\s+)?)(\w+)",
     lambda m: ("enum", m.group(1))),
    # typedef
    (r"^\s*typedef\s+.+?\s+(\w+)\s*;",
     lambda m: ("typedef", m.group(1))),
    # using alias (C++11): using Name = Type;
    (r"^\s*using\s+(\w+)\s*=",
     lambda m: ("using", m.group(1))),
    # C-style function: ReturnType functionName(...) { or ;
    (r"^\s*(?:" + _MOD + r")?(\w+(?:\s*\*)*(?:\s+\w+)*?)\s+(\w+)\s*\([^)]*\)\s*(?:const\s*)?(?:\{|;|$)",
     lambda m: ("function", m.group(2))),
    # C++ destructor: ~ClassName() 
    (r"^\s+" + _MOD + r"~(\w+)\s*\([^)]*\)\s*(?:\{|;|$)",
     lambda m: ("destructor", f"~{m.group(1)}")),
    # C++ constructor/method (must match a word followed by ( possibly with ::)
    (r"^\s+" + _MOD + r"(?:(\w+(?:::\w+)*)::)?(\w+)\s*\([^)]*\)\s*(?::\s*[^{]*)?(?:\{|;|$)",
     lambda m: ("method" if (m.group(1) or False) else "constructor",
                f"{m.group(1) + '::' if m.group(1) else ''}{m.group(2)}")),
    # field: Type name; inside a type
    (r"^\s+(?:" + _MOD + r")?(\w+(?:\s*\*?\s*\w+)*)\s+(\w+)\s*(?:\[[^\]]*\])?\s*(?:=|;|$)",
     lambda m: ("field", m.group(2))),
]


class _CppIndexBuilder:
    """Regex-based C/C++ source code indexer."""

    def __init__(self, source: str, filepath: str = ""):
        self.source = source
        self.filepath = filepath
        self.lines = source.split("\n")
        self.entries: list[dict[str, Any]] = []
        self._parse()

    def _clean_line(self, line: str) -> str:
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
        cleaned = self._clean_line(raw)
        depth = 0
        in_str = False
        sc = None
        in_angle = 0
        for ch in cleaned:
            if in_str:
                if ch == sc:
                    in_str = False
                continue
            if ch in ('"', "'"):
                in_str = True
                sc = ch
                continue
            if ch == "<" and in_angle >= 0:
                in_angle += 1
                continue
            if ch == ">" and in_angle > 0:
                in_angle -= 1
                continue
            if in_angle > 0:
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
                try:
                    kind, name = extractor(m)
                except Exception:
                    continue
                results.append((kind, name))
                break
        return results

    def _parse(self):
        entries: list[dict] = []
        stack: list[dict] = []
        stack_start_depth: list[int] = []
        brace_depth = 0
        pending_template = False

        for i, raw in enumerate(self.lines):
            stripped = raw.strip()
            if not stripped:
                bd = self._guess_brace_depth(raw)
                brace_depth += bd
                continue

            bd = self._guess_brace_depth(raw)
            old_depth = brace_depth
            brace_depth += bd

            defs = self._detect_definitions(raw)
            for kind, name in defs:
                if kind == "template":
                    pending_template = True
                    continue
                if kind in ("preproc",):
                    continue
                if kind in ("namespace", "type", "enum", "extern_c"):
                    entry = {
                        "kind": kind,
                        "name": name,
                        "line": i,
                        "end_line": i,
                        "level": len(stack),
                        "label": f"{kind} {name}",
                        "members": [],
                    }
                    entries.append(entry)
                    stack.append(entry)
                    stack_start_depth.append(old_depth)
                    pending_template = False
                elif kind in ("typedef", "using"):
                    entry = {
                        "kind": kind,
                        "name": name,
                        "line": i,
                        "end_line": i,
                        "level": 0,
                        "label": name,
                    }
                    entries.append(entry)
                    pending_template = False
                elif kind in ("function",):
                    if stack:
                        # Inside a type/namespace → treat as method/constructor member
                        container = stack[-1]
                        member = {
                            "kind": "method" if pending_template else "method",
                            "name": name,
                            "line": i,
                            "end_line": i,
                            "level": len(stack),
                            "label": f"{name}()",
                        }
                        container.setdefault("members", []).append(member)
                        pending_template = False
                    else:
                        # Top-level function
                        label = f"template {name}()" if pending_template else f"{name}()"
                        entry = {
                            "kind": "function",
                            "name": name,
                            "line": i,
                            "end_line": i,
                            "level": 0,
                            "label": label,
                            "members": [],
                        }
                        entries.append(entry)
                        pending_template = False
                elif kind in ("constructor", "method", "destructor"):
                    if stack:
                        container = stack[-1]
                        member = {
                            "kind": kind,
                            "name": name,
                            "line": i,
                            "end_line": i,
                            "level": len(stack),
                            "label": f"{name}()" if kind == "method" else f"{name}()",
                        }
                        container.setdefault("members", []).append(member)
                elif kind == "field":
                    if stack:
                        container = stack[-1]
                        member = {
                            "kind": "field",
                            "name": name,
                            "line": i,
                            "end_line": i,
                            "level": len(stack),
                            "label": name,
                        }
                        container.setdefault("members", []).append(member)

            # Pop stack when scope ends
            while stack_start_depth and brace_depth <= stack_start_depth[-1] and bd < 0:
                if stack:
                    popped = stack.pop()
                    popped["end_line"] = i
                stack_start_depth.pop()

            # If no def matched and no brace change, reset pending_template
            if not defs and bd == 0:
                pending_template = False

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
        return _("err.file_not_found", default="Error: File not found: {path}", path=path)

    try:
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
    except Exception as e:
        return _("err.read_error", default="Error reading file: {e}", e=str(e))

    try:
        builder = _CppIndexBuilder(source, filepath=path)
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
                "To retrieve a definition, call cpp2idx with mode='section' and the section number."
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
