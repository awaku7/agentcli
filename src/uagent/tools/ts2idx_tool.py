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
        "name": "ts2idx",
        "description": _(
            "tool.description",
            default=(
                "Parse a TypeScript/JavaScript file into functions, classes, interfaces, "
                "and methods and return a numbered index or a specific definition section. "
                "Use this when you need to read a large .ts/.js file: first call with "
                "mode='index' to get the table of contents, then call with mode='section' "
                "and the section number to retrieve only the definition you need. "
                "This saves tokens compared to reading the entire file."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "read typescript file",
                "read javascript file",
                "ts file index",
                "js file index",
                "function list",
                "class index",
                "TypeScriptファイルを読む",
                "関数一覧",
                "クラス一覧",
            ],
        ),
        "x_search_terms_en": [
            "read typescript file",
            "read javascript file",
            "ts file index",
            "js file index",
            "function list",
            "class index",
        ],
        "x_parallel_safe": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Path to the TypeScript/JavaScript file.",
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


# Regex patterns for TypeScript/JavaScript definitions
_PATTERNS = [
    # export default class / export default function / export default async function
    (r"^export\s+default\s+(?:abstract\s+|async\s+)?(class|function|interface)\s+(\w+)",
     lambda m, kw: ("class" if m.group(1) in ("class",) else m.group(1), m.group(2))),
    # export abstract class / export class / export interface / export enum / export type / export function / export namespace
    (r"^export\s+(?:abstract\s+|async\s+)?(class|interface|enum|type|function|namespace)\s+(\w+)",
     lambda m, kw: (m.group(1), m.group(2))),
    # standalone: abstract class / class / interface / enum / type / function / async function / namespace
    (r"^(?:abstract\s+|async\s+)?(class|interface|enum|type|function|namespace)\s+(\w+)",
     lambda m, kw: (m.group(1), m.group(2))),
    # const/let/var foo = (...) =>  (arrow function / function expression)
    (r"^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*(?::\s*[^=]+)?\s*=\s*(?:async\s*)?\(",
     lambda m, kw: ("function", m.group(1))),
    # const/let/var foo = function
    (r"^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?function",
     lambda m, kw: ("function", m.group(1))),
    # getter/setter in classes
    (r"^\s+(?:public|private|protected|\s)*(?:static\s+)?(?:get|set)\s+(\w+)\s*\(",
     lambda m, kw: ("method", m.group(1))),
    # method declaration: name(...) {  (indented, inside a class-like block)
    (r"^\s+(?:public|private|protected|\s)*(?:static\s+)?(?:async\s+)?(\w+)\s*\([^)]*\)\s*(?::\s*\w+(?:<[^>]*>)?)?\s*\{",
     lambda m, kw: ("method", m.group(1))),
    # constructor
    (r"^\s+(?:public|private|protected|\s)*constructor\s*\(",
     lambda m, kw: ("method", "constructor")),
]


