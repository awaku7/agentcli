from __future__ import annotations

import os
import re

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

TOOL_SPEC = {
    "type": "function",
    "tool_genre": "index",
    "function": {
        "name": "go2idx",
        "description": _(
            "tool.description",
            default=(
                "Parse a Go (.go) file into functions, structs, interfaces, methods, "
                "and const/var/type declarations and return a numbered index or a "
                "specific definition section. Use this when you need to read a large "
                ".go file: first call with mode='index' to get the table of contents, "
                "then call with mode='section' and the section number to retrieve only "
                "the definition you need."
            ),
        ),
        "x_parallel_safe": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": _("param.path.description", default="Path to the Go (.go) file.")},
                "mode": {"type": "string", "enum": ["index", "section"], "description": _("param.mode.description", default='"index" returns a numbered table of contents. "section" returns a specific definition by number.')},
                "section": {"type": "integer", "description": _("param.section.description", default="Section number to retrieve (used only when mode='section').")},
            },
            "required": ["path", "mode"],
            "additionalProperties": False,
        },
    },
}

_PATTERNS = [
    (r"^\s*package\s+(\w+)", lambda m: ("package", m.group(1))),
    (r"^\s*type\s+(\w+)\s+(?:struct|interface)\b", lambda m: ("type", m.group(1))),
    (r"^\s*type\s+(\w+)\s*=", lambda m: ("type_alias", m.group(1))),
    (r"^\s*const\s+(\w+)", lambda m: ("const", m.group(1))),
    (r"^\s*var\s+(\w+)", lambda m: ("var", m.group(1))),
    (r"^\s*func\s+(?:\([^)]*\)\s+)?(\w+)\s*\([^)]*\)\s*(?:\(?[^)]*\)?\s*\{)?",
     lambda m: ("func", m.group(1))),
    (r"^\s+(\w+)\s+(?:int|string|float|bool|byte|rune|\w+(?:\.\w+)*|\[\]|map|chan|func|interface|struct)\b",
     lambda m: ("field", m.group(1))),
]


class _GoIndexBuilder:
    def __init__(self, source: str, filepath: str = ""):
        self.source = source
        self.filepath = filepath
        self.lines = source.split("\n")
        self.entries = []
        self._parse()

    def _clean_line(self, line: str) -> str:
        in_str = False; sc = None; res = []; i = 0
        while i < len(line):
            ch = line[i]
            if in_str:
                res.append(ch)
                if ch == "\\" and i + 1 < len(line): res.append(line[i+1]); i += 2; continue
                if ch == sc: in_str = False
                i += 1; continue
            if ch in ('"', "'", '`'):
                in_str = True; sc = ch; res.append(ch); i += 1; continue
            if ch == "/" and i + 1 < len(line):
                if line[i+1] == "/": break
                if line[i+1] == "*": return "".join(res)
            res.append(ch); i += 1
        return "".join(res)

    def _guess_brace_depth(self, raw: str) -> int:
        cleaned = self._clean_line(raw); d = 0; in_str = False; sc = None
        for ch in cleaned:
            if in_str:
                if ch == sc: in_str = False; continue
                continue
            if ch in ('"', "'", '`'): in_str = True; sc = ch; continue
            if ch == "{": d += 1
            elif ch == "}": d -= 1
        return d

    def _detect(self, line: str):
        cleaned = self._clean_line(line)
        if not cleaned.strip(): return []
        for pat, ext in _PATTERNS:
            m = re.match(pat, cleaned)
            if m:
                try:
                    r = ext(m)
                    return [r] if r else []
                except: return []
        return []

    def _parse(self):
        entries = []; stack = []; stack_dep = []; depth = 0
        for i, raw in enumerate(self.lines):
            if not raw.strip():
                depth += self._guess_brace_depth(raw); continue
            bd = self._guess_brace_depth(raw); od = depth; depth += bd
            defs = self._detect(raw)
            for k, n in defs:
                if k in ("package",):
                    e = {"kind": k, "name": n, "line": i + 1, "end_line": i + 1, "label": n, "members": []}
                    entries.append(e)
                    stack.append(e); stack_dep.append(od)
                elif k in ("type",):
                    e = {"kind": "type", "name": n, "line": i + 1, "end_line": i + 1, "label": f"type {n}", "members": []}
                    entries.append(e)
                    stack.append(e); stack_dep.append(od)
                elif k in ("func",):
                    if stack:
                        c = stack[-1]
                        c.setdefault("members", []).append({"kind": "func", "name": n, "line": i + 1, "end_line": i + 1, "label": f"{n}()"})
                    else:
                        entries.append({"kind": "func", "name": n, "line": i + 1, "end_line": i + 1, "label": f"{n}()"})
                elif k in ("const", "var", "type_alias"):
                    entries.append({"kind": k, "name": n, "line": i + 1, "end_line": i + 1, "label": n})
                elif k == "field" and stack:
                    c = stack[-1]
                    c.setdefault("members", []).append({"kind": "field", "name": n, "line": i + 1, "end_line": i + 1, "label": n})
            while stack_dep and depth <= stack_dep[-1] and bd < 0:
                if stack: stack.pop()["end_line"] = i
                stack_dep.pop()
        self._assign_end_lines(entries)
        self.entries = entries

    def _assign_end_lines(self, entries):
        for i, e in enumerate(entries):
            e["end_line"] = entries[i+1]["line"] - 1 if i + 1 < len(entries) else len(self.lines) - 1
            for j, m in enumerate(e.get("members", [])):
                m["end_line"] = e["members"][j+1]["line"] - 1 if j + 1 < len(e["members"]) else e["end_line"]

    def build_index(self):
        if not self.entries: return _("msg.no_entries", default="(no definitions found)")
        lines = []; idx = 0
        for e in self.entries:
            idx += 1; lines.append(f"  {idx}. L{e['line']} {e['label']}")
            for m in e.get("members", []):
                idx += 1; lines.append(f"      {idx}. L{m['line']} {m['label']}")
        return "\n".join(lines)

    def get_section(self, n):
        flat = []
        for e in self.entries:
            flat.append(e); flat.extend(e.get("members", []))
        if n < 1 or n > len(flat): return None
        e = flat[n-1]
        return "\n".join(self.lines[e["line"]:e.get("end_line", e["line"])+1]).rstrip("\n")

    def section_count(self):
        return sum(1 + len(e.get("members", [])) for e in self.entries)


def run_tool(args):
    path, mode = args.get("path", ""), args.get("mode", "index")
    if not path:
        return _("err.path_required", default="Error: 'path' is required.")
    if not os.path.isfile(path):
        return _("err.file_not_found", default="Error: File not found: {path}", path=path)
    try:
        with open(path, "r", encoding="utf-8") as _f:
            _source = _f.read()
        builder = _GoIndexBuilder(_source, filepath=path)
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
                "To retrieve a definition, call go2idx with mode='section' and the section number."
            ),
            path=path,
            total=total,
            toc=toc,
        )
    elif mode == "section":
        sn = args.get("section")
        if sn is None:
            return _("err.section_required", default="Error: 'section' (integer) is required when mode='section'.")
        try:
            c = builder.get_section(int(sn))
        except (TypeError, ValueError):
            return _("err.section_invalid", default="Error: 'section' must be an integer.", section_num=repr(sn))
        if c is None:
            total = builder.section_count()
            return _(
                "err.section_not_found",
                default="Error: Section {section_num} not found. Valid range: 1..{last}.",
                section_num=sn,
                last=total,
            )
        return c
    return _("err.invalid_mode", default="Error: Invalid mode '{mode}'. Use 'index' or 'section'.", mode=mode)
