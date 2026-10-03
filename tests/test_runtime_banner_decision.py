from __future__ import annotations

from types import SimpleNamespace

import pytest

from uagent.decision import settings
from uagent.runtime import runtime_banner


@pytest.mark.parametrize(
    "provider,model",
    [
        ("none", "-"),
        ("typesafe", "jev-latest"),
        ("openrouter", "~typesafe/jev-latest"),
        ("laya", "laya-multilingual"),
    ],
)
def test_startup_banner_shows_resolved_decision_provider_without_initializing(
    monkeypatch, provider, model
):
    monkeypatch.setattr(
        settings, "_current_settings", settings.DecisionSettings(provider, "cli")
    )
    # A conflicting environment provider must not override the resolved CLI choice.
    monkeypatch.setenv(
        "UAGENT_DECISION_PROVIDER", "laya" if provider != "laya" else "none"
    )
    monkeypatch.setenv("UAGENT_PROVIDER", "openai")
    for name in ("TYPESAFE", "OPENROUTER", "LAYA"):
        monkeypatch.delenv(f"UAGENT_DECISION_{name}_DEPNAME", raising=False)
        monkeypatch.delenv(f"UAGENT_DECISION_{name}_API_KEY", raising=False)
    monkeypatch.setattr(runtime_banner, "_", lambda text: text)
    monkeypatch.setattr(runtime_banner, "_startup_optional_model_infos", lambda: [])

    def fail_factory(*args, **kwargs):
        raise AssertionError("banner must not initialize a decision adapter")

    import uagent.decision

    monkeypatch.setattr(uagent.decision, "create_decision_provider", fail_factory)
    banner = runtime_banner.build_startup_banner(
        core=SimpleNamespace(), workdir="workspace", workdir_source="cli"
    )
    assert (
        banner.splitlines()[1]
        == f"[INFO] Decision Provider = {provider}; model = {model}"
    )
    assert banner.count("Decision Provider") == 1


@pytest.mark.parametrize("provider", ["typesafe", "openrouter", "laya"])
@pytest.mark.parametrize(
    "value,expected", [("  custom-model  ", "custom-model"), ("  ", None)]
)
def test_decision_banner_model_override_and_blank_default(
    monkeypatch, provider, value, expected
):
    monkeypatch.setattr(
        settings, "_current_settings", settings.DecisionSettings(provider)
    )
    monkeypatch.setenv(f"UAGENT_DECISION_{provider.upper()}_DEPNAME", value)
    defaults = {
        "typesafe": "jev-latest",
        "openrouter": "~typesafe/jev-latest",
        "laya": "laya-multilingual",
    }
    assert runtime_banner._decision_model_info() == (
        provider,
        expected or defaults[provider],
    )
