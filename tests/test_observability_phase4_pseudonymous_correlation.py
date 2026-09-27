from __future__ import annotations

import base64
from contextlib import contextmanager

from uagent.auth.credential_store import Credential, CredentialKind
from uagent.runtime.execution import (
    apply_turn_context_to_current_agent_span,
    lifecycle_execution,
)
from uagent.runtime.identity_context import IdentityContext, TurnContext
from uagent.runtime.observability.pseudonymous_correlation import (
    build_correlation_attributes,
    make_pseudonym,
)
from uagent.runtime.observability.settings import ObservabilitySettings


class _Store:
    def __init__(self, credential: object = None) -> None:
        self.credential = credential
        self.set_calls: list[Credential] = []

    def get(self, name: str):
        del name
        return self.credential

    def set(self, credential: Credential, *, name: str | None = None) -> None:
        assert name is None or name == credential.name
        self.set_calls.append(credential)
        self.credential = credential

    def delete(self, name: str) -> bool:
        if isinstance(self.credential, Credential) and self.credential.name == name:
            self.credential = None
            return True
        return False


class _Span:
    def __init__(self) -> None:
        self.attributes: dict[str, object] = {}
        self.status: list[tuple[str, str | None]] = []

    def set_attribute(self, key, value) -> None:
        self.attributes[key] = value

    def set_status(self, status, description=None) -> None:
        self.status.append((status, description))


class _Backend:
    enabled = True

    def __init__(self) -> None:
        self.spans: list[_Span] = []

    @contextmanager
    def start_span(self, operation, *, attributes=None, root=False):
        del operation, root
        span = _Span()
        span.attributes.update(attributes or {})
        self.spans.append(span)
        yield span

    @contextmanager
    def attach_remote_context(self, carrier):
        del carrier
        yield False


def _settings(**overrides) -> ObservabilitySettings:
    values = {
        "enabled": True,
        "pseudonymous_correlation": True,
        "deployment_scope": "prod-jp",
        "correlation_key_name": "observability/correlation",
        "correlation_key_version": "v1",
    }
    values.update(overrides)
    return ObservabilitySettings(**values)


def _credential(key: bytes = bytes(range(32)), **overrides) -> Credential:
    values = {
        "name": "observability/correlation",
        "kind": CredentialKind.OTHER,
        "secret": base64.urlsafe_b64encode(key).decode("ascii").rstrip("="),
        "metadata": {
            "purpose": "observability_pseudonym_v1",
            "key_version": "v1",
        },
    }
    values.update(overrides)
    return Credential(**values)


def test_phase4b_hmac_vector_is_stable() -> None:
    assert (
        make_pseudonym(
            bytes(range(32)),
            deployment_scope="prod-jp",
            kind="principal",
            raw_identifier="user-123",
        )
        == "4ad1ba8930fe3a2417640862d4b5e329"
    )


def test_phase4b_hmac_is_domain_separated() -> None:
    key = bytes(range(32))
    principal = make_pseudonym(
        key,
        deployment_scope="prod-jp",
        kind="principal",
        raw_identifier="shared-id",
    )
    room = make_pseudonym(
        key,
        deployment_scope="prod-jp",
        kind="room",
        raw_identifier="shared-id",
    )
    other_deployment = make_pseudonym(
        key,
        deployment_scope="prod-us",
        kind="principal",
        raw_identifier="shared-id",
    )

    assert principal is not None
    assert len({principal, room, other_deployment}) == 3


def test_phase4b_builds_only_closed_attributes() -> None:
    turn = TurnContext(
        principal_id="user-123",
        room_id="room-1",
        project_id="project-1",
        session_id="session-secret",
        entry_point="web",
        authenticated=True,
        authn_kind="oidc",
    )

    attributes = build_correlation_attributes(
        turn,
        _settings(),
        credential_store=_Store(_credential()),
    )

    assert set(attributes) == {
        "uag.correlation.principal",
        "uag.correlation.room",
        "uag.correlation.project",
        "uag.correlation.key_version",
    }
    assert attributes["uag.correlation.key_version"] == "v1"
    assert "user-123" not in attributes.values()
    assert "room-1" not in attributes.values()
    assert "project-1" not in attributes.values()
    assert "session-secret" not in attributes.values()


def test_phase4b_missing_key_fails_closed_without_runtime_provisioning() -> None:
    store = _Store()
    turn = TurnContext(
        principal_id="local",
        room_id="",
        project_id="",
        session_id="",
        entry_point="cli",
        authenticated=True,
        authn_kind="local",
    )

    attributes = build_correlation_attributes(
        turn,
        _settings(),
        credential_store=store,
    )

    assert attributes == {}
    assert store.set_calls == []


def test_phase4b_invalid_settings_and_credentials_fail_closed() -> None:
    turn = TurnContext(
        principal_id="user-123",
        room_id="room-1",
        project_id="project-1",
        session_id="",
        entry_point="web",
        authenticated=True,
        authn_kind="oidc",
    )

    for settings in (
        _settings(enabled=False),
        _settings(pseudonymous_correlation=False),
        _settings(deployment_scope=" prod"),
        _settings(deployment_scope="prod\n"),
        _settings(correlation_key_name="bad\x00name"),
        _settings(correlation_key_version="V1"),
        _settings(correlation_key_version="v1/next"),
    ):
        assert (
            build_correlation_attributes(
                turn,
                settings,
                credential_store=_Store(_credential()),
            )
            == {}
        )

    bad_credentials = (
        object(),
        _credential(kind=CredentialKind.API_KEY),
        _credential(name="other"),
        _credential(metadata={"purpose": "wrong", "key_version": "v1"}),
        _credential(metadata={"purpose": "observability_pseudonym_v1"}),
        _credential(secret="A" * 42),
        _credential(secret="A" * 43 + "="),
    )
    for credential in bad_credentials:
        assert (
            build_correlation_attributes(
                turn,
                _settings(),
                credential_store=_Store(credential),
            )
            == {}
        )


def test_phase4b_attaches_once_to_canonical_agent_span(monkeypatch) -> None:
    backend = _Backend()
    turn = TurnContext.from_identity(
        IdentityContext("user-123", True, "oidc"),
        room_id="room-1",
        project_id="project-1",
        entry_point="web",
    )
    calls: list[TurnContext] = []

    monkeypatch.setattr(
        "uagent.runtime.observability.bootstrap.get_observability_backend",
        lambda: backend,
    )
    monkeypatch.setattr(
        "uagent.runtime.execution._attach_turn_correlation",
        lambda _span, bound_turn: calls.append(bound_turn) or True,
    )

    with lifecycle_execution(turn_context=turn):
        apply_turn_context_to_current_agent_span(turn)

    assert calls == [turn]


def test_phase4b_late_turn_resolution_attaches_once(monkeypatch) -> None:
    backend = _Backend()
    turn = TurnContext.from_identity(
        IdentityContext("local", True, "local"),
        entry_point="cli",
    )
    calls: list[TurnContext] = []

    monkeypatch.setattr(
        "uagent.runtime.observability.bootstrap.get_observability_backend",
        lambda: backend,
    )
    monkeypatch.setattr(
        "uagent.runtime.execution._attach_turn_correlation",
        lambda _span, bound_turn: calls.append(bound_turn) or True,
    )

    with lifecycle_execution():
        apply_turn_context_to_current_agent_span(turn)
        apply_turn_context_to_current_agent_span(turn)

    assert calls == [turn]
