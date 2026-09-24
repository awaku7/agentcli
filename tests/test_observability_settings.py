from uagent.runtime.observability.settings import (
    ObservabilitySettings,
    consume_otel_cli_flags,
)


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
    enabled, remaining = consume_otel_cli_flags(
        ["--otel", "input.txt", "--no-otel"]
    )
    assert enabled is False
    assert remaining == ["input.txt"]
