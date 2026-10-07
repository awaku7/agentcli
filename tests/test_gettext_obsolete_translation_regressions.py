from __future__ import annotations

from pathlib import Path

LOCALES_DIR = Path(__file__).resolve().parents[1] / "src" / "uagent" / "locales"


def _unescape_po(value: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(value):
        ch = value[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue

        i += 1
        if i >= len(value):
            out.append("\\")
            break

        esc = value[i]
        i += 1
        if esc == "n":
            out.append("\n")
        elif esc == "t":
            out.append("\t")
        elif esc == "r":
            out.append("\r")
        elif esc == "\\":
            out.append("\\")
        elif esc == '"':
            out.append('"')
        else:
            out.append("\\" + esc)

    return "".join(out)


def _unquote_po(token: str) -> str:
    token = token.strip()
    if len(token) >= 2 and token[0] == '"' and token[-1] == '"':
        return token[1:-1]
    return token


def _parse_entries(text: str, *, obsolete: bool) -> dict[str, str]:
    messages: dict[str, str] = {}
    msgid: list[str] = []
    msgstr: list[str] = []
    in_msgid = False
    in_msgstr = False

    def commit() -> None:
        nonlocal msgid, msgstr, in_msgid, in_msgstr
        if msgid:
            messages["".join(msgid)] = "".join(msgstr)
        msgid = []
        msgstr = []
        in_msgid = False
        in_msgstr = False

    for raw in text.splitlines():
        if obsolete:
            if not raw.startswith("#~"):
                continue
            raw = raw[2:].lstrip()
        elif raw.startswith("#~"):
            continue

        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("msgid "):
            commit()
            in_msgid = True
            in_msgstr = False
            msgid.append(_unescape_po(_unquote_po(line[6:].strip())))
            continue

        if line.startswith("msgstr "):
            in_msgid = False
            in_msgstr = True
            msgstr.append(_unescape_po(_unquote_po(line[7:].strip())))
            continue

        if line.startswith('"') and line.endswith('"'):
            part = _unescape_po(_unquote_po(line))
            if in_msgid:
                msgid.append(part)
            elif in_msgstr:
                msgstr.append(part)

    commit()
    return messages


def test_active_translations_do_not_regress_to_msgid_when_obsolete_translation_exists():
    regressions: list[str] = []

    for po_path in sorted(LOCALES_DIR.glob("*/LC_MESSAGES/uag.po")):
        locale = po_path.parent.parent.name
        if locale == "en":
            continue

        text = po_path.read_text(encoding="utf-8")
        active = _parse_entries(text, obsolete=False)
        obsolete = _parse_entries(text, obsolete=True)

        for msgid, translated in active.items():
            old_translation = obsolete.get(msgid)
            if (
                msgid
                and translated == msgid
                and old_translation
                and old_translation != msgid
            ):
                regressions.append(f"{locale}: {msgid!r}")

    assert not regressions, (
        "Active translations regressed to the source msgid even though a translated "
        "obsolete entry still exists:\n" + "\n".join(regressions)
    )
