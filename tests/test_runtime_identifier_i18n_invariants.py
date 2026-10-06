import json
import re
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1] / "src" / "uagent" / "tools"


def _load(name: str) -> dict:
    return json.loads((TOOLS_DIR / name).read_text(encoding="utf-8"))


def _has_standalone_token(text: str, token: str) -> bool:
    pattern = rf"(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])"
    return re.search(pattern, text) is not None


def test_audio_speech_language_description_preserves_auto_enum():
    payload = _load("audio_speech_tool.json")
    invalid = []

    for lang, messages in payload.items():
        if not isinstance(messages, dict):
            continue
        description = messages.get("param.language.description")
        if description is None:
            continue
        if not _has_standalone_token(description, "auto"):
            invalid.append(lang)

    assert not invalid, "Corrupted audio_speech auto enum: " + ", ".join(invalid)


def test_audio_transcribe_fmt_description_preserves_enum_values():
    payload = _load("audio_transcribe_tool.json")
    invalid = []

    for lang, messages in payload.items():
        if not isinstance(messages, dict):
            continue
        description = messages.get("param.fmt.description")
        if description is None:
            continue

        for token in ("text", "json"):
            if not _has_standalone_token(description, token):
                invalid.append(f"{lang}:{token}")

    assert not invalid, "Corrupted audio_transcribe fmt enums: " + ", ".join(invalid)


def test_azure_api_descriptions_preserve_runtime_identifiers():
    payload = _load("azure_api_tool.json")
    invalid = []

    for lang, messages in payload.items():
        if not isinstance(messages, dict):
            continue

        provider = messages.get("param.provider")
        if provider is not None and not _has_standalone_token(
            provider, "Microsoft.Compute"
        ):
            invalid.append(f"{lang}:Microsoft.Compute")

        resource = messages.get("param.resource")
        if resource is not None and not _has_standalone_token(resource, "ARM"):
            invalid.append(f"{lang}:ARM")

        confirm_write = messages.get("param.confirm_write")
        if confirm_write is not None and not _has_standalone_token(
            confirm_write, "GET"
        ):
            invalid.append(f"{lang}:GET")

    assert not invalid, "Corrupted Azure API identifiers: " + ", ".join(invalid)
