from __future__ import annotations

from types import SimpleNamespace

import pytest


def test_make_client_openrouter_uses_sdk_and_exposes_compat_methods(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent.providers import util_providers

    calls: dict[str, dict[str, object]] = {}

    class DummyChat:
        def send(self, **kwargs):
            calls["chat"] = kwargs
            return {"kind": "chat"}

    class DummyResponses:
        def send(self, **kwargs):
            calls["responses"] = kwargs
            return {"kind": "responses"}

    class DummySDK:
        def __init__(self, **kwargs):
            calls["ctor"] = kwargs
            self.chat = DummyChat()
            self.beta = SimpleNamespace(responses=DummyResponses())

    class DummyCore:
        def get_env(self, name: str):
            return {
                "UAGENT_OPENROUTER_API_KEY": "test-key",
            }.get(name)

        def get_env_url(self, name: str, default: str | None = None):
            return default or "https://openrouter.ai/api/v1"

    monkeypatch.setattr(util_providers, "_OpenRouterSDK", DummySDK)
    monkeypatch.setattr(util_providers, "make_httpx_client", lambda **_: None)
    monkeypatch.setattr(
        util_providers,
        "env_get",
        lambda name, default=None: {
            "UAGENT_PROVIDER": "openrouter",
            "UAGENT_OPENROUTER_DEPNAME": "test-model",
            "UAGENT_OPENROUTER_API_KEY": "test-key",
        }.get(name, default),
    )

    provider, client, model_name = util_providers.make_client(DummyCore())

    assert provider == "openrouter"
    assert model_name == "test-model"
    assert calls["ctor"]["api_key"] == "test-key"
    assert calls["ctor"]["http_referer"] == "https://localhost/agent"
    assert calls["ctor"]["x_open_router_title"] == "scheck-openrouter"

    chat_result = client.chat.completions.create(
        model="m",
        messages=[{"role": "user", "content": "hi"}],
        extra_body={
            "reasoning": {"effort": "medium", "summary": "auto"},
            "provider": {"ignore": ["provider-a"]},
        },
    )
    assert chat_result == {"kind": "chat"}
    assert calls["chat"]["model"] == "m"
    assert calls["chat"]["reasoning"]["effort"] == "medium"
    assert calls["chat"]["reasoning"]["summary"] == "auto"
    assert calls["chat"]["provider"]["ignore"] == ["provider-a"]
    assert "extra_body" not in calls["chat"]

    responses_result = client.responses.create(
        model="m",
        input="hello",
        extra_body={"reasoning": {"effort": "low", "enabled": True}},
    )
    assert responses_result == {"kind": "responses"}
    assert calls["responses"]["model"] == "m"
    assert calls["responses"]["reasoning"]["effort"] == "low"
    assert "extra_body" not in calls["responses"]

    # The SDK adapter should also keep the beta.responses route usable.
    beta_result = client.beta.responses.send(model="m", input="beta")
    assert beta_result == {"kind": "responses"}
    assert calls["responses"]["input"] == "beta"
