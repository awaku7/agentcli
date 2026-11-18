from __future__ import annotations

import types
from types import SimpleNamespace

import pytest

from uagent import env_validate
from uagent.providers import util_providers


@pytest.fixture()
def clean_vertex_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "UAGENT_PROVIDER",
        "UAGENT_VERTEXAI_API_KEY",
        "UAGENT_VERTEXAI_DEPNAME",
        "UAGENT_VERTEXAI_PROJECT",
        "UAGENT_VERTEXAI_LOCATION",
        "UAGENT_GOOGLE_CREDENTIALS",
        "UAGENT_GOOGLE_LOCATION",
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_CLOUD_LOCATION",
        "GOOGLE_APPLICATION_CREDENTIALS",
    ):
        monkeypatch.delenv(key, raising=False)


def test_validate_startup_env_vertexai_allows_iam_without_api_key(
    clean_vertex_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UAGENT_PROVIDER", "vertexai")
    monkeypatch.setenv("UAGENT_VERTEXAI_DEPNAME", "gemini-2.5-flash")
    monkeypatch.setenv("UAGENT_VERTEXAI_PROJECT", "my-gcp-project")

    provider, missing, warnings = env_validate.validate_startup_env()

    assert provider == "vertexai"
    assert missing == []
    assert isinstance(warnings, list)


def test_validate_startup_env_vertexai_allows_google_application_credentials(
    clean_vertex_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UAGENT_PROVIDER", "vertexai")
    monkeypatch.setenv("UAGENT_VERTEXAI_DEPNAME", "gemini-2.5-flash")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/adc.json")

    provider, missing, _warnings = env_validate.validate_startup_env()

    assert provider == "vertexai"
    assert missing == []


def test_validate_startup_env_vertexai_allows_gcloud_adc_without_env(
    clean_vertex_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UAGENT_PROVIDER", "vertexai")
    monkeypatch.setenv("UAGENT_VERTEXAI_DEPNAME", "gemini-2.5-flash")

    fake_google = types.ModuleType("google")
    fake_auth = types.ModuleType("google.auth")
    fake_auth.default = lambda: (object(), "adc-project")
    fake_google.auth = fake_auth
    monkeypatch.setitem(__import__("sys").modules, "google", fake_google)
    monkeypatch.setitem(__import__("sys").modules, "google.auth", fake_auth)

    provider, missing, _warnings = env_validate.validate_startup_env()

    assert provider == "vertexai"
    assert missing == []


def test_validate_startup_env_vertexai_requires_api_key_or_iam(
    clean_vertex_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UAGENT_PROVIDER", "vertexai")
    monkeypatch.setenv("UAGENT_VERTEXAI_DEPNAME", "gemini-2.5-flash")

    fake_google = types.ModuleType("google")
    fake_auth = types.ModuleType("google.auth")

    def _raise_adc():
        raise RuntimeError("no adc")

    fake_auth.default = _raise_adc
    fake_google.auth = fake_auth
    monkeypatch.setitem(__import__("sys").modules, "google", fake_google)
    monkeypatch.setitem(__import__("sys").modules, "google.auth", fake_auth)

    provider, missing, _warnings = env_validate.validate_startup_env()

    assert provider == "vertexai"
    assert [m.name for m in missing] == ["UAGENT_VERTEXAI_API_KEY"]


def test_make_client_vertexai_with_project_and_adc(
    clean_vertex_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UAGENT_PROVIDER", "vertexai")
    monkeypatch.setenv("UAGENT_VERTEXAI_DEPNAME", "gemini-2.5-flash")
    monkeypatch.setenv("UAGENT_VERTEXAI_PROJECT", "my-gcp-project")

    captured: list[dict] = []

    class FakeClient:
        def __init__(self, **kwargs):
            captured.append(kwargs)

    fake_google = types.ModuleType("google")
    fake_genai = types.ModuleType("google.genai")
    fake_genai.Client = FakeClient
    fake_google.genai = fake_genai
    monkeypatch.setitem(__import__("sys").modules, "google", fake_google)
    monkeypatch.setitem(__import__("sys").modules, "google.genai", fake_genai)

    monkeypatch.setattr(util_providers, "make_httpx_client", lambda: None)

    provider, _client, model_name = util_providers.make_client(SimpleNamespace())

    assert provider == "vertexai"
    assert model_name == "gemini-2.5-flash"
    assert captured == [
        {
            "vertexai": True,
            "project": "my-gcp-project",
            "location": "global",
        }
    ]


def test_make_client_vertexai_with_credentials_file(
    clean_vertex_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UAGENT_PROVIDER", "vertexai")
    monkeypatch.setenv("UAGENT_VERTEXAI_DEPNAME", "gemini-2.5-flash")
    monkeypatch.setenv("UAGENT_GOOGLE_CREDENTIALS", "/tmp/sa.json")
    monkeypatch.setenv("UAGENT_GOOGLE_LOCATION", "asia-northeast1")

    captured: list[dict] = []
    sentinel_creds = object()

    class FakeClient:
        def __init__(self, **kwargs):
            captured.append(kwargs)

    fake_google = types.ModuleType("google")
    fake_genai = types.ModuleType("google.genai")
    fake_genai.Client = FakeClient
    fake_auth = types.ModuleType("google.auth")
    fake_auth.load_credentials_from_file = lambda path, scopes=None: (
        sentinel_creds,
        "detected-project",
    )
    fake_google.genai = fake_genai
    fake_google.auth = fake_auth
    monkeypatch.setitem(__import__("sys").modules, "google", fake_google)
    monkeypatch.setitem(__import__("sys").modules, "google.genai", fake_genai)
    monkeypatch.setitem(__import__("sys").modules, "google.auth", fake_auth)

    monkeypatch.setattr(util_providers, "make_httpx_client", lambda: None)

    provider, _client, model_name = util_providers.make_client(SimpleNamespace())

    assert provider == "vertexai"
    assert model_name == "gemini-2.5-flash"
    assert captured == [
        {
            "vertexai": True,
            "credentials": sentinel_creds,
            "project": "detected-project",
            "location": "asia-northeast1",
        }
    ]
