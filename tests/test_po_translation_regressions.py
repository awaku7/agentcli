from __future__ import annotations

import ast
from pathlib import Path


LOCALES_DIR = Path(__file__).resolve().parents[1] / "src" / "uagent" / "locales"
INTENTIONAL_ACTIVE_ENGLISH = {"[display_reasoning] %(state)s"}


def _decode_po_entries(path: Path, *, obsolete: bool) -> dict[str, str]:
    entries: dict[str, str] = {}
    msgid: list[str] = []
    msgstr: list[str] = []
    field: str | None = None

    def commit() -> None:
        nonlocal msgid, msgstr, field
        if msgid:
            entries["".join(msgid)] = "".join(msgstr)
        msgid = []
        msgstr = []
        field = None

    for raw in path.read_text(encoding="utf-8").splitlines():
        is_obsolete = raw.startswith("#~ ")
        if obsolete:
            if not is_obsolete:
                continue
            raw = raw[3:]
        elif is_obsolete or raw.startswith("#"):
            continue

        line = raw.strip()
        if line.startswith("msgid "):
            commit()
            field = "msgid"
            msgid.append(ast.literal_eval(line[6:].strip()))
        elif line.startswith("msgstr "):
            field = "msgstr"
            msgstr.append(ast.literal_eval(line[7:].strip()))
        elif line.startswith('"') and line.endswith('"'):
            value = ast.literal_eval(line)
            if field == "msgid":
                msgid.append(value)
            elif field == "msgstr":
                msgstr.append(value)

    commit()
    return entries


def test_active_translation_does_not_regress_to_obsolete_english_fallback() -> None:
    regressions: list[str] = []

    for po_path in sorted(LOCALES_DIR.glob("*/LC_MESSAGES/uag.po")):
        active = _decode_po_entries(po_path, obsolete=False)
        obsolete = _decode_po_entries(po_path, obsolete=True)

        for msgid, msgstr in active.items():
            old_translation = obsolete.get(msgid)
            if (
                msgid
                and msgstr == msgid
                and old_translation
                and old_translation != msgid
                and msgid not in INTENTIONAL_ACTIVE_ENGLISH
            ):
                regressions.append(f"{po_path.parent.parent.name}: {msgid!r}")

    assert not regressions, (
        "Active translations must not fall back to English when the same msgid "
        "still has a translated obsolete entry: " + ", ".join(regressions)
    )
