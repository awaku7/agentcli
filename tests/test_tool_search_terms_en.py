import json
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1] / "src" / "uagent" / "tools"
DISCORD_CHANNEL_I18N = TOOLS_DIR / "discord_channel_tool.json"
DISCORD_BRAND_SEARCH_TERM_INDEXES = (0, 1, 3, 5, 7, 9)


def test_localized_search_terms_have_english_fallback() -> None:
    missing = []
    for path in sorted(TOOLS_DIR.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if '"x_search_terms": _(' in text and '"x_search_terms_en"' not in text:
            missing.append(path.name)

    assert not missing, (
        "Tools with localized x_search_terms must also define "
        'function["x_search_terms_en"]: ' + ", ".join(missing)
    )


def test_discord_search_terms_preserve_brand_name() -> None:
    payload = json.loads(DISCORD_CHANNEL_I18N.read_text(encoding="utf-8"))
    invalid = []

    for locale, messages in sorted(payload.items()):
        terms = messages.get("x_search_terms")
        if not isinstance(terms, list):
            invalid.append(f"{locale}: x_search_terms is not a list")
            continue

        for index in DISCORD_BRAND_SEARCH_TERM_INDEXES:
            if index >= len(terms):
                invalid.append(f"{locale}: x_search_terms[{index}] is missing")
                continue

            term = str(terms[index])
            normalized = term.lower()
            padded = f" {normalized} "
            if not any(
                marker in padded
                for marker in (
                    " discord ",
                    " discord-",
                    "-discord ",
                    " discord_",
                    "_discord ",
                )
            ):
                invalid.append(f"{locale}[{index}]={term!r}")

    assert not invalid, (
        "Discord brand name must remain literal in brand-specific localized "
        "search terms: " + ", ".join(invalid)
    )
