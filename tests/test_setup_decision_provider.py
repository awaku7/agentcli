import os

from uagent import setup_cli


def _state(provider, values=None):
    return setup_cli._WizardState(
        provider="openai",
        decision_provider=provider,
        decision_values=dict(values or {}),
    )


def test_setup_defaults_decision_provider_to_openai_for_openai_llm(monkeypatch):
    state = _state("none")
    seen = {}

    def fake_menu(_title, options, *, default_index, allow_back):
        seen["options"] = options
        seen["default_index"] = default_index
        return str(default_index)

    monkeypatch.setattr(setup_cli, "_menu_choice", fake_menu)
    monkeypatch.setattr(
        setup_cli,
        "_ask_text",
        lambda _label, *, default, required, allow_back: ("ok", default),
    )

    assert setup_cli._ask_decision_provider(state) == "ok"
    assert seen["options"][seen["default_index"] - 1].startswith("openai ")
    assert state.decision_provider == "openai"


def test_setup_keeps_none_as_default_for_other_llm_providers(monkeypatch):
    state = _state("none")
    state.provider = "azure"
    seen = {}

    def fake_menu(_title, options, *, default_index, allow_back):
        seen["options"] = options
        seen["default_index"] = default_index
        return str(default_index)

    monkeypatch.setattr(setup_cli, "_menu_choice", fake_menu)

    assert setup_cli._ask_decision_provider(state) == "ok"
    assert seen["options"][seen["default_index"] - 1].startswith("none ")
    assert state.decision_provider == "none"


def test_setup_preserves_explicit_none_for_openai_llm(monkeypatch):
    state = _state("none")
    state.values = {"UAGENT_DECISION_PROVIDER": "none"}
    seen = {}

    def fake_menu(_title, _options, *, default_index, allow_back):
        seen["default_index"] = default_index
        return str(default_index)

    monkeypatch.setattr(setup_cli, "_menu_choice", fake_menu)

    assert setup_cli._ask_decision_provider(state) == "ok"
    assert seen["default_index"] == 1
    assert state.decision_provider == "none"


def test_setup_env_emits_decision_provider_none():
    lines = setup_cli._env_lines_from_state(_state("none"))
    text = "\n".join(lines)

    assert "UAGENT_DECISION_PROVIDER=none" in text
    assert "# UAGENT_DECISION_TYPESAFE_API_KEY=" in text
    assert "# UAGENT_DECISION_OPENAI_DEPNAME=gpt-6-luna" in text
    assert "# UAGENT_DECISION_LAYA_DEPNAME=laya-multilingual" in text


def test_setup_env_emits_typesafe_decision_settings():
    lines = setup_cli._env_lines_from_state(
        _state(
            "typesafe",
            {
                "UAGENT_DECISION_TYPESAFE_DEPNAME": "jev-latest",
                "UAGENT_DECISION_TYPESAFE_BASE_URL": "https://api.typesafe.ai",
                "UAGENT_DECISION_TYPESAFE_API_KEY": "secret",
            },
        )
    )
    text = "\n".join(lines)

    assert "UAGENT_DECISION_PROVIDER=typesafe" in text
    assert "UAGENT_DECISION_TYPESAFE_DEPNAME=jev-latest" in text
    assert "UAGENT_DECISION_TYPESAFE_BASE_URL=https://api.typesafe.ai" in text
    assert "UAGENT_DECISION_TYPESAFE_API_KEY=secret" in text
    assert "# UAGENT_DECISION_LAYA_DEVICE=auto" in text


def test_setup_env_emits_openrouter_decision_settings():
    lines = setup_cli._env_lines_from_state(
        _state(
            "openrouter",
            {
                "UAGENT_DECISION_OPENROUTER_DEPNAME": "~typesafe/jev-latest",
                "UAGENT_DECISION_OPENROUTER_BASE_URL": "https://openrouter.ai/api",
                "UAGENT_DECISION_OPENROUTER_API_KEY": "",
            },
        )
    )
    text = "\n".join(lines)

    assert "UAGENT_DECISION_PROVIDER=openrouter" in text
    assert "UAGENT_DECISION_OPENROUTER_DEPNAME=~typesafe/jev-latest" in text
    assert "UAGENT_DECISION_OPENROUTER_BASE_URL=https://openrouter.ai/api" in text
    assert "UAGENT_DECISION_OPENROUTER_API_KEY=" in text
    assert "# UAGENT_DECISION_TYPESAFE_API_KEY=" in text
    assert "# UAGENT_DECISION_LAYA_DEVICE=auto" in text


