from __future__ import annotations

import os
import re

from .i18n_helper import make_tool_translator
from .index_tool_helpers import read_index_source, resolve_index_path

_ = make_tool_translator(__file__)

TOOL_SPEC = {
    "type": "function",
    "tool_genre": "index",
    "function": {
        "name": "kt2idx",
        "description": _(
            "tool.description",
            default="Parse a Kotlin (.kt) file into classes, interfaces, objects, functions, and properties and return a numbered index or a specific definition section.",
        ),
        "x_parallel_safe": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Path to the Kotlin (.kt) file.",
                    ),
                },
                "mode": {
                    "type": "string",
                    "enum": ["index", "section"],
                    "description": _(
                        "param.mode.description",
                        default='"index" returns a numbered table of contents. "section" returns a specific definition by number.',
                    ),
                },
                "section": {
                    "type": "integer",
                    "description": _(
                        "param.section.description",
                        default="Section number to retrieve (used only when mode='section').",
                    ),
                },
            },
            "required": ["path", "mode"],
            "additionalProperties": False,
        },
    },
}

_MOD = r"(?:(?:public|private|protected|internal|open|final|abstract|sealed|data|inner|inline|suspend|operator|infix|tailrec|external|override|lateinit|noinline|crossinline|const|actual|expect)\s+)*"


def _kt_fun_extract(m: re.Match) -> tuple:
    """Return (kind, name[, receiver]) for Kotlin fun declarations."""
    receiver = (m.group(1) or "").strip()
    name = m.group(2)
    if receiver:
        receiver = re.sub(r"\s+", "", receiver)
        return ("extension", name, receiver)
    return ("func", name)


_PATTERNS = [
    (r"^\s*(?:import|package)\s+", lambda m: None),
    (
        r"^\s*"
        + _MOD
        + r"(class|interface|object|enum\s+class|annotation\s+class|data\s+class|sealed\s+class|sealed\s+interface)\s+(\w+(?:<[^>]*>)?)",
        lambda m: ("type", m.group(2), re.sub(r"\s+", " ", m.group(1).strip())),
    ),
    (
        r"^\s*"
        + _MOD
        + r"fun\s*(?:<[^>\n]*>\s*)?(?:((?:[\w.]+)(?:\s*<[^>\n]*>)?(?:\?)?(?:\s*\.\s*(?:[\w.]+)(?:\s*<[^>\n]*>)?(?:\?)?)*)\s*\.\s*)?(\w+)\s*\(",
        _kt_fun_extract,
    ),
    (
        r"^\s*" + _MOD + r"(?:val|var)\s+(\w+)\s*(?::|=)",
        lambda m: ("property", m.group(1)),
    ),
    (r"^\s*" + _MOD + r"init\s*(?:\{|$)", lambda m: ("init", "init")),
    (
        r"^\s*" + _MOD + r"companion\s+object(?:\s+(\w+))?\s*(?:\{|$|:)",
        lambda m: ("companion", m.group(1) or "companion"),
    ),
    (r"^\s*(?:enum\s+)?(\w+)\s*(?:\(|,)", lambda m: ("enum_entry", m.group(1))),
]


