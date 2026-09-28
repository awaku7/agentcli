from __future__ import annotations

import base64
import threading
from contextlib import contextmanager
from contextvars import copy_context

from opentelemetry.attributes import BoundedAttributes

from uagent.auth.credential_store import Credential, CredentialKind
from uagent.runtime.execution import (
    apply_turn_context_to_current_agent_span,
    lifecycle_execution,
)
from uagent.runtime.identity_context import IdentityContext, TurnContext
from uagent.runtime.observability import pseudonymous_correlation as correlation
from uagent.runtime.observability.otel_backend import OpenTelemetrySpan
from uagent.runtime.observability.pseudonymous_correlation import (
    attach_pseudonymous_correlation,
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
        self.initial_attributes: list[dict[str, object]] = []

    @contextmanager
    def start_span(self, operation, *, attributes=None, root=False):
        del operation, root
        initial_attributes = dict(attributes or {})
        span = _Span()
        span.attributes.update(initial_attributes)
        self.initial_attributes.append(initial_attributes)
        self.spans.append(span)
        yield span

    @contextmanager
    def attach_remote_context(self, carrier):
        del carrier
        yield False


class _RawSpan:
    def __init__(
        self,
        *,
        max_attributes: int | None = None,
        max_value_length: int | None = None,
        attributes: dict[str, object] | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self._end_time = None
        self._attributes = BoundedAttributes(
            maxlen=max_attributes,
            attributes=attributes,
            immutable=False,
            max_value_len=max_value_length,
        )

    @property
    def attributes(self) -> dict[str, object]:
        return dict(self._attributes)

    def set_attribute(self, key, value) -> None:
        with self._lock:
            self._attributes[key] = value


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


def _turn() -> TurnContext:
    return TurnContext(
        principal_id="user-123",
        room_id="room-1",
        project_id="project-1",
        session_id="session-secret",
        entry_point="web",
        authenticated=True,
        authn_kind="oidc",
    )


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
    turn = _turn()

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
    turn = _turn()

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


def test_phase4b_rejects_returned_name_before_metadata_contents(monkeypatch) -> None:
    turn = _turn()
    calls: list[object] = []

    def validate_contents(metadata):
        calls.append(metadata)
        return False

    monkeypatch.setattr(correlation, "_valid_metadata_contents", validate_contents)

    attributes = build_correlation_attributes(
        turn,
        _settings(),
        credential_store=_Store(_credential(name="other")),
    )

    assert attributes == {}
    assert calls == []


def test_phase4b_metadata_reads_only_validated_snapshot(monkeypatch) -> None:
    turn = _turn()
    source_metadata = {
        "purpose": "observability_pseudonym_v1",
        "key_version": "v1",
    }
    credential = _credential(metadata=source_metadata)
    original_validator = correlation._valid_metadata_contents
    snapshots: list[dict[object, object]] = []

    def validate_snapshot(metadata):
        snapshots.append(metadata)
        source_metadata["purpose"] = "mutated-after-snapshot"
        return original_validator(metadata)

    monkeypatch.setattr(correlation, "_valid_metadata_contents", validate_snapshot)

    attributes = build_correlation_attributes(
        turn,
        _settings(),
        credential_store=_Store(credential),
    )

    assert attributes["uag.correlation.key_version"] == "v1"
    assert snapshots and snapshots[0] is not source_metadata
    assert snapshots[0]["purpose"] == "observability_pseudonym_v1"


def test_phase4b_span_count_limit_fails_closed_without_partial_set() -> None:
    raw_span = _RawSpan(max_attributes=1)
    span = OpenTelemetrySpan(raw_span, capture_content=False)

    attached = attach_pseudonymous_correlation(
        span,
        _turn(),
        _settings(),
        credential_store=_Store(_credential()),
    )

    assert attached is False
    assert not {
        key for key in raw_span.attributes if key.startswith("uag.correlation.")
    }


def test_phase4b_span_value_limit_fails_closed_without_truncation() -> None:
    raw_span = _RawSpan(max_attributes=8, max_value_length=16)
    span = OpenTelemetrySpan(raw_span, capture_content=False)

    attached = attach_pseudonymous_correlation(
        span,
        _turn(),
        _settings(),
        credential_store=_Store(_credential()),
    )

    assert attached is False
    assert not {
        key for key in raw_span.attributes if key.startswith("uag.correlation.")
    }


def test_phase4b_complete_set_survives_reserved_status_update() -> None:
    raw_span = _RawSpan(
        max_attributes=5,
        max_value_length=32,
        attributes={"uag.agent.lifecycle_status": "created"},
    )
    span = OpenTelemetrySpan(raw_span, capture_content=False)

    attached = attach_pseudonymous_correlation(
        span,
        _turn(),
        _settings(),
        credential_store=_Store(_credential()),
    )

    assert attached is True
    raw_span.set_attribute("uag.agent.lifecycle_status", "completed")
    attributes = raw_span.attributes
    assert attributes["uag.agent.lifecycle_status"] == "completed"
    assert attributes["uag.correlation.key_version"] == "v1"
    assert len(attributes["uag.correlation.principal"]) == 32
    assert len(attributes["uag.correlation.room"]) == 32
    assert len(attributes["uag.correlation.project"]) == 32


def test_phase4b_unsupported_span_never_uses_partial_single_attribute_writes() -> None:
    class PartialOnlySpan:
        def __init__(self) -> None:
            self.attributes = {}
            self.calls = 0

        def set_attribute(self, key, value) -> None:
            self.calls += 1
            self.attributes[key] = value
            raise RuntimeError("partial write")

    span = PartialOnlySpan()

    attached = attach_pseudonymous_correlation(
        span,
        _turn(),
        _settings(),
        credential_store=_Store(_credential()),
    )

    assert attached is False
    assert span.calls == 0
    assert span.attributes == {}


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
        lambda _span, bound_turn: calls.append(bound_turn) or False,
    )

    with lifecycle_execution(turn_context=turn):
        apply_turn_context_to_current_agent_span(turn)

    assert calls == [turn]
    assert backend.initial_attributes[0]["uag.agent.lifecycle_status"] == "created"
    assert backend.spans[0].attributes["uag.agent.lifecycle_status"] == "completed"


def test_phase4b_late_turn_resolution_attempt_is_terminal(monkeypatch) -> None:
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
        lambda _span, bound_turn: calls.append(bound_turn) or False,
    )

    with lifecycle_execution():
        apply_turn_context_to_current_agent_span(turn)
        apply_turn_context_to_current_agent_span(turn)

    assert calls == [turn]


def test_phase4b_copied_contexts_share_terminal_span_state(monkeypatch) -> None:
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
        lambda _span, bound_turn: calls.append(bound_turn) or False,
    )

    with lifecycle_execution():
        first_context = copy_context()
        second_context = copy_context()
        first_context.run(apply_turn_context_to_current_agent_span, turn)
        second_context.run(apply_turn_context_to_current_agent_span, turn)

    assert calls == [turn]


def test_phase4b_failed_first_attempt_is_not_retried(monkeypatch) -> None:
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
        lambda _span, bound_turn: calls.append(bound_turn) or False,
    )

    with lifecycle_execution():
        apply_turn_context_to_current_agent_span(turn)
        apply_turn_context_to_current_agent_span(turn)

    assert calls == [turn]
    assert not {
        key for key in backend.spans[0].attributes if key.startswith("uag.correlation.")
    }
