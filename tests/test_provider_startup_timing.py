"""Opt-in provider startup timings must preserve client creation semantics."""

import sys
from types import SimpleNamespace

import pytest

from uagent.providers import util_providers as providers


@pytest.mark.parametrize("enabled", ["0", "1"])
@pytest.mark.parametrize("fallback", [False, True])
def test_openai_client_startup_timing(monkeypatch, capsys, enabled, fallback):
    monkeypatch.setenv("UAGENT_STARTUP_TIMING", enabled)
    monkeypatch.setattr(providers, "detect_provider", lambda: "openai")
    monkeypatch.setattr(providers, "_ensure_provider_dependency", lambda provider: None)
    monkeypatch.setattr(providers, "get_model_name", lambda: "test-model")
    monkeypatch.setattr(providers, "_provider_api_key", lambda core, provider: "secret")
    monkeypatch.setattr(providers, "is_ssl_verify_disabled", lambda: False)
    monkeypatch.setattr(providers, "make_httpx_timeout", lambda: 10)
    monkeypatch.setattr(providers, "_register_httpx_client", lambda client: None)

    http_client = object()
    sdk_client = object()
    http_calls = []
    sdk_calls = []

    def make_http(**kwargs):
        http_calls.append(kwargs)
        if fallback and "event_hooks" in kwargs:
            raise TypeError("unsupported hooks")
        return http_client

    def make_sdk(**kwargs):
        sdk_calls.append(kwargs)
        if fallback and "http_client" in kwargs:
            raise TypeError("unsupported http_client")
        return sdk_client

    monkeypatch.setitem(sys.modules, "httpx", SimpleNamespace(Client=make_http))
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=make_sdk))
    core = SimpleNamespace(get_env_url=lambda name, default: default)

    assert providers.make_client(core) == ("openai", sdk_client, "test-model")
    assert http_calls[0]["timeout"] == 10
    assert "response" in http_calls[0]["event_hooks"]
    assert sdk_calls[0]["http_client"] is http_client
    assert len(http_calls) == len(sdk_calls) == (2 if fallback else 1)
    if fallback:
        assert "event_hooks" not in http_calls[1]
        assert "http_client" not in sdk_calls[1]

    output = capsys.readouterr().err
    if enabled == "0":
        assert output == ""
    else:
        for stage in (
            "provider.detect",
            "provider.dependency",
            "provider.model",
            "provider.openai.sdk_import",
            "provider.openai.credentials",
            "provider.openai.base_url",
            "provider.openai.http_client",
            "provider.httpx.import",
            "provider.httpx.timeout",
            "provider.httpx.client",
            "provider.httpx.register",
            "provider.openai.sdk_client",
        ):
            assert output.count(f"[startup-timing] detail.{stage}=") == 1
        assert "secret" not in output


def test_provider_dependency_failure_is_preserved(monkeypatch, capsys):
    monkeypatch.setenv("UAGENT_STARTUP_TIMING", "1")
    monkeypatch.setattr(providers, "detect_provider", lambda: "openai")

    def unavailable(provider):
        raise ImportError("SDK unavailable")

    monkeypatch.setattr(providers, "_ensure_provider_dependency", unavailable)
    with pytest.raises(ImportError, match="SDK unavailable"):
        providers.make_client(object())

    output = capsys.readouterr().err
    assert "detail.provider.dependency=" in output
    assert "detail.provider.model=" not in output
