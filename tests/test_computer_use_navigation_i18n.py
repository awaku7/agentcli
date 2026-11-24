"""Computer Use direct-navigation results are localized, not hard-coded."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

LOCALES_DIR = Path(__file__).resolve().parents[1] / "src" / "uagent" / "locales"
FAIL_MSGID = "Could not open the browser: %(diagnostic)s"
OK_MSGID = "Opened the browser."


def _entries(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    msgid: list[str] = []
    msgstr: list[str] = []
    field: str | None = None
    for raw in path.read_text(encoding="utf-8").splitlines() + ['msgid ""']:
        line = raw.strip()
        if line.startswith("#"):
            continue
        if line.startswith("msgid "):
            if msgid:
                entries["".join(msgid)] = "".join(msgstr)
            msgid, msgstr, field = [ast.literal_eval(line[6:])], [], "msgid"
        elif line.startswith("msgstr "):
            msgstr, field = [ast.literal_eval(line[7:])], "msgstr"
        elif line.startswith('"') and field == "msgid":
            msgid.append(ast.literal_eval(line))
        elif line.startswith('"') and field == "msgstr":
            msgstr.append(ast.literal_eval(line))
    return entries


LOCALES = sorted(
    p.name for p in LOCALES_DIR.iterdir() if (p / "LC_MESSAGES" / "uag.po").exists()
)


@pytest.mark.parametrize("lang", LOCALES)
def test_every_locale_translates_navigation_results(lang: str) -> None:
    entries = _entries(LOCALES_DIR / lang / "LC_MESSAGES" / "uag.po")
    assert entries.get(OK_MSGID)
    assert "%(diagnostic)s" in entries.get(FAIL_MSGID, "")
    if lang != "en":
        assert entries[OK_MSGID] != OK_MSGID


def test_pot_declares_navigation_msgids() -> None:
    pot = _entries(LOCALES_DIR / "uagent.pot")
    assert OK_MSGID in pot and FAIL_MSGID in pot


@pytest.mark.parametrize(
    ("lang", "ok", "fail"),
    [
        ("en", "Opened the browser.", "Could not open the browser: boom"),
        ("ja", "ブラウザーを開きました。", "ブラウザーを開けませんでした: boom"),
    ],
)
def test_runtime_returns_localized_navigation_results(
    lang: str, ok: str, fail: str
) -> None:
    from uagent import i18n

    previous = i18n.get_thread_lang()
    i18n.set_thread_lang(lang)
    try:
        assert i18n._(OK_MSGID) == ok
        assert i18n._(FAIL_MSGID) % {"diagnostic": "boom"} == fail
    finally:
        i18n.set_thread_lang(previous)


def test_direct_navigation_has_no_hard_coded_japanese() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "src" / "uagent" / "uagent_llm.py"
    ).read_text(encoding="utf-8")
    assert "ブラウザーを開" not in source
