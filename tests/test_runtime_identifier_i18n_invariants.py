import json
import re
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1] / "src" / "uagent" / "tools"
SUB_AGENT_PROMPT_KEYS = (
    "auto.6cb7e91442d0aa96",
    "auto.238f691c6304d301",
    "auto.da98c4c06ff99472",
    "auto.417eea12dad04caa",
    "auto.4651eaae39b1dbbb",
    "auto.c30a5aed7a2d7578",
    "auto.924901d00f734fac",
)
SUB_AGENT_PROMPT_ARTIFACT_RE = re.compile(
    r"(?:Constant\\(value=|Konstant\\(value=|ধ্রুবক\\(মান=|"
    r"(?<![A-Za-z])PH(?:_[A-Za-z0-9]+)*(?![A-Za-z])|_PH|__\\d+|\\|{3,}|"
    r"\\[Output format\\]|\\[Edge cases\\]|\\[Self-evaluation\\]|"
    r"\\[Token efficiency\\]|\\[Step-by-step reasoning\\]|"
    r"\\bYou are\\b|\\bStrictly output\\b)"
)
TRANSLATION_PLACEHOLDER_ARTIFACT_RE = re.compile(
    r"(?:"
    r"(?<![A-Za-z])PH(?:_[A-Za-z0-9]+)*(?![A-Za-z])"
    r"|__|_\d+\b|-_th\b|\|{3,}"
    r")"
)


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


def test_runtime_enum_descriptions_preserve_exact_values():
    cases = (
        ("get_geoip_tool.json", "param.format.description", ("text", "json")),
        (
            "exstruct_tool.json",
            "param.action.description",
            ("extract", "export_file"),
        ),
        (
            "exstruct_tool.json",
            "param.mode.description",
            ("light", "standard", "verbose"),
        ),
        ("exstruct_tool.json", "param.format.description", ("json", "yaml")),
        (
            "code_map_tool.json",
            "param.format.description",
            ("json", "mermaid", "ontology", "html"),
        ),
        (
            "office_to_markdown_tool.json",
            "param.format.description",
            ("auto", "pptx", "xlsx", "docx"),
        ),
        (
            "ucp_catalog_tool.json",
            "param.mode.description",
            ("search", "lookup"),
        ),
        ("ucp_order_tool.json", "param.mode.description", ("list", "get")),
        (
            "ucp_cart_tool.json",
            "param.mode.description",
            ("create", "get", "update"),
        ),
        (
            "ucp_identity_tool.json",
            "param.mode.description",
            ("link", "status"),
        ),
        (
            "ucp_mcp_server_tool.json",
            "param.mode.description",
            ("start", "stop", "status"),
        ),
        (
            "diff_files_tool.json",
            "param.mode.description",
            ("unified", "summary", "json_diff"),
        ),
        (
            "replace_in_file_tool.json",
            "param.mode.description",
            ("literal", "regex"),
        ),
        (
            "replace_in_file_tool.json",
            "param.mode_after.description",
            ("literal", "regex"),
        ),
        ("lint_format_tool.json", "param.mode.description", ("check", "fix")),
    )
    invalid = []

    for filename, key, tokens in cases:
        payload = _load(filename)
        for lang, messages in payload.items():
            if not isinstance(messages, dict):
                continue
            description = messages.get(key)
            if description is None:
                continue
            for token in tokens:
                if not _has_standalone_token(description, token):
                    invalid.append(f"{filename}:{lang}:{key}:{token}")

    assert not invalid, "Corrupted runtime enum literals: " + ", ".join(invalid)


def test_repaired_tool_catalogs_have_no_translation_placeholder_artifacts():
    repaired_catalogs = (
        "http_request_tool.json",
        "office_to_markdown_tool.json",
    )
    invalid = []

    for filename in repaired_catalogs:
        text = (TOOLS_DIR / filename).read_text(encoding="utf-8")
        match = TRANSLATION_PLACEHOLDER_ARTIFACT_RE.search(text)
        if match:
            invalid.append(f"{filename}:{match.group(0)}")

    assert not invalid, "Translation placeholder artifacts: " + ", ".join(invalid)


def test_sub_agent_internal_prompts_are_clean_localized_text():
    payload = _load("sub_agent_tool.json")
    invalid = []

    for lang, messages in payload.items():
        if not isinstance(messages, dict):
            continue
        for key in SUB_AGENT_PROMPT_KEYS:
            prompt = messages.get(key)
            if not isinstance(prompt, str) or not prompt.strip():
                invalid.append(f"{lang}:{key}:missing")
                continue
            if "[Protocol invariants]" not in prompt:
                invalid.append(f"{lang}:{key}:protocol")
            if "\\n" in prompt:
                invalid.append(f"{lang}:{key}:literal-newline")
            match = SUB_AGENT_PROMPT_ARTIFACT_RE.search(prompt)
            if match:
                invalid.append(f"{lang}:{key}:{match.group(0)}")

    assert not invalid, "Corrupted sub-agent prompt translations: " + ", ".join(invalid)
