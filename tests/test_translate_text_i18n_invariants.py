import json
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1] / "src" / "uagent" / "tools"


def _load() -> dict:
    return json.loads(
        (TOOLS_DIR / "translate_text_tool.json").read_text(encoding="utf-8")
    )


def test_translate_text_description_preserves_parameter_identifier():
    payload = _load()
    invalid = []

    for lang, messages in payload.items():
        if not isinstance(messages, dict):
            continue
        description = messages.get("tool.description")
        if description is None:
            continue
        if "protect_placeholders" not in description:
            invalid.append(lang)

    assert not invalid, "Corrupted protect_placeholders identifier: " + ", ".join(
        invalid
    )


def test_translate_provider_description_preserves_enum_values_and_brand():
    payload = _load()
    invalid = []

    for lang, messages in payload.items():
        if not isinstance(messages, dict):
            continue
        description = messages.get("param.provider.description")
        if description is None:
            continue

        for token in ("auto", "google", "deepl", "DeepL"):
            if token not in description:
                invalid.append(f"{lang}:{token}")

    assert not invalid, "Corrupted translate provider identifiers: " + ", ".join(
        invalid
    )
