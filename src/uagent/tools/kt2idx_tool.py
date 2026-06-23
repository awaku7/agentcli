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
        "name": "kt2idx",
        "description": _("tool.description", default="Parse a Kotlin (.kt) file into classes, interfaces, objects, functions, and properties and return a numbered index or a specific definition section."),
        "x_parallel_safe": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": _("param.path.description", default="Path to the Kotlin (.kt) file.")},
                "mode": {"type": "string", "enum": ["index", "section"], "description": _("param.mode.description", default='"index" returns a numbered table of contents. "section" returns a specific definition by number.')},
                "section": {"type": "integer", "description": _("param.section.description", default="Section number to retrieve (used only when mode='section').")},
            },
            "required": ["path", "mode"],
            "additionalProperties": False,
        },
    },
}

_MOD = r"(?:(?:public|private|protected|internal|open|final|abstract|sealed|data|inner|inline|suspend|operator|infix|tailrec|external|override|lateinit|noinline|crossinline|const|actual|expect)\s+)*"

_PATTERNS = [
    (r"^\s*(?:import|package)\s+", lambda m: None),
    (r"^\s*" + _MOD + r"(?:class|interface|object|enum class|annotation class|data class|sealed class|sealed interface)\s+(\w+(?:<[^>]*>)?)",
     lambda m: ("type", m.group(1))),
    (r"^\s*" + _MOD + r"fun\s+(?:(\w+(?:\.\w+)*)\.)?(\w+)\s*\([^)]*\)\s*(?::\s*(?:\w+(?:<[^>]*>)?(?:\?)?(?:\s*\.\s*\w+(?:<[^>]*>)?)*)\s*)?(?:\{|$|=)",
     lambda m: ("func", m.group(2))),
    (r"^\s*" + _MOD + r"(?:val|var)\s+(\w+)\s*(?::|=)",
     lambda m: ("property", m.group(1))),
    (r"^\s*" + _MOD + r"init\s*(?:\{|$)",
     lambda m: ("init", "init")),
    (r"^\s*" + _MOD + r"companion\s+object\s*(?:\{|\w)",
     lambda m: ("companion", "companion")),
    (r"^\s*(?:enum\s+)?(\w+)\s*(?:\(|,)", lambda m: ("enum_entry", m.group(1))),
]


class _KtIndexBuilder:
    def __init__(self, source: str, filepath: str = ""):
        self.source = source; self.filepath = filepath
        self.lines = source.split("\n"); self.entries = []; self._parse()

    def _clean_line(self, line):
        in_str = False; sc = None; res = []; i = 0
        while i < len(line):
            ch = line[i]
            if in_str:
                res.append(ch)
                if ch == "\\" and i+1 < len(line): res.append(line[i+1]); i+=2; continue
                if ch == sc: in_str = False; i+=1; continue
                i+=1; continue
            if ch in ('"', "'"): in_str = True; sc = ch; res.append(ch); i+=1; continue
            if ch == "/" and i+1 < len(line):
                if line[i+1] == "/": break
                if line[i+1] == "*": return "".join(res)
            res.append(ch); i+=1
        return "".join(res)

    def _brace_depth(self, raw):
        c = self._clean_line(raw); d = 0; in_str = False; sc = None
        for ch in c:
            if in_str:
                if ch == sc: in_str = False; continue
                continue
            if ch in ('"', "'"): in_str = True; sc = ch; continue
            if ch == "{": d += 1
            elif ch == "}": d -= 1
        return d

    def _detect(self, line):
        c = self._clean_line(line)
        if not c.strip(): return []
        for pat, ext in _PATTERNS:
            m = re.match(pat, c)
            if m:
                try:
                    r = ext(m)
                    return [r] if r else []
                except: return []
        return []

    def _parse(self):
        entries = []; stack = []; stack_d = []; depth = 0
        for i, raw in enumerate(self.lines):
            bd = self._brace_depth(raw); od = depth; depth += bd
            defs = self._detect(raw)
            for k, n in defs:
                if k == "type":
                    e = {"kind": "type", "name": n, "line": i + 1, "end_line": i + 1, "label": n, "members": []}
                    entries.append(e); stack.append(e); stack_d.append(od)
                elif k == "companion":
                    if stack:
                        stack[-1].setdefault("members", []).append({"kind": "companion", "name": "companion", "line": i + 1, "end_line": i + 1, "label": "companion"})
                elif k in ("func", "init"):
                    if stack:
                        lbl = f"{n}()" if k == "func" else n
                        stack[-1].setdefault("members", []).append({"kind": k, "name": n, "line": i + 1, "end_line": i + 1, "label": lbl})
                    else:
                        entries.append({"kind": "func", "name": n, "line": i + 1, "end_line": i + 1, "label": f"{n}()"})
                elif k in ("property",):
                    if stack:
                        stack[-1].setdefault("members", []).append({"kind": "property", "name": n, "line": i + 1, "end_line": i + 1, "label": n})
                    else:
                        entries.append({"kind": "property", "name": n, "line": i + 1, "end_line": i + 1, "label": n})
                elif k == "enum_entry" and stack:
                    stack[-1].setdefault("members", []).append({"kind": "enum_entry", "name": n, "line": i + 1, "end_line": i + 1, "label": n})
            while stack_d and depth <= stack_d[-1] and bd < 0:
                if stack: stack.pop()["end_line"] = i
                stack_d.pop()
        for i, e in enumerate(entries):
            e["end_line"] = entries[i+1]["line"]-1 if i+1 < len(entries) else len(self.lines)-1
            for j, m in enumerate(e.get("members", [])):
                m["end_line"] = e["members"][j+1]["line"]-1 if j+1 < len(e["members"]) else e["end_line"]
        self.entries = entries

    def build_index(self):
        if not self.entries: return "(no definitions found)"
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
    if not path: return "Error: 'path' is required."
    if not os.path.isfile(path): return f"Error: File not found: {path}"
    try:
        with open(path, "r", encoding="utf-8") as _f:
            _source = _f.read()
        builder = _KtIndexBuilder(_source, filepath=path)
    except Exception as e:
        return f"Error parsing file: {e}"
    if mode == "index":
        return f"Index for: {path}\n---\n{builder.build_index()}\n---\nTotal definitions: {builder.section_count()}"
    elif mode == "section":
        sn = args.get("section")
        if sn is None: return "Error: 'section' (integer) is required."
        c = builder.get_section(int(sn))
        return c if c is not None else f"Error: Section {sn} not found."
    return "Error: Invalid mode."