class _KtIndexBuilder:
    def __init__(self, source: str, filepath: str = ""):
        self.source = source
        self.filepath = filepath
        self.lines = source.split("\n")
        self.entries = []
        self.diag: list[str] = []
        self._parse()

    def _preprocess(self):
        """Join multi-line signatures ending with ',' or '('."""
        result = []
        i = 0
        while i < len(self.lines):
            raw = self.lines[i]
            stripped = raw.strip()
            if stripped.startswith("@"):
                i += 1
                continue
            ends = stripped.rstrip()
            if (ends.endswith(",") or ends.endswith("(")) and i + 1 < len(self.lines):
                joined = raw.rstrip(chr(10)).rstrip()
                orig = i
                i += 1
                while i < len(self.lines):
                    ns = self.lines[i].strip()
                    if not ns or self.lines[i].startswith((" ", chr(9))):
                        if ns.startswith("@"):
                            i += 1
                            continue
                        joined += " " + ns
                        if not ns.endswith(","):
                            i += 1
                            break
                    else:
                        break
                    i += 1
                result.append((orig, joined))
            else:
                result.append((i, raw))
                i += 1
        return result

    def _clean_line(self, line):
        in_str = False
        sc = None
        res = []
        i = 0
        while i < len(line):
            ch = line[i]
            if in_str:
                res.append(ch)
                if ch == "\\" and i + 1 < len(line):
                    res.append(line[i + 1])
                    i += 2
                    continue
                if ch == sc:
                    in_str = False
                    i += 1
                    continue
                i += 1
                continue
            if ch in ('"', "'"):
                in_str = True
                sc = ch
                res.append(ch)
                i += 1
                continue
            if ch == "/" and i + 1 < len(line):
                if line[i + 1] == "/":
                    break
                if line[i + 1] == "*":
                    return "".join(res)
            res.append(ch)
            i += 1
        return "".join(res)

    def _brace_depth(self, raw):
        c = self._clean_line(raw)
        d = 0
        in_str = False
        sc = None
        for ch in c:
            if in_str:
                if ch == sc:
                    in_str = False
                    continue
                continue
            if ch in ('"', "'"):
                in_str = True
                sc = ch
                continue
            if ch == "{":
                d += 1
            elif ch == "}":
                d -= 1
        return d

    def _detect(self, line):
        c = self._clean_line(line)
        if not c.strip():
            return []
        for pat, ext in _PATTERNS:
            m = re.match(pat, c)
            if m:
                try:
                    r = ext(m)
                    return [r] if r else []
                except Exception:
                    return []
        return []

    def _parse(self):
        entries = []
        stack = []
        stack_d = []
        depth = 0
        preprocessed = self._preprocess()
        for orig_idx, raw in preprocessed:
            i = orig_idx
            bd = self._brace_depth(raw)
            od = depth
            depth += bd
            defs = self._detect(raw)
            for d in defs:
                k, n = d[0], d[1]
                extra = d[2] if len(d) > 2 else ""
                if k == "type":
                    tkind = extra or "class"
                    e = {
                        "kind": "type",
                        "name": n,
                        "line": i + 1,
                        "end_line": i + 1,
                        "label": f"{tkind} {n}",
                        "members": [],
                    }
                    entries.append(e)
                    stack.append(e)
                    stack_d.append(od)
                elif k == "companion":
                    if stack:
                        stack[-1].setdefault("members", []).append(
                            {
                                "kind": "companion",
                                "name": n,
                                "line": i + 1,
                                "end_line": i + 1,
                                "label": (
                                    f"companion object {n}"
                                    if n != "companion"
                                    else "companion object"
                                ),
                            }
                        )
                elif k in ("func", "init", "extension"):
                    if k == "extension":
                        lbl = f"fun {extra}.{n}()"
                        kind = "extension"
                    elif k == "func":
                        lbl = f"fun {n}()"
                        kind = "func"
                    else:
                        lbl = n
                        kind = k
                    item = {
                        "kind": kind,
                        "name": n,
                        "line": i + 1,
                        "end_line": i + 1,
                        "label": lbl,
                    }
                    if k == "extension":
                        item["receiver"] = extra
                    if stack:
                        stack[-1].setdefault("members", []).append(item)
                    else:
                        entries.append(item)
                elif k in ("property",):
                    if stack:
                        stack[-1].setdefault("members", []).append(
                            {
                                "kind": "property",
                                "name": n,
                                "line": i + 1,
                                "end_line": i + 1,
                                "label": n,
                            }
                        )
                    else:
                        entries.append(
                            {
                                "kind": "property",
                                "name": n,
                                "line": i + 1,
                                "end_line": i + 1,
                                "label": n,
                            }
                        )
                elif k == "enum_entry" and stack:
                    stack[-1].setdefault("members", []).append(
                        {
                            "kind": "enum_entry",
                            "name": n,
                            "line": i + 1,
                            "end_line": i + 1,
                            "label": n,
                        }
                    )
            while stack_d and depth <= stack_d[-1]:
                if stack:
                    stack.pop()["end_line"] = i
                stack_d.pop()
        for i, e in enumerate(entries):
            e["end_line"] = (
                entries[i + 1]["line"] - 1
                if i + 1 < len(entries)
                else len(self.lines) - 1
            )
            for j, m in enumerate(e.get("members", [])):
                m["end_line"] = (
                    e["members"][j + 1]["line"] - 1
                    if j + 1 < len(e["members"])
                    else e["end_line"]
                )
        self.entries = entries

    def _count_braces(self):
        opens = closes = 0
        raw = chr(10).join(self.lines)
        cleaned = self._clean_line(raw)
        for ch in cleaned:
            if ch == "{":
                opens += 1
            elif ch == "}":
                closes += 1
        return opens, closes

    def _diag_hint(self):
        parts = []
        opens, closes = self._count_braces()
        if opens != closes:
            parts.append(
                _(
                    "msg.brace_imbalance",
                    default="brace imbalance: {open} open vs {close} close",
                ).format(open=opens, close=closes)
            )
        if parts:
            return " (" + "; ".join(parts) + ")"
        return ""

    def build_index(self) -> str:
        if not self.entries:
            hint = self._diag_hint()
            return _("msg.no_entries", default="(no definitions found)") + hint

        lines = []
        idx = 0
        for e in self.entries:
            idx += 1
            lines.append(f"  {idx}. L{e['line']} {e['label']}")
            for m in e.get("members", []):
                idx += 1
                lines.append(f"      {idx}. L{m['line']} {m['label']}")
        return "\n".join(lines)

    def get_section(self, n):
        flat = []
        for e in self.entries:
            flat.append(e)
            flat.extend(e.get("members", []))
        if n < 1 or n > len(flat):
            return None
        e = flat[n - 1]
        # entry line/end_line are 1-based inclusive; self.lines is 0-based.
        start = max(0, e["line"] - 1)
        end = e.get("end_line", e["line"])
        if end > len(self.lines):
            end = len(self.lines)
        return "\n".join(self.lines[start:end]).rstrip("\n")

    def section_count(self):
        return sum(1 + len(e.get("members", [])) for e in self.entries)


