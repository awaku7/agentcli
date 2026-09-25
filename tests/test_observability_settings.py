from uagent.runtime.observability.settings import (
    ObservabilitySettings,
    _reset_observability_settings_for_tests,
    consume_otel_cli_flags,
    consume_process_otel_cli_flags,
    get_observability_settings,
    refresh_observability_settings,
    set_observability_entrypoint_override,
)


def setup_function():
    _reset_observability_settings_for_tests()


def test_observability_defaults_off():
    settings = ObservabilitySettings.resolve(environ={})
    assert settings.enabled is False
    assert settings.capture_content is False
    assert settings.enabled_source == "default"
    assert settings.capture_content_source == "default"


def test_observability_environment_fallback():
    settings = ObservabilitySettings.resolve(
        environ={
            "UAGENT_OTEL_ENABLED": "yes",
            "UAGENT_OTEL_CAPTURE_CONTENT": "1",
        }
    )
    assert settings.enabled is True
    assert settings.capture_content is True
    assert settings.enabled_source == "environment"
    assert settings.capture_content_source == "environment"


def test_explicit_observability_setting_overrides_environment():
    settings = ObservabilitySettings.resolve(
        explicit_enabled=False,
        explicit_capture_content=False,
        environ={
            "UAGENT_OTEL_ENABLED": "1",
            "UAGENT_OTEL_CAPTURE_CONTENT": "true",
        },
    )
    assert settings.enabled is False
    assert settings.capture_content is False
    assert settings.enabled_source == "explicit"
    assert settings.capture_content_source == "explicit"


def test_invalid_environment_value_fails_closed():
    settings = ObservabilitySettings.resolve(
        environ={"UAGENT_OTEL_ENABLED": "unexpected"}
    )
    assert settings.enabled is False


def test_consume_otel_cli_flags_preserves_other_arguments():
    enabled, remaining = consume_otel_cli_flags(
        ["--workdir", "C:/tmp", "--otel", "input.txt"]
    )
    assert enabled is True
    assert remaining == ["--workdir", "C:/tmp", "input.txt"]


def test_last_otel_cli_flag_wins():
    enabled, remaining = consume_otel_cli_flags(["--otel", "input.txt", "--no-otel"])
    assert enabled is False
    assert remaining == ["input.txt"]


def test_process_flags_are_removed_before_launcher_parser():
    argv = ["uagw", "--host", "127.0.0.1", "--otel"]
    enabled = consume_process_otel_cli_flags(argv)

    assert enabled is True
    assert argv == ["uagw", "--host", "127.0.0.1"]
    settings = refresh_observability_settings(environ={"UAGENT_OTEL_ENABLED": "0"})
    assert settings.enabled is True
    assert settings.enabled_source == "explicit"


def test_launcher_without_otel_flag_does_not_clear_existing_override():
    first_argv = ["uag", "--no-otel"]
    consume_process_otel_cli_flags(first_argv)

    second_argv = ["uaga", "--host", "0.0.0.0"]
    consume_process_otel_cli_flags(second_argv)

    settings = refresh_observability_settings(environ={"UAGENT_OTEL_ENABLED": "1"})
    assert settings.enabled is False
    assert settings.enabled_source == "explicit"


def test_refresh_uses_environment_loaded_after_entrypoint_parse():
    set_observability_entrypoint_override(None)
    settings = refresh_observability_settings(environ={"UAGENT_OTEL_ENABLED": "1"})

    assert settings.enabled is True
    assert settings.enabled_source == "environment"
    assert get_observability_settings() == settings


def test_reload_dotenv_refreshes_observability_after_project_env(monkeypatch, tmp_path):
    from uagent.runtime import runtime_init

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("UAGENT_OTEL_ENABLED", raising=False)
    monkeypatch.setattr(runtime_init, "_STARTUP_UAGENT_ENV_SNAPSHOT", {})
    (tmp_path / ".env").write_text("UAGENT_OTEL_ENABLED=1\n", encoding="utf-8")

    runtime_init.reload_dotenv_custom()

    settings = get_observability_settings()
    assert settings.enabled is True
    assert settings.enabled_source == "environment"


def test_explicit_override_wins_after_project_dotenv_reload(monkeypatch, tmp_path):
    from uagent.runtime import runtime_init

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("UAGENT_OTEL_ENABLED", raising=False)
    monkeypatch.setattr(runtime_init, "_STARTUP_UAGENT_ENV_SNAPSHOT", {})
    (tmp_path / ".env").write_text("UAGENT_OTEL_ENABLED=1\n", encoding="utf-8")
    set_observability_entrypoint_override(False)

    runtime_init.reload_dotenv_custom()

    settings = get_observability_settings()
    assert settings.enabled is False
    assert settings.enabled_source == "explicit"
