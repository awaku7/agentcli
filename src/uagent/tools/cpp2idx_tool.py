from __future__ import annotations

import os
import re
from typing import Any

from .i18n_helper import make_tool_translator
from .index_tool_helpers import read_index_source, resolve_index_path

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
    (
        r"^\s*#\s*(?:include|define|ifdef|ifndef|endif|pragma|error|warning|undef|if|else|elif)\b.*",
        lambda m: ("preproc", m.group(0).strip()[:50]),
    ),
    # namespace
    (
        r"^\s*namespace\s+(\w+(?:::\w+)*)\s*(?:\{|$)",
        lambda m: ("namespace", m.group(1)),
    ),
    # extern "C" { ... }
    (r"^\s*extern\s+\"C\"\s*\{", lambda m: ("extern_c", 'extern "C"')),
    # template declaration (just note it, attach to next def)
    (r"^\s*template\s*<[^>]*>\s*$", lambda m: ("template", "")),
    # class / struct / union
    (
        r"^\s*(?:"
        + _MOD
        + r")?(?:class|struct|union)\s+(\w+(?:\s*:\s*(?:public|private|protected)\s+\w+(?:<[^>]*>)?(?:\s*,\s*(?:public|private|protected)\s+\w+(?:<[^>]*>)?)*)?)\s*(?:\{|$)",
        lambda m: ("type", m.group(1).split()[0]),
    ),
    # enum (also enum class in C++11)
    (r"^\s*(?:enum\s+(?:class\s+)?)(\w+)", lambda m: ("enum", m.group(1))),
    # typedef
    (r"^\s*typedef\s+.+?\s+(\w+)\s*;", lambda m: ("typedef", m.group(1))),
    # using alias (C++11): using Name = Type;
    (r"^\s*using\s+(\w+)\s*=", lambda m: ("using", m.group(1))),
    # C++ operator declarations/definitions (including return types and templates).
    (
        r"^\s*(?:[\w:<>,*&]+\s+)+(?:[\w:]+(?:<[^>]*>)?::)*operator\s*([^\s(]+)\s*\([^)]*\)\s*(?:const\s*)?(?::\s*[^{]*)?(?:\{|;|$)",
        lambda m: ("operator", f"operator{m.group(1)}"),
    ),
    # C++ out-of-class method definitions such as T Box<T>::get().
    (
        r"^\s*[\w:<>,*&]+\s+([\w:]+(?:<[^>]*>)?::)(\w+)\s*\([^)]*\)\s*(?:const\s*)?(?::\s*[^{]*)?(?:\{|;|$)",
        lambda m: ("method", f"{m.group(1)}{m.group(2)}"),
    ),
    # C-style function: ReturnType functionName(...) { or ;
    (
        r"^\s*(?:"
        + _MOD
        + r")?(?!.*\boperator\s*)"
        + r"(\w+(?:\s*\*)*(?:\s+\w+)*?)\s+(\w+)\s*\([^)]*\)\s*(?:const\s*)?(?:\{|;|$)",
        lambda m: ("function", m.group(2)),
    ),
    # C++ destructor: ~ClassName()
    (
        r"^\s+" + _MOD + r"~(\w+)\s*\([^)]*\)\s*(?:\{|;|$)",
        lambda m: ("destructor", f"~{m.group(1)}"),
    ),
    # C++ operator definitions/declarations (return type may precede operator).
    (
        r"^\s*"
        + _MOD
        + r"(?:[\w:<>,*&]+\s+)+(?:[\w:]+(?:<[^>]*>)?::)*operator\s*([^\s(]+)\s*\([^)]*\)\s*(?::\s*[^{]*)?(?:\{|;|$)",
        lambda m: ("operator", f"operator{m.group(1)}"),
    ),
    # C++ constructor/method definitions and declarations.
    (
        r"^\s+"
        + _MOD
        + r"(?:(\w+(?:::\w+)*)::)?(\w+)\s*\([^)]*\)\s*(?::\s*[^{]*)?(?:\{|;|$)",
        lambda m: (
            "method" if m.group(1) else "constructor",
            f"{m.group(1) + '::' if m.group(1) else ''}{m.group(2)}",
        ),
    ),
    # field: Type name; inside a type
    (
        r"^\s+(?:"
        + _MOD
        + r")?(\w+(?:\s*\*?\s*\w+)*)\s+(\w+)\s*(?:\[[^\]]*\])?\s*(?:=|;|$)",
        lambda m: ("field", m.group(2)),
    ),
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
        function_scopes: list[int] = []
        brace_depth = 0
        pending_template = False

        for i, raw in enumerate(self.lines):
            cleaned = self._clean_line(raw)
            bd = self._guess_brace_depth(raw)
            old_depth = brace_depth
            brace_depth += bd

            # A function body is not a declaration scope.  Suppress field and
            # nested-definition heuristics while inside one.
            inside_function = bool(function_scopes and old_depth >= function_scopes[-1])
            defs = [] if inside_function else self._detect_definitions(raw)

            for kind, name in defs:
                if kind == "template":
                    pending_template = True
                    continue

                if kind == "preproc":
                    entries.append({
                        "kind": kind,
                        "name": name,
                        "line": i + 1,
                        "end_line": i + 1,
                        "level": 0,
                        "label": name,
                    })
                    continue

                if kind in ("namespace", "type", "enum", "extern_c"):
                    entry = {
                        "kind": kind,
                        "name": name,
                        "line": i + 1,
                        "end_line": i,
                        "level": len(stack),
                        "label": f"{kind} {name}",
                        "members": [],
                    }
                    entries.append(entry)
                    stack.append(entry)
                    stack_start_depth.append(old_depth)
                    pending_template = False
                    continue

                if kind in ("typedef", "using"):
                    entries.append({
                        "kind": kind,
                        "name": name,
                        "line": i + 1,
                        "end_line": i,
                        "level": len(stack),
                        "label": name,
                    })
                    pending_template = False
                    continue

                if kind in ("function", "constructor", "method", "destructor", "operator"):
                    member_kind = "operator" if kind == "operator" else kind
                    label = f"{name}()" if kind != "operator" else name
                    member = {
                        "kind": member_kind,
                        "name": name,
                        "line": i + 1,
                        "end_line": i,
                        "level": len(stack),
                        "label": label,
                    }
                    if stack and stack[-1].get("kind") in ("type", "enum"):
                        stack[-1].setdefault("members", []).append(member)
                    else:
                        entries.append({
                            "kind": member_kind if kind != "method" else "function",
                            "name": name,
                            "line": i + 1,
                            "end_line": i,
                            "level": 0,
                            "label": (f"template {label}" if pending_template else label),
                            "members": [],
                        })
                    pending_template = False
                    if "{" in cleaned and "}" not in cleaned:
                        function_scopes.append(brace_depth)
                    continue

                if (
                    kind == "field"
                    and stack
                    and not function_scopes
                    and stack[-1].get("kind") in ("type", "enum")
                ):
                    stack[-1].setdefault("members", []).append({
                        "kind": "field",
                        "name": name,
                        "line": i + 1,
                        "end_line": i + 1,
                        "level": len(stack),
                        "label": name,
                    })

            while stack_start_depth and brace_depth <= stack_start_depth[-1] and bd < 0:
                popped = stack.pop()
                popped["end_line"] = i
                stack_start_depth.pop()

            while function_scopes and brace_depth < function_scopes[-1]:
                function_scopes.pop()

            if not defs and bd == 0 and not pending_template:
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
    try:
        safe_path = resolve_index_path(str(path))
    except Exception:
        return _("err.file_not_found", default="Error: File not found: {path}", path=path)

    if not os.path.isfile(safe_path):
        return _("err.file_not_found", default="Error: File not found: {path}", path=path)

    try:
        source = read_index_source(safe_path)
    except Exception as e:
        return _("err.read_error", default="Error reading file: {e}", e=str(e))

    try:
        builder = _CppIndexBuilder(source, filepath=safe_path)
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
