from __future__ import annotations

from queue import Queue

import pytest

from uagent.nostr_remote_dispatch import (
    MAX_REMOTE_TEXT_BYTES,
    RemoteCLIRequestError,
    authorize_nostr_remote_request,
    enqueue_nostr_remote_request,
)

SENDER = "ab" * 32
RUMOR_ID = "cd" * 32


def _rumor(content: str = "hello from phone") -> dict[str, object]:
    return {
        "kind": 14,
        "pubkey": SENDER,
        "id": RUMOR_ID,
        "created_at": 1_700_000_000,
        "content": content,
    }


def _event(content: str = "hello from phone") -> dict[str, object]:
    queue: Queue[dict[str, object]] = Queue()
    enqueue_nostr_remote_request(
        queue, _rumor(content), target_session_id="active-session"
    )
    return queue.get_nowait()


def test_enqueue_captures_minimal_rumor_and_active_session() -> None:
    queue: Queue[dict[str, object]] = Queue()
    enqueue_nostr_remote_request(
        queue,
        _rumor(),
        target_session_id="active-session",
    )

    assert queue.get_nowait() == {
        "kind": "nostr_remote_request",
        "sender_pubkey": SENDER,
        "rumor_id": RUMOR_ID,
        "created_at": 1_700_000_000,
        "session_id": "active-session",
        "text": "hello from phone",
    }


@pytest.mark.parametrize(
    "rumor, session",
    [
        ({**_rumor(), "kind": 1059}, "active-session"),
        ({**_rumor(), "pubkey": "bad"}, "active-session"),
        ({**_rumor(), "id": "01" * 33}, "active-session"),
        ({**_rumor(), "created_at": True}, "active-session"),
        ({**_rumor(), "content": "\x00bad"}, "active-session"),
        ({**_rumor(), "content": "x" * (MAX_REMOTE_TEXT_BYTES + 1)}, "active-session"),
        (_rumor(), ""),
    ],
)
def test_enqueue_rejects_malformed_or_oversized_rumors(
    rumor: dict[str, object], session: str
) -> None:
    queue: Queue[dict[str, object]] = Queue()
    with pytest.raises(RemoteCLIRequestError):
        enqueue_nostr_remote_request(queue, rumor, target_session_id=session)
    assert queue.empty()


def test_foreground_dispatch_revalidates_pairing_and_routes_plain_chat() -> None:
    checks: list[str] = []
    action = authorize_nostr_remote_request(
        _event(),
        current_session_id="active-session",
        authorize_sender=lambda sender: checks.append(sender) is None
        and sender == SENDER,
        now=1_700_000_000,
    )

    assert checks == [SENDER]
    assert action.kind == "user"
    assert action.text == "hello from phone"
    assert action.session_id == "active-session"


def test_explicit_remote_cli_command_is_separate_from_chat() -> None:
    action = authorize_nostr_remote_request(
        _event("/uag cmd :help"),
        current_session_id="active-session",
        authorize_sender=lambda _sender: True,
        now=1_700_000_000,
    )

    assert action.kind == "command"
    assert action.text == ":help"


@pytest.mark.parametrize(
    "content",
    [
        "/uag cmd :nostr pair abcd",
        "/uag cmd :NOSTR revoke abcd",
        "/uag cmd :nostr remote start",
        "/uag cmd :nostr:pair abcd",
        "/uag cmd :nostr:remote start",
    ],
)
def test_pairing_changes_are_local_only(content: str) -> None:
    with pytest.raises(RemoteCLIRequestError, match="local-only"):
        authorize_nostr_remote_request(
            _event(content),
            current_session_id="active-session",
            authorize_sender=lambda _sender: True,
            now=1_700_000_000,
        )


def test_unknown_uag_operation_is_not_forwarded_as_chat() -> None:
    with pytest.raises(RemoteCLIRequestError, match="unsupported"):
        authorize_nostr_remote_request(
            _event("/uag status"),
            current_session_id="active-session",
            authorize_sender=lambda _sender: True,
            now=1_700_000_000,
        )


def test_foreground_dispatch_fails_closed_for_unpaired_sender() -> None:
    called = False

    def reject(_sender: str) -> bool:
        nonlocal called
        called = True
        return False

    with pytest.raises(RemoteCLIRequestError, match="not paired"):
        authorize_nostr_remote_request(
            _event(),
            current_session_id="active-session",
            authorize_sender=reject,
            now=1_700_000_000,
        )
    assert called


def test_session_and_freshness_are_rechecked_before_authorization() -> None:
    called = False

    def authorize(_sender: str) -> bool:
        nonlocal called
        called = True
        return True

    with pytest.raises(RemoteCLIRequestError, match="different session"):
        authorize_nostr_remote_request(
            _event(),
            current_session_id="new-session",
            authorize_sender=authorize,
            now=1_700_000_000,
        )
    assert not called

    with pytest.raises(RemoteCLIRequestError, match="stale"):
        authorize_nostr_remote_request(
            _event(),
            current_session_id="active-session",
            authorize_sender=authorize,
            now=1_700_000_601,
        )
    assert not called


def test_foreground_dispatch_rejects_invalid_or_multiline_commands() -> None:
    for content in ("/uag nonsense", "/uag cmd help", "/uag cmd :one\n:two"):
        with pytest.raises(RemoteCLIRequestError):
            authorize_nostr_remote_request(
                _event(content),
                current_session_id="active-session",
                authorize_sender=lambda _sender: True,
                now=1_700_000_000,
            )


def test_expired_revoked_and_async_authorizers_fail_closed() -> None:
    with pytest.raises(RemoteCLIRequestError, match="future"):
        authorize_nostr_remote_request(
            _event(),
            current_session_id="active-session",
            authorize_sender=lambda _sender: True,
            now=1_699_999_699,
            future_tolerance_seconds=300,
        )

    async def async_authorize(_sender: str) -> bool:
        return True

    with pytest.raises(RemoteCLIRequestError, match="synchronous"):
        authorize_nostr_remote_request(
            _event(),
            current_session_id="active-session",
            authorize_sender=async_authorize,
            now=1_700_000_000,
        )
