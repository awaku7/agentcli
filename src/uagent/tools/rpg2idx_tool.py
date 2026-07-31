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
        "name": "rpg2idx",
        "description": _(
            "tool.description",
            default=(
                "Parse an IBM i RPG/RPGLE/SQLRPGLE (.rpg/.rpgle/.sqlrpgle) file into control "
                "options, files, definitions, procedures, subroutines, copy/include, embedded "
                "SQL (EXEC SQL), conditional compile (/IF /DEFINE), and fixed-form specs, "
                "and return a numbered index or a specific definition section. Use this when "
                "you need to read a large RPG source: first call with mode='index', then "
                "mode='section'."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "read rpg file",
                "rpgle index",
                "rpg procedure",
                "IBM i RPG",
                "SQLRPGLE",
                "EXEC SQL",
                "/IF",
                "RPGソースを読む",
                "RPGLE プログラム構造",
                "dcl-proc",
                "begsr",
            ],
        ),
        "x_search_terms_en": [
            "read rpg file",
            "rpgle index",
            "rpg procedure",
            "IBM i RPG",
            "SQLRPGLE",
            "EXEC SQL",
            "/IF",
            "dcl-proc",
            "begsr",
        ],
        "x_parallel_safe": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Path to the RPG/RPGLE (.rpg/.rpgle/.sqlrpgle) source file.",
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


def _strip_seq(line: str) -> str:
    """Drop SEU 5–6 digit sequence prefix when present."""
    if len(line) >= 7 and line[:6].isdigit():
        return line[6:]
    if len(line) >= 6 and line[:5].isdigit() and line[5] in " \t":
        return line[5:]
    return line


def _is_full_line_comment(line: str) -> bool:
    s = _strip_seq(line).lstrip()
    if not s:
        return True
    # Free-form // comment
    if s.startswith("//"):
        return True
    # Compiler directives **free / **end-free are not comments
    low = s.lower()
    if low.startswith("**free") or low.startswith("** free"):
        return False
    if low.startswith("**end-free") or low.startswith("** end-free"):
        return False
    # Fixed-format: asterisk comment (but not ** directives already handled)
    raw = _strip_seq(line)
    if len(raw) >= 1 and raw[0] == "*" and not raw.startswith("**"):
        return True
    # With form-type style: * in column 7 of full card
    if len(line) >= 7 and line[6] == "*" and (line[:6].isdigit() or line[:6].isspace()):
        # allow **free starting at col 7
        tail = line[6:].lstrip().lower()
        if tail.startswith("**free") or tail.startswith("**end-free"):
            return False
        return True
    return False


def _strip_inline_free_comment(line: str) -> str:
    """Remove // comments outside strings (free-form)."""
    in_str = False
    sc = None
    i = 0
    while i < len(line):
        ch = line[i]
        if in_str:
            if ch == sc:
                in_str = False
            i += 1
            continue
        if ch in ("'", '"'):
            in_str = True
            sc = ch
            i += 1
            continue
        if ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
            return line[:i]
        i += 1
    return line


