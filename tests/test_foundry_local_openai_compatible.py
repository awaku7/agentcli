from __future__ import annotations

import pytest

from uagent.llmcapa_util import current_model, provider_candidates
from uagent.providers.llm_foundry_local import (
    make_foundry_local_client,
    normalize_foundry_local_base_url,
)
from uagent.providers.provider_caps import DEFAULT_PROVIDER_REGISTRY
from uagent.providers.runtime_registry import supports_provider_runtime
from uagent.providers.util_providers import get_model_name


def test_foundry_local_url_is_loopback_and_normalized() -> None:
    assert (
        normalize_foundry_local_base_url("http://localhost:5272")
        == "http://localhost:5272/v1"
    )
    assert (
        normalize_foundry_local_base_url("http://127.0.0.1:5272/v1/")
        == "http://127.0.0.1:5272/v1"
    )
    with pytest.raises(ValueError):
        normalize_foundry_local_base_url("https://example.com/v1")


def test_foundry_local_provider_wiring(monkeypatch) -> None:
    spec = DEFAULT_PROVIDER_REGISTRY.resolve("foundry-local")
    assert spec.auth_requirement == "local_endpoint"
    assert "responses" in spec.capabilities
    assert supports_provider_runtime("foundry-local") is True
    assert provider_candidates("foundry-local")[:2] == [
        "foundry-local",
        "foundry_local",
    ]
    monkeypatch.setenv("UAGENT_PROVIDER", "foundry-local")
    monkeypatch.setenv("UAGENT_FOUNDRY_LOCAL_DEPNAME", "phi-local")
    assert get_model_name() == "phi-local"
    assert current_model("foundry-local") == "phi-local"


def test_foundry_local_client_uses_openai_compatible_endpoint() -> None:
    class Core:
        @staticmethod
        def get_env(name: str):
            if name == "UAGENT_FOUNDRY_LOCAL_BASE_URL":
                return "http://localhost:5272"
            return ""

    client = make_foundry_local_client(Core())
    try:
        assert str(client.base_url).rstrip("/") == "http://localhost:5272/v1"
    finally:
        client.close()


def test_foundry_local_responses_is_decided_by_llmcapa(monkeypatch) -> None:
    import uagent.llmcapa_util as llmcapa_util

    monkeypatch.setattr(
        llmcapa_util,
        "supports_responses_api",
        lambda *_args, **_kwargs: False,
    )
    assert not llmcapa_util.provider_allows_responses_api("foundry-local", "phi-local")
    monkeypatch.setattr(
        llmcapa_util,
        "supports_responses_api",
        lambda *_args, **_kwargs: True,
    )
    assert llmcapa_util.provider_allows_responses_api("foundry-local", "phi-local")


def test_explicit_responses_respects_llmcapa_false(monkeypatch) -> None:
    import uagent.llmcapa_util as llmcapa_util
    from uagent.llm_round_helpers import _resolve_round_runtime_flags

    monkeypatch.setenv("UAGENT_RESPONSES", "1")
    monkeypatch.setattr(
        llmcapa_util,
        "provider_allows_responses_api",
        lambda *_args, **_kwargs: False,
    )
    use_responses, _streaming = _resolve_round_runtime_flags(
        tr_cfg=None,
        core=object(),
        provider="foundry-local",
        depname="phi-local",
    )
    assert use_responses is False
