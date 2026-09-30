from __future__ import annotations

from uagent.runtime.status import normalize_status_label


def test_foundry_status_label_is_provider_neutral(monkeypatch) -> None:
    monkeypatch.delenv("UAGENT_REASONING", raising=False)

    assert normalize_status_label(True, "LLM:Foundry:inference") == "LLM"
    assert normalize_status_label(True, "LLM:Foundry:reasoning") == "LLM"
    assert normalize_status_label(True, "LLM:Foundry:streaming") == "LLM"
    assert normalize_status_label(True, "LLM:Foundry:tool-call") == "LLM"


def test_foundry_status_label_uses_common_reasoning_label(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_REASONING", "auto")

    assert normalize_status_label(True, "LLM:Foundry:inference") == "LLM:auto"


def test_foundry_status_label_is_normalized_when_not_busy(monkeypatch) -> None:
    monkeypatch.delenv("UAGENT_REASONING", raising=False)

    assert normalize_status_label(False, "LLM:Foundry:inference") == "LLM"


def test_non_foundry_status_labels_are_unchanged(monkeypatch) -> None:
    monkeypatch.delenv("UAGENT_REASONING", raising=False)

    assert normalize_status_label(True, "LLM:medium") == "LLM:medium"
    assert normalize_status_label(True, "tool:fetch_url") == "tool:fetch_url"
