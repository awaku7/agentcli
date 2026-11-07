from __future__ import annotations

import pytest

from uagent.runtime.identity_context import (
    IdentityContext,
    TurnContext,
    bind_turn_context,
)
from uagent.runtime.observability.settings import ObservabilitySettings
from uagent.runtime.observability.user_identity import user_attributes


def _turn(identity, entry_point="web"):
    return TurnContext.from_identity(identity, entry_point=entry_point)


def test_local_cli_uses_os_account_not_the_generic_memory_principal(monkeypatch):
    monkeypatch.setattr("getpass.getuser", lambda: "alice")
    monkeypatch.setattr("socket.gethostname", lambda: "workstation")
    turn = _turn(IdentityContext("local", True, "local"), "cli")
    assert user_attributes(turn, ObservabilitySettings(enabled=True)) == {
        "user.id": "local:workstation:alice",
        "user.name": "alice",
    }


def test_remote_actor_never_uses_server_os_account(monkeypatch):
    def forbidden():
        raise AssertionError("remote turns must not inspect the OS account")

    monkeypatch.setattr("getpass.getuser", forbidden)
    identity = IdentityContext("oidc:actor", True, "oidc", username="verified-login")
    turn = _turn(identity)
    with bind_turn_context(turn, identity_context=identity):
        assert user_attributes(turn, ObservabilitySettings(enabled=True)) == {
            "user.id": "oidc:actor",
            "user.name": "verified-login",
        }
    assert user_attributes(turn, ObservabilitySettings(enabled=True)) == {
        "user.id": "oidc:actor"
    }


def test_disabled_guest_and_pseudonymous_modes_omit_user_attributes():
    identity = IdentityContext("oidc:actor", True, "oidc", username="alice")
    turn = _turn(identity)
    with bind_turn_context(turn, identity_context=identity):
        assert user_attributes(turn, ObservabilitySettings()) == {}
        assert (
            user_attributes(
                turn, ObservabilitySettings(enabled=True, pseudonymous_correlation=True)
            )
            == {}
        )
    guest = _turn(IdentityContext("guest:1", False, "browser", username="guest"))
    assert user_attributes(guest, ObservabilitySettings(enabled=True)) == {}


@pytest.mark.parametrize("name", ["a" * 513, "alice\nforged", "\ud800", ""])
def test_invalid_login_names_are_not_exported(name):
    identity = IdentityContext("oidc:actor", True, "oidc", username=name)
    turn = _turn(identity)
    with bind_turn_context(turn, identity_context=identity):
        assert user_attributes(turn, ObservabilitySettings(enabled=True)) == {
            "user.id": "oidc:actor"
        }


def test_mismatched_bound_identity_cannot_supply_another_users_name():
    first = IdentityContext("oidc:first", True, "oidc", username="first")
    second = IdentityContext("oidc:second", True, "oidc", username="second")
    with bind_turn_context(_turn(first), identity_context=first):
        assert user_attributes(_turn(second), ObservabilitySettings(enabled=True)) == {
            "user.id": "oidc:second"
        }


def test_real_sdk_canonical_span_exports_bound_user_and_late_cli_identity(monkeypatch):
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )
    from uagent.runtime.execution import (
        lifecycle_execution,
        apply_turn_context_to_current_agent_span,
    )
    from uagent.runtime.observability.otel_backend import OpenTelemetryBackend

    settings = ObservabilitySettings(enabled=True)
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    backend = OpenTelemetryBackend(
        tracer=provider.get_tracer(__name__), provider=provider, settings=settings
    )
    monkeypatch.setattr(
        "uagent.runtime.observability.bootstrap.get_observability_backend",
        lambda: backend,
    )
    monkeypatch.setattr(
        "uagent.runtime.observability.settings.get_observability_settings",
        lambda: settings,
    )
    identity = IdentityContext("oidc:actor", True, "oidc", username="verified-login")
    turn = _turn(identity)
    try:
        with bind_turn_context(turn, identity_context=identity):
            with lifecycle_execution(turn_context=turn):
                pass
        monkeypatch.setattr("getpass.getuser", lambda: "alice")
        monkeypatch.setattr("socket.gethostname", lambda: "workstation")
        with lifecycle_execution():
            apply_turn_context_to_current_agent_span(
                _turn(IdentityContext("local", True, "local"), "cli")
            )
        spans = exporter.get_finished_spans()
        assert spans[0].attributes["user.id"] == "oidc:actor"
        assert spans[0].attributes["user.name"] == "verified-login"
        assert spans[1].attributes["user.name"] == "alice"
        assert "principal_id" not in spans[0].attributes
    finally:
        backend.shutdown()
