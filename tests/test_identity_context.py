from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError

import pytest

from uagent.runtime.identity_context import (
    IdentityConfigurationError,
    IdentityContext,
    IdentityResolutionError,
    LocalIdentityResolver,
    TurnContext,
    bind_turn_context,
    create_identity_resolver,
    get_current_identity_context,
    get_current_turn_context,
    resolve_identity_mode,
    resolve_turn_context,
    submit_with_current_context,
)


def test_local_identity_is_default_and_stable(monkeypatch) -> None:
    monkeypatch.delenv("UAGENT_IDENTITY_MODE", raising=False)

    assert resolve_identity_mode() == "local"
    resolver = create_identity_resolver()
    assert isinstance(resolver, LocalIdentityResolver)

    identity = resolver.resolve()
    assert identity == IdentityContext(
        principal_id="local",
        authenticated=True,
        authn_kind="local",
    )


def test_unknown_identity_mode_fails_fast(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_IDENTITY_MODE", "mystery")

    with pytest.raises(IdentityConfigurationError, match="unsupported identity mode"):
        create_identity_resolver()


def test_known_future_mode_does_not_fallback_to_local(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_IDENTITY_MODE", "oidc")

    with pytest.raises(IdentityConfigurationError, match="not implemented"):
        create_identity_resolver()


def test_identity_and_turn_contexts_are_immutable() -> None:
    identity = IdentityContext(
        principal_id=" user-1 ",
        authenticated=True,
        authn_kind=" LOCAL ",
    )
    turn = TurnContext.from_identity(
        identity,
        room_id=" room-a ",
        project_id=" project-a ",
        session_id=" session-a ",
        entry_point=" CLI ",
    )

    assert identity.principal_id == "user-1"
    assert identity.authn_kind == "local"
    assert turn.room_id == "room-a"
    assert turn.project_id == "project-a"
    assert turn.session_id == "session-a"
    assert turn.entry_point == "cli"

    with pytest.raises(FrozenInstanceError):
        turn.room_id = "other"  # type: ignore[misc]


def test_resolve_turn_context_uses_selected_resolver() -> None:
    identity, turn = resolve_turn_context(
        entry_point="web",
        room_id="room-x",
        project_id="agentcli",
        session_id="session-x",
        mode="local",
    )

    assert identity.principal_id == "local"
    assert turn == TurnContext(
        principal_id="local",
        room_id="room-x",
        project_id="agentcli",
        session_id="session-x",
        entry_point="web",
        authenticated=True,
        authn_kind="local",
    )


def test_resolver_and_mode_cannot_both_be_supplied() -> None:
    with pytest.raises(ValueError, match="mutually exclusive"):
        resolve_turn_context(
            entry_point="cli",
            resolver=LocalIdentityResolver(),
            mode="local",
        )


def test_turn_binding_is_nested_and_restored() -> None:
    outer_identity = IdentityContext("user-a", True, "local")
    outer_turn = TurnContext.from_identity(outer_identity, entry_point="cli")
    inner_identity = IdentityContext("user-b", True, "local")
    inner_turn = TurnContext.from_identity(inner_identity, entry_point="web")

    assert get_current_identity_context() is None
    assert get_current_turn_context() is None

    with bind_turn_context(outer_turn, identity_context=outer_identity):
        assert get_current_identity_context() == outer_identity
        assert get_current_turn_context() == outer_turn

        with bind_turn_context(inner_turn, identity_context=inner_identity):
            assert get_current_identity_context() == inner_identity
            assert get_current_turn_context() == inner_turn

        assert get_current_identity_context() == outer_identity
        assert get_current_turn_context() == outer_turn

    assert get_current_identity_context() is None
    assert get_current_turn_context() is None


def test_turn_binding_rejects_identity_mismatch() -> None:
    identity = IdentityContext("user-a", True, "local")
    turn = TurnContext(
        principal_id="user-b",
        room_id="",
        project_id="",
        session_id="",
        entry_point="web",
        authenticated=True,
        authn_kind="local",
    )

    with pytest.raises(IdentityResolutionError, match="principal mismatch"):
        with bind_turn_context(turn, identity_context=identity):
            pass


def test_context_is_propagated_explicitly_to_thread_pool() -> None:
    identity = IdentityContext("user-a", True, "local")
    turn = TurnContext.from_identity(
        identity,
        room_id="room-a",
        project_id="agentcli",
        session_id="session-a",
        entry_point="web",
    )

    def read_context() -> tuple[str, str]:
        current_identity = get_current_identity_context()
        current_turn = get_current_turn_context()
        assert current_identity is not None
        assert current_turn is not None
        return current_identity.principal_id, current_turn.room_id

    with ThreadPoolExecutor(max_workers=1) as executor:
        with bind_turn_context(turn, identity_context=identity):
            future = submit_with_current_context(executor, read_context)
            assert future.result(timeout=5) == ("user-a", "room-a")


def test_parallel_turn_contexts_do_not_leak_between_workers() -> None:
    def submit_for(principal: str, room: str):
        identity = IdentityContext(principal, True, "local")
        turn = TurnContext.from_identity(identity, room_id=room, entry_point="web")

        def read_context() -> tuple[str, str]:
            current_turn = get_current_turn_context()
            assert current_turn is not None
            return current_turn.principal_id, current_turn.room_id

        with bind_turn_context(turn, identity_context=identity):
            return submit_with_current_context(executor, read_context)

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_a = submit_for("user-a", "room-a")
        future_b = submit_for("user-b", "room-b")
        assert future_a.result(timeout=5) == ("user-a", "room-a")
        assert future_b.result(timeout=5) == ("user-b", "room-b")

    assert get_current_turn_context() is None
