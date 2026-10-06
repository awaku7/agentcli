from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "i18n_validate", ROOT / "scripts" / "i18n_validate.py"
)
assert SPEC and SPEC.loader
validate_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validate_module
SPEC.loader.exec_module(validate_module)


def test_tool_catalog_validation_rejects_en_only() -> None:
    result = validate_module._validate_tool_catalog({"en": {"message": "Hello"}})

    assert result["ok"] is False
    assert "must not contain an 'en' block" in result["errors"][0]


def test_tool_catalog_validation_accepts_translation_only_catalog() -> None:
    result = validate_module._validate_tool_catalog(
        {"ja": {"message": "こんにちは"}, "de": {"message": "Hallo"}}
    )

    assert result == {
        "mode": "tool_catalog",
        "checked_locales": 2,
        "errors": [],
        "ok": True,
    }


def test_non_i18n_json_is_not_misclassified_as_tool_catalog() -> None:
    assert validate_module._looks_like_tool_catalog(
        {"ja": {"message": "こんにちは"}}
    )
    assert not validate_module._looks_like_tool_catalog(
        {"id": {"value": 1}, "metadata": {"version": 1}}
    )


def test_translation_manifest_keeps_protected_token_validation() -> None:
    result = validate_module._validate_translation_manifest(
        {
            "locales": ["de"],
            "entries": {
                "message": {
                    "source_masked": "Hello __UAG_PROTECTED_0__",
                    "translations": {"de": "Hallo"},
                }
            },
        }
    )

    assert result["ok"] is False
    assert result["checked_translations"] == 1
