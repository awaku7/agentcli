from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from uagent.decision.catalog import (
    CatalogDecisionConfigurationError,
    CatalogDecisionProvider,
    _select_adapter,
)
from uagent.decision.goal_completion import (
    provider_supports_goal_completion,
    provider_uses_atomic_goal_completion,
)
from uagent.decision.models import DecisionQuestion, DecisionRequest
from uagent.decision.settings import DecisionSettings


class FakeResponse:
    status_code = 200

    def json(self):
        return {
            "model": "microsoft-decision-1",
            "answers": {
                "goal_status": {
                    "type": "choice",
                    "choice": "COMPLETE",
                    "probabilities": {"COMPLETE": 0.9, "CONTINUE": 0.1},
                    "confidence": 0.9,
                }
            },
        }


class FakeClient:
    def __init__(self):
        self.calls = []
        self.closed = False

    def post(self, url, *, headers, json):
        self.calls.append({"url": url, "headers": headers, "json": json})
        return FakeResponse()

    def close(self):
        self.closed = True


def _capability(provider, endpoint, *, protocol="", extra=None):
    return SimpleNamespace(
        provider=provider,
        decision=SimpleNamespace(
            decision=True,
            endpoints=(endpoint,),
            question_kinds=("noul", "choice", "score"),
            answer_fields=("noul", "choice", "score", "probabilities", "confidence"),
            calibrated_confidence=True,
            extra={"endpoint_protocol": protocol, **(extra or {})},
        ),
    )


def _request():
    return DecisionRequest(
        state={"task": "all requested work is complete"},
        questions=(
            DecisionQuestion(
                id="goal_status",
                kind="choice",
                instruction="Is the requested work complete?",
                choices=("COMPLETE", "CONTINUE"),
            ),
        ),
    )


def test_auto_routes_microsoft_systemone_model_and_uses_foundry_api_key(monkeypatch):
    capability = _capability(
        "microsoft",
        "https://{azure_endpoint}/providers/microsoft/v1/systemone",
        protocol="microsoft-systemone-v1",
    )
    monkeypatch.setattr(
        "uagent.decision.catalog.get_capability",
        lambda model, provider, *, scoped_only: capability,
    )
    monkeypatch.setattr(
        "uagent.decision.catalog.validate_model_decision_request",
        lambda **_kwargs: capability.decision,
    )
    client = FakeClient()
    provider = CatalogDecisionProvider(
        settings=DecisionSettings("auto"),
        environ={
            "UAGENT_DECISION_MODEL": "Microsoft-Decision-1",
            "UAGENT_DECISION_MODEL_PROVIDER": "microsoft",
            "UAGENT_DECISION_DEPLOYMENT": "ticket-router-prod",
            "UAGENT_AZURE_BASE_URL": "https://foundry.example.test",
            "UAGENT_AZURE_API_KEY": "foundry-secret",
        },
        client=client,
    )

    result = provider.decide(_request())

    assert provider.name == "microsoft"
    assert provider.catalog_model == "Microsoft-Decision-1"
    assert provider.model == "ticket-router-prod"
    assert result.provider == "microsoft"
    assert result.answers["goal_status"].value == "COMPLETE"
    assert client.calls[0]["url"] == (
        "https://foundry.example.test/providers/microsoft/v1/systemone"
    )
    assert client.calls[0]["headers"]["api-key"] == "foundry-secret"
    assert "Authorization" not in client.calls[0]["headers"]
    assert client.calls[0]["json"]["model"] == "ticket-router-prod"
    provider.close()
    assert client.closed is False


def test_auto_routes_perplexity_only_when_systemone_schema_is_documented(monkeypatch):
    capability = _capability(
        "perplexity",
        "https://api.perplexity.ai/v1/decisions",
        protocol="perplexity-decisions-v1",
        extra={"systemone_schema_compatible": True},
    )
    monkeypatch.setattr(
        "uagent.decision.catalog.get_capability",
        lambda *_args, **_kwargs: capability,
    )
    provider = CatalogDecisionProvider(
        settings=DecisionSettings("auto"),
        environ={
            "UAGENT_DECISION_MODEL": "pplx-decider-v1.1-27b",
            "UAGENT_DECISION_API_KEY": "perplexity-secret",
        },
        client=FakeClient(),
    )

    assert provider.name == "perplexity"
    assert provider._adapter == "systemone"
    assert (
        provider._delegate._config.endpoint == "https://api.perplexity.ai/v1/decisions"
    )
    assert provider._delegate._config.auth_header == "bearer"
    provider.close()


