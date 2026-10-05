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
