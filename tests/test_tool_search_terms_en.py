import json
import re
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1] / "src" / "uagent" / "tools"
DISCORD_CHANNEL_I18N = TOOLS_DIR / "discord_channel_tool.json"
DISCORD_BRAND_SEARCH_TERM_INDEXES = (0, 1, 3, 5, 7, 9)
BLUESKY_I18N = TOOLS_DIR / "bluesky_tool.json"
BLUESKY_BRAND_SEARCH_TERMS = {
    0: "bluesky",
    1: "bsky",
    5: "bluesky",
    9: "bluesky",
}


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
            if (
                re.search(
                    r"(^|[^a-z])discord($|[^a-z])",
                    term,
                    flags=re.IGNORECASE,
                )
                is None
            ):
                invalid.append(f"{locale}[{index}]={term!r}")

    assert not invalid, (
        "Discord brand name must remain literal in brand-specific localized "
        "search terms: " + ", ".join(invalid)
    )


def test_sidecar_search_terms_are_wired_into_tool_spec() -> None:
    missing = []

    for json_path in sorted(TOOLS_DIR.rglob("*.json")):
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        if not isinstance(payload, dict):
            continue

        has_localized_search_terms = any(
            isinstance(messages, dict) and "x_search_terms" in messages
            for messages in payload.values()
        )
        if not has_localized_search_terms:
            continue

        python_path = json_path.with_suffix(".py")
        if not python_path.exists():
            continue

        candidate_sources = [python_path]
        stem = json_path.stem
        base_name = stem[:-5] if stem.endswith("_tool") else stem
        impl_dir = json_path.parent / f"{base_name}_impl"
        if impl_dir.is_dir():
            candidate_sources.extend(sorted(impl_dir.rglob("*.py")))

        if not any(
            '"x_search_terms": _(' in source_path.read_text(encoding="utf-8")
            for source_path in candidate_sources
        ):
            missing.append(python_path.name)

    assert not missing, (
        "Tool sidecars with localized x_search_terms must wire them into "
        'TOOL_SPEC via _("x_search_terms", default=...): ' + ", ".join(missing)
    )


def test_bluesky_search_terms_preserve_brand_name() -> None:
    payload = json.loads(BLUESKY_I18N.read_text(encoding="utf-8"))
    invalid = []

    for locale, messages in sorted(payload.items()):
        terms = messages.get("x_search_terms")
        if not isinstance(terms, list):
            invalid.append(f"{locale}: x_search_terms is not a list")
            continue

        for index, token in BLUESKY_BRAND_SEARCH_TERMS.items():
            if index >= len(terms):
                invalid.append(f"{locale}: x_search_terms[{index}] is missing")
                continue

            term = str(terms[index])
            if token not in term.lower():
                invalid.append(f"{locale}[{index}]={term!r}")

    assert not invalid, (
        "Bluesky brand names must remain literal in brand-specific localized "
        "search terms: " + ", ".join(invalid)
    )
