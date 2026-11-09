"""Isolated NIP-17 relay I/O primitives for experimental remote CLI work.

This module deliberately does not alter the legacy bitchat Nostr transport or
start a CLI remote-control service. It publishes already-created kind-1059
NIP-17 gift wraps to their verified inbox-relay lists and listens for addressed
wraps. The separate foreground dispatcher can validate and map accepted rumors
to the existing CLI event kinds, but pairing-store wiring, service lifecycle,
response delivery, and the local relay/egress allowlist remain caller-owned.
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
    unwrap_nip17_private_message,
)
from .nostr_remote_state import SQLiteReplayStore, validate_rumor_timestamp
from .tools.nostr_transport import _verify_event

MAX_RELAY_FRAME_BYTES = 1_000_000
DEFAULT_RELAY_TIMEOUT_SECONDS = 15


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
    if connect_factory is not None:
        return connect_factory
    try:
        from websockets.asyncio.client import connect
    except ImportError as exc:
        raise ModuleNotFoundError("Nostr remote transport requires websockets") from exc
    return connect


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
                            await websocket.send(
                                json.dumps(
                                    ["EVENT", event],
                                    separators=(",", ":"),
                                    ensure_ascii=False,
                                )
                            )
                            continue
                        if frame[1] == event_id:
                            return RelayDelivery(
                                relay_url=relay_url,
                                event_id=event_id,
                                accepted=frame[2] is True,
                                message=str(frame[3])[:512],
                            )
                    if frame[0] == "NOTICE" and len(frame) >= 2:
                        notice = str(frame[1])[:512]
                        if notice.lower().startswith("auth-required"):
                            return RelayDelivery(relay_url, event_id, False, notice)
    except TimeoutError:
        return RelayDelivery(relay_url, event_id, False, "relay response timed out")
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


async def listen_nip17_messages(
    relay_url: str,
    private_key: bytes,
    on_message: Callable[[dict[str, Any]], Any | Awaitable[Any]],
    *,
    authorize_sender: Callable[[str], bool | Awaitable[bool]],
    replay_store: SQLiteReplayStore,
    since: int | None = None,
    now_fn: Callable[[], int] | None = None,
    max_age_seconds: int = 600,
    future_tolerance_seconds: int = 300,
    stop_event: asyncio.Event | None = None,
    connect_factory: Callable[..., Any] | None = None,
    timeout: float = DEFAULT_RELAY_TIMEOUT_SECONDS,
) -> None:
    """Listen for addressed kind-1059 events on one configured inbox relay.

    Invalid, oversized, unauthenticated, unauthorized, stale, or duplicate
    messages are ignored. The authenticated seal author is passed to
    ``authorize_sender``; only after it approves and the rumor's own timestamp
    passes freshness checks is the sender/rumor pair atomically claimed in
    ``replay_store``. The callback therefore only sees authorized, fresh,
    first-seen rumors. Claim-before-callback is intentionally at-most-once: if
    the callback or process fails after the claim but before it durably hands
    off the request, the rumor can be lost rather than replayed. A retryable
    inbox/outbox transaction is required before promising delivery. This
    function does not reconnect; the caller owns reconnect/backoff and CLI
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
    if not callable(getattr(replay_store, "claim", None)):
        raise TypeError("replay_store must provide an atomic claim method")
    if now_fn is not None and not callable(now_fn):
        raise TypeError("now_fn must be callable")

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
                try:
                    _event_json_bytes(event)
                except (TypeError, ValueError):
                    continue
                if not _verify_event(event):
                    continue
                try:
                    rumor = unwrap_nip17_private_message(event, private_key)
                except (ValueError, TypeError, KeyError):
                    continue
                sender = rumor["pubkey"]
                authorized = authorize_sender(sender)
                if inspect.isawaitable(authorized):
                    authorized = await authorized
                if not authorized:
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
                    continue
                if not replay_store.claim(sender, rumor["id"], received_at=received_at):
                    continue
                result = on_message(rumor)
                if inspect.isawaitable(result):
                    await result
        finally:
            try:
                await websocket.send(json.dumps(["CLOSE", subscription_id]))
            except Exception:
                pass
