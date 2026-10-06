from __future__ import annotations

import json

from uagent.tools import i18n_helper


def test_tool_translator_ignores_json_english_block(tmp_path, monkeypatch) -> None:
    tool_py = tmp_path / "sample.py"
    tool_py.write_text("", encoding="utf-8")
    tool_json = tmp_path / "sample.json"
    tool_json.write_text(
        json.dumps(
            {
                "en": {"message": "stale JSON English"},
                "ja": {"message": "日本語"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    i18n_helper.clear_tool_i18n_cache()
    monkeypatch.setattr(i18n_helper, "get_locale", lambda: "en")
    translate = i18n_helper.make_tool_translator(str(tool_py))

    assert translate("message", default="canonical Python English") == (
        "canonical Python English"
    )

    monkeypatch.setattr(i18n_helper, "get_locale", lambda: "ja")
    assert translate("message", default="canonical Python English") == "日本語"


def test_tool_translator_falls_back_for_incompatible_translation(
    tmp_path, monkeypatch
) -> None:
    tool_py = tmp_path / "sample.py"
    tool_py.write_text("", encoding="utf-8")
    tool_json = tmp_path / "sample.json"
    tool_json.write_text(
        json.dumps(
            {
                "ja": {
                    "message": "こんにちは {user}",
                    "nested": {"message": "翻訳"},
                    "choices": ["一"],
                    "x_search_terms": ["検索"],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    i18n_helper.clear_tool_i18n_cache()
    monkeypatch.setattr(i18n_helper, "get_locale", lambda: "ja")
    translate = i18n_helper.make_tool_translator(str(tool_py))

    assert translate("message", default="Hello {name}", name="Alice") == "Hello Alice"
    assert translate(
        "nested",
        default={"message": "Hello", "detail": "Detail"},
    ) == {"message": "Hello", "detail": "Detail"}
    assert translate("choices", default=["one", "two"]) == ["one", "two"]
    assert translate(
        "x_search_terms",
        default=["search", "find"],
    ) == ["検索"]


def test_tool_translator_uses_compatible_localized_placeholder(
    tmp_path, monkeypatch
) -> None:
    tool_py = tmp_path / "sample.py"
    tool_py.write_text("", encoding="utf-8")
    tool_json = tmp_path / "sample.json"
    tool_json.write_text(
        json.dumps(
            {"ja": {"message": "こんにちは {name}"}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    i18n_helper.clear_tool_i18n_cache()
    monkeypatch.setattr(i18n_helper, "get_locale", lambda: "ja")
    translate = i18n_helper.make_tool_translator(str(tool_py))

    assert (
        translate("message", default="Hello {name}", name="Alice") == "こんにちは Alice"
    )
