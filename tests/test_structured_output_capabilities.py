from __future__ import annotations

from uagent.llmcapa_util import supports_json_mode, supports_json_schema
from uagent.providers.structured_output import native_structured_output_request


class Cap:
    def __init__(self, json_mode=None, json_schema=None):
        self.supports_json_mode = json_mode
        self.supports_json_schema = json_schema

    def supports(self, feature):
        return getattr(self, f"supports_{feature}", None)


def messages(schema=None):
    text = "response_mode: json"
    if schema is not None:
        text += "\n\nresponse_schema:\n" + __import__("json").dumps(schema)
    return [{"role": "system", "content": text}]


def test_capabilities_are_tri_state_and_model_scoped(monkeypatch):
    caps = {
        ("openai", "model-a"): Cap(True, True),
        ("openai", "model-b"): Cap(True, False),
        ("other", "model-a"): Cap(False, None),
    }
    monkeypatch.setattr("uagent.llmcapa_util.get_capability", lambda model, provider: caps.get((provider, model)))
    assert supports_json_schema("model-a", "openai") is True
    assert supports_json_schema("model-b", "openai") is False
    assert supports_json_mode("model-a", "other") is False
    assert supports_json_schema("unknown", "openai") is None


def test_schema_is_not_sent_to_json_mode_only_model(monkeypatch):
    monkeypatch.setattr("uagent.llmcapa_util.get_capability", lambda *_: Cap(True, False))
    result = native_structured_output_request(messages({"type": "object"}), model_id="m", provider="p")
    assert result == {"type": "json_object"}


def test_schema_is_sent_only_when_supported(monkeypatch):
    monkeypatch.setattr("uagent.llmcapa_util.get_capability", lambda *_: Cap(True, True))
    result = native_structured_output_request(messages({"type": "object"}), model_id="m", provider="p")
    assert result["type"] == "json_schema"


def test_unknown_model_uses_prompt_fallback(monkeypatch):
    monkeypatch.setattr("uagent.llmcapa_util.get_capability", lambda *_: None)
    assert native_structured_output_request(messages({"type": "object"}), model_id="m", provider="p") is None


def test_azure_deployment_does_not_fall_back_to_openai(monkeypatch):
    import llmcapa
    from uagent.llmcapa_util import clear_capability_cache, get_capability

    calls = []

    def fake_get(model_id, provider=None):
        calls.append((model_id, provider))
        return Cap(True, True) if provider == "openai" else None

    monkeypatch.setattr(llmcapa, "get", fake_get)
    clear_capability_cache()
    try:
        assert get_capability("deployment-name", "azure", scoped_only=True) is None
        assert all(provider != "openai" for _, provider in calls)
    finally:
        clear_capability_cache()


def test_structured_output_switch_wins(monkeypatch):
    monkeypatch.setenv("UAGENT_STRUCTURED_OUTPUT", "false")
    monkeypatch.setattr("uagent.llmcapa_util.get_capability", lambda *_: Cap(True, True))
    assert native_structured_output_request(messages(), model_id="m", provider="p") is None