class _RpgIndexBuilder:
    """Indexer for IBM i RPG III / RPGLE / SQLRPGLE (fixed + free-form).

    Detects:
    - **free / ctl-opt / H-spec
    - dcl-f / F-spec files (with usage/device hints)
    - dcl-s / dcl-c / dcl-ds / dcl-pi / dcl-pr / D-spec (DS/S/C/PI/PR)
    - dcl-proc / end-proc / P-spec procedures
    - begsr / endsr subroutines; key C-spec opcodes (CALL/EVAL/IF/...)
    - /copy /include
    - embedded SQL: exec sql ... ; and /EXEC SQL ... /END-EXEC
    - conditional compile: /IF /ELSEIF /ELSE /ENDIF /DEFINE /UNDEFINE /EOF
    - monitor blocks (start only)
    - I/O specs
    """

    def __init__(self, source: str, filepath: str = ""):
        self.source = source
        self.filepath = filepath
        self.lines = source.split("\n")
        self.entries: list[dict[str, Any]] = []
        self._free_mode = False
        self._parse()

    def _logical_lines(self) -> list[tuple[int, int, str]]:
        """Join free-form continuation, multi-line EXEC SQL, and /EXEC SQL blocks.

        Returns list of (start_idx, end_idx_inclusive, joined_text).
        """
        result: list[tuple[int, int, str]] = []
        i = 0
        n = len(self.lines)
        while i < n:
            raw = self.lines[i]
            if _is_full_line_comment(raw):
                i += 1
                continue
            line = _strip_inline_free_comment(_strip_seq(raw)).rstrip()
            if not line.strip():
                i += 1
                continue

            low = line.strip().lower()
            start = i

            # Free-form: exec sql ... ;
            # Fixed/directive: /EXEC SQL ... /END-EXEC
            is_exec_sql = bool(
                re.match(r"^/exec\s+sql\b", low) or re.match(r"^exec\s+sql\b", low)
            )
            if is_exec_sql:
                directive_style = low.startswith("/exec")
                parts = [line.strip()]
                end = i
                # Single-line free-form already complete?
                if (not directive_style) and ";" in line:
                    result.append((start, end, line.strip()))
                    i += 1
                    continue
                if directive_style and re.search(r"/end-exec\b", low):
                    result.append((start, end, line.strip()))
                    i += 1
                    continue
                i += 1
                while i < n:
                    nxt_raw = self.lines[i]
                    if _is_full_line_comment(nxt_raw):
                        i += 1
                        continue
                    nxt = _strip_inline_free_comment(_strip_seq(nxt_raw)).rstrip()
                    if not nxt.strip():
                        i += 1
                        continue
                    parts.append(nxt.strip())
                    end = i
                    i += 1
                    joined_tmp = " ".join(parts)
                    jlow = joined_tmp.lower()
                    if directive_style:
                        if re.search(r"/end-exec\b", jlow):
                            break
                    elif ";" in joined_tmp:
                        break
                result.append((start, end, " ".join(parts)))
                continue

            # free-form line continuation ends with ...
            stripped = line.rstrip()
            if stripped.endswith("...") and i + 1 < n:
                parts = [stripped[:-3].rstrip()]
                end = i
                i += 1
                while i < n:
                    nxt_raw = self.lines[i]
                    if _is_full_line_comment(nxt_raw):
                        i += 1
                        continue
                    nxt = _strip_inline_free_comment(_strip_seq(nxt_raw)).rstrip()
                    if not nxt.strip():
                        i += 1
                        continue
                    if nxt.endswith("..."):
                        parts.append(nxt[:-3].rstrip())
                        end = i
                        i += 1
                        continue
                    parts.append(nxt)
                    end = i
                    i += 1
                    break
                result.append((start, end, " ".join(p.strip() for p in parts)))
            else:
                result.append((i, i, line))
                i += 1
        return result

    def _detect(self, line: str) -> list[tuple[str, str]]:
        s = line.strip()
        if not s:
            return []
        low = s.lower()

        # Directives
        if low.startswith("**free") or low.startswith("** free"):
            self._free_mode = True
            return [("directive", "**free")]
        if low.startswith("**end-free") or low.startswith("** end-free"):
            self._free_mode = False
            return [("directive", "**end-free")]

        # /copy /include
        m = re.match(r"^/(copy|include)\b\s*(.*)$", s, re.I)
        if m:
            kind = m.group(1).lower()
            rest = (m.group(2) or "").strip()
            label = f"/{kind} {rest}".strip()
            return [("include", label)]

        # Conditional compile directives
        m = re.match(
            r"^/(if|elseif|else|endif|define|undefine|eof)\b\s*(.*)$",
            s,
            re.I,
        )
        if m:
            dkw = m.group(1).lower()
            rest = (m.group(2) or "").strip()
            rest = re.sub(r"\s+", " ", rest)
            if len(rest) > 40:
                rest = rest[:37] + "..."
            label = f"/{dkw}" + (f" {rest}" if rest else "")
            return [("cond_compile", label)]

        # Embedded SQL (joined logical line may span multiple source lines)
        m = re.match(r"^/exec\s+sql\b(.*)$", s, re.I | re.S)
        if m:
            body = m.group(1) or ""
            body = re.sub(r"/end-exec\b", "", body, flags=re.I)
            body = re.sub(r"\s+", " ", body).strip(" ;")
            summary = self._sql_summary(body)
            return [("sql", f"EXEC SQL {summary}".strip())]
        m = re.match(r"^exec\s+sql\b(.*)$", s, re.I | re.S)
        if m:
            body = m.group(1) or ""
            body = re.sub(r";\s*$", "", body.strip())
            body = re.sub(r"\s+", " ", body).strip()
            summary = self._sql_summary(body)
            return [("sql", f"EXEC SQL {summary}".strip())]

        # Free-form declarations and structures
        # ctl-opt
        if re.match(r"^ctl-opt\b", low):
            summary = re.sub(r"\s+", " ", s)
            if len(summary) > 60:
                summary = summary[:57] + "..."
            return [("ctl_opt", summary)]

        # dcl-proc name
        m = re.match(
            r"^(?:dcl-proc)\s+([A-Za-z@#$][\w@#$]*)\b(.*)$",
            s,
            re.I,
        )
        if m:
            name = m.group(1)
            export = (
                " export" if re.search(r"\bexport\b", m.group(2) or "", re.I) else ""
            )
            return [("proc", f"dcl-proc {name}{export}")]

        if re.match(r"^end-proc\b", low):
            return [("end_proc", "end-proc")]

        # dcl-f file
        m = re.match(r"^dcl-f\s+([A-Za-z@#$][\w@#$]*)\b(.*)$", s, re.I)
        if m:
            name = m.group(1)
            usage = ""
            um = re.search(r"\busage\(([^)]*)\)", s, re.I)
            if um:
                usage = f" usage({um.group(1).strip()})"
            return [("file", f"dcl-f {name}{usage}")]

        # dcl-ds / dcl-pi / dcl-pr / dcl-s / dcl-c / dcl-subf / dcl-parm
        m = re.match(
            r"^(dcl-ds|dcl-pi|dcl-pr|dcl-s|dcl-c|dcl-subf|dcl-parm)\s+([A-Za-z@#$*][\w@#$]*)\b(.*)$",
            s,
            re.I,
        )
        if m:
            kw = m.group(1).lower()
            name = m.group(2)
            rest = m.group(3) or ""
            if kw == "dcl-ds":
                return [("ds", f"dcl-ds {name}")]
            if kw == "dcl-pi":
                return [("pi", f"dcl-pi {name}")]
            if kw == "dcl-pr":
                return [("pr", f"dcl-pr {name}")]
            if kw == "dcl-s":
                typ = self._free_type_summary(rest)
                return [("field", f"dcl-s {name}{typ}")]
            if kw == "dcl-c":
                return [("const", f"dcl-c {name}")]
            if kw == "dcl-subf":
                return [("subf", f"dcl-subf {name}")]
            if kw == "dcl-parm":
                return [("parm", f"dcl-parm {name}")]

        # anonymous pi/pr/ds
        m = re.match(r"^(dcl-pi|dcl-pr|dcl-ds)\b(?!\s+[A-Za-z@#$])(.*)$", s, re.I)
        if m:
            kw = m.group(1).lower()
            return [(kw.replace("dcl-", ""), f"{kw} *N")]

        if re.match(r"^end-(ds|pi|pr)\b", low):
            return [("end_block", low.split()[0].lower())]

        # begsr / endsr
        m = re.match(r"^begsr\s+([A-Za-z@#$][\w@#$]*)\b", s, re.I)
        if m:
            return [("subroutine", f"begsr {m.group(1)}")]
        if re.match(r"^endsr\b", low):
            return [("end_sr", "endsr")]

        # monitor
        if re.match(r"^monitor\b", low):
            return [("monitor", "monitor")]
        if re.match(r"^endmon\b", low):
            return [("end_monitor", "endmon")]

        # Fixed-format specs (columns after sequence strip)
        # Standard RPG: col 6 = spec type (H F D I C O P)
        fixed = _strip_seq(line)
        # If free mode and line looks free, skip fixed
        if self._free_mode and not re.match(r"^\s*[HFDICOP]\s", fixed.upper()):
            # already handled free forms above
            return []

        spec = self._fixed_spec(fixed)
        if spec:
            return [spec]

        return []

    def _free_type_summary(self, rest: str) -> str:
        rest_u = rest.strip()
        if not rest_u:
            return ""
        # like "char(10)" or "like(x)" or "ind"
        m = re.match(r"([A-Za-z@#$][\w@#$]*)\s*(\([^)]*\))?", rest_u)
        if m:
            t = m.group(1)
            a = m.group(2) or ""
            return f" {t}{a}"
        return ""

    @staticmethod
    def _sql_summary(body: str) -> str:
        """Compress SQL body to a short index label."""
        b = re.sub(r"\s+", " ", (body or "").strip())
        if not b:
            return "(sql)"
        # Leading verb + optional object hint
        m = re.match(
            r"^(select|insert|update|delete|declare|open|fetch|close|set|call|"
            r"commit|rollback|connect|disconnect|create|drop|alter|values|"
            r"prepare|execute|describe|whenever)\b(.*)$",
            b,
            re.I,
        )
        if m:
            verb = m.group(1).upper()
            rest = (m.group(2) or "").strip()
            # pull first identifier-ish token for context
            hint = ""
            im = re.search(
                r"\b(?:into|from|table|cursor|procedure)?\s*"
                r"([A-Za-z@#$][\w@#$]*(?:\.[A-Za-z@#$][\w@#$]*)?)",
                rest,
                re.I,
            )
            if im:
                hint = im.group(1)
            label = f"{verb} {hint}".strip() if hint else verb
            if len(label) > 48:
                label = label[:45] + "..."
            return label
        if len(b) > 48:
            return b[:45] + "..."
        return b

    # Notable C-spec opcodes worth indexing (fixed-form calc)
    _C_INDEX_OPS = frozenset(
        {
            "CALL",
            "CALLB",
            "CALLP",
            "EVAL",
            "EVALR",
            "IF",
            "WHEN",
            "OTHER",
            "SELECT",
            "FOR",
            "DO",
            "DOW",
            "DOU",
            "ITER",
            "LEAVE",
            "LEAVESR",
            "RETURN",
            "EXFMT",
            "CHAIN",
            "READ",
            "READE",
            "READP",
            "READPE",
            "WRITE",
            "UPDATE",
            "DELETE",
            "SETLL",
            "SETGT",
            "OPEN",
            "CLOSE",
            "MONITOR",
            "ON-ERROR",
            "ON-EXIT",
        }
    )

    def _fixed_spec(self, fixed: str) -> tuple[str, str] | None:
        """Parse fixed-format RPG line. Spec type typically at column 6 (1-based).

        Layout variants tried (after optional SEU sequence strip):
          - classic: form at index 5 (col 6 with leading spaces)
          - flush: form at index 0
        D-spec DS/S/C/PI/PR from declaration-type columns; F-spec usage/device.
        C-spec: BEGSR/ENDSR/EXSR plus selected opcodes.
        """
        if not fixed or fixed.lstrip().startswith("*"):
            return None
        # Pad for column access; after seq strip, col6 is often index 5
        p = fixed if len(fixed) >= 100 else fixed + " " * (100 - len(fixed))

        # Try spec type at index 5 (col 6) and index 0
        for spec_i in (5, 0):
            st = p[spec_i : spec_i + 1].upper()
            if st not in ("H", "F", "D", "I", "C", "O", "P"):
                continue

            if st == "H":
                # Keywords often start around col 7+
                kw = p[spec_i + 1 :].strip()
                kw = re.sub(r"\s+", " ", kw)
                if kw and len(kw) > 40:
                    kw = kw[:37] + "..."
                return ("ctl_opt", f"H-spec {kw}".strip() if kw else "H-spec")

            if st == "F":
                # File name cols 7-14 (1-based) -> index spec_i+1 : spec_i+9
                name = p[spec_i + 1 : spec_i + 9].strip()
                # File type I/O/U/C often col 15 -> index spec_i+9
                ftype = p[spec_i + 9 : spec_i + 10].strip().upper()
                # Designation (F/E) col 17 -> index spec_i+11
                desig = p[spec_i + 11 : spec_i + 12].strip().upper()
                # Device cols 36-42 approx -> index spec_i+30 : spec_i+37
                device = p[spec_i + 30 : spec_i + 37].strip().upper()
                extras: list[str] = []
                if ftype:
                    extras.append(ftype)
                if desig:
                    extras.append(desig)
                if device:
                    extras.append(device)
                extra_s = (" " + " ".join(extras)) if extras else ""
                if name and name[0] != "*":
                    return ("file", f"F {name}{extra_s}")
                return ("file", f"F-spec{extra_s}".strip())

            if st == "D":
                # Name cols 7-21 (spec_i+1 : spec_i+16)
                name = p[spec_i + 1 : spec_i + 16].strip()
                # External type / DS etc. — declaration type typically cols 24-25
                # With form at 5: name 6:21, E 21, DS/S/C/PI/PR around 23:25
                decl_area = p[spec_i + 17 : spec_i + 25].upper()
                kind_hint = ""
                for tok in ("PI", "PR", "DS", "S", "C"):
                    # word-boundary-ish match in decl area
                    if re.search(
                        rf"(?:^|\s){tok}(?:\s|$)", decl_area
                    ) or decl_area.strip().startswith(tok):
                        kind_hint = tok
                        break
                if not kind_hint:
                    # fallback: two-char slice historically used
                    ds = p[spec_i + 15 : spec_i + 17].strip().upper()
                    decl = p[spec_i + 17 : spec_i + 19].strip().upper()
                    kind_hint = decl or ds
                # Data type letter often col 40 -> index ~spec_i+34
                dtype = p[spec_i + 34 : spec_i + 35].strip().upper()
                # Length cols 33-39 rough
                length = p[spec_i + 27 : spec_i + 34].strip()
                length = re.sub(r"[^\d.]", "", length)
                if name.startswith("*") and name.upper() not in (
                    "*N",
                    "*AUTO",
                    "*DTAARA",
                ):
                    # *LIKE DEFINE etc. still useful sometimes
                    if not kind_hint:
                        return None
                type_bits: list[str] = []
                if kind_hint:
                    type_bits.append(kind_hint)
                if length:
                    type_bits.append(length)
                if dtype and dtype.isalpha():
                    type_bits.append(dtype)
                suffix = (" " + " ".join(type_bits)) if type_bits else ""
                if not name:
                    return ("def", f"D-spec{suffix}".strip())
                # Map DS/PI/PR to structured kinds when clear
                if kind_hint == "DS":
                    return ("ds", f"D {name} DS")
                if kind_hint == "PI":
                    return ("pi", f"D {name} PI")
                if kind_hint == "PR":
                    return ("pr", f"D {name} PR")
                if kind_hint == "S":
                    return (
                        "field",
                        f"D {name} S{(' ' + length + dtype) if length or dtype else ''}".rstrip(),
                    )
                if kind_hint == "C":
                    return ("const", f"D {name} C")
                return ("def", f"D {name}{suffix}")

            if st == "P":
                # Procedure begin/end: name cols 7-21, begin/end marker
                name = p[spec_i + 1 : spec_i + 16].strip()
                rest = p[spec_i + 16 :].upper()
                # begin marker 'B' typically in col 24 area
                begin_m = p[spec_i + 18 : spec_i + 24].upper()
                if "B" in begin_m and not re.search(r"\bE\b", begin_m):
                    return ("proc", f"P {name or '*N'} B")
                if re.search(r"\bE\b", rest[:20]) or rest.strip().startswith("E"):
                    return ("end_proc", f"P {name or ''} E".strip())
                if "B" in rest[:10] and "E" not in rest[:3]:
                    return ("proc", f"P {name or '*N'} B")
                if name:
                    return ("proc", f"P {name}")
                return None

            if st == "C":
                # Factor1 / opcode / factor2 style extraction
                # With form at 5: factor1 ~6:20, opcode ~20:30, factor2 ~30:44
                factor1 = p[spec_i + 1 : spec_i + 15].strip()
                opcode = p[spec_i + 15 : spec_i + 25].strip().upper()
                factor2 = p[spec_i + 25 : spec_i + 39].strip()
                # Some exports pack differently — also regex fallback
                up = fixed.upper()

                def _is_name(tok: str) -> bool:
                    return bool(re.match(r"^[A-Za-z@#$][\w@#$]*$", tok or ""))

                # Normalize opcode token (drop extender like (E))
                op_base = re.sub(r"\(.*\)$", "", opcode).strip()
                if not op_base or not re.match(r"^[A-Z][A-Z0-9-]*$", op_base):
                    # regex scan for known ops
                    m_op = re.search(
                        r"\b(BEGSR|ENDSR|EXSR|CALLP?|CALLB|EVALR?|EXFMT|"
                        r"CHAIN|READE?|READPE?|WRITE|UPDATE|DELETE|SETLL|SETGT|"
                        r"MONITOR|RETURN|IF|WHEN|SELECT|FOR|DO[WU]?)\b",
                        up,
                    )
                    if m_op:
                        op_base = m_op.group(1).upper()
                    else:
                        op_base = ""

                if op_base == "BEGSR":
                    name = factor1
                    if not _is_name(name):
                        m = re.search(r"\bBEGSR\s+([A-Za-z@#$][\w@#$]*)", fixed, re.I)
                        if m:
                            name = m.group(1)
                        else:
                            m = re.search(
                                r"\b([A-Za-z@#$][\w@#$]*)\s+BEGSR\b", fixed, re.I
                            )
                            name = m.group(1) if m else ""
                    return ("subroutine", f"begsr {name}".strip())
                if op_base == "ENDSR":
                    return ("end_sr", "endsr")
                if op_base == "EXSR":
                    target = factor2 or factor1
                    if not _is_name(target):
                        m = re.search(r"\bEXSR\s+([A-Za-z@#$][\w@#$]*)", fixed, re.I)
                        target = m.group(1) if m else target
                    return ("exsr", f"exsr {target}".strip())
                if op_base == "MONITOR":
                    return ("monitor", "monitor")
                if op_base in self._C_INDEX_OPS:
                    # Compact calc entry for navigation
                    bits = [op_base]
                    if _is_name(factor1) and factor1.upper() not in ("C",):
                        bits.append(factor1)
                    if factor2:
                        f2s = re.sub(r"\s+", " ", factor2)
                        if len(f2s) > 24:
                            f2s = f2s[:21] + "..."
                        bits.append(f2s)
                    return ("calc", " ".join(bits))
                return None

            if st == "I":
                name = p[spec_i + 1 : spec_i + 15].strip()
                if name and not name.startswith("*"):
                    return ("input", f"I {name}")
                # record id / file level sometimes blank name
                rec = p[spec_i + 15 : spec_i + 25].strip()
                if rec:
                    return ("input", f"I {rec}")
                return None

            if st == "O":
                name = p[spec_i + 1 : spec_i + 15].strip()
                if name and not name.startswith("*"):
                    return ("output", f"O {name}")
                rec = p[spec_i + 15 : spec_i + 25].strip()
                if rec:
                    return ("output", f"O {rec}")
                return None

        return None

    def _parse(self) -> None:
        entries: list[dict[str, Any]] = []
        current_proc: dict[str, Any] | None = None
        current_ds: dict[str, Any] | None = None
        current_sr: dict[str, Any] | None = None
        # Detect free mode from whole file preamble
        head = "\n".join(self.lines[:30]).lower()
        if "**free" in head:
            self._free_mode = True

        for start_idx, end_idx, raw in self._logical_lines():
            defs = self._detect(raw)
            if not defs:
                continue
            for kind, label in defs:
                item: dict[str, Any] = {
                    "kind": kind,
                    "name": label,
                    "line": start_idx + 1,
                    "end_line": end_idx + 1,
                    "label": label,
                }

                if kind == "proc":
                    item["members"] = []
                    entries.append(item)
                    current_proc = item
                    current_ds = None
                    current_sr = None
                elif kind == "end_proc":
                    if current_proc is not None:
                        current_proc["end_line"] = end_idx + 1
                    # also close open sr/ds inside
                    if current_sr is not None:
                        current_sr["end_line"] = end_idx + 1
                        current_sr = None
                    if current_ds is not None:
                        current_ds["end_line"] = end_idx + 1
                        current_ds = None
                    entries.append(item)
                    current_proc = None
                elif kind == "ds":
                    item["members"] = []
                    self._add(entries, current_proc, item)
                    current_ds = item
                elif kind == "end_block":
                    if "ds" in label and current_ds is not None:
                        current_ds["end_line"] = end_idx + 1
                        current_ds = None
                    else:
                        # end-pi / end-pr: attach as marker under proc or top
                        self._add(entries, current_proc, item)
                elif kind == "subroutine":
                    item["members"] = []
                    self._add(entries, current_proc, item)
                    current_sr = item
                elif kind == "end_sr":
                    if current_sr is not None:
                        current_sr["end_line"] = end_idx + 1
                        current_sr = None
                    else:
                        self._add(entries, current_proc, item)
                elif (
                    kind in ("subf", "parm", "field", "const")
                    and current_ds is not None
                ):
                    current_ds.setdefault("members", []).append(item)
                elif kind in (
                    "file",
                    "def",
                    "field",
                    "const",
                    "pi",
                    "pr",
                    "ctl_opt",
                    "include",
                    "directive",
                    "monitor",
                    "end_monitor",
                    "exsr",
                    "input",
                    "output",
                    "parm",
                    "subf",
                    "sql",
                    "cond_compile",
                    "calc",
                ):
                    # Prefer nesting under subroutine if active for calc-like / sql
                    if current_sr is not None and kind in (
                        "exsr",
                        "monitor",
                        "end_monitor",
                        "sql",
                        "calc",
                    ):
                        current_sr.setdefault("members", []).append(item)
                    else:
                        self._add(entries, current_proc, item)
                else:
                    self._add(entries, current_proc, item)

        self._assign_end_lines(entries)
        self.entries = entries

    def _add(
        self,
        entries: list[dict[str, Any]],
        current_proc: dict[str, Any] | None,
        item: dict[str, Any],
    ) -> None:
        if current_proc is not None:
            current_proc.setdefault("members", []).append(item)
        else:
            entries.append(item)

    def _assign_end_lines(self, entries: list[dict]) -> None:
        for idx, e in enumerate(entries):
            if e.get("end_line", e["line"]) <= e["line"]:
                if idx + 1 < len(entries):
                    e["end_line"] = entries[idx + 1]["line"] - 1
                else:
                    e["end_line"] = len(self.lines)
            members = e.get("members", [])
            if members and e["kind"] in ("proc", "ds", "subroutine"):
                last = max(m.get("end_line", m["line"]) for m in members)
                if last > e["end_line"]:
                    e["end_line"] = last
            for midx, m in enumerate(members):
                if m.get("end_line", m["line"]) <= m["line"]:
                    if midx + 1 < len(members):
                        m["end_line"] = members[midx + 1]["line"] - 1
                    else:
                        m["end_line"] = e["end_line"]
                sub = m.get("members", [])
                for sidx, sm in enumerate(sub):
                    if sm.get("end_line", sm["line"]) <= sm["line"]:
                        if sidx + 1 < len(sub):
                            sm["end_line"] = sub[sidx + 1]["line"] - 1
                        else:
                            sm["end_line"] = m["end_line"]

    def _flatten(self) -> list[dict]:
        flat: list[dict] = []

        def walk(items: list[dict]) -> None:
            for e in items:
                flat.append(e)
                walk(e.get("members", []))

        walk(self.entries)
        return flat

    def build_index(self) -> str:
        if not self.entries:
            return _("msg.no_entries", default="(no definitions found)")
        lines_out: list[str] = []
        idx = 0

        def emit(e: dict, indent: int) -> None:
            nonlocal idx
            idx += 1
            # first level uses 2 spaces base like other tools
            if indent == 0:
                lines_out.append(f"  {idx}. L{e['line']} {e['label']}")
            else:
                lines_out.append(f"      {idx}. L{e['line']} {e['label']}")
            for m in e.get("members", []):
                # nested members of ds/sr under proc: still one indent level for simplicity
                emit_member(m, 1)

        def emit_member(e: dict, indent: int) -> None:
            nonlocal idx
            idx += 1
            lines_out.append(f"      {idx}. L{e['line']} {e['label']}")
            for m in e.get("members", []):
                idx += 1
                lines_out.append(f"          {idx}. L{m['line']} {m['label']}")

        for e in self.entries:
            emit(e, 0)
        return "\n".join(lines_out)

    def get_section(self, n: int) -> str | None:
        flat = self._flatten()
        if n < 1 or n > len(flat):
            return None
        e = flat[n - 1]
        start_0 = e["line"] - 1
        end_0 = e.get("end_line", e["line"])
        if end_0 > len(self.lines):
            end_0 = len(self.lines)
        code_lines = self.lines[start_0:end_0]
        while code_lines and not code_lines[-1].strip():
            code_lines.pop()
        return "\n".join(code_lines).rstrip("\n")

    def section_count(self) -> int:
        return len(self._flatten())


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
        builder = _RpgIndexBuilder(source, filepath=safe_path)
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
                "To retrieve a definition, call rpg2idx with mode='section' and the section number."
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
