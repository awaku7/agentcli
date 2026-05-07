from __future__ import annotations

from pathlib import Path

from polib import POEntry, POFile, pofile

ROOT = Path(__file__).resolve().parents[1]
POT_PATH = ROOT / "src" / "uagent" / "locales" / "uagent.pot"
PO_PATH = ROOT / "src" / "uagent" / "locales" / "en" / "LC_MESSAGES" / "uag.po"


def main() -> None:
    pot = pofile(str(POT_PATH))
    new_po = POFile()
    new_po.metadata = pot.metadata.copy()

    for entry in pot:
        new_po.append(
            POEntry(
                msgid=entry.msgid,
                msgstr=entry.msgid if entry.msgid else "",
            )
        )

    new_po.save(str(PO_PATH))
    print(f"WROTE: {PO_PATH}")


if __name__ == "__main__":
    main()
