from __future__ import annotations

from uagent import setup_cli


def test_setup_env_lines_emit_laya_decision_provider():
    state = setup_cli._WizardState(
        provider="openai",
        decision_provider="laya",
        decision_values={
            "UAGENT_DECISION_LAYA_DEPNAME": "laya-multilingual",
            "UAGENT_DECISION_LAYA_DEVICE": "auto",
        },
    )

    lines = setup_cli._env_lines_from_state(state)
    text = "\n".join(lines)

    assert "UAGENT_DECISION_PROVIDER=laya" in text
    assert "UAGENT_DECISION_LAYA_DEPNAME=laya-multilingual" in text
    assert "UAGENT_DECISION_LAYA_DEVICE=auto" in text
    assert "# UAGENT_DECISION_TYPESAFE_API_KEY=" in text


def test_setup_env_lines_emit_typesafe_decision_provider():
    state = setup_cli._WizardState(
        provider="openai",
        decision_provider="typesafe",
        decision_values={
            "UAGENT_DECISION_TYPESAFE_DEPNAME": "jev-latest",
            "UAGENT_DECISION_TYPESAFE_BASE_URL": "https://api.typesafe.ai",
            "UAGENT_DECISION_TYPESAFE_API_KEY": "secret-key",
        },
    )

    lines = setup_cli._env_lines_from_state(state)
    text = "\n".join(lines)

    assert "UAGENT_DECISION_PROVIDER=typesafe" in text
    assert "UAGENT_DECISION_TYPESAFE_DEPNAME=jev-latest" in text
    assert "UAGENT_DECISION_TYPESAFE_BASE_URL=https://api.typesafe.ai" in text
    assert "UAGENT_DECISION_TYPESAFE_API_KEY=secret-key" in text
    assert "# UAGENT_DECISION_LAYA_DEPNAME=laya-multilingual" in text


def test_setup_decision_provider_laya_defaults(monkeypatch):
    state = setup_cli._WizardState()
    choices = iter(["3"])
    values = iter(
        [
            ("ok", "laya-multilingual"),
            ("ok", "auto"),
        ]
    )

    monkeypatch.setattr(
        setup_cli,
        "_menu_choice",
        lambda *_args, **_kwargs: next(choices),
    )
    monkeypatch.setattr(
        setup_cli,
        "_ask_text",
        lambda *_args, **_kwargs: next(values),
    )

    status = setup_cli._ask_decision_provider(state)

    assert status == "ok"
    assert state.decision_provider == "laya"
    assert state.decision_values == {
        "UAGENT_DECISION_LAYA_DEPNAME": "laya-multilingual",
        "UAGENT_DECISION_LAYA_DEVICE": "auto",
    }


def test_setup_decision_provider_none_clears_provider_values(monkeypatch):
    state = setup_cli._WizardState(
        decision_provider="typesafe",
        decision_values={"UAGENT_DECISION_TYPESAFE_API_KEY": "secret"},
    )
    monkeypatch.setattr(
        setup_cli,
        "_menu_choice",
        lambda *_args, **_kwargs: "1",
    )

    status = setup_cli._ask_decision_provider(state)

    assert status == "ok"
    assert state.decision_provider == "none"
    assert state.decision_values == {}


def test_setup_laya_install_uses_shared_auto_install(monkeypatch):
    state = setup_cli._WizardState(decision_provider="laya")
    calls = []

    monkeypatch.setattr(
        "uagent._pip_auto.install_with_status",
        lambda *args, **kwargs: calls.append((args, kwargs)) or True,
    )

    assert setup_cli._install_selected_decision_runtime(state) is True
    assert calls == [
        (
            ("laya", "laya"),
            {
                "display_name": "laya",
                "version_spec": ">=0.3.23,<0.4",
            },
        )
    ]


def test_setup_non_laya_does_not_install(monkeypatch):
    state = setup_cli._WizardState(decision_provider="typesafe")

    def fail(*_args, **_kwargs):
        raise AssertionError("installer must not run")

    monkeypatch.setattr("uagent._pip_auto.install_with_status", fail)

    assert setup_cli._install_selected_decision_runtime(state) is True


def test_setup_laya_install_honors_loaded_auto_install_policy(monkeypatch):
    state = setup_cli._WizardState(
        decision_provider="laya",
        values={"UAGENT_AUTO_INSTALL": "off"},
    )
    seen = []

    monkeypatch.delenv("UAGENT_AUTO_INSTALL", raising=False)

    def fake_install(*_args, **_kwargs):
        import os

        seen.append(os.environ.get("UAGENT_AUTO_INSTALL"))
        return False

    monkeypatch.setattr("uagent._pip_auto.install_with_status", fake_install)

    assert setup_cli._install_selected_decision_runtime(state) is False
    assert seen == ["off"]

    import os

    assert "UAGENT_AUTO_INSTALL" not in os.environ


def test_setup_env_preserves_auto_install_policy():
    state = setup_cli._WizardState(
        provider="openai",
        values={"UAGENT_AUTO_INSTALL": "prompt"},
    )

    text = "\n".join(setup_cli._env_lines_from_state(state))

    assert "UAGENT_AUTO_INSTALL=prompt" in text
