from uagent.runtime.observability.settings import (
    ObservabilitySettings,
    _reset_observability_settings_for_tests,
    consume_observability_cli_flags,
    consume_process_otel_cli_flags,
    refresh_observability_settings,
)


def setup_function():
    _reset_observability_settings_for_tests()


def teardown_function():
    _reset_observability_settings_for_tests()


def test_phase4_defaults_are_independently_off():
    settings = ObservabilitySettings.resolve(environ={})

    assert settings.enabled is False
    assert settings.capture_content is False
    assert settings.capture_categories == frozenset()
    assert settings.capture_max_field_chars == 2048
    assert settings.capture_max_span_chars == 8192
    assert settings.pseudonymous_correlation is False
    assert settings.provider_instrumentation == frozenset()
    assert settings.trace_query_enabled is False


def test_capture_environment_resolves_closed_categories_and_bounds():
    settings = ObservabilitySettings.resolve(
        environ={
            "UAGENT_OTEL_ENABLED": "YES",
            "UAGENT_OTEL_CAPTURE_CONTENT": "\tOn ",
            "UAGENT_OTEL_CAPTURE_CATEGORIES": "user_input, assistant_output,user_input",
            "UAGENT_OTEL_CAPTURE_MAX_FIELD_CHARS": "4096",
            "UAGENT_OTEL_CAPTURE_MAX_SPAN_CHARS": "12000",
        }
    )

    assert settings.capture_content is True
    assert settings.capture_categories == frozenset({"user_input", "assistant_output"})
    assert settings.capture_max_field_chars == 4096
    assert settings.capture_max_span_chars == 12000


def test_invalid_category_disables_content_without_environment_fallback():
    settings = ObservabilitySettings.resolve(
        explicit_capture_categories="user_input,unknown",
        explicit_capture_content=True,
        explicit_enabled=True,
        environ={"UAGENT_OTEL_CAPTURE_CATEGORIES": "user_input"},
    )

    assert settings.capture_content is False
    assert settings.capture_categories == frozenset()


def test_invalid_bound_grammar_and_inconsistent_bounds_disable_content():
    for field_value, span_value in [
        ("+64", "8192"),
        ("064", "8192"),
        ("６４", "8192"),
        ("63", "8192"),
        ("2048", "02048"),
        ("4096", "2048"),
    ]:
        settings = ObservabilitySettings.resolve(
            environ={
                "UAGENT_OTEL_ENABLED": "1",
                "UAGENT_OTEL_CAPTURE_CONTENT": "1",
                "UAGENT_OTEL_CAPTURE_CATEGORIES": "user_input",
                "UAGENT_OTEL_CAPTURE_MAX_FIELD_CHARS": field_value,
                "UAGENT_OTEL_CAPTURE_MAX_SPAN_CHARS": span_value,
            }
        )
        assert settings.capture_content is False


def test_invalid_higher_precedence_boolean_fails_closed():
    settings = ObservabilitySettings.resolve(
        explicit_enabled=True,
        explicit_capture_content=1,  # type: ignore[arg-type]
        explicit_capture_categories="user_input",
        environ={"UAGENT_OTEL_CAPTURE_CONTENT": "1"},
    )

    assert settings.capture_content is False
    assert settings.capture_content_source == "explicit-invalid"


def test_core_no_otel_is_authoritative_over_phase4_features():
    settings = ObservabilitySettings.resolve(
        explicit_enabled=False,
        explicit_capture_content=True,
        explicit_capture_categories="user_input",
        explicit_pseudonymous_correlation=True,
        explicit_provider_instrumentation="openai,claude",
        explicit_trace_query_enabled=True,
    )

    assert settings.capture_content is False
    assert settings.pseudonymous_correlation is False
    assert settings.provider_instrumentation == frozenset()
    assert settings.trace_query_enabled is False


def test_provider_selector_keeps_valid_siblings_and_ignores_unknowns():
    settings = ObservabilitySettings.resolve(
        explicit_enabled=True,
        explicit_provider_instrumentation="openai,anthropic,,claude",
    )

    assert settings.provider_instrumentation == frozenset({"openai", "claude"})


def test_phase4_cli_surface_is_consumed_and_last_boolean_wins():
    overrides, remaining = consume_observability_cli_flags(
        [
            "--otel",
            "--otel-capture-content",
            "--otel-capture-categories",
            "user_input,assistant_output",
            "--otel-capture-max-field-chars",
            "1024",
            "--otel-capture-max-span-chars",
            "4096",
            "--otel-pseudonymous-correlation",
            "--otel-deployment-scope",
            "prod",
            "--otel-correlation-key-name",
            "observability/correlation",
            "--otel-correlation-key-version",
            "v2",
            "--otel-provider-instrumentation",
            "openai,claude",
            "--otel-trace-query",
            "--no-otel-trace-query",
            "--host",
            "127.0.0.1",
        ]
    )

    assert overrides.enabled is True
    assert overrides.capture_content is True
    assert overrides.capture_categories == "user_input,assistant_output"
    assert overrides.capture_max_field_chars == "1024"
    assert overrides.capture_max_span_chars == "4096"
    assert overrides.pseudonymous_correlation is True
    assert overrides.deployment_scope == "prod"
    assert overrides.correlation_key_version == "v2"
    assert overrides.provider_instrumentation == "openai,claude"
    assert overrides.trace_query_enabled is False
    assert remaining == ["--host", "127.0.0.1"]


def test_process_phase4_cli_survives_dotenv_refresh_and_strips_launcher_argv():
    argv = [
        "uagw",
        "--otel",
        "--otel-capture-content",
        "--otel-capture-categories",
        "user_input",
        "--host",
        "0.0.0.0",
    ]

    consume_process_otel_cli_flags(argv)
    settings = refresh_observability_settings(
        environ={
            "UAGENT_OTEL_ENABLED": "0",
            "UAGENT_OTEL_CAPTURE_CONTENT": "0",
            "UAGENT_OTEL_CAPTURE_CATEGORIES": "assistant_output",
        }
    )

    assert argv == ["uagw", "--host", "0.0.0.0"]
    assert settings.enabled is True
    assert settings.capture_content is True
    assert settings.capture_categories == frozenset({"user_input"})


def test_missing_cli_value_is_consumed_and_fails_closed():
    argv = [
        "uag",
        "--otel",
        "--otel-capture-content",
        "--otel-capture-categories",
    ]

    consume_process_otel_cli_flags(argv)
    settings = refresh_observability_settings(
        environ={"UAGENT_OTEL_CAPTURE_CATEGORIES": "user_input"}
    )

    assert argv == ["uag"]
    assert settings.capture_content is False
