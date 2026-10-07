import json
import re
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1] / "src" / "uagent" / "tools"


def _load() -> dict:
    return json.loads((TOOLS_DIR / "search_web_tool.json").read_text(encoding="utf-8"))


def _has_standalone_token(text: str, token: str) -> bool:
    pattern = rf"(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def test_search_web_tool_description_mentions_supported_engines():
    payload = _load()
    invalid = []

    for lang, messages in payload.items():
        if not isinstance(messages, dict):
            continue
        description = messages.get("tool.description")
        if description is None:
            continue
        lowered = description.lower()
        for token in ("startpage", "duckduckgo", "brave search", "yahoo japan"):
            if token not in lowered:
                invalid.append(f"{lang}:{token}")

    assert not invalid, "Missing engine in localized tool description: " + ", ".join(
        invalid
    )


def test_search_web_engine_description_preserves_enum_values():
    payload = _load()
    invalid = []

    for lang, messages in payload.items():
        if not isinstance(messages, dict):
            continue
        description = messages.get("param.engine.description")
        if description is None:
            continue

        for token in ("startpage", "duckduckgo", "brave", "yahoo_jp", "yahoo"):
            if not _has_standalone_token(description, token):
                invalid.append(f"{lang}:{token}")

    assert not invalid, "Corrupted search engine enum values: " + ", ".join(invalid)


def test_search_web_error_messages_preserve_parameter_and_type_names():
    payload = _load()
    invalid = []

    for lang, messages in payload.items():
        if not isinstance(messages, dict):
            continue

        missing_query = messages.get("error.missing_query_parameter")
        if missing_query is not None and not _has_standalone_token(
            missing_query, "query"
        ):
            invalid.append(f"{lang}:query")

        args_error = messages.get("error.args_must_be_dict")
        if args_error is not None and not _has_standalone_token(args_error, "dict"):
            invalid.append(f"{lang}:dict")

    assert not invalid, "Corrupted search_web error identifiers: " + ", ".join(invalid)


def test_search_web_limit_description_is_not_cross_key_content():
    payload = _load()
    invalid = []

    for lang, messages in payload.items():
        if not isinstance(messages, dict):
            continue
        description = messages.get("param.limit.description")
        if description is None:
            continue
        if "5" not in description or "uagent" in description.lower():
            invalid.append(lang)

    assert not invalid, "Corrupted search_web limit descriptions: " + ", ".join(invalid)


def test_search_web_localized_strings_are_not_punctuation_only():
    payload = _load()
    invalid = []

    for lang, messages in payload.items():
        if not isinstance(messages, dict):
            continue
        for key, value in messages.items():
            if not isinstance(value, str):
                continue
            stripped = value.strip()
            if stripped and all(
                char in ".,;:!?。！？、，；：" for char in stripped
            ):
                invalid.append(f"{lang}:{key}")

    assert not invalid, "Punctuation-only search_web translations: " + ", ".join(
        invalid
    )


def test_search_web_search_terms_are_clean_and_unique():
    payload = _load()
    invalid = []

    forbidden_fragments = {
        "ja": ("バスカー",),
        "ko": ("버스카",),
        "id": ("buscar en la web",),
        "ru": ("автобус",),
        "vi": ("xe buýt",),
        "pl": ("autobus", "recherche"),
        "hi": ("बसकार", "रेचेर्चे"),
        "sv": ("buscar",),
        "sw": ("buscar", "recherche"),
        "nb": ("buscar",),
        "nl": ("buscar",),
        "fi": ("buscar", "recherche"),
        "cs": ("buscar",),
        "uk": ("автобус",),
        "tr": ("otobüs",),
        "th": ("รถบัส",),
        "zh_CN": ("巴士",),
        "zh_TW": ("巴士",),
        "bn": ("বাসকার", "recherche"),
        "fa": ("buscar", "recherche"),
        "mn": ("автобус", "recherche"),
        "mr": ("buscar", "recherche"),
        "el": ("buscar", "recherche"),
        "he": ("buscar", "recherche"),
        "hu": ("buscar", "recherche"),
        "ro": ("recherche",),
        "fil": ("buscar", "recherche"),
        "ms": ("buscar", "recherche"),
        "da": ("buscar", "recherche"),
        "nn": ("buscar", "recherche"),
    }

    for lang, messages in payload.items():
        if not isinstance(messages, dict):
            continue
        terms = messages.get("x_search_terms")
        if not isinstance(terms, list) or not terms:
            invalid.append(f"{lang}:missing")
            continue

        normalized = [
            str(term).strip().casefold()
            for term in terms
            if str(term).strip()
        ]
        if len(normalized) != len(terms):
            invalid.append(f"{lang}:blank")
        if len(set(normalized)) != len(normalized):
            invalid.append(f"{lang}:duplicate")
        for required in ("duckduckgo", "google"):
            if required not in normalized:
                invalid.append(f"{lang}:missing-{required}")

        joined = "\n".join(normalized)
        for fragment in forbidden_fragments.get(lang, ()):
            if fragment.casefold() in joined:
                invalid.append(f"{lang}:legacy-{fragment}")

    assert not invalid, "Corrupted search_web search terms: " + ", ".join(invalid)

