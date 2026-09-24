from uagent.runtime.observability.dependencies import (
    OTEL_DEPENDENCIES,
    OTEL_VERSION,
    _reset_dependency_state_for_tests,
    ensure_otel_dependencies,
)
from uagent.runtime.observability.settings import ObservabilitySettings


def setup_function():
    _reset_dependency_state_for_tests()


def teardown_function():
    _reset_dependency_state_for_tests()


def test_disabled_observability_never_invokes_installer():
    calls = []

    def installer(*args, **kwargs):
        calls.append((args, kwargs))
        return True

    ready = ensure_otel_dependencies(
        ObservabilitySettings(enabled=False), installer=installer
    )

    assert ready is False
    assert calls == []


def test_enabled_observability_installs_supported_otel_set_once():
    calls = []

    def installer(package_name, module_name, **kwargs):
        calls.append((package_name, module_name, kwargs))
        return True

    settings = ObservabilitySettings(enabled=True)
    assert ensure_otel_dependencies(settings, installer=installer) is True
    assert ensure_otel_dependencies(settings, installer=installer) is True

    assert len(calls) == len(OTEL_DEPENDENCIES)
    assert [call[0] for call in calls] == [
        "opentelemetry-api",
        "opentelemetry-sdk",
        "opentelemetry-exporter-otlp",
    ]
    assert all(call[2]["version_spec"] == f"=={OTEL_VERSION}" for call in calls)


def test_dependency_failure_is_cached_and_stops_at_first_failure():
    calls = []

    def installer(package_name, module_name, **kwargs):
        calls.append(package_name)
        return package_name != "opentelemetry-sdk"

    settings = ObservabilitySettings(enabled=True)
    assert ensure_otel_dependencies(settings, installer=installer) is False
    assert ensure_otel_dependencies(settings, installer=installer) is False
    assert calls == ["opentelemetry-api", "opentelemetry-sdk"]
