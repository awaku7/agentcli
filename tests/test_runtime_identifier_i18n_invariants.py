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
SUB_AGENT_PROMPT_FIELDS = {
    "auto.6cb7e91442d0aa96": (
        "status",
        "role",
        "summary",
        "assumptions",
        "risks",
        "next_actions",
    ),
    "auto.238f691c6304d301": (
        "status",
        "role",
        "summary",
        "findings",
        "risks",
        "recommended_actions",
    ),
    "auto.da98c4c06ff99472": (
        "status",
        "role",
        "summary",
        "key_points",
        "open_questions",
    ),
    "auto.417eea12dad04caa": (
        "status",
        "role",
        "summary",
        "files",
        "changes",
        "risks",
        "validation_steps",
    ),
    "auto.4651eaae39b1dbbb": (
        "status",
        "role",
        "summary",
        "root_cause",
        "evidence",
        "proposed_actions",
    ),
    "auto.c30a5aed7a2d7578": (
        "status",
        "role",
        "summary",
        "source_lang",
        "target_lang",
        "translation",
        "notes",
    ),
    "auto.924901d00f734fac": (
        "status",
        "role",
        "summary",
        "details",
        "notes",
    ),
}
SUB_AGENT_PROTECTED_TOKEN_RE = re.compile(r"__UAG_PROTECTED_\d+__")
SUB_AGENT_PROMPT_ARTIFACT_RE = re.compile(
    r"(?:Constant\(value=|Konstant\(value=|ধ্রুবক\(মান=|"
    r"(?<![A-Za-z])PH(?:_[A-Za-z0-9]+)*(?![A-Za-z])|_PH|__|"
    r"(?<![A-Za-z0-9_])_(?:[A-Za-z0-9]+|\[)|"
    r"\b\d+n\b|\b\d+_[A-Za-z0-9_]+|\|{3,}|"
    r"(?:kind|tipo|laji|kedves|type|art|typ|jenis|tipe)\s*=\s*[^,\n)]+\)|"
    r"\[Output format\]|\[Edge cases\]|\[Self-evaluation\]|"
    r"\[Token efficiency\]|\[Step-by-step reasoning\]|"
    r"\bYou are\b|\bStrictly output\b)"
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
            scan_prompt = SUB_AGENT_PROTECTED_TOKEN_RE.sub("", prompt)
            match = SUB_AGENT_PROMPT_ARTIFACT_RE.search(scan_prompt)
            if match:
                invalid.append(f"{lang}:{key}:{match.group(0)}")

    assert not invalid, "Corrupted sub-agent prompt translations: " + ", ".join(invalid)


def test_mongolian_summarizer_preserves_canonical_semantics():
    catalog = json.loads(
        (TOOLS_DIR / "sub_agent_tool.json").read_text(encoding="utf-8")
    )
    prompt = catalog["mn"]["auto.da98c4c06ff99472"]
    body = prompt.split("\n[Protocol invariants]", 1)[0]

    assert '\n - role: үргэлж "summarizer"' in body
    assert "\n - summary:" in body
    assert "Техникийн нэр томьёог бичсэн хэвээр нь хадгал." in body
    assert "20 үгнээс хэтрүүлэхгүй" in body
    assert "20 үгэнд багтаахаас зайлсхий" not in body


def test_vietnamese_error_analyst_preserves_canonical_semantics():
    catalog = json.loads(
        (TOOLS_DIR / "sub_agent_tool.json").read_text(encoding="utf-8")
    )
    prompt = catalog["vi"]["auto.4651eaae39b1dbbb"]
    body = prompt.split("\n[Protocol invariants]", 1)[0]

    assert "nhiều nguyên nhân có thể xảy ra" in body
    assert "theo thứ tự khả năng xảy ra" in body
    assert "[Tự đánh giá]" in body
    assert "tái tạo lỗi" in body
    assert "proposed_actions" in body


def test_simplified_chinese_error_analyst_preserves_canonical_semantics():
    catalog = json.loads(
        (TOOLS_DIR / "sub_agent_tool.json").read_text(encoding="utf-8")
    )
    prompt = catalog["zh_CN"]["auto.4651eaae39b1dbbb"]
    body = prompt.split("\n[Protocol invariants]", 1)[0]

    assert "多个可能原因" in body
    assert "按可能性高低排序" in body
    assert "[自我评估]" in body
    assert "复现错误" in body
    assert "proposed_actions" in body


def test_known_localized_prompt_semantics_are_complete():
    catalog = json.loads(
        (TOOLS_DIR / "sub_agent_tool.json").read_text(encoding="utf-8")
    )

    id_planner = catalog["id"]["auto.6cb7e91442d0aa96"]
    assert "Jika tugas sudah selesai" in id_planner
    assert "next_actions kosong" in id_planner

    ja_summarizer = catalog["ja"]["auto.da98c4c06ff99472"]
    assert "key_points は省略できます" in ja_summarizer
    assert "技術用語は記載どおりに維持" in ja_summarizer

    ko_patch = catalog["ko"]["auto.417eea12dad04caa"]
    assert "summary에 이유를 설명" in ko_patch
    assert "권장 순서대로 나열" in ko_patch

    for lang in ("pt", "pt_BR"):
        planner_prompt = catalog[lang]["auto.6cb7e91442d0aa96"]
        assert "tarefa já estiver concluída" in planner_prompt
        assert "next_actions vazia" in planner_prompt


def test_japanese_and_indonesian_prompt_semantics_are_complete():
    catalog = json.loads(
        (TOOLS_DIR / "sub_agent_tool.json").read_text(encoding="utf-8")
    )

    ja = catalog["ja"]
    assert "追加で必要な情報を具体的に列挙" in ja["auto.6cb7e91442d0aa96"]
    assert "false positive" in ja["auto.238f691c6304d301"]
    assert "可能性が高い順" in ja["auto.4651eaae39b1dbbb"]
    assert "混在している箇所を notes で説明" in ja["auto.c30a5aed7a2d7578"]

    ident = catalog["id"]
    assert "istilah teknis persis seperti ditulis" in ident["auto.da98c4c06ff99472"]
    assert "beberapa kemungkinan penyebab" in ident["auto.4651eaae39b1dbbb"]
    assert "berdasarkan urutan kemungkinan" in ident["auto.4651eaae39b1dbbb"]


def test_ukrainian_reviewer_preserves_no_problems_condition():
    catalog = json.loads(
        (TOOLS_DIR / "sub_agent_tool.json").read_text(encoding="utf-8")
    )
    reviewer = catalog["uk"]["auto.238f691c6304d301"]

    assert "Якщо проблем немає" in reviewer
    assert "порожній список findings" in reviewer


def test_recent_reviewed_prompt_semantics_are_complete():
    catalog = json.loads(
        (TOOLS_DIR / "sub_agent_tool.json").read_text(encoding="utf-8")
    )

    de_planner = catalog["de"]["auto.6cb7e91442d0aa96"]
    assert "Aufgabe bereits abgeschlossen" in de_planner
    assert "leere next_actions-Liste" in de_planner

    de_error = catalog["de"]["auto.4651eaae39b1dbbb"]
    assert "mehrere Ursachen möglich" in de_error
    assert "Reihenfolge ihrer Wahrscheinlichkeit" in de_error

    fr_summarizer = catalog["fr"]["auto.da98c4c06ff99472"]
    assert "termes techniques" in fr_summarizer
    assert "tels qu’ils sont écrits" in fr_summarizer

    for lang in ("pt", "pt_BR"):
        summarizer = catalog[lang]["auto.da98c4c06ff99472"]
        assert "termos técnicos" in summarizer
        assert "como estão escritos" in summarizer


def test_localized_prompts_do_not_keep_known_sentence_fragments():
    catalog = json.loads(
        (TOOLS_DIR / "sub_agent_tool.json").read_text(encoding="utf-8")
    )
    prompts = [
        value
        for messages in catalog.values()
        if isinstance(messages, dict)
        for key, value in messages.items()
        if key.startswith("auto.") and isinstance(value, str)
    ]

    forbidden = (
        " list.",
        ". summary.",
        "warum summary.",
        "waarom summary.",
        "alasannya summary.",
        "[Token]effektivitet]",
    )
    for prompt in prompts:
        for fragment in forbidden:
            assert fragment not in prompt


def test_sub_agent_internal_prompts_preserve_canonical_role_instructions():
    payload = _load("sub_agent_tool.json")
    invalid = []

    for lang, messages in payload.items():
        if not isinstance(messages, dict):
            continue
        for key, expected_fields in SUB_AGENT_PROMPT_FIELDS.items():
            prompt = messages.get(key)
            if not isinstance(prompt, str):
                continue
            body = prompt.split("\n[Protocol invariants]", 1)[0]
            lines = [line for line in body.splitlines() if line.strip()]
            if len(lines) < len(expected_fields) + 4:
                invalid.append(f"{lang}:{key}:truncated")
                continue
            for field in expected_fields:
                if field not in body:
                    invalid.append(f"{lang}:{key}:{field}")
            if "[Protocol invariants]" in body:
                invalid.append(f"{lang}:{key}:protocol-in-body")

    assert not invalid, "Incomplete sub-agent prompt translations: " + ", ".join(
        invalid
    )
