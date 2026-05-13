#!/usr/bin/env python
"""QC summary for gettext .po files.

Usage:
  python scripts/po_qc_summary.py

Scans:
  src/uagent/locales/*/LC_MESSAGES/*.po

Writes:
  outputs/i18n/po_qc_summary.tsv
  outputs/i18n/{locale}_po_qc.txt

Notes:
- Supports plural fallback for malformed PO entries.
- Supports multiline msgid/msgstr.
- Counts plural forms (msgid_plural/msgstr[n]) correctly and ignores msgctxt.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def _force_utf8_stdio() -> None:
    # Avoid UnicodeEncodeError on Windows terminals (cp932 etc.)
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            try:
                s.reconfigure(encoding="utf-8", errors="backslashreplace")
            except Exception:
                pass


_force_utf8_stdio()

ROOT = Path(__file__).resolve().parents[1]
LOCALES_DIR = ROOT / "src" / "uagent" / "locales"
OUT_DIR = ROOT / "outputs" / "i18n"

KEY_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")

JA_RE = re.compile(r"[\u3040-\u30FF\u4E00-\u9FFF]")
ZH_RE = re.compile(r"[\u4E00-\u9FFF]")
KO_RE = re.compile(r"[\uAC00-\uD7AF]")
TH_RE = re.compile(r"[\u0E00-\u0E7F]")

PYFMT_RE = re.compile(r"%\([^)]+\)[a-zA-Z]")


def _unquote_po(token: str) -> str:
    t = (token or "").strip()
    if len(t) >= 2 and t[0] == '"' and t[-1] == '"':
        t = t[1:-1]
    return (
        t.replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace("\\r", "\r")
        .replace("\\\\", "\\")
        .replace('\\"', '"')
    )


def _is_key_like(s: str) -> bool:
    return bool(KEY_RE.fullmatch(s))


def _is_ascii_only(s: str) -> bool:
    try:
        s.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def _has_expected_script(locale: str, s: str) -> bool:
    if locale == "ja":
        return bool(JA_RE.search(s))
    if locale in ("zh_CN", "zh_TW"):
        return bool(ZH_RE.search(s))
    if locale == "ko":
        return bool(KO_RE.search(s))
    if locale == "th":
        return bool(TH_RE.search(s))
    return True


def parse_po_entries(po_path: Path) -> list[dict[str, object]]:
    """Parse .po file into entries.

    Returns list of dicts with:
      {comments: [str], msgid: str, msgstr: str, msgstrs: [str], plural: bool, flags: [str]}

    - Supports multiline msgid/msgstr.
    - Supports plural forms.
    - Treats plain msgstr as fallback for malformed plural entries that lack msgstr[n].
    - Skips msgctxt blocks.
    """

    lines = po_path.read_text(encoding="utf-8", errors="replace").splitlines()

    entries: list[dict[str, object]] = []
    comments: list[str] = []

    msgid: str | None = None
    msgstr: str | None = None
    plural = False
    plural_msgstrs: dict[int, str] = {}
    state: str | None = None  # 'id' | 'str' | 'plural_str'
    plural_current_idx: int | None = None

    def flush() -> None:
        nonlocal comments, msgid, msgstr, plural, plural_msgstrs, state, plural_current_idx
        if msgid is None:
            comments = []
            msgstr = None
            plural = False
            plural_msgstrs = {}
            state = None
            plural_current_idx = None
            return

        if plural:
            if plural_msgstrs:
                msgstrs = [plural_msgstrs[i] for i in sorted(plural_msgstrs)]
                msgstr_out = " | ".join(s for s in msgstrs if s)
            else:
                msgstrs = [msgstr] if msgstr else []
                msgstr_out = msgstr or ""
        else:
            msgstrs = []
            msgstr_out = msgstr or ""

        entries.append(
            {
                "comments": comments[:],
                "msgid": msgid or "",
                "msgstr": msgstr_out,
                "msgstrs": msgstrs,
                "plural": plural,
                "flags": [c[3:].strip() for c in comments if c.startswith("#, ")],
            }
        )

        comments = []
        msgid = None
        msgstr = None
        plural = False
        plural_msgstrs = {}
        state = None
        plural_current_idx = None

    i = 0
    while i < len(lines):
        line = lines[i]

        if not line.strip():
            flush()
            i += 1
            continue

        if line.startswith("#"):
            comments.append(line)
            i += 1
            continue

        if line.startswith("msgctxt "):
            i += 1
            while i < len(lines) and lines[i].lstrip().startswith('"'):
                i += 1
            continue

        if line.startswith("msgid "):
            flush()
            msgid = _unquote_po(line[len("msgid ") :])
            state = "id"
            i += 1
            while i < len(lines) and lines[i].lstrip().startswith('"'):
                msgid += _unquote_po(lines[i])
                i += 1
            continue

        if line.startswith("msgid_plural "):
            plural = True
            plural_msgstrs = {}
            plural_current_idx = None
            i += 1
            while i < len(lines) and lines[i].lstrip().startswith('"'):
                i += 1
            continue

        if line.startswith("msgstr"):
            if line.startswith("msgstr["):
                m = re.match(r"msgstr\[(\d+)\]\s+(.*)$", line)
                if not m:
                    i += 1
                    continue
                plural = True
                idx = int(m.group(1))
                val = _unquote_po(m.group(2))
                plural_msgstrs[idx] = val
                plural_current_idx = idx
                state = "plural_str"
                i += 1
                while i < len(lines) and lines[i].lstrip().startswith('"'):
                    if plural_current_idx is not None:
                        plural_msgstrs[plural_current_idx] += _unquote_po(lines[i])
                    i += 1
                continue

            msgstr = _unquote_po(line[len("msgstr ") :])
            state = "str"
            i += 1
            while i < len(lines) and lines[i].lstrip().startswith('"'):
                msgstr += _unquote_po(lines[i])
                i += 1
            continue

        if line.lstrip().startswith('"') and line.rstrip().endswith('"'):
            part = _unquote_po(line)
            if state == "id" and msgid is not None:
                msgid += part
            elif state == "str" and msgstr is not None:
                msgstr += part
            elif state == "plural_str" and plural_current_idx is not None:
                plural_msgstrs[plural_current_idx] = (
                    plural_msgstrs.get(plural_current_idx, "") + part
                )
            i += 1
            continue

        i += 1

    flush()
    return entries


def main() -> int:
    if not LOCALES_DIR.exists():
        print(f"ERROR: locales dir not found: {LOCALES_DIR}", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    po_paths = sorted(LOCALES_DIR.glob("*/LC_MESSAGES/*.po"))
    if not po_paths:
        print(f"ERROR: no .po files found under: {LOCALES_DIR}", file=sys.stderr)
        return 1

    # Load EN map for same_as_en check
    en_map: dict[str, str] = {}
    en_po = LOCALES_DIR / "en" / "LC_MESSAGES" / "uag.po"
    if en_po.exists():
        for e in parse_po_entries(en_po):
            mid = str(e["msgid"])
            if mid:
                en_map[mid] = str(e["msgstr"])

    reports: dict[str, dict[str, object]] = {}

    for po in po_paths:
        locale = po.parts[po.parts.index("locales") + 1]
        entries = parse_po_entries(po)

        problems = {
            "empty": [],
            "fuzzy": [],
            "same_as_en": [],
            "ascii_nonkey": [],
            "no_expected_script": [],
            "same_as_msgid": [],
        }

        for e in entries:
            mid = str(e["msgid"])
            if mid == "":
                # header
                continue

            flags = {str(x) for x in e.get("flags", [])}
            plural = bool(e.get("plural"))
            msgstrs = [str(x) for x in e.get("msgstrs", [])]
            mst = " | ".join(s for s in msgstrs if s) if plural else str(e["msgstr"])

            if plural:
                has_any_translation = any(s for s in msgstrs)
            else:
                has_any_translation = mst != ""

            if not has_any_translation:
                problems["empty"].append(mid)
            if "fuzzy" in flags:
                problems["fuzzy"].append(mid)
            if mst == mid and mst != "":
                problems["same_as_msgid"].append(mid)

            if locale != "en":
                if mst and (not _has_expected_script(locale, mst)):
                    problems["no_expected_script"].append(mid)

                if mst and _is_ascii_only(mst) and (not _is_key_like(mst)):
                    problems["ascii_nonkey"].append(mid)

                en_str = en_map.get(mid)
                if (
                    mst
                    and en_str
                    and mst == en_str
                    and mst != mid
                    and (not _is_key_like(mst))
                ):
                    problems["same_as_en"].append(mid)

            _ = PYFMT_RE.findall(mid)

        reports[locale] = {
            "po": str(po.relative_to(ROOT)),
            "total_entries": sum(1 for e in entries if str(e["msgid"]) != ""),
            "counts": {k: len(v) for k, v in problems.items()},
            "problems": problems,
        }

    # Write per-locale detailed files
    for loc, rep in reports.items():
        lines: list[str] = []
        lines.append(f"locale: {loc}")
        lines.append(f"po: {rep['po']}")
        lines.append(f"entries: {rep['total_entries']}")
        lines.append("")
        for cat in [
            "empty",
            "fuzzy",
            "same_as_en",
            "ascii_nonkey",
            "no_expected_script",
            "same_as_msgid",
        ]:
            lines.append(f"[{cat}] count={rep['counts'][cat]}")
            for mid in rep["problems"][cat]:
                lines.append(mid)
            lines.append("")
        (OUT_DIR / f"{loc}_po_qc.txt").write_text(
            "\n".join(lines).rstrip() + "\n", encoding="utf-8"
        )

    # Write summary TSV
    header = "locale\tentries\tempty\tfuzzy\tsame_as_en\tascii_nonkey\tno_expected_script\tsame_as_msgid\tpo"
    summary_lines = [header]
    for loc in sorted(reports.keys()):
        c = reports[loc]["counts"]
        summary_lines.append(
            "\t".join(
                [
                    loc,
                    str(reports[loc]["total_entries"]),
                    str(c["empty"]),
                    str(c["fuzzy"]),
                    str(c["same_as_en"]),
                    str(c["ascii_nonkey"]),
                    str(c["no_expected_script"]),
                    str(c["same_as_msgid"]),
                    str(reports[loc]["po"]),
                ]
            )
        )

    out_path = OUT_DIR / "po_qc_summary.tsv"
    out_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    # Print summary path and table
    print(f"WROTE: {out_path.relative_to(ROOT)}")
    print("\n".join(summary_lines))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
