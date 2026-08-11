"""Normalize the existing Norwegian translations to Nynorsk (nn).

This is intentionally offline and deterministic: it keeps placeholders and
technical tokens untouched while applying reviewed Bokmål -> Nynorsk forms.
It is a reproducible first pass for the host PO and tool JSON catalogues.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# Longer phrases first. Keep this list conservative: command names, URLs,
# placeholders, and product names must remain unchanged.
REPLACEMENTS = {
    "ikke tilgjengelig": "ikkje tilgjengeleg",
    "ikke funnet": "ikkje funnen",
    "ikke konfigurert": "ikkje konfigurert",
    "kan ikke": "kan ikkje",
    "kunne ikke": "kunne ikkje",
    "vil ikke": "vil ikkje",
    "hvis du": "viss du",
    "i stedet for": "i staden for",
    "tilgjengelig": "tilgjengeleg",
    "tilgjengelige": "tilgjengelege",
    "nødvendig": "naudsynt",
    "nødvendige": "naudsynte",
    "vellykket": "vellukka",
    "mislyktes": "mislukkast",
    "mislykket": "mislukka",
    "konfigurasjon": "konfigurasjon",
    "Konfigurasjon": "Konfigurasjon",
    "bruker": "brukar",
    "Bruker": "Brukar",
    "brukere": "brukarar",
    "Brukere": "Brukarar",
    "brukes": "vert brukt",
    "Brukes": "Vert brukt",
    "bruk": "bruk",
    "navn": "namn",
    "Navn": "Namn",
    "melding": "melding",
    "meldinger": "meldingar",
    "feil": "feil",
    "ukjent": "ukjend",
    "Ukjent": "Ukjend",
    "hendelse": "hending",
    "hendelser": "hendingar",
    "hendelsestype": "hendingstype",
    "installere": "installere",
    "installerer": "installerer",
    "installert": "installert",
    "oppdatering": "oppdatering",
    "oppdatert": "oppdatert",
    "starter": "startar",
    "Starter": "Startar",
    "starte": "starte",
    "avslutning": "avslutting",
    "Avslutning": "Avslutting",
    "mottatt": "motteke",
    "Mottatt": "Motteke",
    "flerlinjesvar": "flerlinjesvar",
    "spørsmål": "spørsmål",
    "svar": "svar",
    "eller": "eller",
    "uten": "utan",
    "Uten": "Utan",
    "fra": "frå",
    "Fra": "Frå",
    "også": "òg",
    "Også": "Òg",
    "bare": "berre",
    "Bare": "Berre",
    "nå": "no",
    "Nå": "No",
    "hvordan": "korleis",
    "Hvordan": "Korleis",
    "hva": "kva",
    "Hva": "Kva",
    "hvor": "kvar",
    "Hvor": "Kvar",
    "hvilken": "kva",
    "Hvilken": "Kva",
    "dette": "dette",
    "disse": "desse",
    "Denne": "Denne",
    "før": "før",
    "etter": "etter",
    "sammen": "saman",
    "Sammen": "Saman",
    "gjennom": "gjennom",
    "tilbake": "tilbake",
    "innstillinger": "innstillingar",
    "Innstillinger": "Innstillingar",
    "språk": "språk",
    "Språk": "Språk",
    "filbane": "filbane",
    "filbaner": "filbaner",
    "mappe": "mappe",
    "mapper": "mapper",
    "lese": "lese",
    "skrive": "skrive",
    "velg": "vel",
    "Velg": "Vel",
}


# Word boundaries prevent changing technical identifiers such as --force.
def translate_text(text: str) -> str:
    for source, target in sorted(REPLACEMENTS.items(), key=lambda item: -len(item[0])):
        text = re.sub(rf"(?<![\w-]){re.escape(source)}(?![\w-])", target, text)
    return text


def update_po(path: Path) -> int:
    import polib

    po = polib.pofile(str(path))
    changed = 0
    for entry in po:
        if entry.msgstr:
            new = translate_text(entry.msgstr)
            if new != entry.msgstr:
                entry.msgstr = new
                changed += 1
    po.metadata["Language"] = "nn"
    po.save(str(path))
    return changed


def update_json(root: Path) -> int:
    changed = 0
    for path in sorted(root.glob("*_tool.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        block = data.get("nn")
        if not isinstance(block, dict):
            continue

        def walk(value):
            nonlocal changed
            if isinstance(value, str):
                new = translate_text(value)
                changed += new != value
                return new
            if isinstance(value, list):
                return [walk(item) for item in value]
            if isinstance(value, dict):
                return {key: walk(item) for key, item in value.items()}
            return value

        data["nn"] = walk(block)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return changed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--po", type=Path, default=Path("src/uagent/locales/nn/LC_MESSAGES/uag.po")
    )
    parser.add_argument("--tools", type=Path, default=Path("src/uagent/tools"))
    args = parser.parse_args()
    print(f"PO changed entries: {update_po(args.po)}")
    print(f"Tool strings changed: {update_json(args.tools)}")


if __name__ == "__main__":
    main()