class _TsIndexBuilder:
    """Regex-based TypeScript/JavaScript section indexer.

    Scans line by line for class, interface, function, method, etc. definitions.
    Tracks brace depth to associate methods with their enclosing class.
    """

    def __init__(self, source: str, filepath: str = ""):
        self.source = source
        self.filepath = filepath
        self.lines = source.split("\n")
        self.entries: list[dict[str, Any]] = []
        self._parse()

    def _clean_comment(self, line: str) -> str:
        """Remove single-line comments and trailing comments conservatively."""
        # Remove string contents first to avoid false matches
        in_string = False
        string_char = None
        result = []
        i = 0
        while i < len(line):
            ch = line[i]
            if in_string:
                result.append(ch)
                if ch == "\\" and i + 1 < len(line):
                    result.append(line[i + 1])
                    i += 2
                    continue
                if ch == string_char:
                    in_string = False
                i += 1
                continue
            if ch in ("'", '"', "`"):
                in_string = True
                string_char = ch
                result.append(ch)
                i += 1
                continue
            if ch == "/" and i + 1 < len(line):
                if line[i + 1] == "/":
                    break  # rest is comment
                if line[i + 1] == "*":
                    # block comment start - skip rest
                    return "".join(result)
            result.append(ch)
            i += 1
        return "".join(result)

    def _estimate_brace_change(self, line: str) -> int:
        """Count { and } changes in a line, ignoring strings and comments."""
        cleaned = self._clean_comment(line)
        # Remove regex literals roughly
        cleaned = re.sub(r"/[^/]+/[gimsuy]*", "", cleaned)
        depth = 0
        in_str = False
        sc = None
        for ch in cleaned:
            if in_str:
                if ch == sc:
                    in_str = False
                continue
            if ch in ("'", '"', "`"):
                in_str = True
                sc = ch
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
        return depth

    def _parse(self):
        class_stack: list[dict] = []
        brace_depth = 0
        entries: list[dict] = []
        pending_endline: dict[int, int] = {}  # track end lines by start line

        i = 0
        while i < len(self.lines):
            raw = self.lines[i]
            cleaned = self._clean_comment(raw)
            if not cleaned.strip():
                brace_depth += self._estimate_brace_change(raw)
                i += 1
                continue

            # Try matching patterns
            matched = False
            for pattern, extractor in _PATTERNS:
                m = re.match(pattern, cleaned)
                if not m:
                    continue
                kind, name = extractor(m, cleaned)

                if kind in ("class", "interface", "enum", "namespace"):
                    entry: dict = {
                        "kind": kind,
                        "name": name,
                        "line": i + 1,
                        "end_line": i + 1,
                        "level": 0,
                        "label": f"{kind} {name}",
                        "methods": [],
                    }
                    entries.append(entry)
                    class_stack.append(entry)
                    matched = True
                    break

                elif kind == "type":
                    entry = {
                        "kind": "type",
                        "name": name,
                        "line": i + 1,
                        "end_line": i + 1,
                        "level": 0,
                        "label": f"type {name}",
                    }
                    entries.append(entry)
                    matched = True
                    break

                elif kind == "function":
                    if class_stack:
                        method = {
                            "kind": "method",
                            "name": name,
                            "line": i + 1,
                            "end_line": i + 1,
                            "level": 1,
                            "label": f"{name}()",
                            "is_arrow": "=>" not in raw and True,
                        }
                        class_stack[-1].setdefault("methods", []).append(method)
                    else:
                        entry = {
                            "kind": "function",
                            "name": name,
                            "line": i + 1,
                            "end_line": i + 1,
                            "level": 0,
                            "label": f"function {name}",
                        }
                        entries.append(entry)
                    matched = True
                    break

                elif kind == "method":
                    if class_stack or name == "constructor":
                        container = class_stack[-1] if class_stack else {"methods": []}
                        method = {
                            "kind": "method",
                            "name": name,
                            "line": i + 1,
                            "end_line": i + 1,
                            "level": 1,
                            "label": f"{name}()",
                        }
                        container.setdefault("methods", []).append(method)
                        matched = True
                        break

            if not matched:
                pass

            brace_change = self._estimate_brace_change(raw)
            if brace_change < 0 and class_stack:
                pass
            brace_depth += brace_change
            i += 1

        # Estimate end lines using brace depth tracking
        self._resolve_end_lines(entries)
        self.entries = entries

    def _resolve_end_lines(self, entries: list[dict]):
        """Walk through lines and assign end_line based on brace depth."""
        if not entries:
            return
        brace_map: dict[int, int] = {}
        depth = 0
        entry_starts: list[int] = []

        for entry in entries:
            entry_starts.append(entry["line"])

        # Simple heuristic: use next definition line as end estimate
        entry_starts.sort()
        for idx, entry in enumerate(entries):
            if idx + 1 < len(entry_starts):
                entry["end_line"] = entry_starts[idx + 1] - 1
            else:
                entry["end_line"] = len(self.lines) - 1
            for method in entry.get("methods", []):
                method["end_line"] = entry["end_line"]

    def build_index(self) -> str:
        if not self.entries:
            return _("msg.no_entries", default="(no definitions found)")

        lines_out: list[str] = []
        idx = 0
        for entry in self.entries:
            idx += 1
            lines_out.append(f"  {idx}. L{entry['line']} {entry['label']}")
            for method in entry.get("methods", []):
                idx += 1
                lines_out.append(f"      {idx}. L{method['line']} {method['label']}")
        return "\n".join(lines_out)

    def _source_lines(self, entry: dict) -> str:
        start = entry["line"]
        end = entry.get("end_line", entry["line"]) + 1
        # Extend end to next empty line or significant indent drop
        if end >= len(self.lines):
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
            flat.extend(entry.get("methods", []))
        if number > len(flat):
            return None
        target = flat[number - 1]
        return self._source_lines(target)

    def section_count(self) -> int:
        count = 0
        for entry in self.entries:
            count += 1
            count += len(entry.get("methods", []))
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
        builder = _TsIndexBuilder(source, filepath=path)
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
                "To retrieve a definition, call ts2idx with mode='section' and the section number."
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
