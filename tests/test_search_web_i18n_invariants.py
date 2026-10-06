import json
import re
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1] / "src" / "uagent" / "tools"


def _load() -> dict:
    return json.loads(
        (TOOLS_DIR / "search_web_tool.json").read_text(encoding="utf-8")
    )


def _has_standalone_token(text: str, token: str) -> bool:
    pattern = rf"(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def test_search_web_tool_description_mentions_startpage():
    payload = _load()
    invalid = []

    for lang, messages in payload.items():
        if not isinstance(messages, dict):
            continue
        description = messages.get("tool.description")
        if description is None:
            continue
        if "startpage" not in description.lower():
            invalid.append(lang)

    assert not invalid, "Missing StartPage in localized tool description: " + ", ".join(
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