def run_tool(args):
    path, mode = args.get("path", ""), args.get("mode", "index")
    if not path:
        return _("err.path_required", default="Error: 'path' is required.")
    try:
        safe_path = resolve_index_path(str(path))
    except Exception:
        return _(
            "err.file_not_found", default="Error: File not found: {path}", path=path
        )

    if not os.path.isfile(safe_path):
        return _(
            "err.file_not_found", default="Error: File not found: {path}", path=path
        )

    try:
        _source = read_index_source(safe_path)
        builder = _KtIndexBuilder(_source, filepath=safe_path)
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
                "To retrieve a definition, call kt2idx with mode='section' and the section number."
            ),
            path=path,
            total=total,
            toc=toc,
        )
    elif mode == "section":
        sn = args.get("section")
        if sn is None:
            return _(
                "err.section_required",
                default="Error: 'section' (integer) is required when mode='section'.",
            )
        try:
            c = builder.get_section(int(sn))
        except (TypeError, ValueError):
            return _(
                "err.section_invalid",
                default="Error: 'section' must be an integer.",
                section_num=repr(sn),
            )
        if c is None:
            total = builder.section_count()
            return _(
                "err.section_not_found",
                default="Error: Section {section_num} not found. Valid range: 1..{last}.",
                section_num=sn,
                last=total,
            )
        return c
    return _(
        "err.invalid_mode",
        default="Error: Invalid mode '{mode}'. Use 'index' or 'section'.",
        mode=mode,
    )
