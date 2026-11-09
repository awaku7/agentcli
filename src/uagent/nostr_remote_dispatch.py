"""Foreground CLI dispatch boundary for experimental Nostr remote requests.

The relay listener must verify/decrypt the NIP-17 event, authorize pairing, and
claim its rumor ID in the durable replay store before enqueueing it. This module
then revalidates the sender and the session on the CLI thread immediately before
routing chat or an explicitly requested CLI command through the existing input
paths. It does not start a relay listener, create pairings, or send DM replies.
"""

from __future__ import annotations

import inspect
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

MAX_REMOTE_TEXT_BYTES = 16_384
MAX_REMOTE_COMMAND_BYTES = 4_096
MAX_SESSION_ID_CHARS = 128
_HEX_32 = re.compile(r"^[0-9a-fA-F]{64}$")


class RemoteCLIRequestError(ValueError):
    """A remote request failed validation, freshness, or foreground authorization."""


@dataclass(frozen=True)
class RemoteCLIAction:
    """Validated user action ready for the CLI's existing event handler."""

    kind: Literal["user", "command"]
    text: str
    sender_pubkey: str
    rumor_id: str
    session_id: str


def _valid_hex32(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _HEX_32.fullmatch(value):
        raise RemoteCLIRequestError(f"invalid {field}")
    return value.lower()


def _utf8_size(value: str, field: str) -> int:
    try:
        return len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise RemoteCLIRequestError(f"invalid UTF-8 {field}") from exc


def enqueue_nostr_remote_request(
    event_queue: Any,
    rumor: Mapping[str, Any],
    *,
    target_session_id: str,
) -> None:
    """Queue a minimal event from a verified NIP-17 kind-14 rumor.

    Call only from the relay callback after signature/decryption checks, current
    pairing authorization, timestamp validation, and atomic replay claiming have
    succeeded. The session is captured at ingress and checked again on the CLI
    thread, so queued work cannot silently follow a later session switch.
    """
    if not callable(getattr(event_queue, "put", None)):
        raise TypeError("event_queue must provide put()")
    if not isinstance(rumor, Mapping) or rumor.get("kind") != 14:
        raise RemoteCLIRequestError("expected a NIP-17 kind-14 rumor")
    sender = _valid_hex32(rumor.get("pubkey"), "sender pubkey")
    rumor_id = _valid_hex32(rumor.get("id"), "rumor id")
    created_at = rumor.get("created_at")
    if (
        not isinstance(created_at, int)
        or isinstance(created_at, bool)
        or created_at < 0
    ):
        raise RemoteCLIRequestError("invalid rumor timestamp")
    text = rumor.get("content")
    if not isinstance(text, str) or not text.strip():
        raise RemoteCLIRequestError("remote message is empty or not text")
    if _utf8_size(text, "message") > MAX_REMOTE_TEXT_BYTES or "\x00" in text:
        raise RemoteCLIRequestError("remote message exceeds limits")
    if (
        not isinstance(target_session_id, str)
        or not target_session_id
        or len(target_session_id) > MAX_SESSION_ID_CHARS
    ):
        raise RemoteCLIRequestError("invalid target session")

    event = {
        "kind": "nostr_remote_request",
        "sender_pubkey": sender,
        "rumor_id": rumor_id,
        "created_at": created_at,
        "session_id": target_session_id,
        "text": text,
    }
    event_queue.put(event)


def _parse_action(text: str) -> tuple[Literal["user", "command"], str]:
    """Separate natural chat from explicit ``/uag cmd :...`` requests."""
    stripped = text.strip()
    if not stripped:
        raise RemoteCLIRequestError("remote message is empty")

    if stripped == "/uag" or stripped.startswith(("/uag ", "/uag\t", "/uag\n")):
        if not stripped.startswith("/uag cmd "):
            # In particular, never let unknown /uag control text fall through to
            # the LLM as ordinary conversation.
            raise RemoteCLIRequestError("unsupported /uag operation")
        command = stripped[len("/uag cmd ") :].strip()
        if (
            not command.startswith(":")
            or _utf8_size(command, "command") > MAX_REMOTE_COMMAND_BYTES
            or "\n" in command
            or "\r" in command
            or "\x00" in command
        ):
            raise RemoteCLIRequestError("invalid explicit CLI command")
        return "command", command

    return "user", text


def authorize_nostr_remote_request(
    event: Mapping[str, Any],
    *,
    current_session_id: str,
    authorize_sender: Callable[[str], bool],
    now: int | None = None,
    max_age_seconds: int = 600,
    future_tolerance_seconds: int = 300,
) -> RemoteCLIAction:
    """Validate and authorize a queued request on the foreground CLI thread.

    Pairing is intentionally rechecked here, not trusted from relay-ingress
    time, so a revoked device's already-queued event will be rejected. A pairing
    store callback must be synchronous and fail closed. The message must also
    target the exact session still active at dispatch time.
    """
    if not isinstance(event, Mapping) or event.get("kind") != "nostr_remote_request":
        raise RemoteCLIRequestError("invalid remote event")
    sender = _valid_hex32(event.get("sender_pubkey"), "sender pubkey")
    rumor_id = _valid_hex32(event.get("rumor_id"), "rumor id")
    target_session_id = event.get("session_id")
    if (
        not isinstance(target_session_id, str)
        or not target_session_id
        or len(target_session_id) > MAX_SESSION_ID_CHARS
        or not isinstance(current_session_id, str)
        or target_session_id != current_session_id
    ):
        raise RemoteCLIRequestError("remote request targets a different session")

    created_at = event.get("created_at")
    if (
        not isinstance(created_at, int)
        or isinstance(created_at, bool)
        or created_at < 0
    ):
        raise RemoteCLIRequestError("invalid rumor timestamp")
    if now is None:
        now = int(time.time())
    if (
        not isinstance(now, int)
        or isinstance(now, bool)
        or now < 0
        or not isinstance(max_age_seconds, int)
        or isinstance(max_age_seconds, bool)
        or max_age_seconds < 0
        or not isinstance(future_tolerance_seconds, int)
        or isinstance(future_tolerance_seconds, bool)
        or future_tolerance_seconds < 0
    ):
        raise RemoteCLIRequestError("invalid timestamp policy")
    if created_at < now - max_age_seconds:
        raise RemoteCLIRequestError("remote rumor is stale")
    if created_at > now + future_tolerance_seconds:
        raise RemoteCLIRequestError("remote rumor is from the future")

    if not callable(authorize_sender):
        raise RemoteCLIRequestError("remote sender authorization unavailable")
    try:
        authorized = authorize_sender(sender)
    except Exception as exc:
        raise RemoteCLIRequestError("remote sender authorization failed") from exc
    if inspect.isawaitable(authorized):
        close = getattr(authorized, "close", None)
        if callable(close):
            close()
        raise RemoteCLIRequestError("remote sender authorization must be synchronous")
    if authorized is not True:
        raise RemoteCLIRequestError("remote sender is not paired")

    text = event.get("text")
    if not isinstance(text, str) or not text.strip():
        raise RemoteCLIRequestError("remote message is empty or not text")
    if _utf8_size(text, "message") > MAX_REMOTE_TEXT_BYTES or "\x00" in text:
        raise RemoteCLIRequestError("remote message exceeds limits")
    kind, action_text = _parse_action(text)
    return RemoteCLIAction(
        kind=kind,
        text=action_text,
        sender_pubkey=sender,
        rumor_id=rumor_id,
        session_id=target_session_id,
    )
