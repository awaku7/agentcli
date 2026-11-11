"""Isolated NIP-17 relay I/O primitives for experimental remote CLI work.

This module deliberately does not alter the legacy bitchat Nostr transport or
start a CLI remote-control service. It publishes already-created kind-1059
NIP-17 gift wraps to their verified inbox-relay lists and listens for addressed
wraps. The listener can optionally persist verified encrypted wraps in a SQLite
inbox before notifying its callback. The opt-in CLI runtime owns inbox recovery,
foreground dispatch, pairing-store wiring, and service lifecycle. This module
still does not send response DMs; incoming relay destinations come from the
locally configured Nostr transport relay list.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import secrets
import ssl
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .nostr_nip17 import (
    _public_key_x,
    _sign_event,
    _validate_private_key,
    _validate_relay_uri,
    extract_nip17_relay_list,
    unwrap_nip17_private_message,
)
from .nostr_remote_inbox import InboxFullError, SQLiteNostrInboxStore
from .nostr_remote_state import SQLiteReplayStore, validate_rumor_timestamp
from .tools.nostr_transport import _verify_event

MAX_RELAY_FRAME_BYTES = 1_000_000
DEFAULT_RELAY_TIMEOUT_SECONDS = 15


class NostrRecipientRelayListUnavailable(ValueError):
    """No valid signed kind-10050 list could be read from permitted relays."""


@dataclass(frozen=True)
class RelayDelivery:
    """Result of one event publication attempt to one relay."""

    relay_url: str
    event_id: str
    accepted: bool
    message: str = ""


def _event_json_bytes(event: dict[str, Any]) -> bytes:
    try:
        encoded = json.dumps(event, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise ValueError("event is not JSON-serializable UTF-8") from exc
    if len(encoded) > MAX_RELAY_FRAME_BYTES:
        raise ValueError("event exceeds the remote relay size limit")
    return encoded


def _decode_relay_frame(raw: str | bytes) -> list[Any] | None:
    if isinstance(raw, bytes):
        if len(raw) > MAX_RELAY_FRAME_BYTES:
            return None
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError:
            return None
    elif not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_RELAY_FRAME_BYTES:
        return None
    try:
        message = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return message if isinstance(message, list) else None


def _make_auth_event(
    relay_url: str, challenge: str, private_key: bytes
) -> dict[str, Any]:
    if not isinstance(challenge, str) or not challenge or len(challenge) > 512:
        raise ValueError("relay AUTH challenge is invalid")
    private_key = _validate_private_key(private_key)
    event: dict[str, Any] = {
        "pubkey": _public_key_x(private_key).hex(),
        "created_at": int(time.time()),
        "kind": 22242,
        "tags": [["relay", relay_url], ["challenge", challenge]],
        "content": "",
    }
    return _sign_event(event, private_key)


def _connect_factory(connect_factory: Callable[..., Any] | None) -> Callable[..., Any]:
    """Use exact configured relay URLs; do not follow implicit HTTP redirects."""
    if connect_factory is not None:
        return connect_factory
    try:
        from websockets.asyncio.client import connect
    except ImportError as exc:
        raise ModuleNotFoundError("Nostr remote transport requires websockets") from exc

    class NoRedirectConnect(connect):
        def process_redirect(self, exc: Exception) -> Exception:
            # websockets follows 3xx redirects, including to unapproved hosts.
            # An OK from such a destination must not be attributed to the
            # originally configured relay.
            return exc

    return NoRedirectConnect


async def publish_nip17_gift_wrap(
    relay_url: str,
    event: dict[str, Any],
    auth_private_key: bytes,
    *,
    allowed_relay_urls: Sequence[str],
    connect_factory: Callable[..., Any] | None = None,
    timeout: float = DEFAULT_RELAY_TIMEOUT_SECONDS,
) -> RelayDelivery:
    """Publish one signed kind-1059 event and handle an optional NIP-42 challenge.

    The event is sent only to the caller-selected relay. TLS verification is
    always enabled here; callers cannot disable it through UAG's general SSL
    setting. The caller must choose the relay from a verified kind-10050 list
    and enforce its own egress policy before calling this function.
    """
    relay_url = _validate_relay_uri(relay_url)
    if isinstance(allowed_relay_urls, (str, bytes)) or not allowed_relay_urls:
        raise ValueError("a non-empty local relay egress allowlist is required")
    allowed = {_validate_relay_uri(url) for url in allowed_relay_urls}
    if relay_url not in allowed:
        raise ValueError("relay is not permitted by the local egress allowlist")
    if not isinstance(event, dict) or event.get("kind") != 1059:
        raise ValueError("only NIP-17 kind-1059 gift wraps may be published")
    _event_json_bytes(event)
    if not _verify_event(event):
        raise ValueError("gift-wrap event signature is invalid")
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        raise ValueError("timeout must be a positive number")

    connect = _connect_factory(connect_factory)
    auth_private_key = _validate_private_key(auth_private_key)
    event_id = str(event.get("id", ""))
    auth_challenges: set[str] = set()
    pending_auth_event_id: str | None = None
    event_auth_required = False
    try:
        async with asyncio.timeout(float(timeout)):
            async with connect(
                relay_url,
                ssl=ssl.create_default_context(),
                open_timeout=float(timeout),
                close_timeout=min(float(timeout), 5.0),
                max_size=MAX_RELAY_FRAME_BYTES,
            ) as websocket:
                await websocket.send(
                    json.dumps(
                        ["EVENT", event], separators=(",", ":"), ensure_ascii=False
                    )
                )
                while True:
                    frame = _decode_relay_frame(await websocket.recv())
                    if frame is None or not frame:
                        continue
                    if frame[0] == "AUTH" and len(frame) >= 2:
                        challenge = frame[1]
                        if (
                            not isinstance(challenge, str)
                            or challenge in auth_challenges
                        ):
                            raise ValueError(
                                "relay repeated or malformed its AUTH challenge"
                            )
                        auth_challenges.add(challenge)
                        auth_event = _make_auth_event(
                            relay_url, challenge, auth_private_key
                        )
                        pending_auth_event_id = auth_event["id"]
                        await websocket.send(
                            json.dumps(
                                ["AUTH", auth_event],
                                separators=(",", ":"),
                                ensure_ascii=False,
                            )
                        )
                        continue
                    if frame[0] == "OK" and len(frame) >= 4:
                        if frame[1] == pending_auth_event_id:
                            pending_auth_event_id = None
                            if frame[2] is not True:
                                return RelayDelivery(
                                    relay_url,
                                    event_id,
                                    False,
                                    f"relay rejected AUTH: {str(frame[3])[:400]}",
                                )
                            # NIP-42 relays may reject the initial EVENT with a
                            # challenge. Retry it only after AUTH is accepted.
                            event_auth_required = False
                            await websocket.send(
                                json.dumps(
                                    ["EVENT", event],
                                    separators=(",", ":"),
                                    ensure_ascii=False,
                                )
                            )
                            continue
                        if frame[1] == event_id:
                            accepted = frame[2] is True
                            message = str(frame[3])[:512]
                            if not accepted and message.lower().startswith(
                                "auth-required"
                            ):
                                # NIP-42 publication flow can reject EVENT
                                # before sending the AUTH challenge. Treat this
                                # OK as provisional and continue reading.
                                event_auth_required = True
                                continue
                            return RelayDelivery(
                                relay_url=relay_url,
                                event_id=event_id,
                                accepted=accepted,
                                message=message,
                            )
                    if frame[0] == "NOTICE" and len(frame) >= 2:
                        notice = str(frame[1])[:512]
                        if notice.lower().startswith("auth-required"):
                            event_auth_required = True
                            continue
    except TimeoutError:
        if pending_auth_event_id is not None:
            message = "relay AUTH response timed out"
        elif event_auth_required:
            message = "relay required AUTH but sent no usable challenge"
        else:
            message = "relay response timed out"
        return RelayDelivery(relay_url, event_id, False, message)
    except Exception as exc:
        # Keep relay errors bounded and avoid logging event contents or keys.
        return RelayDelivery(
            relay_url,
            event_id,
            False,
            f"{type(exc).__name__}: {str(exc)[:400]}",
        )


async def publish_nip17_gift_wraps(
    events: Sequence[dict[str, Any]],
    relay_lists_by_pubkey: Mapping[str, Sequence[str]],
    auth_private_key: bytes,
    *,
    allowed_relay_urls: Sequence[str],
    connect_factory: Callable[..., Any] | None = None,
    timeout: float = DEFAULT_RELAY_TIMEOUT_SECONDS,
) -> list[RelayDelivery]:
    """Route each gift wrap only to the inbox relays for its single ``p`` tag.

    ``relay_lists_by_pubkey`` must be populated from verified kind-10050 events.
    ``allowed_relay_urls`` is a separate local egress allowlist. The effective
    destinations are their intersection, preventing a signed remote relay list
    from making this process connect to an arbitrary internal or local service.
    Missing recipient routes or an empty intersection are hard errors; this
    function never broadcasts to the local relay pool as a fallback.
    """
    if isinstance(allowed_relay_urls, (str, bytes)) or not allowed_relay_urls:
        raise ValueError("a non-empty local relay egress allowlist is required")
    allowed = {_validate_relay_uri(url) for url in allowed_relay_urls}
    results: list[RelayDelivery] = []
    for event in events:
        if not isinstance(event, dict) or event.get("kind") != 1059:
            raise ValueError("only NIP-17 kind-1059 gift wraps may be routed")
        tags = event.get("tags")
        p_tags = [
            tag
            for tag in tags or []
            if isinstance(tag, list) and len(tag) >= 2 and tag[0] == "p"
        ]
        if len(p_tags) != 1 or not isinstance(p_tags[0][1], str):
            raise ValueError("gift wrap must contain exactly one recipient p tag")
        recipient = p_tags[0][1]
        relay_urls = relay_lists_by_pubkey.get(recipient)
        if not relay_urls:
            raise ValueError(f"no verified inbox relays for recipient {recipient[:12]}")
        # Normalize and deduplicate while preserving the signed relay-list order.
        signed_relays = list(
            dict.fromkeys(_validate_relay_uri(url) for url in relay_urls)
        )
        relays = [url for url in signed_relays if url in allowed]
        if not relays:
            raise ValueError(
                f"no recipient inbox relay is allowed by local policy for {recipient[:12]}"
            )
        for relay_url in relays:
            results.append(
                await publish_nip17_gift_wrap(
                    relay_url,
                    event,
                    auth_private_key,
                    allowed_relay_urls=[relay_url],
                    connect_factory=connect_factory,
                    timeout=timeout,
                )
            )
    return results


def _readback_connect_factory(
    connect_factory: Callable[..., Any] | None,
) -> Callable[..., Any]:
    """Use the same no-redirect connector as NIP-17 publication and listening."""
    return _connect_factory(connect_factory)


async def read_back_nip17_gift_wrap(
    relay_url: str,
    event_id: str,
    *,
    allowed_relay_urls: Sequence[str],
    auth_private_key: bytes | None = None,
    connect_factory: Callable[..., Any] | None = None,
    timeout: float = 3.0,
) -> str:
    """Read an encrypted reply by its exact event ID; never expose the content.

    A relay's publication OK does not prove that it retains an event. The
    result is "found", "not_returned" (EOSE without the ID), or "unavailable"
    (connection/auth/timeout/invalid response). Only locally allowed relays
    are contacted, and no participant-supplied URLs are followed.
    """
    relay_url = _validate_relay_uri(relay_url)
    if isinstance(allowed_relay_urls, (str, bytes)) or not allowed_relay_urls:
        raise ValueError("a non-empty relay allowlist is required")
    if relay_url not in {_validate_relay_uri(url) for url in allowed_relay_urls}:
        raise ValueError("relay is not permitted by the local egress allowlist")
    if (
        not isinstance(event_id, str)
        or len(event_id) != 64
        or any(ch not in "0123456789abcdefABCDEF" for ch in event_id)
    ):
        raise ValueError("event ID must be 32-byte hex")
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        raise ValueError("timeout must be positive")

    event_id = event_id.lower()
    sub_id = "uag-readback-" + secrets.token_hex(8)
    request = ["REQ", sub_id, {"ids": [event_id], "kinds": [1059], "limit": 1}]
    connect = _readback_connect_factory(connect_factory)
    auth_key = (
        None if auth_private_key is None else _validate_private_key(auth_private_key)
    )
    invalid_reply = False
    try:
        async with asyncio.timeout(float(timeout)):
            async with connect(
                relay_url,
                ssl=ssl.create_default_context(),
                open_timeout=float(timeout),
                close_timeout=min(float(timeout), 5.0),
                max_size=MAX_RELAY_FRAME_BYTES,
            ) as websocket:
                await websocket.send(json.dumps(request, separators=(",", ":")))
                auth_challenges: set[str] = set()
                pending_auth_event_id: str | None = None
                while True:
                    frame = _decode_relay_frame(await websocket.recv())
                    if frame is None or not frame:
                        continue
                    if frame[0] == "AUTH" and len(frame) >= 2:
                        challenge = frame[1]
                        if (
                            auth_key is None
                            or not isinstance(challenge, str)
                            or challenge in auth_challenges
                            or len(auth_challenges) >= 2
                        ):
                            return "unavailable"
                        auth_challenges.add(challenge)
                        auth_event = _make_auth_event(relay_url, challenge, auth_key)
                        pending_auth_event_id = auth_event["id"]
                        await websocket.send(
                            json.dumps(["AUTH", auth_event], separators=(",", ":"))
                        )
                        continue
                    if frame[0] == "OK" and len(frame) >= 4:
                        if frame[1] == pending_auth_event_id:
                            if frame[2] is not True:
                                return "unavailable"
                            pending_auth_event_id = None
                            await websocket.send(
                                json.dumps(request, separators=(",", ":"))
                            )
                            continue
                    if (
                        frame[0] == "EVENT"
                        and len(frame) >= 3
                        and frame[1] == sub_id
                        and isinstance(frame[2], dict)
                        and frame[2].get("id") == event_id
                    ):
                        if frame[2].get("kind") == 1059 and _verify_event(frame[2]):
                            return "found"
                        invalid_reply = True
                    elif frame[0] == "EOSE" and len(frame) >= 2 and frame[1] == sub_id:
                        return "unavailable" if invalid_reply else "not_returned"
                    elif (
                        frame[0] == "CLOSED"
                        and len(frame) >= 3
                        and frame[1] == sub_id
                        and pending_auth_event_id is not None
                        and isinstance(frame[2], str)
                        and frame[2].startswith("auth-required:")
                    ):
                        # The initial REQ may be rejected before AUTH is acknowledged.
                        continue
                    elif (
                        frame[0] == "CLOSED" and len(frame) >= 2 and frame[1] == sub_id
                    ):
                        return "unavailable"
    except Exception:
        return "unavailable"


async def fetch_nip17_relay_list(
    participant_pubkey_hex: str,
    lookup_relays: Sequence[str],
    *,
    allowed_relay_urls: Sequence[str],
    auth_private_key: bytes | None = None,
    connect_factory: Callable[..., Any] | None = None,
    timeout: float = 5.0,
) -> list[str]:
    """Fetch the participant's newest signed kind-10050 inbox relay list.

    Lookup connections are restricted to the caller's local relay allowlist.
    The returned destinations are signature-verified but still must be
    intersected with that allowlist before publishing any gift wraps.
    """
    if not isinstance(participant_pubkey_hex, str) or len(participant_pubkey_hex) != 64:
        raise ValueError("participant pubkey must be 32-byte hex")
    try:
        participant_pubkey_hex = bytes.fromhex(participant_pubkey_hex).hex()
    except ValueError as exc:
        raise ValueError("participant pubkey must be 32-byte hex") from exc
    if isinstance(lookup_relays, (str, bytes)) or not lookup_relays:
        raise ValueError("at least one local lookup relay is required")
    if isinstance(allowed_relay_urls, (str, bytes)) or not allowed_relay_urls:
        raise ValueError("a non-empty local relay allowlist is required")
    allowed = {_validate_relay_uri(url) for url in allowed_relay_urls}
    relays = list(dict.fromkeys(_validate_relay_uri(url) for url in lookup_relays))
    if len(relays) > 10 or any(url not in allowed for url in relays):
        raise ValueError("lookup relays must be in the local relay allowlist")
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        raise ValueError("timeout must be a positive number")
    auth_key = (
        None if auth_private_key is None else _validate_private_key(auth_private_key)
    )

    connect = _connect_factory(connect_factory)
    candidates: list[tuple[int, list[str]]] = []
    for relay_url in relays:
        subscription_id = "uag-relay-list-" + secrets.token_hex(8)
        request = [
            "REQ",
            subscription_id,
            {"kinds": [10050], "authors": [participant_pubkey_hex], "limit": 10},
        ]
        auth_challenges: set[str] = set()
        pending_auth_event_id: str | None = None
        try:
            async with asyncio.timeout(float(timeout)):
                async with connect(
                    relay_url,
                    ssl=ssl.create_default_context(),
                    open_timeout=float(timeout),
                    close_timeout=min(float(timeout), 5.0),
                    max_size=MAX_RELAY_FRAME_BYTES,
                ) as websocket:
                    await websocket.send(
                        json.dumps(request, separators=(",", ":"), ensure_ascii=False)
                    )
                    while True:
                        frame = _decode_relay_frame(await websocket.recv())
                        if frame is None or not frame:
                            continue
                        if frame[0] == "AUTH" and len(frame) >= 2:
                            challenge = frame[1]
                            if (
                                auth_key is None
                                or not isinstance(challenge, str)
                                or not challenge
                                or challenge in auth_challenges
                                or len(auth_challenges) >= 3
                            ):
                                raise PermissionError(
                                    "relay AUTH challenge is unusable"
                                )
                            auth_challenges.add(challenge)
                            auth_event = _make_auth_event(
                                relay_url, challenge, auth_key
                            )
                            pending_auth_event_id = auth_event["id"]
                            await websocket.send(
                                json.dumps(["AUTH", auth_event], separators=(",", ":"))
                            )
                            continue
                        if (
                            frame[0] == "OK"
                            and len(frame) >= 4
                            and frame[1] == pending_auth_event_id
                        ):
                            pending_auth_event_id = None
                            if frame[2] is not True:
                                raise PermissionError("relay rejected NIP-42 AUTH")
                            await websocket.send(
                                json.dumps(
                                    request, separators=(",", ":"), ensure_ascii=False
                                )
                            )
                            continue
                        if (
                            frame[0] == "EVENT"
                            and len(frame) >= 3
                            and frame[1] == subscription_id
                            and isinstance(frame[2], dict)
                        ):
                            event = frame[2]
                            try:
                                inbox_relays = extract_nip17_relay_list(
                                    event, participant_pubkey_hex
                                )
                            except (TypeError, ValueError):
                                continue
                            candidates.append((event["created_at"], inbox_relays))
                        elif (
                            frame[0] == "CLOSED"
                            and len(frame) >= 3
                            and frame[1] == subscription_id
                            and pending_auth_event_id is not None
                            and isinstance(frame[2], str)
                            and frame[2].startswith("auth-required:")
                        ):
                            # Some relays close the initial unauthenticated
                            # subscription before acknowledging our AUTH event.
                            # Keep the socket open so the OK frame can trigger
                            # an authenticated REQ retry.
                            continue
                        elif (
                            frame[0] in {"EOSE", "CLOSED"}
                            and len(frame) >= 2
                            and frame[1] == subscription_id
                        ):
                            break
                    try:
                        await websocket.send(json.dumps(["CLOSE", subscription_id]))
                    except Exception:
                        pass
        except Exception:
            # Try other locally configured relays; never follow a relay URL
            # supplied by the untrusted participant during discovery.
            continue

    if not candidates:
        raise NostrRecipientRelayListUnavailable(
            "no valid participant kind-10050 relay list was found"
        )
    return max(candidates, key=lambda candidate: candidate[0])[1]


async def listen_nip17_messages(
    relay_url: str,
    private_key: bytes,
    on_message: Callable[[dict[str, Any]], Any | Awaitable[Any]],
    *,
    authorize_sender: Callable[[str], bool | Awaitable[bool]],
    replay_store: SQLiteReplayStore | None = None,
    inbox_store: SQLiteNostrInboxStore | None = None,
    target_session_id: str | None = None,
    since: int | None = None,
    now_fn: Callable[[], int] | None = None,
    max_age_seconds: int = 600,
    future_tolerance_seconds: int = 300,
    stop_event: asyncio.Event | None = None,
    connect_factory: Callable[..., Any] | None = None,
    timeout: float = DEFAULT_RELAY_TIMEOUT_SECONDS,
    diagnostic_callback: Callable[[str], None] | None = None,
) -> None:
    """Listen for addressed kind-1059 events on one configured inbox relay.

    Invalid, oversized, unauthenticated, unauthorized, stale, or duplicate
    messages are ignored. The authenticated seal author is passed to
    ``authorize_sender``; only after it approves and the rumor's own timestamp
    passes freshness checks, deduplication is persisted. Supply exactly one of
    ``replay_store`` or ``inbox_store``. Legacy replay-store mode claims before
    invoking the callback and may lose a request if that handoff fails. Durable
    inbox mode persists the encrypted outer gift wrap and its target session
    before invoking the callback; a callback failure leaves a pending row that
    the caller must enumerate with ``list_pending`` after restart. Claiming an
    inbox row moves it to ``dispatching`` permanently; after a crash, inspect
    ``list_dispatching`` and do not automatically re-execute it. This preserves
    at-most-once CLI side effects but may require manual reconciliation. The
    function does not reconnect; the caller owns recovery, backoff, and CLI
    dispatch policy.
    """
    relay_url = _validate_relay_uri(relay_url)
    private_key = _validate_private_key(private_key)
    if since is not None and (not isinstance(since, int) or since < 0):
        raise ValueError("since must be a non-negative integer")
    if not callable(on_message):
        raise TypeError("on_message must be callable")
    if not callable(authorize_sender):
        raise TypeError("authorize_sender must be callable")
    if (replay_store is None) == (inbox_store is None):
        raise ValueError("provide exactly one of replay_store or inbox_store")
    if replay_store is not None:
        if not callable(getattr(replay_store, "claim", None)):
            raise TypeError("replay_store must provide an atomic claim method")
    else:
        if not callable(getattr(inbox_store, "enqueue_verified_wrap", None)):
            raise TypeError("inbox_store must provide enqueue_verified_wrap()")
        if (
            not isinstance(target_session_id, str)
            or not target_session_id
            or len(target_session_id) > 128
            or any(
                ord(char) < 32 or 127 <= ord(char) < 160 for char in target_session_id
            )
        ):
            raise ValueError("target_session_id is required for durable inbox mode")
    if now_fn is not None and not callable(now_fn):
        raise TypeError("now_fn must be callable")
    if diagnostic_callback is not None and not callable(diagnostic_callback):
        raise TypeError("diagnostic_callback must be callable")

    def record_diagnostic(event: str) -> None:
        # Diagnostics are non-authoritative and must never interrupt receipt.
        if diagnostic_callback is not None:
            try:
                diagnostic_callback(event)
            except Exception:
                pass

    connect = _connect_factory(connect_factory)
    pubkey = _public_key_x(private_key).hex()
    subscription_id = "uag-remote-" + secrets.token_hex(12)
    filter_data: dict[str, Any] = {"kinds": [1059], "#p": [pubkey], "limit": 100}
    if since is not None:
        filter_data["since"] = since
    request_frame = ["REQ", subscription_id, filter_data]
    auth_challenges: set[str] = set()
    pending_auth_event_id: str | None = None

    async with connect(
        relay_url,
        ssl=ssl.create_default_context(),
        open_timeout=float(timeout),
        close_timeout=min(float(timeout), 5.0),
        max_size=MAX_RELAY_FRAME_BYTES,
    ) as websocket:
        await websocket.send(
            json.dumps(request_frame, separators=(",", ":"), ensure_ascii=False)
        )
        record_diagnostic("connected")
        try:
            while stop_event is None or not stop_event.is_set():
                if stop_event is None:
                    raw = await websocket.recv()
                else:
                    try:
                        raw = await asyncio.wait_for(websocket.recv(), timeout=0.5)
                    except TimeoutError:
                        continue

                frame = _decode_relay_frame(raw)
                if frame is None or not frame:
                    continue
                if frame[0] == "AUTH" and len(frame) >= 2:
                    challenge = frame[1]
                    if not isinstance(challenge, str) or challenge in auth_challenges:
                        continue
                    auth_challenges.add(challenge)
                    auth_event = _make_auth_event(relay_url, challenge, private_key)
                    pending_auth_event_id = auth_event["id"]
                    await websocket.send(
                        json.dumps(["AUTH", auth_event], separators=(",", ":"))
                    )
                    continue
                if (
                    frame[0] == "OK"
                    and len(frame) >= 4
                    and frame[1] == pending_auth_event_id
                ):
                    pending_auth_event_id = None
                    if frame[2] is not True:
                        raise PermissionError(
                            f"relay rejected NIP-42 AUTH: {str(frame[3])[:400]}"
                        )
                    # Re-submit the REQ after authentication; relays commonly
                    # reject the unauthenticated subscription rather than queue it.
                    await websocket.send(
                        json.dumps(
                            request_frame, separators=(",", ":"), ensure_ascii=False
                        )
                    )
                    continue
                if frame[0] != "EVENT" or len(frame) < 3 or frame[1] != subscription_id:
                    continue
                event = frame[2]
                if not isinstance(event, dict) or event.get("kind") != 1059:
                    continue
                record_diagnostic("gift_wraps")
                try:
                    _event_json_bytes(event)
                except (TypeError, ValueError):
                    record_diagnostic("invalid")
                    continue
                if not _verify_event(event):
                    record_diagnostic("invalid")
                    continue
                try:
                    # NIP-01's event id covers these fields only. Drop any
                    # relay-added, unsigned keys before decrypting or storing.
                    canonical_event = {
                        field: event[field]
                        for field in (
                            "id",
                            "pubkey",
                            "created_at",
                            "kind",
                            "tags",
                            "content",
                            "sig",
                        )
                    }
                except (KeyError, TypeError):
                    record_diagnostic("invalid")
                    continue
                try:
                    rumor = unwrap_nip17_private_message(canonical_event, private_key)
                except (ValueError, TypeError, KeyError):
                    record_diagnostic("decrypt_failed")
                    continue
                sender = rumor["pubkey"]
                authorized = authorize_sender(sender)
                if inspect.isawaitable(authorized):
                    authorized = await authorized
                if not authorized:
                    record_diagnostic("unauthorized")
                    continue
                received_at = int(time.time()) if now_fn is None else now_fn()
                try:
                    validate_rumor_timestamp(
                        rumor["created_at"],
                        now=received_at,
                        max_age_seconds=max_age_seconds,
                        future_tolerance_seconds=future_tolerance_seconds,
                    )
                except ValueError:
                    record_diagnostic("stale")
                    continue
                if inbox_store is not None:
                    try:
                        enqueued = inbox_store.enqueue_verified_wrap(
                            sender,
                            rumor["id"],
                            canonical_event,
                            created_at=rumor["created_at"],
                            received_at=received_at,
                            session_id=target_session_id,
                        )
                    except (ValueError, InboxFullError):
                        # A malformed/oversized event or saturated local inbox
                        # rejects this request, not the entire relay listener.
                        record_diagnostic("inbox_rejected")
                        continue
                    if not enqueued:
                        record_diagnostic("duplicate")
                        continue
                elif not replay_store.claim(
                    sender, rumor["id"], received_at=received_at
                ):
                    record_diagnostic("duplicate")
                    continue
                result = on_message(rumor)
                if inspect.isawaitable(result):
                    await result
                record_diagnostic("queued")
        finally:
            record_diagnostic("disconnected")
            try:
                await websocket.send(json.dumps(["CLOSE", subscription_id]))
            except Exception:
                pass
