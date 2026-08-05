from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from .i18n_helper import make_tool_translator
from .index_tool_helpers import read_index_source, resolve_index_path

_ = make_tool_translator(__file__)

TOOL_SPEC = {
    "type": "function",
    "tool_genre": "index",
    "function": {
        "name": "dds2idx",
        "description": _(
            "tool.description",
            default=(
                "Parse an IBM i DDS source (PF/LF/DSPF/PRTF; .pf/.lf/.dspf/.prtf/.dds) into "
                "records, fields, keys, and file-level keywords, and return a numbered index "
                "or a specific definition section. Use this when you need to read a large DDS "
                "file: first call with mode='index', then mode='section'."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "read dds file",
                "physical file dds",
                "display file dspf",
                "logical file lf",
                "Read DDS",
                "PF/LF/DSPF definitions",
            ],
        ),
        "x_search_terms_en": [
            "read dds file",
            "physical file dds",
            "display file dspf",
            "logical file lf",
        ],
        "x_parallel_safe": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Path to the DDS (PF/LF/DSPF/PRTF) source file.",
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

# File-level keywords worth indexing on their own.
_FILE_KEYWORDS = {
    "UNIQUE",
    "REF",
    "ALTSEQ",
    "FCFO",
    "FIFO",
    "LIFO",
    "SHARE",
    "DLTPCT",
    "REUSEDLT",
    "CCSIDS",
    "CCSID",
    "IGNORE",
    "INCLUDE",
}

# Field/record-level keywords (not standalone index entries unless useful).
_FIELD_KW = {
    "TEXT",
    "COLHDG",
    "EDTCDE",
    "DSPATR",
    "CHECK",
    "VALUES",
    "RANGE",
    "COMP",
    "REFFLD",
    "ALIAS",
    "DATFMT",
    "TIMFMT",
    "VARLEN",
    "ALWNULL",
    "DFT",
    "CST",
    "EDTWRD",
    "DATSEP",
    "TIMSEP",
    "LOWER",
    "CHECKMSG",
    "ERRMSG",
    "MSGCON",
    "OVERLAY",
    "WINDOW",
    "KEEP",
    "ASSUME",
    "INVITE",
    "INDARA",
    "PRINT",
    "HELP",
    "HLPARA",
    "SFL",
    "SFLCTL",
    "SFLCLR",
    "SFLDSP",
    "SFLDSPCTL",
    "SFLSIZ",
    "SFLPAG",
    "CF01",
    "CF02",
    "CF03",
    "CF04",
    "CF05",
    "CF06",
    "CF07",
    "CF08",
    "CF09",
    "CF10",
    "CF11",
    "CF12",
    "CF13",
    "CF14",
    "CF15",
    "CF16",
    "CF17",
    "CF18",
    "CF19",
    "CF20",
    "CF21",
    "CF22",
    "CF23",
    "CF24",
    "CA01",
    "CA03",
    "ROLLUP",
    "ROLLDOWN",
    "HOME",
    "BLANKS",
    "CHANGE",
    "LOCK",
    "PROTECT",
    "DSPMOD",
    "WDWLOC",
    "WDWTITLE",
    "USRRSTDSP",
    "PUTOVR",
    "OVRDTA",
    "OVRATR",
    "CLRL",
    "ERASEINP",
    "INZINP",
    "KEEP",
    "BLINK",
    "CSRLOC",
    "RTNCSRLOC",
    "SPACEB",
    "SPACEA",
    "SKIPB",
    "SKIPA",
    "HIGHLIGHT",
    "UNDERLINE",
    "COLOR",
    "PAGEREC",
    "PAGSEG",
    "CHRSIZ",
    "FONT",
}

_LF_HINTS = ("PFILE(", "JFILE(", "JDFTVAL", "JDUPSEQ", "DYNSLT", "JOIN(")
_DSPF_HINTS = (
    "DSPATR",
    "CF0",
    "CA0",
    "SFLCTL",
    "SFLDSP",
    "OVERLAY",
    "WINDOW",
    "KEEP",
    "ASSUME",
    "INDARA",
)
_PRTF_HINTS = (
    "SPACEB",
    "SPACEA",
    "SKIPB",
    "SKIPA",
    "HIGHLIGHT",
    "UNDERLINE",
    "PAGEREC",
)

# DSPATR attribute codes (IBM i DDS)
_DSPATR_CODES = {
    "HI": "HI",  # high intensity
    "RI": "RI",  # reverse image
    "UL": "UL",  # underline
    "BL": "BL",  # blink
    "CS": "CS",  # column separator
    "ND": "ND",  # non-display
    "PC": "PC",  # position cursor
    "PR": "PR",  # protect
    "MDT": "MDT",  # set MDT on
    "OID": "OID",  # operator ID
    "SP": "SP",  # suppress input
}
# COLOR keyword values
_COLOR_CODES = {
    "BLU": "BLU",
    "GRN": "GRN",
    "PNK": "PNK",
    "RED": "RED",
    "TRQ": "TRQ",
    "WHT": "WHT",
    "YLW": "YLW",
}


def _decode_dspatr_arg(arg: str) -> str:
    """Expand DSPATR(...) body into normalized attribute tokens.

    Accepts space/comma-separated codes; unknown tokens kept as-is (upper).
    Example: 'HI UL ND' -> 'HI UL ND'; 'hi,ri' -> 'HI RI'
    """
    raw = (arg or "").strip()
    if not raw:
        return ""
    parts = re.split(r"[\s,]+", raw.upper())
    out: list[str] = []
    for p in parts:
        p = p.strip("() ")
        if not p:
            continue
        if p in _DSPATR_CODES:
            out.append(_DSPATR_CODES[p])
        else:
            out.append(p)
    return " ".join(out)


def _decode_color_arg(arg: str) -> str:
    raw = (arg or "").strip().upper()
    if not raw:
        return ""
    parts = re.split(r"[\s,]+", raw)
    out: list[str] = []
    for p in parts:
        p = p.strip("() ")
        if not p:
            continue
        out.append(_COLOR_CODES.get(p, p))
    return " ".join(out)


def _format_keyword_detail(name: str, arg: str) -> str:
    """Return keyword label with decoded DSPATR/COLOR/CFxx detail."""
    n = (name or "").upper()
    a = (arg or "").strip()
    # strip outer parens from arg if present
    inner = a
    if inner.startswith("(") and inner.endswith(")"):
        inner = inner[1:-1].strip()

    if n == "DSPATR":
        decoded = _decode_dspatr_arg(inner)
        return f"DSPATR({decoded})" if decoded else "DSPATR"
    if n == "COLOR":
        decoded = _decode_color_arg(inner)
        return f"COLOR({decoded})" if decoded else "COLOR"
    # CFnn / CAnn response indicator: CF03(03 'Exit') or CF03(03)
    m = re.match(r"^(CF|CA)(\d{2})$", n)
    if m:
        if inner:
            # keep indicator + optional text, compress
            inner_c = re.sub(r"\s+", " ", inner)
            if len(inner_c) > 28:
                inner_c = inner_c[:25] + "..."
            return f"{n}({inner_c})"
        return n
    # SFL* with args
    if n.startswith("SFL") and inner:
        inner_c = re.sub(r"\s+", " ", inner)
        if len(inner_c) > 20:
            inner_c = inner_c[:17] + "..."
        return f"{n}({inner_c})"
    if a:
        if a.startswith("("):
            return f"{n}{a}"
        return f"{n}({inner})" if inner else n
    return n


def _parse_cond_indicators(text: str) -> str:
    """Parse conditioning indicator area into normalized form like '01 N02 50'.

    Accepts SEU cols content or free-form 'N01' / '01 02' / 'N01N02'.
    """
    if not text:
        return ""
    s = text.upper().replace(",", " ")
    # Insert spaces between glued tokens: N01N02 -> N01 N02, 0102 -> 01 02
    s = re.sub(r"(N?\d{2})(?=N?\d{2})", r"\1 ", s)
    s = re.sub(r"\s+", " ", s).strip()
    tokens = []
    for tok in s.split():
        if re.fullmatch(r"N?\d{2}", tok):
            tokens.append(tok)
    return " ".join(tokens)


class _DdsIndexBuilder:
    """Fixed-column-aware IBM i DDS source indexer (v2).

    Improvements:
    - SEU fixed-column primary parse (name/len/type/decimal/keyword areas)
    - free-format / spaced export fallback
    - DSPF constants, indicators, SFLCTL markers
    - field keyword attachment (TEXT/COLHDG/DSPATR) on prior field\n    - DSPF conditioning indicators + DSPATR/COLOR/CFxx full decode
    - better file type detection
    - REF / REFFLD simple follow within workdir (depth-limited)
    """

    _REF_EXTS = (".pf", ".lf", ".dds", ".PF", ".LF", ".DDS", ".dspf", ".prtf")
    _MAX_REF_DEPTH = 1

    def __init__(
        self,
        source: str,
        filepath: str = "",
        *,
        follow_ref: bool = True,
        _ref_depth: int = 0,
        _ref_stack: set[str] | None = None,
    ):
        self.source = source
        self.filepath = filepath
        self.lines = source.split("\n")
        self.file_type = self._guess_file_type()
        self.entries: list[dict[str, Any]] = []
        self.ref_notes: list[str] = []
        self._follow_ref = follow_ref
        self._ref_depth = _ref_depth
        self._ref_stack = set(_ref_stack or ())
        if filepath:
            try:
                self._ref_stack.add(str(Path(filepath).resolve()))
            except Exception:
                self._ref_stack.add(str(filepath))
        self._parse()
        if self._follow_ref and self._ref_depth < self._MAX_REF_DEPTH:
            self._apply_ref_follow()

    def _guess_file_type(self) -> str:
        ext = os.path.splitext(self.filepath)[1].lower()
        ext_map = {
            ".pf": "PF",
            ".lf": "LF",
            ".dspf": "DSPF",
            ".prtf": "PRTF",
            ".dds": "",
        }
        if ext in ext_map and ext_map[ext]:
            return ext_map[ext]

        joined = "\n".join(self.lines).upper()
        scores = {"PF": 0, "LF": 0, "DSPF": 0, "PRTF": 0}
        for h in _PRTF_HINTS:
            if h in joined:
                scores["PRTF"] += 2
        for h in _DSPF_HINTS:
            if h in joined:
                scores["DSPF"] += 2
        for h in _LF_HINTS:
            if h in joined:
                scores["LF"] += 2
        if re.search(r"\bPFILE\s*\(", joined):
            scores["LF"] += 3
        if re.search(r"\bUNIQUE\b", joined):
            scores["PF"] += 1
        # bare S/O select-omit lines
        if re.search(r"^\s*A?\s*[SO]\s+[A-Z@#]", joined, re.M):
            scores["LF"] += 2
        best = max(scores, key=scores.get)
        if scores[best] <= 0:
            return "PF"
        return best

    def _strip_sequence(self, line: str) -> str:
        """Drop leading 5–6 digit sequence numbers if present."""
        m = re.match(r"^(\d{5,6})([ *A].*)$", line)
        if m:
            return m.group(2)
        return line

    def _pad(self, s: str, width: int = 80) -> str:
        if len(s) >= width:
            return s
        return s + (" " * (width - len(s)))

    def _is_comment(self, line: str) -> bool:
        s = self._strip_sequence(line).rstrip("\n")
        stripped = s.lstrip()
        if not stripped:
            return True
        if stripped.startswith("*") or stripped.upper().startswith("A*"):
            return True
        # Fixed: form type at col 6 (1-based) / index 5, comment * at col 7 / index 6
        # After sequence strip, form often at index 0.
        if len(s) >= 2 and s[0] in "Aa" and s[1] == "*":
            return True
        if len(s) >= 7 and s[6] == "*" and s[5] in "Aa ":
            return True
        return False

    def _seu_slice(self, line: str) -> dict[str, str] | None:
        """Extract SEU-style fixed columns.

        Classic SEU (1-based, with 6-digit sequence still present):
          1-5 seq, 6 form(A), 7 comment/cond, 8-16 name? (varies)
        Common text export WITHOUT sequence (0-based after strip):
          0: A (form)
          1: condition / comment area start
          Name: cols 19-28 in full SEU = indices 18:28 with seq,
                without seq often 12:22 or spaces-aligned free form.

        We try multiple layouts and score them.
        """
        raw = line.rstrip("\n")
        if not raw.strip() or self._is_comment(line):
            return None

        candidates: list[dict[str, Any]] = []

        def try_layout(
            src: str,
            form_i: int,
            name_s: int,
            name_e: int,
            ref_i: int,
            len_s: int,
            len_e: int,
            type_i: int,
            dec_s: int,
            dec_e: int,
            kw_s: int,
            tag: str,
            cond_s: int = -1,
            cond_e: int = -1,
        ) -> None:
            p = self._pad(src, max(kw_s + 20, 80))
            form = p[form_i : form_i + 1].upper()
            if form not in ("A", " ", ""):
                # allow missing form on free lines
                if form_i == 0 and form not in ("A", " "):
                    return
            name = p[name_s:name_e].strip()
            ref = p[ref_i : ref_i + 1].strip().upper() if ref_i >= 0 else ""
            length = p[len_s:len_e].strip()
            typ = p[type_i : type_i + 1].strip().upper() if type_i >= 0 else ""
            dec = p[dec_s:dec_e].strip() if dec_s >= 0 else ""
            kw = p[kw_s:].strip()
            cond_raw = ""
            if cond_s >= 0 and cond_e > cond_s:
                cond_raw = p[cond_s:cond_e]
            cond = _parse_cond_indicators(cond_raw)
            score = 0
            if form == "A":
                score += 1
            if name and re.match(r"^[A-Za-z@#$RJKSO][\w@#$]*$", name):
                score += 3
            if length.isdigit():
                score += 2
            if typ and typ in "ASPBFLOZTHGE":
                score += 2
            if kw:
                score += 1
            if ref in ("R", "K", "J", "S", "O", ""):
                score += 1
            if cond:
                score += 1
            candidates.append(
                {
                    "score": score,
                    "form": form,
                    "name": name,
                    "ref": ref,
                    "length": length,
                    "type": typ,
                    "dec": dec,
                    "keyword": kw,
                    "cond": cond,
                    "tag": tag,
                    "src": src,
                }
            )

        # With 6-digit sequence still on line (classic SEU 1-based cols)
        # cond indicators: cols 7-16 -> index 6:16 with form at 5
        try_layout(raw, 5, 18, 28, 16, 29, 34, 34, 35, 37, 44, "seu+seq", 6, 16)
        # Sequence stripped already
        s = self._strip_sequence(raw)
        # form at 0, cond 1:11 (cols 7-16 of SEU without seq offset)
        try_layout(s, 0, 12, 22, 10, 23, 28, 28, 29, 31, 38, "seu-noseq", 1, 11)
        try_layout(s, 0, 7, 17, 5, 18, 23, 23, 24, 26, 32, "compact", 1, 7)
        # Free-ish: name early after A
        try_layout(s, 0, 2, 12, 1, 13, 18, 18, 19, 21, 25, "loose", -1, -1)

        if not candidates:
            return None
        best = max(candidates, key=lambda c: c["score"])
        if best["score"] < 3:
            return None
        return best

    def _spec_body(self, line: str) -> str:
        """Return free-form body for regex fallback."""
        s = self._strip_sequence(line).rstrip("\n")
        if not s.strip():
            return ""
        stripped = s.lstrip()
        if stripped.upper().startswith("A ") or stripped.upper() == "A":
            return stripped[1:].strip()
        if len(s) >= 1 and s[0] in ("A", "a") and (len(s) == 1 or s[1] in " \t"):
            return s[1:].strip()
        m = re.match(r"^A\s+(.*)$", s.strip(), re.I)
        if m:
            return m.group(1).strip()
        return s.strip()

    def _detect_line(self, line: str) -> list[tuple[str, str, dict[str, str]]]:
        """Return list of (kind, label, meta)."""
        if self._is_comment(line):
            return []

        seu = self._seu_slice(line)
        body = self._spec_body(line)

        # Prefer structured detection from body tokens (works for free format)
        results = self._detect_from_body(body, line)
        if results:
            return results

        # SEU fixed-column driven detection
        if seu and seu.get("name"):
            name = seu["name"].upper()
            ref = (seu.get("ref") or "").upper()
            length = re.sub(r"[^\d]", "", seu.get("length") or "")
            typ = (seu.get("type") or "").upper()
            dec = re.sub(r"[^\d]", "", seu.get("dec") or "")
            kw = (seu.get("keyword") or "").strip()
            # Reject form-type letter misread as name on constant/keyword lines
            if (
                name in {"A", "R"}
                and not length
                and not typ
                and not dec
                and (
                    re.search(r"['\"]", kw)
                    or re.match(r"^\d{1,3}\s+\d{1,3}", kw)
                    or (kw.upper().split("(")[0] in _FIELD_KW)
                )
            ):
                name = ""

            # Record: name starts with R as type indicator in name area sometimes "R CUST"
            # Or ref/name area holds R
            if (
                name == "R"
                or ref == "R"
                or re.match(r"^R\s+\w", body.upper() if body else "")
            ):
                # handled by body usually
                pass

            if ref == "R":
                meta_r: dict[str, str] = {"ref_field": "1"}
                km = re.search(r"REFFLD\(([^)]*)\)", kw.upper()) if kw else None
                if km:
                    meta_r["reffld"] = km.group(1).strip()
                label_r = f"{name} R" if name else "R"
                return [("field", label_r, meta_r)]

            if (
                name.startswith("R")
                and length == ""
                and typ == ""
                and " " not in name
                and len(name) > 1
                and name[0] == "R"
            ):
                # ambiguous record-like name; body path usually handles real records
                pass

            if ref == "K" or name.startswith("K") and len(name) > 1 and not length:
                # key field name might be in keyword or name
                key_name = (
                    name if ref != "K" else (name or kw.split()[0] if kw else name)
                )
                if ref == "K":
                    key_name = name or (kw.split()[0] if kw else "")
                    if key_name:
                        return [("key", f"K {key_name}", {"keyword": kw})]

            if ref in ("S", "O"):
                fld = name or (kw.split()[0] if kw else "")
                if fld:
                    return [("select_omit", f"{ref} {fld}", {"keyword": kw})]

            if ref == "J":
                return [("join", f"J {name or kw[:20]}".strip(), {"keyword": kw})]

            cond = (seu.get("cond") or "").strip()

            # Keyword-only line with optional conditioning indicators
            if name and name in _FIELD_KW:
                arg = ""
                if kw:
                    rest_kw = kw
                    if rest_kw.upper().startswith(name):
                        rest_kw = rest_kw[len(name) :].strip()
                    if rest_kw.startswith("("):
                        pm = re.match(r"^(\([^)]*\))", rest_kw)
                        arg = pm.group(1) if pm else rest_kw
                    elif rest_kw:
                        arg = f"({rest_kw})" if not rest_kw.startswith("(") else rest_kw
                detail = _format_keyword_detail(name, arg)
                meta_k: dict[str, str] = {"attach": "1", "keyword": detail}
                if cond:
                    meta_k["cond"] = cond
                    detail = f"[{cond}] {detail}"
                if name == "REFFLD":
                    rm = re.search(r"REFFLD\(([^)]*)\)", detail.upper())
                    if rm:
                        meta_k["reffld"] = rm.group(1).strip()
                return [("keyword", detail, meta_k)]

            # Field with length/type
            if (
                name
                and re.match(r"^[A-Z@#$][\w@#$]*$", name)
                and name not in _FILE_KEYWORDS
            ):
                parts = [name]
                type_part = f"{length}{typ}" if (length or typ) else ""
                if dec and typ:
                    type_part = f"{length}{typ}{dec}"
                elif dec and length:
                    type_part = f"{length} {dec}"
                if type_part:
                    parts.append(type_part)
                meta = {"keyword": kw, "length": length, "type": typ, "dec": dec}
                if cond:
                    meta["cond"] = cond
                    parts.insert(0, f"[{cond}]")
                if kw:
                    km = re.match(r"([A-Z][\w@#$]*)(\([^)]*\))?", kw.upper())
                    if km:
                        parts.append(
                            _format_keyword_detail(km.group(1), km.group(2) or "")
                        )
                return [("field", " ".join(parts), meta)]

        # Indicator-only SEU line (cond present, no usable name)
        if seu:
            cond2 = (seu.get("cond") or "").strip()
            kw2 = (seu.get("keyword") or "").strip()
            name2 = (seu.get("name") or "").strip()
            if cond2 and not name2 and self.file_type == "DSPF":
                kw_detail = ""
                if kw2:
                    km = re.match(r"([A-Z][\w@#$]*)(\([^)]*\))?", kw2.upper())
                    if km:
                        kw_detail = " " + _format_keyword_detail(
                            km.group(1), km.group(2) or ""
                        )
                return [
                    (
                        "indicator",
                        f"[{cond2}]{kw_detail}".strip(),
                        {"cond": cond2, "keyword": kw2},
                    )
                ]

        return []

    def _detect_from_body(
        self, body: str, raw_line: str
    ) -> list[tuple[str, str, dict[str, str]]]:
        if not body:
            return []
        upper = body.upper()

        # Record format: R NAME ...
        m = re.match(r"^R\s+([A-Z@#$][\w@#$]*)\b(.*)$", upper)
        if m:
            name = m.group(1)
            extra = ""
            for key in (
                "PFILE",
                "JFILE",
                "FORMAT",
                "SFLCTL",
                "SFL",
                "TEXT",
                "OVERLAY",
                "WINDOW",
            ):
                km = re.search(rf"{key}\(([^)]*)\)", upper)
                if km:
                    extra = f" {key}({km.group(1).strip()})"
                    break
            if not extra:
                rest = m.group(2).strip()
                if rest:
                    tok = rest.split()[0]
                    if tok in (
                        "SFLCTL",
                        "SFL",
                        "SFLMSG",
                        "SUBFILE",
                        "OVERLAY",
                        "WINDOW",
                    ):
                        extra = f" {tok}"
            return [("record", f"R {name}{extra}", {})]

        # Key: K NAME
        m = re.match(r"^K\s+([A-Z@#$][\w@#$]*)\b", upper)
        if m:
            return [("key", f"K {m.group(1)}", {})]

        # Select / Omit
        m = re.match(r"^([SO])\s+([A-Z@#$][\w@#$]*)\b", upper)
        if m:
            return [("select_omit", f"{m.group(1)} {m.group(2)}", {})]

        # Join
        m = re.match(r"^J\b(.*)$", upper)
        if m:
            jfile = re.search(r"JFILE\(([^)]*)\)", upper)
            if jfile:
                return [("join", f"J JFILE({jfile.group(1).strip()})", {})]
            rest = m.group(1).strip()
            if rest:
                return [("join", f"J {rest.split()[0]}", {})]
            return [("join", "J", {})]

        # File-level keyword
        m = re.match(r"^([A-Z][\w@#$]*)\b(.*)$", upper)
        if m:
            kw = m.group(1)
            rest = m.group(2).strip()
            if kw in _FILE_KEYWORDS:
                if rest.startswith("("):
                    pm = re.match(r"^(\([^)]*\))", rest)
                    arg = pm.group(1) if pm else ""
                    return [("file_keyword", f"{kw}{arg}", {})]
                return [("file_keyword", kw, {})]

        # DSPF constant / layout:  row col 'text'   or   'text'
        # DDS often packs col against quote:  5  2'Name'  (no space before quote)
        body_s = body.strip()
        m = re.match(
            r"^(?:(\d{1,3})\s+(\d{1,3})\s*)?(['\"])([^'\"]*)\3",
            body_s,
        )
        if m and (m.group(1) or body_s[:1] in "'\""):
            row, col, text = m.group(1), m.group(2), m.group(4)
            if row and col:
                label = f"{row},{col} const '{self._short(text, 20)}'"
            else:
                # only count as layout if looks like constant line (no field name)
                if not re.match(r"^[A-Z@#$][\w@#$]*\s+\d", upper):
                    label = f"const '{self._short(text, 20)}'"
                else:
                    label = ""
            if label:
                return [("layout", label, {})]

        # Indicator-only / conditioned keyword line (DSPF)
        # e.g. "N01" / "01 02" / "50 DSPATR(HI)" / "N03 CF03(03)"
        m = re.match(
            r"^((?:N?\d{2}\s*){1,3})(?:\s+([A-Z][\w@#$]*)(\([^)]*\))?(.*))?$",
            upper.strip(),
        )
        if m and self.file_type == "DSPF":
            cond = _parse_cond_indicators(m.group(1))
            if cond and not re.match(r"^[A-Z@#$][\w@#$]*\s+\d", upper.strip()):
                kw_name = (m.group(2) or "").strip()
                kw_arg = (m.group(3) or "").strip()
                if kw_name and (
                    kw_name in _FIELD_KW
                    or kw_name in _FILE_KEYWORDS
                    or re.match(r"^(CF|CA)\d{2}$", kw_name)
                ):
                    detail = _format_keyword_detail(kw_name, kw_arg)
                    return [
                        (
                            "keyword",
                            f"[{cond}] {detail}",
                            {"attach": "1", "cond": cond, "keyword": detail},
                        )
                    ]
                if not kw_name:
                    return [("indicator", f"[{cond}]", {"cond": cond})]

        # Leading conditioning indicators before field/keyword:
        # "01 FIELD 10A" or "N01N02 DSPATR(HI UL)"
        m_cond = re.match(r"^((?:N?\d{2}){1,3})\s+(.*)$", upper.strip())
        leading_cond = ""
        body_work = upper
        body_orig = body
        if m_cond:
            maybe = _parse_cond_indicators(m_cond.group(1))
            rest = m_cond.group(2).strip()
            if maybe and rest and re.match(r"^[A-Z@#$']", rest):
                leading_cond = maybe
                body_work = rest
                bm = re.match(r"^((?:N?\d{2}){1,3})\s+(.*)$", body.strip(), re.I)
                if bm:
                    body_orig = bm.group(2)

        # Field: NAME [len][type][decimals] [keywords]
        # Reference field: NAME R [REFFLD(...)]  (R is not a DDS data type)
        m_ref = re.match(
            r"^([A-Z@#$][\w@#$]*)\b\s+R\b(?:\s+(.*))?$",
            body_work,
        )
        if m_ref:
            name = m_ref.group(1)
            if name not in _FILE_KEYWORDS and name not in _FIELD_KW:
                rest = (m_ref.group(2) or "").strip()
                meta: dict[str, str] = {"ref_field": "1"}
                rm = re.search(r"REFFLD\(([^)]*)\)", rest)
                if rm:
                    meta["reffld"] = rm.group(1).strip()
                label = f"{name} R"
                if leading_cond:
                    meta["cond"] = leading_cond
                    label = f"[{leading_cond}] {label}"
                return [("field", label, meta)]

        m = re.match(
            r"^([A-Z@#$][\w@#$]*)\b(?:\s+(\d{1,5}))?(?:\s*([ASPBFLOZTHGE]))?(?:\s+(\d{1,2}))?\b(.*)$",
            body_work,
        )
        if m:
            name = m.group(1)
            if name in _FILE_KEYWORDS or name in _FIELD_KW:
                # keyword continuation — attach to previous field in parse
                rest = m.group(5).strip() if m.lastindex and m.lastindex >= 5 else ""
                arg = ""
                if rest.startswith("("):
                    pm = re.match(r"^(\([^)]*\))", rest)
                    arg = pm.group(1) if pm else rest[:20]
                detail = _format_keyword_detail(name, arg)
                meta_kw: dict[str, str] = {"attach": "1", "keyword": detail}
                if leading_cond:
                    meta_kw["cond"] = leading_cond
                    detail = f"[{leading_cond}] {detail}"
                if name == "REFFLD" and arg:
                    meta_kw["reffld"] = arg.strip("()")
                elif name == "REF" and arg:
                    meta_kw["ref_file"] = arg.strip("()")
                return [("keyword", detail, meta_kw)]
            length = m.group(2) or ""
            typ = m.group(3) or ""
            dec = m.group(4) or ""
            rest = (m.group(5) or "").strip()
            parts: list[str] = []
            if leading_cond:
                parts.append(f"[{leading_cond}]")
            parts.append(name)
            type_part = f"{length}{typ}"
            if dec:
                type_part = f"{type_part}{dec}" if typ else f"{length} {dec}"
            if type_part:
                parts.append(type_part)
            meta_f: dict[str, str] = {}
            if leading_cond:
                meta_f["cond"] = leading_cond
            rm = re.search(r"REFFLD\(([^)]*)\)", rest)
            if rm:
                meta_f["reffld"] = rm.group(1).strip()
                meta_f["ref_field"] = "1"
            # inline DSPATR/COLOR on field line
            for kwn in ("DSPATR", "COLOR", "CHECK", "VALUES", "RANGE"):
                km = re.search(rf"{kwn}\(([^)]*)\)", rest)
                if km:
                    parts.append(_format_keyword_detail(kwn, f"({km.group(1)})"))
            # constant on same line as named field
            src_for_quote = body_orig
            if "'" in src_for_quote or '"' in src_for_quote:
                cm = re.search(r"['\"]([^'\"]*)['\"]", src_for_quote)
                if cm and not length and not typ:
                    parts = ([f"[{leading_cond}]"] if leading_cond else []) + [
                        name,
                        "const",
                    ]
            # bare name with no type may still be a reference field
            if not length and not typ and not dec:
                if re.search(r"\bR\b", rest) or rm:
                    meta_f["ref_field"] = "1"
                    if " R" not in " ".join(parts):
                        base = [name, "R"]
                        parts = ([f"[{leading_cond}]"] if leading_cond else []) + base
            return [("field", " ".join(parts), meta_f)]

        return []

    @staticmethod
    def _short(text: str, n: int) -> str:
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) <= n:
            return text
        return text[: n - 3] + "..."

    def _parse(self) -> None:
        entries: list[dict[str, Any]] = []
        current_record: dict[str, Any] | None = None
        last_field: dict[str, Any] | None = None

        for i, raw in enumerate(self.lines):
            defs = self._detect_line(raw)
            if not defs:
                continue
            for kind, label, meta in defs:
                item: dict[str, Any] = {
                    "kind": kind,
                    "name": label,
                    "line": i + 1,
                    "end_line": i + 1,
                    "label": label,
                    "meta": dict(meta) if meta else {},
                }
                if kind == "record":
                    item["members"] = []
                    entries.append(item)
                    current_record = item
                    last_field = None
                elif kind == "file_keyword":
                    # Capture REF(file) target on the entry meta
                    rm = re.match(r"^REF\(([^)]*)\)$", label.upper())
                    if rm:
                        item["meta"]["ref_file"] = rm.group(1).strip()
                    elif label.upper() == "REF":
                        item["meta"]["ref_file"] = ""
                    entries.append(item)
                    last_field = None
                elif kind == "keyword":
                    # Attach decoded keyword summary to previous field/record label
                    # label may be "DSPATR(HI UL)" or "[01] DSPATR(HI)" etc.
                    attach_text = (meta.get("keyword") or label or "").strip()
                    # Prefer full label (includes cond prefix) when present
                    if label and label not in (attach_text,):
                        attach_text = label
                    # Token used for de-dup / REFFLD detection
                    bare = re.sub(r"^\[[^\]]+\]\s*", "", attach_text).strip()
                    kw = bare.split("(")[0].split()[0] if bare else ""
                    if last_field is not None:
                        if attach_text and attach_text not in last_field["label"]:
                            # avoid duplicate bare keyword name when detail already there
                            if not (
                                kw
                                and kw in last_field["label"]
                                and "(" not in attach_text
                            ):
                                last_field["label"] = (
                                    f"{last_field['label']} {attach_text}"
                                )
                                last_field["end_line"] = i + 1
                        if meta.get("cond"):
                            last_field.setdefault("meta", {})["cond"] = meta["cond"]
                        if meta.get("reffld"):
                            last_field.setdefault("meta", {})["reffld"] = meta["reffld"]
                            last_field["meta"]["ref_field"] = "1"
                        if kw == "REFFLD" and not meta.get("reffld"):
                            rm2 = re.search(r"REFFLD\(([^)]*)\)", attach_text.upper())
                            if rm2:
                                last_field.setdefault("meta", {})["reffld"] = rm2.group(
                                    1
                                ).strip()
                                last_field["meta"]["ref_field"] = "1"
                        # stash dspatr detail on meta for consumers
                        if kw == "DSPATR":
                            dm = re.search(r"DSPATR\(([^)]*)\)", attach_text.upper())
                            if dm:
                                last_field.setdefault("meta", {})["dspatr"] = dm.group(
                                    1
                                ).strip()
                        if kw == "COLOR":
                            cm = re.search(r"COLOR\(([^)]*)\)", attach_text.upper())
                            if cm:
                                last_field.setdefault("meta", {})["color"] = cm.group(
                                    1
                                ).strip()
                    elif current_record is not None:
                        # record-level keyword (CF keys, SFLDSP, conditioned DSPATR, ...)
                        if attach_text and attach_text not in current_record["label"]:
                            if not (
                                kw
                                and kw in current_record["label"]
                                and "(" not in attach_text
                            ):
                                current_record["label"] = (
                                    f"{current_record['label']} {attach_text}"
                                )
                                current_record["end_line"] = i + 1
                        if meta.get("cond"):
                            current_record.setdefault("meta", {}).setdefault(
                                "conds", []
                            )
                    else:
                        # orphan keyword at file level — keep as entry for CF/INDARA etc.
                        entries.append(item)
                    # do not add as separate entry when attached (reduces noise)
                elif current_record is not None and kind in (
                    "field",
                    "key",
                    "select_omit",
                    "join",
                    "indicator",
                    "layout",
                ):
                    current_record.setdefault("members", []).append(item)
                    if kind == "field":
                        last_field = item
                    else:
                        last_field = None
                else:
                    entries.append(item)
                    if kind == "field":
                        last_field = item
                    else:
                        last_field = None

        self._assign_end_lines(entries)
        self.entries = entries

    def _assign_end_lines(self, entries: list[dict]) -> None:
        for idx, e in enumerate(entries):
            if idx + 1 < len(entries):
                e["end_line"] = max(e["end_line"], entries[idx + 1]["line"] - 1)
            else:
                e["end_line"] = max(e["end_line"], len(self.lines))
            members = e.get("members", [])
            for midx, m in enumerate(members):
                if midx + 1 < len(members):
                    m["end_line"] = max(m["end_line"], members[midx + 1]["line"] - 1)
                else:
                    m["end_line"] = max(m["end_line"], e["end_line"])

    # --- REF / REFFLD follow (workdir-local, depth-limited) -----------------

    @staticmethod
    def _normalize_ref_name(raw: str) -> str:
        """Strip library qualifier and quotes: LIB/FILE or 'FILE' -> FILE."""
        s = (raw or "").strip().strip("\"'")
        if not s:
            return ""
        # LIB/FILE or LIB.FILE
        if "/" in s:
            s = s.split("/")[-1]
        if "." in s and not s.upper().endswith(
            (".PF", ".LF", ".DDS", ".DSPF", ".PRTF")
        ):
            # object.member style — take last segment as file-ish name
            parts = s.split(".")
            s = parts[-1]
        return s.strip()

    def _base_dir(self) -> Path:
        if self.filepath:
            return Path(self.filepath).resolve().parent
        return Path(os.getcwd()).resolve()

    def _resolve_ref_path(self, ref_name: str) -> str | None:
        """Locate REF target source under workdir. Same-dir first, then shallow walk."""
        name = self._normalize_ref_name(ref_name)
        if not name:
            return None
        base = self._base_dir()
        workdir = Path(os.getcwd()).resolve()
        candidates: list[Path] = []

        # Exact / extension variants next to the source file
        stem = Path(name).stem if Path(name).suffix else name
        for ext in ("",) + self._REF_EXTS:
            if ext:
                candidates.append(base / f"{stem}{ext}")
                candidates.append(base / f"{stem}{ext.lower()}")
                candidates.append(base / f"{stem}{ext.upper()}")
            else:
                candidates.append(base / stem)
                candidates.append(base / name)

        # Direct child match (case-insensitive) in same directory
        try:
            for p in base.iterdir():
                if not p.is_file():
                    continue
                if p.stem.upper() == stem.upper() and p.suffix.lower() in {
                    "",
                    ".pf",
                    ".lf",
                    ".dds",
                    ".dspf",
                    ".prtf",
                }:
                    candidates.append(p)
        except OSError:
            pass

        # Shallow workdir walk (depth 3) for same stem
        try:
            root = workdir
            max_depth = 3
            root_len = len(root.parts)
            for dirpath, dirnames, filenames in os.walk(root):
                rel_parts = Path(dirpath).resolve().parts
                depth = len(rel_parts) - root_len
                if depth >= max_depth:
                    dirnames[:] = []
                    continue
                # skip heavy/irrelevant dirs
                dirnames[:] = [
                    d
                    for d in dirnames
                    if d
                    not in {
                        ".git",
                        ".venv",
                        "venv",
                        "node_modules",
                        "__pycache__",
                        ".tox",
                        "dist",
                        "build",
                    }
                    and not d.startswith(".")
                ]
                for fn in filenames:
                    fp = Path(dirpath) / fn
                    if fp.stem.upper() == stem.upper() and fp.suffix.lower() in {
                        ".pf",
                        ".lf",
                        ".dds",
                        ".dspf",
                        ".prtf",
                        "",
                    }:
                        candidates.append(fp)
        except OSError:
            pass

        seen: set[str] = set()
        for c in candidates:
            try:
                resolved = str(c.resolve())
            except OSError:
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            if not os.path.isfile(resolved):
                continue
            # must stay in workdir
            try:
                resolve_index_path(resolved)
            except Exception:
                continue
            if resolved in self._ref_stack:
                continue
            return resolved
        return None

    def _load_ref_builder(self, path: str) -> _DdsIndexBuilder | None:
        try:
            src = read_index_source(path)
            return _DdsIndexBuilder(
                src,
                filepath=path,
                follow_ref=True,
                _ref_depth=self._ref_depth + 1,
                _ref_stack=self._ref_stack,
            )
        except Exception:
            return None

    def _field_map(self, builder: _DdsIndexBuilder) -> dict[str, dict[str, Any]]:
        """Map FIELDNAME -> entry for fields in a builder."""
        out: dict[str, dict[str, Any]] = {}
        for e in builder.entries:
            if e.get("kind") == "field":
                key = self._field_key(e.get("label", ""))
                if key:
                    out.setdefault(key, e)
            for m in e.get("members", []):
                if m.get("kind") == "field":
                    key = self._field_key(m.get("label", ""))
                    if key:
                        out.setdefault(key, m)
        return out

    @staticmethod
    def _field_key(label: str) -> str:
        if not label:
            return ""
        tok = label.strip().split()[0]
        return tok.upper()

    @staticmethod
    def _field_type_summary(label: str) -> str:
        """Extract type tokens from a field label like 'CUSTID 10A' or 'BALANCE 9P2'."""
        parts = label.strip().split()
        if len(parts) <= 1:
            return ""
        # drop leading name; keep type-ish tokens until a pure keyword
        skip = {
            "R",
            "TEXT",
            "COLHDG",
            "REFFLD",
            "EDTCDE",
            "DSPATR",
            "ALIAS",
            "VARLEN",
            "ALWNULL",
            "DFT",
        }
        kept: list[str] = []
        for p in parts[1:]:
            pu = p.upper()
            if pu in skip or pu.startswith("REFFLD(") or pu.startswith("TEXT("):
                break
            if (
                re.match(r"^\d+[ASPBFLOZTHGE]\d*$", pu)
                or re.match(r"^\d+$", pu)
                or re.match(r"^[ASPBFLOZTHGE]\d*$", pu)
            ):
                kept.append(p)
            elif kept:
                break
            else:
                # unknown token before type — stop
                break
        return " ".join(kept)

    def _collect_default_ref_file(self) -> str:
        for e in self.entries:
            if e.get("kind") == "file_keyword":
                meta = e.get("meta") or {}
                if "ref_file" in meta and meta.get("ref_file"):
                    return str(meta["ref_file"])
                lab = e.get("label", "")
                rm = re.match(r"^REF\(([^)]*)\)$", lab.upper())
                if rm:
                    return rm.group(1).strip()
        return ""

    def _parse_reffld_arg(self, raw: str) -> tuple[str, str]:
        """Return (field_name, optional_file_name) from REFFLD arg."""
        s = (raw or "").strip()
        if not s:
            return "", ""
        # REFFLD(field) or REFFLD(field FILE) or REFFLD(FILE/field) variants
        s = s.strip("\"'")
        if "/" in s and " " not in s:
            # FILE/FIELD or LIB/FILE/FIELD — last is field, previous is file
            parts = [p for p in s.split("/") if p]
            if len(parts) >= 2:
                return parts[-1].strip(), parts[-2].strip()
        bits = s.split()
        if len(bits) == 1:
            return bits[0], ""
        # field file  OR  file field — prefer first as field (IBM docs: REFFLD(name [file]))
        return bits[0], bits[1]

    def _apply_ref_follow(self) -> None:
        default_ref = self._collect_default_ref_file()
        cache: dict[str, _DdsIndexBuilder | None] = {}
        resolved_paths: dict[str, str | None] = {}

        def get_builder(ref_name: str) -> tuple[str | None, _DdsIndexBuilder | None]:
            key = self._normalize_ref_name(ref_name).upper()
            if not key:
                return None, None
            if key not in resolved_paths:
                resolved_paths[key] = self._resolve_ref_path(ref_name)
            path = resolved_paths[key]
            if path is None:
                cache[key] = None
                return None, None
            if key not in cache:
                cache[key] = self._load_ref_builder(path)
            return path, cache[key]

        # Annotate REF(...) file_keyword entries
        if default_ref:
            path, bld = get_builder(default_ref)
            for e in self.entries:
                if e.get("kind") != "file_keyword":
                    continue
                lab = e.get("label", "")
                if not lab.upper().startswith("REF"):
                    continue
                if path and bld is not None:
                    rel = path
                    try:
                        rel = str(
                            Path(path)
                            .resolve()
                            .relative_to(Path(os.getcwd()).resolve())
                        )
                    except Exception:
                        rel = os.path.basename(path)
                    e["label"] = f"{lab} -> {rel}"
                    e["meta"]["ref_resolved"] = path
                    n_fields = sum(
                        1
                        for x in bld.entries
                        for y in ([x] + x.get("members", []))
                        if y.get("kind") == "field"
                    )
                    self.ref_notes.append(
                        f"REF({self._normalize_ref_name(default_ref)}) -> {rel} ({n_fields} fields)"
                    )
                else:
                    e["label"] = f"{lab} [not found]"
                    self.ref_notes.append(
                        f"REF({self._normalize_ref_name(default_ref)}) [not found]"
                    )

        # Annotate reference fields
        for e in self.entries:
            members = e.get("members") or []
            # walk record members; also top-level field entries
            targets = list(members)
            if e.get("kind") == "field":
                targets.append(e)
            for m in targets:
                if m.get("kind") != "field":
                    continue
                meta = m.setdefault("meta", {})
                reffld = meta.get("reffld", "")
                is_ref = meta.get("ref_field") == "1" or bool(reffld)
                label = m.get("label", "")
                # also treat typeless non-const fields as possible refs when file has REF
                if not is_ref and default_ref:
                    summary = self._field_type_summary(label)
                    if not summary and " const" not in f" {label.lower()} ":
                        # typeless field under REF file — try same-name lookup
                        is_ref = True
                        meta["ref_field"] = "1"
                if not is_ref:
                    continue

                field_name = self._field_key(label)
                ref_file = default_ref
                src_field = field_name
                if reffld:
                    src_field, alt_file = self._parse_reffld_arg(reffld)
                    src_field = src_field.upper() or field_name
                    if alt_file:
                        ref_file = alt_file
                if not ref_file:
                    continue
                path, bld = get_builder(ref_file)
                if not path or bld is None:
                    if "[ref?" not in m["label"]:
                        m["label"] = (
                            f"{m['label']} [ref? {self._normalize_ref_name(ref_file)}]"
                        )
                    continue
                fmap = self._field_map(bld)
                src = fmap.get(src_field.upper())
                if not src:
                    m["label"] = (
                        f"{m['label']} [ref {self._normalize_ref_name(ref_file)}."
                        f"{src_field} missing]"
                    )
                    continue
                type_sum = self._field_type_summary(src.get("label", ""))
                ref_tag = self._normalize_ref_name(ref_file)
                rel = os.path.basename(path)
                if type_sum:
                    # Avoid duplicating type if already present
                    if type_sum.upper() not in m["label"].upper():
                        # Insert type after name / R marker
                        parts = m["label"].split()
                        # name [R] [existing...]
                        head: list[str] = []
                        if parts:
                            head.append(parts[0])
                            rest = parts[1:]
                        else:
                            rest = []
                        if rest and rest[0].upper() == "R":
                            head.append(rest[0])
                            rest = rest[1:]
                        head.append(type_sum)
                        head.append(f"<= {ref_tag}.{src_field}")
                        # keep useful trailing keywords (TEXT etc.) but drop bare R dup
                        for tok in rest:
                            if tok.upper() == "R":
                                continue
                            if tok.upper().startswith("REFFLD"):
                                continue
                            head.append(tok)
                        m["label"] = " ".join(head)
                    else:
                        if f"<= {ref_tag}." not in m["label"]:
                            m["label"] = f"{m['label']} <= {ref_tag}.{src_field}"
                else:
                    if f"<= {ref_tag}." not in m["label"]:
                        m["label"] = f"{m['label']} <= {ref_tag}.{src_field}"
                meta["ref_resolved"] = path
                meta["ref_source_field"] = src_field
                meta["ref_type"] = type_sum

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
        if self.ref_notes:
            lines_out.append("  ---")
            lines_out.append("  REF follow:")
            for note in self.ref_notes:
                lines_out.append(f"    - {note}")
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
        builder = _DdsIndexBuilder(source, filepath=safe_path)
    except Exception as e:
        return _("err.parse_error", default="Error parsing file: {e}", e=str(e))

    if mode == "index":
        toc = builder.build_index()
        total = builder.section_count()
        type_hint = f" ({builder.file_type})" if builder.file_type else ""
        return _(
            "msg.index_output",
            default=(
                "Index for: {path}{type_hint}\n"
                "---\n"
                "{toc}\n"
                "---\n"
                "Total definitions: {total}\n"
                "To retrieve a definition, call dds2idx with mode='section' and the section number."
            ),
            path=path,
            type_hint=type_hint,
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
