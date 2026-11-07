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


@pytest.mark.parametrize("fail_round", [False, True])
def test_web_worker_binds_supplied_oidc_identity_before_canonical_span(
    monkeypatch, tmp_path, fail_round
):
    import threading
    from types import SimpleNamespace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )
    from uagent.runtime.identity_context import (
        get_current_identity_context,
        get_current_turn_context,
    )
    from uagent.runtime.observability.otel_backend import OpenTelemetryBackend
    from uagent.runtime.session_store import project_id_from_path
    from uagent.web_impl import agent_worker
    from uagent.web_impl.rooms import WebRoom

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
    monkeypatch.setenv("UAGENT_PROVIDER", "offline-test")
    monkeypatch.setattr(agent_worker.web_manager, "room_worker_pool", None)
    monkeypatch.setattr(
        agent_worker.web_manager, "execution_profile", "local_trusted", raising=False
    )
    monkeypatch.setattr(
        agent_worker.web_manager, "sandbox_enabled", False, raising=False
    )
    core = SimpleNamespace(
        log_message=lambda message: None,
        auto_pilot_active=False,
        interrupt_lock=threading.Lock(),
        interrupt_requested=False,
        status_busy=False,
        status_label="IDLE",
        _last_round_outcome={},
    )
    monkeypatch.setattr(agent_worker, "core", core)
    monkeypatch.setattr(
        agent_worker.providers,
        "make_client",
        lambda core: ("offline-test", object(), "test-model"),
    )
    seen = []

    def run_round(_provider, _client, _model, history, **kwargs):
        identity = get_current_identity_context()
        seen.append(identity.username)
        message = {"role": "assistant", "content": "done"}
        history.append(message)
        core.log_message(message)
        if fail_round:
            raise RuntimeError("simulated provider failure")

    monkeypatch.setattr(agent_worker.llm_util, "run_llm_rounds", run_round)
    errors = []

    def fresh_worker_thread():
        try:
            assert get_current_identity_context() is None
            for username in ("alice", "bob"):
                identity = IdentityContext(
                    f"oidc:{username}", True, "oidc", username=username
                )
                room = WebRoom(f"oidc-{username}")
                room.base_dir = str(tmp_path)
                room.history_initialized = True
                room.private_session = True
                turn = TurnContext.from_identity(
                    identity,
                    entry_point="web",
                    room_id=room.room_id,
                    project_id=project_id_from_path(str(tmp_path)),
                    private_session=True,
                )
                agent_worker.run_agent_worker(
                    room,
                    "hello",
                    turn_context=turn,
                    identity_context=identity,
                    project_path=str(tmp_path),
                )
                assert get_current_identity_context() is None
                assert get_current_turn_context() is None
        except BaseException as exc:
            errors.append(exc)

    try:
        thread = threading.Thread(target=fresh_worker_thread)
        thread.start()
        thread.join(timeout=15)
        assert not thread.is_alive()
        assert not errors
        assert seen == ["alice", "bob"]
        spans = [
            span
            for span in exporter.get_finished_spans()
            if span.attributes.get("gen_ai.operation.name") == "invoke_agent"
        ]
        assert len(spans) == 2
        assert [
            (span.attributes.get("user.id"), span.attributes.get("user.name"))
            for span in spans
        ] == [("oidc:alice", "alice"), ("oidc:bob", "bob")]
    finally:
        backend.shutdown()