def test_auto_selects_known_native_protocols():
    assert (
        _select_adapter(
            provider="openai",
            protocol="openai-decisions-v1",
            endpoint="https://api.openai.com/v1/decisions",
            extra={},
        )
        == "openai"
    )
    assert (
        _select_adapter(
            provider="openrouter",
            protocol="openrouter-alpha-decisions",
            endpoint="https://openrouter.ai/api/alpha/decisions",
            extra={},
        )
        == "openrouter"
    )


@pytest.mark.parametrize(
    ("provider", "protocol", "endpoint", "adapter_module", "adapter_class"),
    [
        (
            "openai",
            "openai-decisions-v1",
            "https://api.openai.com/v1/decisions",
            "uagent.decision.openai",
            "OpenAIDecisionProvider",
        ),
        (
            "openrouter",
            "openrouter-alpha-decisions",
            "https://openrouter.ai/api/alpha/decisions",
            "uagent.decision.openrouter",
            "OpenRouterDecisionProvider",
        ),
    ],
)
def test_auto_passes_catalog_endpoint_and_key_to_native_adapters(
    monkeypatch, provider, protocol, endpoint, adapter_module, adapter_class
):
    capability = _capability(provider, endpoint, protocol=protocol)
    monkeypatch.setattr(
        "uagent.decision.catalog.get_capability",
        lambda *_args, **_kwargs: capability,
    )
    captured = {}

    class AdapterSpy:
        def __init__(self, *, settings, environ, client):
            captured.update(settings=settings, environ=environ, client=client)

    monkeypatch.setattr(f"{adapter_module}.{adapter_class}", AdapterSpy)
    client = object()
    CatalogDecisionProvider(
        settings=DecisionSettings("auto"),
        environ={
            "UAGENT_DECISION_MODEL": "catalog-model",
            "UAGENT_DECISION_API_KEY": "catalog-key",
        },
        client=client,
    )

    assert captured["settings"].provider == provider
    assert captured["client"] is client
    prefix = f"UAGENT_DECISION_{provider.upper()}_"
    assert captured["environ"][prefix + "DEPNAME"] == "catalog-model"
    assert captured["environ"][prefix + "BASE_URL"] == endpoint
    assert captured["environ"][prefix + "API_KEY"] == "catalog-key"


def test_auto_fails_closed_for_undocumented_chat_completion_decision_protocol():
    with pytest.raises(
        CatalogDecisionConfigurationError, match="does not yet implement"
    ):
        _select_adapter(
            provider="together",
            protocol="openai-compatible-chat-completions",
            endpoint="https://api.example.test/v1/chat/completions",
            extra={},
        )


def test_auto_requires_a_catalog_model_id():
    with pytest.raises(
        CatalogDecisionConfigurationError, match="UAGENT_DECISION_MODEL"
    ):
        CatalogDecisionProvider(
            settings=DecisionSettings("auto"),
            environ={},
            client=FakeClient(),
        )


def test_auto_does_not_guess_unknown_endpoint_protocol(monkeypatch):
    capability = _capability(
        "other-provider",
        "https://api.example.test/decide",
        protocol="other-decision-v7",
    )
    monkeypatch.setattr(
        "uagent.decision.catalog.get_capability",
        lambda *_args, **_kwargs: capability,
    )
    with pytest.raises(CatalogDecisionConfigurationError, match="does not yet have"):
        CatalogDecisionProvider(
            settings=DecisionSettings("auto"),
            environ={
                "UAGENT_DECISION_MODEL": "other-model",
                "UAGENT_DECISION_API_KEY": "api-key",
            },
            client=FakeClient(),
        )


def test_auto_goal_completion_uses_catalog_question_kinds(monkeypatch):
    capability = SimpleNamespace(
        decision=SimpleNamespace(question_kinds=("noul", "choice", "score")),
        supports=lambda feature: feature == "decision_output",
    )
    monkeypatch.setitem(
        sys.modules,
        "llmcapa",
        SimpleNamespace(get=lambda model, *, provider: capability),
    )
    provider = SimpleNamespace(
        name="microsoft",
        model="ticket-router-prod",
        catalog_model="Microsoft-Decision-1",
        uses_catalog_metadata=True,
    )

    assert provider_uses_atomic_goal_completion(provider) is True
    assert provider_supports_goal_completion(provider) is True


def test_non_catalog_provider_keeps_its_existing_goal_completion_contract(
    monkeypatch,
):
    capability = SimpleNamespace(
        decision=SimpleNamespace(question_kinds=("noul", "choice")),
        supports=lambda feature: feature == "decision_output",
    )
    monkeypatch.setitem(
        sys.modules,
        "llmcapa",
        SimpleNamespace(get=lambda *_args, **_kwargs: capability),
    )
    provider = SimpleNamespace(name="laya", model="laya-model")

    assert provider_uses_atomic_goal_completion(provider) is False
    assert provider_supports_goal_completion(provider) is True
