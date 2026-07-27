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
        "name": "cl2idx",
        "description": _(
            "tool.description",
            default=(
                "Parse an IBM i CL/CLP/CLLE (.cl/.clp/.clle) file into program entry, "
                "declarations, labels, control commands, and calls, and return a numbered "
                "index or a specific definition section. Use this when you need to read a "
                "large CL source: first call with mode='index', then mode='section'."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "read cl file",
                "clle index",
                "clp program structure",
                "IBM i CL",
                "CLソースを読む",
                "CLプログラム構造",
            ],
        ),
        "x_search_terms_en": [
            "read cl file",
            "clle index",
            "clp program structure",
            "IBM i CL",
        ],
        "x_parallel_safe": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Path to the CL/CLP/CLLE source file.",
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

# Commands treated as structural index entries (upper-case).
_CONTROL_CMDS = {
    "IF",
    "ELSE",
    "ENDIF",
    "DO",
    "DOWHILE",
    "DOUNTIL",
    "DOFOR",
    "ENDDO",
    "SELECT",
    "WHEN",
    "OTHERWISE",
    "ENDSELECT",
    "GOTO",
    "ITERATE",
    "LEAVE",
    "RETURN",
    "CHGVAR",
    "MONMSG",
    "TFRCTL",
    "SBMJOB",
    "SNDPGMMSG",
    "RCVMSG",
    "SNDRCVF",
    "RCVF",
    "SNDF",
    "INCLUDE",
    "COPY",
    "RTVJOBA",
    "RTVSYSVAL",
    "CHKOBJ",
}

# Block openers paired with closers for end_line refinement.
_BLOCK_OPEN = {
    "IF": "ENDIF",
    "DO": "ENDDO",
    "DOWHILE": "ENDDO",
    "DOUNTIL": "ENDDO",
    "DOFOR": "ENDDO",
    "SELECT": "ENDSELECT",
}
_BLOCK_CLOSE = {"ENDIF", "ENDDO", "ENDSELECT"}

# Words that must not be treated as labels.
_LABEL_EXCLUDE = _CONTROL_CMDS | {
    "PGM",
    "ENDPGM",
    "DCL",
    "DCLF",
    "CALL",
    "CALLPRC",
    "THEN",
    "AND",
    "OR",
    "NOT",
    "END",
    "EXEC",
}


def _strip_block_comments_span(text: str) -> str:
    """Remove /* ... */ comments, including multi-line spans."""
    out: list[str] = []
    i = 0
    n = len(text)
    in_comment = False
    while i < n:
        if not in_comment and i + 1 < n and text[i : i + 2] == "/*":
            in_comment = True
            i += 2
            continue
        if in_comment and i + 1 < n and text[i : i + 2] == "*/":
            in_comment = False
            i += 2
            # keep a space so tokens don't glue across comments
            out.append(" ")
            continue
        if not in_comment:
            out.append(text[i])
        elif text[i] == "\n":
            out.append("\n")
        i += 1
    return "".join(out)


def _strip_sequence_area(line: str) -> str:
    """Drop SEU-style 6-digit sequence prefix when present."""
    if len(line) >= 7 and line[:6].isdigit():
        return line[6:]
    if len(line) >= 6 and line[:5].isdigit() and line[5] in " \t":
        return line[5:]
    return line