def test_setup_env_emits_openai_decision_settings():
    lines = setup_cli._env_lines_from_state(
        _state(
            "openai",
            {
                "UAGENT_DECISION_OPENAI_DEPNAME": "gpt-6-luna",
                "UAGENT_DECISION_OPENAI_BASE_URL": "https://api.openai.com/v1",
                "UAGENT_DECISION_OPENAI_API_KEY": "secret",
            },
        )
    )
    text = "\n".join(lines)

    assert "UAGENT_DECISION_PROVIDER=openai" in text
    assert "UAGENT_DECISION_OPENAI_DEPNAME=gpt-6-luna" in text
    assert "UAGENT_DECISION_OPENAI_BASE_URL=https://api.openai.com/v1" in text
    assert "UAGENT_DECISION_OPENAI_API_KEY=secret" in text
    assert "# UAGENT_DECISION_TYPESAFE_API_KEY=" in text


def test_setup_env_emits_laya_decision_settings():
    lines = setup_cli._env_lines_from_state(
        _state(
            "laya",
            {
                "UAGENT_DECISION_LAYA_DEPNAME": "laya-multilingual",
                "UAGENT_DECISION_LAYA_DEVICE": "cuda",
            },
        )
    )
    text = "\n".join(lines)

    assert "UAGENT_DECISION_PROVIDER=laya" in text
    assert "UAGENT_DECISION_LAYA_DEPNAME=laya-multilingual" in text
    assert "UAGENT_DECISION_LAYA_DEVICE=cuda" in text
    assert "# UAGENT_DECISION_TYPESAFE_API_KEY=" in text


def test_setup_preserves_auto_install_policy_in_generated_env():
    st = _state("none")
    st.values = {"UAGENT_AUTO_INSTALL": "off"}

    text = "\n".join(setup_cli._env_lines_from_state(st))

    assert "UAGENT_AUTO_INSTALL=off" in text


def test_setup_laya_runtime_uses_configured_auto_install_policy(monkeypatch):
    attempts = []
    st = _state("laya")
    st.values = {"UAGENT_AUTO_INSTALL": "off"}
    monkeypatch.setenv("UAGENT_AUTO_INSTALL", "allow")

    from uagent import _pip_auto

    def fake_install(package, module, **kwargs):
        attempts.append(
            (
                package,
                module,
                kwargs,
                os.environ.get("UAGENT_AUTO_INSTALL"),
            )
        )
        return False

    monkeypatch.setattr(_pip_auto, "install_with_status", fake_install)

    assert not setup_cli._ensure_decision_provider_runtime(st)
    assert attempts == [
        (
            "laya",
            "laya",
            {
                "display_name": "Laya Decision Provider",
                "version_spec": ">=0.3.23,<0.4",
            },
            "off",
        )
    ]
    assert os.environ["UAGENT_AUTO_INSTALL"] == "allow"


def test_setup_installs_laya_runtime_with_shared_policy(monkeypatch):
    attempts = []

    from uagent import _pip_auto

    monkeypatch.setattr(
        _pip_auto,
        "install_with_status",
        lambda package, module, **kwargs: attempts.append((package, module, kwargs))
        or True,
    )

    assert setup_cli._ensure_decision_provider_runtime(_state("laya"))
    assert attempts == [
        (
            "laya",
            "laya",
            {
                "display_name": "Laya Decision Provider",
                "version_spec": ">=0.3.23,<0.4",
            },
        )
    ]


def test_setup_skips_runtime_install_for_non_laya(monkeypatch):
    from uagent import _pip_auto

    def fail_install(*_args, **_kwargs):
        raise AssertionError("installer must not run")

    monkeypatch.setattr(_pip_auto, "install_with_status", fail_install)

    assert setup_cli._ensure_decision_provider_runtime(_state("none"))
    assert setup_cli._ensure_decision_provider_runtime(_state("typesafe"))
    assert setup_cli._ensure_decision_provider_runtime(_state("openrouter"))
    assert setup_cli._ensure_decision_provider_runtime(_state("openai"))
