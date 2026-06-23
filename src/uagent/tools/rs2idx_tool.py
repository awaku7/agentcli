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
        "name": "rs2idx",
        "description": _(
            "tool.description",
            default=(
                "Parse a Rust (.rs) file into functions, structs, enums, traits, impls, "
                "and macros and return a numbered index or a specific definition section. "
                "Use this when you need to read a large .rs file: first call with "
                "mode='index' to get the table of contents, then call with mode='section' "
                "and the section number to retrieve only the definition you need. "
                "This saves tokens compared to reading the entire file."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "read rust file",
                "rust file index",
                "function list",
                "struct list",
                "Rustファイルを読む",
                "関数一覧",
                "構造体一覧",
            ],
        ),
        "x_search_terms_en": [
            "read rust file",
            "rust file index",
            "function list",
            "struct list",
        ],
        "x_parallel_safe": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Path to the Rust (.rs) file.",
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

# Rust visibility and modifiers
_MOD = r"(?:(?:pub(?:\s*\(\s*(?:crate|super|self|in\s+\w+(?:::\w+)*)\s*\))?|async|unsafe|const|default|extern|#[^\n]*)\s+)*"

# Rust definition patterns (checked in order)
_PATTERNS = [
    # mod declaration
    (r"^\s*(?:pub\s+)?mod\s+(\w+)",
     lambda m: ("module", m.group(1))),
    # use declaration (skip)
    (r"^\s*(?:pub\s+)?use\s+",
     lambda m: None),
    # struct / union / enum / trait
    (r"^\s*(?:" + _MOD + r")?(?:struct|union|enum|trait)\s+(\w+(?:<[^>]*>)?)",
     lambda m: ("type", m.group(1))),
    # impl block
    (r"^\s*(?:" + _MOD + r")?impl(?:\s*<[^>]*>)?\s+(\w+(?:<[^>]*>)?)\s*(?:for\s+(\w+(?:<[^>]*>)?))?\s*(?:\{|where)",
     lambda m: ("impl", f"{m.group(1)}" + (f" for {m.group(2)}" if m.group(2) else ""))),
    # type alias
    (r"^\s*(?:pub\s+)?type\s+(\w+(?:<[^>]*>)?)\s*=",
     lambda m: ("type_alias", m.group(1))),
    # macro_rules!
    (r"^\s*(?:#\[[^\]]*\]\s*)*macro_rules!\s*[\(\{]?\s*(\w+)",
     lambda m: ("macro", m.group(1))),
    # const / static
    (r"^\s*(?:" + _MOD + r")?(?:const|static)\s+(\w+)\s*(?::|=)",
     lambda m: ("const", m.group(1))),
    # fn declaration
    (r"^\s*(?:" + _MOD + r")?fn\s+(\w+(?:<[^>]*>)?)\s*\([^)]*\)\s*(?:->\s*(?:\w+(?:<[^>]*>)?(?:\s*\|\s*\w+(?:<[^>]*>)?)*\s*)?)?(?:\{|;|where)",
     lambda m: ("fn", m.group(1))),
    # struct field: name: Type,
    (r"^\s+(\w+)\s*:\s*(?:\w+(?:<[^>]*>)?)",
     lambda m: ("field", m.group(1))),
    # enum variant: Name or Name(...) or Name{...}
    (r"^\s+(\w+)\s*(?:\(|{|,)",
     lambda m: ("variant", m.group(1))),
]


class _RsIndexBuilder:
    """Regex-based Rust source code indexer."""

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
        # Skip comment lines
        if cleaned.strip().startswith("//"):
            return []
        results = []
        for pattern, extractor in _PATTERNS:
            m = re.match(pattern, cleaned)
            if m:
                try:
                    result = extractor(m)
                except Exception:
                    continue
                if result is None:
                    break  # matched but should be skipped (e.g., `use ...`)
                results.append(result)
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

            bd = self._guess_brace_depth(raw)
            old_depth = brace_depth
            brace_depth += bd

            defs = self._detect_definitions(raw)
            for kind_name in defs:
                if kind_name is None:
                    continue
                kind, name = kind_name
                if kind in ("type", "impl", "module", "macro"):
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
                elif kind in ("const", "type_alias"):
                    entry = {
                        "kind": kind,
                        "name": name,
                        "line": i + 1,
                        "end_line": i + 1,
                        "level": 0,
                        "label": name,
                    }
                    entries.append(entry)
                elif kind == "fn":
                    if stack:
                        container = stack[-1]
                        member = {
                            "kind": "fn",
                            "name": name,
                            "line": i + 1,
                            "end_line": i + 1,
                            "level": len(stack),
                            "label": f"{name}()",
                        }
                        container.setdefault("members", []).append(member)
                    else:
                        entry = {
                            "kind": "fn",
                            "name": name,
                            "line": i + 1,
                            "end_line": i + 1,
                            "level": 0,
                            "label": f"{name}()",
                            "members": [],
                        }
                        entries.append(entry)
                elif kind in ("field", "variant"):
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
        return _("err.file_not_found", default="Error: File not found: {path}", path=path)

    try:
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
    except Exception as e:
        return _("err.read_error", default="Error reading file: {e}", e=str(e))

    try:
        builder = _RsIndexBuilder(source, filepath=path)
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
                "To retrieve a definition, call rs2idx with mode='section' and the section number."
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
