from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from uagent.tools import translate_text_tool


def test_deepl_provider_translates_and_preserves_placeholders(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[tuple[str, dict]] = []

    class FakeTranslator:
        def translate_text(self, text, **kwargs):
            calls.append((text, kwargs))
            return SimpleNamespace(text="Hallo __PH_0", detected_source_lang="EN")

    monkeypatch.setenv("UAGENT_DEEPL_AUTH_KEY", "test-key")
    monkeypatch.setattr(translate_text_tool, "_deepl_client", lambda: FakeTranslator())

    result = json.loads(
        translate_text_tool.run_tool(
            {
                "texts": ["Hello {name}"],
                "target_lang": "de",
                "provider": "deepl",
            }
        )
    )

    assert result["ok"] is True
    assert result["provider"] == "deepl"
    assert result["translated"] == ["Hallo {name}"]
    assert calls == [("Hello __PH_0", {"target_lang": "DE"})]


def test_auto_provider_uses_google_without_deepl_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("UAGENT_DEEPL_AUTH_KEY", raising=False)
    monkeypatch.delenv("DEEPL_AUTH_KEY", raising=False)
    monkeypatch.delenv("DEEPL_API_KEY", raising=False)
    monkeypatch.setattr(
        translate_text_tool,
        "_translate_texts_batch",
        lambda *args, **kwargs: (["Hallo"], None, 0),
    )

    result = json.loads(
        translate_text_tool.run_tool(
            {"texts": ["Hello"], "target_lang": "de", "provider": "auto"}
        )
    )

    assert result["ok"] is True
    assert result["provider"] == "google"


def test_deepl_requires_auth_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("UAGENT_DEEPL_AUTH_KEY", raising=False)
    monkeypatch.delenv("DEEPL_AUTH_KEY", raising=False)
    monkeypatch.delenv("DEEPL_API_KEY", raising=False)

    result = json.loads(
        translate_text_tool.run_tool(
            {"texts": ["Hello"], "target_lang": "de", "provider": "deepl"}
        )
    )

    assert result["ok"] is False
    assert "requires" in result["error"].lower()
