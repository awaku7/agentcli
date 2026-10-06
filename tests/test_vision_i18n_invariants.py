import json
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1] / "src" / "uagent" / "tools"


def _load(name: str) -> dict:
    return json.loads((TOOLS_DIR / name).read_text(encoding="utf-8"))


def test_vision_provider_missing_env_messages_preserve_provider_names_and_envs():
    payload = _load("vision_openai.json")
    invalid = []

    for lang, messages in payload.items():
        if not isinstance(messages, dict):
            continue

        azure = messages.get("err.missing_env.azure")
        if azure is not None:
            if "azure" not in azure.lower():
                invalid.append(f"{lang}: azure provider name")
            if "UAGENT_AZURE_*" not in azure:
                invalid.append(f"{lang}: UAGENT_AZURE_*")
            if "UAGENT_AZURE_IMG_ANALYSIS_*" not in azure:
                invalid.append(f"{lang}: UAGENT_AZURE_IMG_ANALYSIS_*")

        alibaba = messages.get("vision.alibaba_missing_env")
        if alibaba is not None:
            if "alibaba" not in alibaba.lower():
                invalid.append(f"{lang}: Alibaba provider name")
            if "UAGENT_ALIBABA_*" not in alibaba:
                invalid.append(f"{lang}: UAGENT_ALIBABA_*")

        moonshot = messages.get("vision.moonshot_missing_env")
        if moonshot is not None:
            if "moonshot" not in moonshot.lower():
                invalid.append(f"{lang}: Moonshot provider name")
            if "UAGENT_MOONSHOT_*" not in moonshot:
                invalid.append(f"{lang}: UAGENT_MOONSHOT_*")

    assert not invalid, "Corrupted vision provider locale messages: " + ", ".join(
        invalid
    )


def test_vision_missing_env_messages_do_not_reference_foreign_provider_config():
    payload = _load("vision_openai.json")
    invalid = []

    for lang, messages in payload.items():
        if not isinstance(messages, dict):
            continue

        for key in (
            "err.missing_env.azure",
            "vision.alibaba_missing_env",
            "vision.moonshot_missing_env",
        ):
            message = messages.get(key)
            if message is None:
                continue
            lowered = message.lower()
            if "uagent_responses" in lowered or "bedrock" in lowered:
                invalid.append(f"{lang}:{key}")

    assert (
        not invalid
    ), "Foreign provider/config guidance leaked into messages: " + ", ".join(invalid)


def test_vision_default_prompt_is_not_replaced_by_provider_error():
    payload = _load("vision_openai.json")
    invalid = []

    for lang, messages in payload.items():
        if not isinstance(messages, dict):
            continue
        prompt = messages.get("prompt.default")
        if prompt is None:
            continue
        lowered = prompt.lower()
        if "uagent_" in lowered or "ollama" in lowered:
            invalid.append(lang)

    assert not invalid, "Corrupted localized vision prompt.default: " + ", ".join(
        invalid
    )


def test_generate_image_prompt_empty_does_not_contain_depname_guidance():
    payload = _load("generate_image_tool.json")
    invalid = []

    for lang, messages in payload.items():
        if not isinstance(messages, dict):
            continue
        message = messages.get("err.prompt_empty")
        if message is None:
            continue
        if "UAGENT_" in message:
            invalid.append(lang)

    assert not invalid, "Corrupted localized generate_image prompt error: " + ", ".join(
        invalid
    )
