import sys
import types

import pytest

from uagent.decision import (
    DecisionAnswer,
    DecisionConfigurationError,
    DecisionQuestion,
    DecisionRequest,
    DecisionResult,
    DecisionSettings,
    configure_decision_settings,
    get_decision_settings,
    resolve_decision_settings,
)
from uagent.decision import registry
from uagent.util_common import parse_startup_args


@pytest.fixture(autouse=True)
def _reset_decision_settings():
    configure_decision_settings(environ={})
    yield
    configure_decision_settings(environ={})


def test_default_decision_provider_is_none():
    settings = resolve_decision_settings(environ={})

    assert settings == DecisionSettings(provider="none", source="default")
    assert settings.enabled is False


def test_decision_provider_resolves_from_environment():
    settings = resolve_decision_settings(environ={"UAGENT_DECISION_PROVIDER": "laya"})

    assert settings.provider == "laya"
    assert settings.source == "env"
    assert settings.enabled is True


def test_cli_decision_provider_overrides_environment():
    settings = resolve_decision_settings(
        cli_provider="typesafe",
        environ={"UAGENT_DECISION_PROVIDER": "laya"},
    )

    assert settings.provider == "typesafe"
    assert settings.source == "cli"


def test_invalid_environment_decision_provider_is_rejected():
    with pytest.raises(DecisionConfigurationError):
        resolve_decision_settings(
            environ={"UAGENT_DECISION_PROVIDER": "unknown-provider"},
        )


def test_inactive_provider_specific_settings_are_ignored():
    settings = resolve_decision_settings(
        environ={
            "UAGENT_DECISION_TYPESAFE_API_KEY": "not-used",
            "UAGENT_DECISION_LAYA_DEPNAME": "laya-multilingual",
        },
    )

    assert settings.provider == "none"


def test_configured_settings_are_shared_process_state():
    configured = configure_decision_settings(
        cli_provider="laya",
        environ={"UAGENT_DECISION_PROVIDER": "typesafe"},
    )

    assert get_decision_settings() is configured
    assert get_decision_settings().provider == "laya"


def test_none_factory_does_not_import_any_adapter(monkeypatch):
    def fail_import(_name):
        raise AssertionError("adapter import must not happen for provider=none")

    monkeypatch.setattr(registry.importlib, "import_module", fail_import)

    assert (
        registry.create_decision_provider(
            DecisionSettings(provider="none", source="default")
        )
        is None
    )


@pytest.mark.parametrize(
    ("provider_name", "module_name", "class_name"),
    [
        (
            "typesafe",
            "uagent.decision.typesafe",
            "TypeSafeDecisionProvider",
        ),
        (
            "openrouter",
            "uagent.decision.openrouter",
            "OpenRouterDecisionProvider",
        ),
        ("laya", "uagent.decision.laya", "LayaDecisionProvider"),
    ],
)
def test_non_none_factory_imports_only_selected_adapter(
    monkeypatch,
    provider_name,
    module_name,
    class_name,
):
    imported = []

    class FakeProvider:
        def __init__(self, *, settings, marker=None):
            self.settings = settings
            self.marker = marker

    def fake_import(name):
        imported.append(name)
        assert name == module_name
        return types.SimpleNamespace(**{class_name: FakeProvider})

    monkeypatch.setattr(registry.importlib, "import_module", fake_import)

    settings = DecisionSettings(provider=provider_name, source="env")
    provider = registry.create_decision_provider(settings, marker="ok")

    assert imported == [module_name]
    assert provider.settings is settings
    assert provider.marker == "ok"


def test_decision_result_serialization_omits_raw_by_default():
    question = DecisionQuestion(
        id="goal_status",
        kind="choice",
        instruction="Choose the current goal status.",
        choices=("COMPLETE", "CONTINUE"),
    )
    request = DecisionRequest(
        state={"goal": "finish the task"},
        questions=(question,),
    )
    result = DecisionResult(
        provider="laya",
        model="laya-multilingual",
        answers={
            "goal_status": DecisionAnswer(
                value="CONTINUE",
                confidence=0.7,
                calibrated=False,
            )
        },
        latency_ms=12.5,
        raw=object(),
    )

    assert request.to_dict()["questions"][0]["kind"] == "choice"
    payload = result.to_dict()
    assert payload["answers"]["goal_status"]["value"] == "CONTINUE"
    assert "raw" not in payload


def test_parse_startup_args_accepts_decision_provider(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["uag", "--decision-provider", "laya"],
    )

    args, unknown = parse_startup_args()

    assert args["decision_provider"] == "laya"
    assert unknown == []