class _ClIndexBuilder:
    """Regex-based IBM i CL/CLP/CLLE source indexer (v2).

    Improvements over v1:
    - multi-line /* */ comment stripping
    - continuation lines ending with + or -
    - SEU sequence-number prefix stripping
    - IF/DO/SELECT block end_line pairing with ENDIF/ENDDO/ENDSELECT
    - richer DCL/CALL/MONMSG labels
    """

    def __init__(self, source: str, filepath: str = ""):
        self.source = source
        self.filepath = filepath
        self.lines = source.split("\n")
        self.entries: list[dict[str, Any]] = []
        self._parse()

    def _logical_lines(self) -> list[tuple[int, str]]:
        """Join continuation lines (+ / -) into logical commands.

        Returns list of (start_line_0based, joined_text).
        """
        # First pass: strip multi-line comments on the whole source, keep newlines.
        cleaned_src = _strip_block_comments_span(self.source)
        raw_lines = cleaned_src.split("\n")
        # Align length with original lines for end_line mapping
        if len(raw_lines) < len(self.lines):
            raw_lines.extend([""] * (len(self.lines) - len(raw_lines)))

        result: list[tuple[int, str]] = []
        i = 0
        n = len(raw_lines)
        while i < n:
            line = _strip_sequence_area(raw_lines[i])
            stripped = line.rstrip()
            if not stripped.strip():
                i += 1
                continue

            # Continuation: line ends with + or - (CL continuation characters)
            ends = stripped.rstrip()
            if ends.endswith(("+", "-")) and i + 1 < n:
                parts = [ends[:-1].rstrip()]
                start = i
                i += 1
                while i < n:
                    nxt = _strip_sequence_area(raw_lines[i]).rstrip()
                    if not nxt.strip():
                        i += 1
                        continue
                    if nxt.endswith(("+", "-")):
                        parts.append(nxt[:-1].rstrip())
                        i += 1
                        continue
                    parts.append(nxt)
                    i += 1
                    break
                joined = " ".join(p.strip() for p in parts if p.strip())
                result.append((start, joined))
            else:
                result.append((i, stripped))
                i += 1
        return result

    def _normalize(self, line: str) -> str:
        return re.sub(r"\s+", " ", line).strip()

    def _summarize(self, text: str, limit: int = 40) -> str:
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) <= limit:
            return text
        return text[: limit - 3] + "..."

    def _paren_arg(self, upper: str, key: str) -> str | None:
        m = re.search(rf"{key}\(([^)]*)\)", upper)
        if m:
            return m.group(1).strip()
        return None

    def _detect(self, raw: str) -> list[tuple[str, str, str | None]]:
        """Return list of (kind, label, block_tag).

        block_tag is opener name (IF/DO/...) or closer name, else None.
        """
        normalized = self._normalize(raw)
        if not normalized:
            return []

        upper = normalized.upper()

        # PGM [PARM(...)]
        if re.match(r"^PGM\b", upper):
            parm = self._paren_arg(upper, "PARM")
            label = (
                f"PGM PARM({parm})"
                if parm
                else (
                    f"PGM {normalized[3:].strip()}" if normalized[3:].strip() else "PGM"
                )
            )
            if parm:
                label = f"PGM PARM({self._summarize(parm, 50)})"
            return [("pgm", label, None)]

        if re.match(r"^ENDPGM\b", upper):
            return [("endpgm", "ENDPGM", None)]

        # DCL VAR(&name) TYPE(*CHAR) LEN(n)
        m = re.match(r"^DCL\s+VAR\((&[\w@#$]+)\)(.*)$", upper)
        if m:
            m2 = re.match(r"(?i)^DCL\s+VAR\((&[\w@#$]+)\)(.*)$", normalized)
            name = m2.group(1) if m2 else m.group(1)
            rest = m.group(2)
            typ = self._paren_arg(rest, "TYPE") or ""
            ln = self._paren_arg(rest, "LEN") or ""
            extra = ""
            if typ:
                extra += f" {typ}"
            if ln:
                extra += f" LEN({ln})"
            return [("dcl", f"DCL {name}{extra}".rstrip(), None)]

        m = re.match(r"^DCL\s+(&[\w@#$]+)\b", upper)
        if m:
            m2 = re.match(r"(?i)^DCL\s+(&[\w@#$]+)\b", normalized)
            name = m2.group(1) if m2 else m.group(1)
            return [("dcl", f"DCL {name}", None)]

        if re.match(r"^DCLF\b", upper):
            f = self._paren_arg(upper, "FILE")
            if f:
                return [("dclf", f"DCLF FILE({f})", None)]
            rest = normalized[4:].strip()
            return [("dclf", f"DCLF {rest}".strip() if rest else "DCLF", None)]

        if re.match(r"^CALLPRC\b", upper):
            prc = self._paren_arg(upper, "PRC")
            if prc:
                return [("callprc", f"CALLPRC PRC({prc})", None)]
            return [("callprc", f"CALLPRC {self._summarize(normalized[7:])}", None)]

        if re.match(r"^CALL\b", upper):
            pgm = self._paren_arg(upper, "PGM")
            if pgm:
                return [("call", f"CALL PGM({pgm})", None)]
            return [("call", f"CALL {self._summarize(normalized[4:])}", None)]

        # Label: NAME: [cmd...]
        m = re.match(r"^([A-Z][\w@#$]*)\s*:\s*(.*)$", upper)
        if m:
            label_name = m.group(1)
            rest_upper = m.group(2).strip()
            if label_name not in _LABEL_EXCLUDE:
                results: list[tuple[str, str, str | None]] = [
                    ("label", f"{label_name}:", None)
                ]
                if rest_upper:
                    m2 = re.match(r"^([A-Za-z][\w@#$]*)\s*:\s*(.*)$", normalized)
                    rest_raw = m2.group(2) if m2 else rest_upper
                    results.extend(self._detect_command_only(rest_raw))
                return results

        return self._detect_command_only(normalized)

    def _detect_command_only(
        self, normalized: str
    ) -> list[tuple[str, str, str | None]]:
        upper = normalized.upper()
        m = re.match(r"^([A-Z][\w@#$]*)\b(.*)$", upper)
        if not m:
            return []
        cmd = m.group(1)
        if cmd not in _CONTROL_CMDS:
            return []

        block_tag: str | None = None
        if cmd in _BLOCK_OPEN:
            block_tag = cmd
        elif cmd in _BLOCK_CLOSE:
            block_tag = cmd

        if cmd == "MONMSG":
            msgid = self._paren_arg(upper, "MSGID")
            if msgid:
                return [("subcommand", f"MONMSG MSGID({msgid})", block_tag)]
            return [("subcommand", "MONMSG", block_tag)]

        if cmd == "CHGVAR":
            var = self._paren_arg(upper, "VAR")
            if var:
                return [("subcommand", f"CHGVAR {var}", block_tag)]
            return [("subcommand", "CHGVAR", block_tag)]

        if cmd == "GOTO":
            cm = self._paren_arg(upper, "CMDLBL")
            if cm:
                return [("subcommand", f"GOTO CMDLBL({cm})", block_tag)]
            rest = normalized[4:].strip()
            if rest:
                return [("subcommand", f"GOTO {self._summarize(rest, 30)}", block_tag)]
            return [("subcommand", "GOTO", block_tag)]

        if cmd in ("IF", "WHEN", "DOWHILE", "DOUNTIL", "DOFOR"):
            cond = self._paren_arg(upper, "COND")
            if cond is None:
                # COND may contain nested parens; try balanced extract
                cond = self._balanced_paren_arg(upper, "COND")
            if cond is not None:
                return [
                    (
                        "subcommand",
                        f"{cmd} COND({self._summarize(cond, 30)})",
                        block_tag,
                    )
                ]
            return [("subcommand", cmd, block_tag)]

        if cmd == "DO":
            return [("subcommand", "DO", block_tag)]

        if cmd in ("INCLUDE", "COPY"):
            rest = normalized[len(cmd) :].strip()
            if rest:
                return [("include", f"{cmd} {self._summarize(rest, 40)}", block_tag)]
            return [("include", cmd, block_tag)]

        if cmd in ("TFRCTL", "SBMJOB"):
            pgm = self._paren_arg(upper, "PGM")
            if pgm:
                return [("subcommand", f"{cmd} PGM({pgm})", block_tag)]
            return [("subcommand", cmd, block_tag)]

        if cmd in ("RTVJOBA", "RTVSYSVAL", "CHKOBJ", "SNDRCVF", "RCVF", "SNDF"):
            # keep short form with first keyword arg if any
            for key in ("OBJ", "SYSVAL", "JOB", "DEV"):
                arg = self._paren_arg(upper, key)
                if arg:
                    return [("subcommand", f"{cmd} {key}({arg})", block_tag)]
            return [("subcommand", cmd, block_tag)]

        return [("subcommand", cmd, block_tag)]

    def _balanced_paren_arg(self, upper: str, key: str) -> str | None:
        token = f"{key}("
        idx = upper.find(token)
        if idx < 0:
            return None
        i = idx + len(token)
        depth = 1
        start = i
        while i < len(upper):
            ch = upper[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return upper[start:i].strip()
            i += 1
        return None

    def _parse(self) -> None:
        entries: list[dict[str, Any]] = []
        current_pgm: dict[str, Any] | None = None
        # stack of (block_open_cmd, item_ref) for end_line pairing
        block_stack: list[tuple[str, dict[str, Any]]] = []

        for start_idx, raw in self._logical_lines():
            defs = self._detect(raw)
            if not defs:
                continue

            for kind, label, block_tag in defs:
                item: dict[str, Any] = {
                    "kind": kind,
                    "name": label,
                    "line": start_idx + 1,
                    "end_line": start_idx + 1,
                    "label": label,
                }

                if kind == "pgm":
                    item["members"] = []
                    entries.append(item)
                    current_pgm = item
                    block_stack.clear()
                elif kind == "endpgm":
                    # close open blocks to ENDPGM-1
                    while block_stack:
                        _, ref = block_stack.pop()
                        if ref["end_line"] < start_idx:
                            ref["end_line"] = (
                                start_idx  # line before ENDPGM (1-based: start_idx)
                            )
                    entries.append(item)
                    if current_pgm is not None:
                        # PGM body ends at ENDPGM line
                        current_pgm["end_line"] = start_idx + 1
                    current_pgm = None
                else:
                    target_list: list[dict[str, Any]]
                    if current_pgm is not None:
                        target_list = current_pgm.setdefault("members", [])
                    else:
                        target_list = entries
                        # ensure top-level non-member entries work
                    target_list.append(item)

                    # Block open: remember for closer
                    if block_tag and block_tag in _BLOCK_OPEN:
                        block_stack.append((block_tag, item))
                    elif block_tag and block_tag in _BLOCK_CLOSE:
                        # pop until matching opener
                        want = {
                            "ENDIF": "IF",
                            "ENDDO": "DO",  # also DOWHILE/DOUNTIL/DOFOR
                            "ENDSELECT": "SELECT",
                        }.get(block_tag)
                        while block_stack:
                            open_cmd, ref = block_stack.pop()
                            # ENDDO closes DO/DOWHILE/DOUNTIL/DOFOR
                            if block_tag == "ENDDO" and open_cmd in (
                                "DO",
                                "DOWHILE",
                                "DOUNTIL",
                                "DOFOR",
                            ):
                                ref["end_line"] = start_idx + 1
                                break
                            if want and open_cmd == want:
                                ref["end_line"] = start_idx + 1
                                break
                            # mismatched: still close the inner one
                            ref["end_line"] = start_idx + 1

        self._assign_end_lines(entries)
        self.entries = entries

    def _assign_end_lines(self, entries: list[dict]) -> None:
        """Fill end_line for entries that still span only one line.

        Respects block-refined end_lines already set (> line).
        """
        for idx, e in enumerate(entries):
            if e.get("end_line", e["line"]) <= e["line"]:
                if idx + 1 < len(entries):
                    e["end_line"] = entries[idx + 1]["line"] - 1
                else:
                    e["end_line"] = len(self.lines)
            # PGM with members: extend to cover last member if needed
            members = e.get("members", [])
            if members and e["kind"] == "pgm":
                last_m_end = max(m.get("end_line", m["line"]) for m in members)
                if last_m_end > e["end_line"]:
                    e["end_line"] = last_m_end
            for midx, m in enumerate(members):
                if m.get("end_line", m["line"]) <= m["line"]:
                    if midx + 1 < len(members):
                        m["end_line"] = members[midx + 1]["line"] - 1
                    else:
                        m["end_line"] = e["end_line"]
                # clamp
                if m["end_line"] < m["line"]:
                    m["end_line"] = m["line"]
            if e["end_line"] < e["line"]:
                e["end_line"] = e["line"]

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
        flat: list[dict] = []
        for e in self.entries:
            flat.append(e)
            flat.extend(e.get("members", []))
        if n < 1 or n > len(flat):
            return None
        e = flat[n - 1]
        start_0 = e["line"] - 1
        end_0 = e.get("end_line", e["line"])
        if end_0 > len(self.lines):
            end_0 = len(self.lines)
        # end_line is 1-based inclusive
        code_lines = self.lines[start_0:end_0]
        while code_lines and not code_lines[-1].strip():
            code_lines.pop()
        return "\n".join(code_lines).rstrip("\n")

    def section_count(self) -> int:
        count = 0
        for e in self.entries:
            count += 1
            count += len(e.get("members", []))
        return count


def run_tool(args: dict[str, Any]) -> str:
    path = args.get("path", "")
    mode = args.get("mode", "index")

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
        source = read_index_source(safe_path)
    except Exception as e:
        return _("err.read_error", default="Error reading file: {e}", e=str(e))

    try:
        builder = _ClIndexBuilder(source, filepath=safe_path)
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
                "To retrieve a definition, call cl2idx with mode='section' and the section number."
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
