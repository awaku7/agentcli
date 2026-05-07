#!/usr/bin/env python
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from polib import POEntry, POFile, pofile

from po_qc_summary import _has_expected_script, _is_ascii_only, _is_key_like, parse_po_entries

ROOT = Path(__file__).resolve().parents[1]
LOCALES_DIR = ROOT / "src" / "uagent" / "locales"
POT_PATH = LOCALES_DIR / "uagent.pot"
EN_PO_PATH = LOCALES_DIR / "en" / "LC_MESSAGES" / "uag.po"


def _backup_path(po_path: Path) -> Path:
    base = po_path.name + ".org"
    candidate = po_path.with_name(base)
    if not candidate.exists():
        return candidate
    idx = 1
    while True:
        candidate = po_path.with_name(f"{po_path.name}.org{idx}")
        if not candidate.exists():
            return candidate
        idx += 1


def _load_po(po_path: Path) -> POFile:
    return pofile(str(po_path))


def _build_new_po(pot: POFile, old_po: POFile) -> POFile:
    new_po = POFile()
    new_po.metadata = pot.metadata.copy()

    for entry in pot:
        new_entry = POEntry(
            msgid=entry.msgid,
            msgstr="" if not entry.msgid else "",
            msgctxt=entry.msgctxt,
            msgid_plural=entry.msgid_plural,
        )

        old_entry = old_po.find(entry.msgid, msgctxt=entry.msgctxt)
        if old_entry is not None:
            new_entry.msgstr = old_entry.msgstr
            if getattr(old_entry, "msgstr_plural", None):
                new_entry.msgstr_plural = old_entry.msgstr_plural.copy()
            new_entry.flags = list(old_entry.flags)
            new_entry.comment = old_entry.comment
            new_entry.tcomment = old_entry.tcomment
            new_entry.occurrences = list(entry.occurrences)

        if not entry.msgid:
            new_entry.msgstr = ""

        new_po.append(new_entry)

    return new_po


def _load_en_map() -> dict[str, str]:
    en_map: dict[str, str] = {}
    if not EN_PO_PATH.exists():
        return en_map
    for e in parse_po_entries(EN_PO_PATH):
        mid = str(e["msgid"])
        if mid:
            en_map[mid] = str(e["msgstr"])
    return en_map


def _qc_report(po_path: Path) -> dict[str, int]:
    locale = po_path.parts[po_path.parts.index("locales") + 1]
    en_map = _load_en_map()
    entries = parse_po_entries(po_path)

    counts = {
        "entries": 0,
        "empty": 0,
        "fuzzy": 0,
        "same_as_en": 0,
        "ascii_nonkey": 0,
        "no_expected_script": 0,
        "same_as_msgid": 0,
    }

    for e in entries:
        mid = str(e["msgid"])
        mst = str(e["msgstr"])
        if mid == "":
            continue

        counts["entries"] += 1
        cmts = "\n".join(str(x) for x in e["comments"])

        if mst == "":
            counts["empty"] += 1
        if "fuzzy" in cmts:
            counts["fuzzy"] += 1
        if mst == mid and mst != "":
            counts["same_as_msgid"] += 1
        if locale != "en":
            if mst and en_map.get(mid) == mst:
                counts["same_as_en"] += 1
            if mst and (not _has_expected_script(locale, mst)):
                counts["no_expected_script"] += 1
            if mst and _is_ascii_only(mst) and (not _is_key_like(mst)):
                counts["ascii_nonkey"] += 1

    return counts


def rebuild_one(po_path: Path) -> dict[str, int]:
    if not po_path.exists():
        raise FileNotFoundError(po_path)
    if not POT_PATH.exists():
        raise FileNotFoundError(POT_PATH)

    backup = _backup_path(po_path)
    shutil.copy2(po_path, backup)

    pot = _load_po(POT_PATH)
    old_po = _load_po(backup)
    new_po = _build_new_po(pot, old_po)
    new_po.save(str(po_path))

    return _qc_report(po_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Rebuild one non-en .po file from POT while preserving existing translations and writing a QC summary."
    )
    parser.add_argument("po_path", help="Path to the locale .po file")
    args = parser.parse_args(argv)

    po_path = Path(args.po_path).resolve()
    counts = rebuild_one(po_path)

    print(f"WROTE: {po_path}")
    print(
        "QC: "
        + ", ".join(
            [
                f"entries={counts['entries']}",
                f"empty={counts['empty']}",
                f"fuzzy={counts['fuzzy']}",
                f"same_as_en={counts['same_as_en']}",
                f"ascii_nonkey={counts['ascii_nonkey']}",
                f"no_expected_script={counts['no_expected_script']}",
                f"same_as_msgid={counts['same_as_msgid']}",
            ]
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
