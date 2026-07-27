"""nostr_transport: Nostr relay transport for pybitchat.

Provides kind-1 (public text) and kind-1059 (bitchat private envelope) messaging
over Nostr relays. Uses a separate secp256k1 key pair (Nostr nsec standard).

Dependencies (auto-installed): websockets, pynacl
Uses pure-Python secp256k1 via _secp256k1 module (depends on ecdsa).
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import queue
import threading
import time as _time
from typing import Any, Callable


def ensure_dependencies() -> bool:
    """Check required packages are importable.

    Does NOT auto-install — all deps are lightweight and either pre-installed
    (websockets) or commonly available (pynacl). If missing, user is prompted.
    """
    missing = []
    try:
        import websockets  # noqa: F401
    except ImportError:
        missing.append("websockets")
    try:
        import nacl  # noqa: F401
    except ImportError:
        missing.append("pynacl")
    if missing:
        _notify_display(
            f"[nostr] Missing dependencies: {', '.join(missing)}. "
            f"Run: pip install {' '.join(missing)}"
        )
        return False
    return True


# ---- secp256k1 wrappers (delegated to _secp256k1 module) --------------------


def _import_secp() -> Any:
    """Lazy-import the pure-Python secp256k1 module."""
    from . import _secp256k1 as _s

    return _s


# ---- Key management ---------------------------------------------------------

_NOSTR_KEY_FILE = os.path.join(
    os.path.expanduser("~"), ".uag", "bitchat", "nostr_key.json"
)


def _load_or_create_key() -> tuple[str, str]:
    """Load existing Nostr key or generate a new secp256k1 key pair.

    Returns (nsec_hex, npub_hex) where nsec_hex is the 32-byte private key
    as hex, and npub_hex is the 32-byte x-only public key as hex.
    """
    try:
        if os.path.isfile(_NOSTR_KEY_FILE):
            with open(_NOSTR_KEY_FILE, "r") as f:
                data = json.load(f)
            priv_hex = data.get("private_key", "")
            pub_hex = data.get("public_key", "")
            if priv_hex and pub_hex and len(priv_hex) == 64:
                return priv_hex, pub_hex
    except Exception:
        pass

    _s = _import_secp()
    priv_bytes = _s.generate_private_key()
    pub_bytes = _s.private_to_public(priv_bytes)

    priv_hex = priv_bytes.hex()
    pub_hex = pub_bytes.hex()

    try:
        os.makedirs(os.path.dirname(_NOSTR_KEY_FILE), exist_ok=True)
        with open(_NOSTR_KEY_FILE, "w") as f:
            json.dump({"private_key": priv_hex, "public_key": pub_hex}, f)
    except Exception:
        pass

    return priv_hex, pub_hex


def _sign_event(payload: dict, priv_hex: str) -> str:
    """Sign a NIP-01 event with Schnorr signature.

    The payload dict must have at least: pubkey, created_at, kind, tags, content.
    Returns the 64-byte hex signature.
    """
    _s = _import_secp()

    serial = json.dumps(
        [
            0,
            payload.get("pubkey", ""),
            payload.get("created_at", 0),
            payload.get("kind", 1),
            payload.get("tags", []),
            payload.get("content", ""),
        ],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    event_id = hashlib.sha256(serial.encode("utf-8")).hexdigest()
    payload["id"] = event_id

    sig = _s.schnorr_sign(bytes.fromhex(priv_hex), bytes.fromhex(event_id))
    return sig.hex()


def _verify_event(event: dict) -> bool:
    """Verify a NIP-01 event signature."""
    _s = _import_secp()

    try:
        serial = json.dumps(
            [
                0,
                event.get("pubkey", ""),
                event.get("created_at", 0),
                event.get("kind", 1),
                event.get("tags", []),
                event.get("content", ""),
            ],
            separators=(",", ":"),
            ensure_ascii=False,
        )
        expected_id = hashlib.sha256(serial.encode("utf-8")).hexdigest()
        if expected_id != event.get("id", ""):
            return False

        event_id = event.get("id", "")
        sig_hex = event.get("sig", "")
        pubkey_hex = event.get("pubkey", "")

        if not event_id or not sig_hex or not pubkey_hex:
            return False

        return _s.schnorr_verify(
            bytes.fromhex(pubkey_hex),
            bytes.fromhex(event_id),
            bytes.fromhex(sig_hex),
        )
    except Exception:
        return False


# ---- Nostr relay message types ----------------------------------------------


def _make_subscription_filter(
    kinds: list[int] | None = None,
    authors: list[str] | None = None,
    limit: int | None = None,
    since: int | None = None,
    **extra,
) -> dict:
    filt: dict = {}
    if kinds:
        filt["kinds"] = kinds
    if authors:
        filt["authors"] = authors
    if limit is not None:
        filt["limit"] = limit
    if since is not None:
        filt["since"] = since
    filt.update(extra)
    return filt


def _make_text_event(
    content: str,
    priv_hex: str,
    pub_hex: str,
    tags: list[list[str]] | None = None,
) -> dict:
    """Create and sign a kind-1 text event."""
    now = int(_time.time())
    event: dict = {
        "pubkey": pub_hex,
        "created_at": now,
        "kind": 1,
        "tags": tags or [],
        "content": content,
    }
    sig = _sign_event(event, priv_hex)
    event["sig"] = sig
    return event


def _make_kind1059_event(
    content: str,
    priv_hex: str,
    pub_hex: str,
    recipient_pub_hex: str | None = None,
    tags: list[list[str]] | None = None,
) -> dict:
    """Create and sign a kind-1059 (bitchat private envelope) event.

    If recipient_pub_hex is given, the content is encrypted with
    XChaCha20-Poly1305 using ECDH shared key.
    Otherwise, content is plain text (public broadcast).
    """
    _s = _import_secp()
    import nacl.bindings as _nb

    tags_list = tags or []
    final_content = content

    if recipient_pub_hex:
        # ECDH shared key via secp256k1
        shared_key = _s.ecdh_shared_key(
            bytes.fromhex(priv_hex),
            bytes.fromhex(recipient_pub_hex),
        )

        # XChaCha20-Poly1305 encrypt
        nonce = os.urandom(24)
        encrypted = _nb.crypto_aead_xchacha20poly1305_ietf_encrypt(
            content.encode("utf-8"), None, nonce, shared_key
        )
        payload = nonce + encrypted
        final_content = "v2:" + base64.b64encode(payload).decode("ascii")
        tags_list.append(["p", recipient_pub_hex])

    now = int(_time.time())
    event: dict = {
        "pubkey": pub_hex,
        "created_at": now,
        "kind": 1059,
        "tags": tags_list,
        "content": final_content,
    }
    sig = _sign_event(event, priv_hex)
    event["sig"] = sig
    return event


def _decrypt_kind1059(
    event: dict,
    our_priv_hex: str,
    our_pub_hex: str,
) -> str | None:
    """Decrypt a kind-1059 event if it's encrypted with our key."""
    _s = _import_secp()
    import nacl.bindings as _nb

    content: str = event.get("content", "")
    if not content.startswith("v2:"):
        return content  # plain text

    try:
        payload = base64.b64decode(content[3:])
        if len(payload) < 24:
            return None
        nonce = payload[:24]
        ciphertext = payload[24:]

        sender_pub_hex = event.get("pubkey", "")
        if not sender_pub_hex:
            return None

        shared_key = _s.ecdh_shared_key(
            bytes.fromhex(our_priv_hex),
            bytes.fromhex(sender_pub_hex),
        )

        decrypted = _nb.crypto_aead_xchacha20poly1305_ietf_decrypt(
            ciphertext, None, nonce, shared_key
        )
        return decrypted.decode("utf-8")
    except Exception:
        return None


# ---- NostrTransport class ---------------------------------------------------

# Global instance (thread-safe access via functions)
_NOSTR_INSTANCE: "NostrTransport | None" = None
_NOSTR_LOCK = threading.Lock()


class NostrTransport:
    """Nostr relay transport for bitchat messaging.

    Runs in its own asyncio event loop in a daemon thread.
    """

    def __init__(
        self,
        *,
        relays: list[str] | None = None,
        priv_hex: str | None = None,
        pub_hex: str | None = None,
        nickname: str = "",
        on_message: Callable[[str, str, int], None] | None = None,
        on_kind1059: Callable[[str, str, str], None] | None = None,
    ):
        self.relays = relays or [
            "wss://relay.damus.io",
            "wss://nos.lol",
            "wss://relay.snort.social",
        ]
        self._priv_hex: str = priv_hex or ""
        self._pub_hex: str = pub_hex or ""
        self._nickname: str = (
            nickname or f"uag_{pub_hex[:8]}" if pub_hex else "anonymous"
        )
        self.on_message = on_message  # cb(nick, text, kind)
        self.on_kind1059 = on_kind1059  # cb(sender_pubkey, text, kind)

        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._relay_connections: dict[str, Any] = {}

        # Outbound queue (thread-safe)
        self._outbound: queue.Queue = queue.Queue()

        # Track seen event IDs to avoid duplicates
        self._seen_ids: set[str] = set()
        # Geo channel filters (additional #p tags)
        self._geo_filters: list[str] = []
        self._geo_filters_lock = threading.Lock()

        # Discovered peers: pubkey_hex -> nickname
        self._discovered_peers: dict[str, str] = {}

    @property
    def pubkey_hex(self) -> str:
        return self._pub_hex

    @property
    def is_running(self) -> bool:
        return self._running

    # ---- Geo channel filter management -------------------------------------

    def add_geo_filter(self, peer_id: str) -> None:
        """Add a #p tag filter for a geo channel peer ID."""
        with self._geo_filters_lock:
            if peer_id not in self._geo_filters:
                self._geo_filters.append(peer_id)

    def remove_geo_filter(self, peer_id: str) -> None:
        """Remove a #p tag filter for a geo channel."""
        with self._geo_filters_lock:
            try:
                self._geo_filters.remove(peer_id)
            except ValueError:
                pass

    def get_geo_p_tags(self) -> list[str]:
        """Get all geo-related #p tags for subscription filters."""
        with self._geo_filters_lock:
            return list(self._geo_filters)

    # ---- End geo channel filter management ---------------------------------

    # ---- Peer discovery ----------------------------------------------------

    @property
    def discovered_peers(self) -> dict[str, str]:
        """Get discovered peers (pubkey_hex -> nickname)."""
        return dict(self._discovered_peers)

    async def _beacon_loop(self) -> None:
        """Periodically announce presence on Nostr."""
        await asyncio.sleep(5)  # wait for connection
        while not self._stop_event.is_set():
            try:
                # Send a beacon: short kind-1 with our presence info
                beacon_text = f"bitchat beacon: {self._nickname}"
                self._outbound.put_nowait(
                    {
                        "type": "kind1",
                        "text": beacon_text,
                        "tags": [
                            ["display_name", self._nickname],
                            ["client", "bitchat"],
                            ["t", "bitchat"],
                            ["beacon", "presence"],
                        ],
                    }
                )
            except Exception:
                pass
            # Beacon every 5 minutes
            await asyncio.sleep(300)

    async def _discovery_subscribe(self) -> None:
        """Subscribe to #bitchat hashtag to discover other users."""
        await asyncio.sleep(5)  # wait for connection
        sub_filter = _make_subscription_filter(
            kinds=[1, 1059],
            limit=100,
            **{"#t": ["bitchat"]},
        )
        sub_msg = json.dumps(["REQ", "bitchat-discovery", sub_filter])
        try:
            for ws in list(self._relay_connections.values()):
                try:
                    await ws.send(sub_msg)
                except Exception:
                    pass
        except Exception:
            pass

        # Periodic re-subscribe
        last_since = int(_time.time())
        while not self._stop_event.is_set():
            await asyncio.sleep(120)
            sub_filter2 = _make_subscription_filter(
                kinds=[1, 1059],
                since=last_since,
                limit=50,
                **{"#t": ["bitchat"]},
            )
            sub_msg2 = json.dumps(["REQ", "bitchat-discovery", sub_filter2])
            for ws in list(self._relay_connections.values()):
                try:
                    await ws.send(sub_msg2)
                except Exception:
                    pass
            last_since = int(_time.time())

    # ---- End peer discovery ------------------------------------------------
    # ---- Public API ---------------------------------------------------------

    def start(self) -> dict:
        """Start the Nostr transport in a background thread."""
        if self._running:
            return {"ok": True, "state": "running"}

        # Load or create keys if not provided
        if not self._priv_hex:
            self._priv_hex, self._pub_hex = _load_or_create_key()

        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="nostr-transport",
        )
        self._thread.start()
        return {
            "ok": True,
            "state": "running",
            "pubkey": self._pub_hex,
            "relays": self.relays,
        }

    def stop(self) -> dict:
        """Stop the Nostr transport."""
        self._stop_event.set()
        self._running = False
        if self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        self._relay_connections.clear()
        self._tasks.clear()
        return {"ok": True, "state": "stopped"}

    def status(self) -> dict:
        """Get current status."""
        result: dict = {
            "ok": True,
            "state": "running" if self._running else "stopped",
            "pubkey": self._pub_hex,
            "relays": self.relays,
        }
        if self._running:
            result["connections"] = len(self._relay_connections)
        return result

    def send_text(self, text: str, tags: list[list[str]] | None = None) -> None:
        """Queue a kind-1 text event for broadcast."""
        self._outbound.put_nowait({"type": "kind1", "text": text, "tags": tags or []})

    def send_kind1059(
        self,
        text: str,
        recipient_pub_hex: str | None = None,
    ) -> None:
        """Queue a kind-1059 event (encrypted if recipient given)."""
        tags = []
        if recipient_pub_hex:
            tags.append(["p", recipient_pub_hex])
        # Add display_name for identification
        if self._nickname:
            tags.append(["display_name", self._nickname])
        tags.append(["client", "bitchat"])
        self._outbound.put_nowait(
            {
                "type": "kind1059",
                "text": text,
                "tags": tags,
                "recipient": recipient_pub_hex,
            }
        )

    def send_read_receipt(self, sender_pub_hex: str, event_id: str) -> None:
        """Send a read receipt for a received DM."""
        receipt_text = f"/receipt read {event_id[:16]}"
        self.send_kind1059(receipt_text, sender_pub_hex)

    # ---- Internal asyncio loop ----------------------------------------------

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._run())
        except Exception:
            pass
        finally:
            self._running = False

    async def _run(self) -> None:
        tasks = [
            asyncio.create_task(self._process_outbound()),
        ]
        for relay_url in self.relays:
            tasks.append(asyncio.create_task(self._connect_relay(relay_url)))
        self._tasks = tasks

        # Subscribe to kind-1 and kind-1059 events mentioning our pubkey
        tasks.append(asyncio.create_task(self._subscribe_loop()))

        # Beacon: periodically announce our presence
        tasks.append(asyncio.create_task(self._beacon_loop()))

        # Discovery: subscribe to #bitchat hashtag to find other users
        if self._pub_hex:
            tasks.append(asyncio.create_task(self._discovery_subscribe()))

        await asyncio.sleep(0.1)

        while not self._stop_event.is_set():
            await asyncio.sleep(1)

        # Cleanup
        for task in tasks:
            task.cancel()
        for ws in self._relay_connections.values():
            try:
                await ws.close()
            except Exception:
                pass

    async def _connect_relay(self, url: str) -> None:
        import websockets
        import websockets.exceptions as _wse

        while not self._stop_event.is_set():
            try:
                async with websockets.connect(
                    url,
                    ping_interval=30,
                    ping_timeout=10,
                    max_size=2**20,
                ) as ws:
                    self._relay_connections[url] = ws
                    _notify_display(f"[nostr] Connected to {url}")

                    # Subscribe to events addressed to us + geo channels
                    p_tags = self.get_geo_p_tags()
                    p_tags.append(self._pub_hex)
                    sub_filter = _make_subscription_filter(
                        kinds=[1, 1059],
                        limit=50,
                        since=int(_time.time()) - 300,
                        **{"#p": p_tags},
                    )
                    sub_msg = json.dumps(["REQ", "bitchat-sub", sub_filter])
                    await ws.send(sub_msg)

                    async for raw in ws:
                        if self._stop_event.is_set():
                            break
                        try:
                            data = json.loads(raw)
                            if not isinstance(data, list) or len(data) < 2:
                                continue
                            msg_type = data[0]
                            if msg_type == "EVENT" and len(data) >= 3:
                                event = data[2]
                                await self._handle_event(event)
                            elif msg_type == "EOSE":
                                pass  # end of stored events
                        except json.JSONDecodeError:
                            continue
                        except Exception:
                            continue
            except asyncio.CancelledError:
                break
            except (_wse.WebSocketException, OSError, asyncio.TimeoutError) as e:
                _notify_display(f"[nostr] Relay {url} disconnected: {e}")
                self._relay_connections.pop(url, None)
                if not self._stop_event.is_set():
                    await asyncio.sleep(10)  # reconnect delay
                    continue
            except Exception as e:
                _notify_display(f"[nostr] Relay {url} error: {e}")
                self._relay_connections.pop(url, None)
                if not self._stop_event.is_set():
                    await asyncio.sleep(30)
                    continue
            break  # intentional disconnect

        self._relay_connections.pop(url, None)

    async def _subscribe_loop(self) -> None:
        """Periodically re-subscribe with a since filter for new events."""
        last_since = int(_time.time())
        while not self._stop_event.is_set():
            await asyncio.sleep(30)
            now = int(_time.time())
            p_tags = self.get_geo_p_tags()
            p_tags.append(self._pub_hex)
            sub_filter = _make_subscription_filter(
                kinds=[1, 1059],
                since=last_since,
                limit=50,
                **{"#p": p_tags},
            )
            sub_msg = json.dumps(["REQ", "bitchat-sub-recent", sub_filter])
            for url, ws in list(self._relay_connections.items()):
                try:
                    await ws.send(sub_msg)
                except Exception:
                    pass
            last_since = now

    async def _handle_event(self, event: dict) -> None:
        """Process an incoming Nostr event."""
        event_id = event.get("id", "")
        if not event_id or event_id in self._seen_ids:
            return
        self._seen_ids.add(event_id)
        if len(self._seen_ids) > 10000:
            self._seen_ids = set(list(self._seen_ids)[-5000:])

        kind = event.get("kind", -1)
        pubkey = event.get("pubkey", "")
        content = event.get("content", "")
        tags = event.get("tags", [])

        # Skip our own events
        if pubkey == self._pub_hex:
            return

        # Verify signature
        if not _verify_event(event):
            return

        # Discover peers: record any verified bitchat client
        is_bitchat = False
        nick_from_tags = None
        for tag in tags:
            if len(tag) >= 2:
                if tag[0] == "client" and tag[1] == "bitchat":
                    is_bitchat = True
                elif tag[0] == "display_name":
                    nick_from_tags = tag[1]
        if is_bitchat and pubkey:
            nick = nick_from_tags or pubkey[:8]
            if (
                pubkey not in self._discovered_peers
                or self._discovered_peers[pubkey] != nick
            ):
                old = self._discovered_peers.get(pubkey)
                self._discovered_peers[pubkey] = nick
                if old is None:
                    _notify_display(
                        f"[nostr] Discovered bitchat user: {nick} ({pubkey[:16]}...)"
                    )
        if kind == 1:
            # Public text message
            nick = None
            for tag in tags:
                if len(tag) >= 2 and tag[0] == "display_name":
                    nick = tag[1]
                    break
            if not nick:
                nick = pubkey[:8]

            if self.on_message:
                self.on_message(nick, content, kind)

            # Show locally
            _notify_display(f"[nostr] {nick}: {content}")

            # Forward to BLE mesh if bridge active (skip forwarded mesh messages)
            if not content.startswith("[mesh]") and not content.startswith("[nostr/"):
                try:
                    from .pybitchat_shared import enqueue_send as _es, _NOSTR_BRIDGE

                    if _NOSTR_BRIDGE:
                        _es("text", f"[nostr] {nick}: {content}", via="ble")
                except Exception:
                    pass

        elif kind == 1059:
            # Bitchat private envelope
            is_for_us = False
            for tag in tags:
                if len(tag) >= 2 and tag[0] == "p" and tag[1] == self._pub_hex:
                    is_for_us = True
                    break

            # Extract display_name from tags
            sender_nick = None
            for tag in tags:
                if len(tag) >= 2 and tag[0] == "display_name":
                    sender_nick = tag[1]
                    break
            if not sender_nick:
                sender_nick = pubkey[:8]

            decrypted = None
            if is_for_us:
                decrypted = _decrypt_kind1059(event, self._priv_hex, self._pub_hex)

            if decrypted is not None:
                nick = sender_nick
                if self.on_kind1059:
                    self.on_kind1059(pubkey, decrypted, content)
                if content.startswith("v2:"):
                    _notify_display(f"[nostr/dm] {nick}: {decrypted}")
                    # Auto-send read receipt for DMs
                    if not decrypted.startswith("/read ") and not decrypted.startswith(
                        "/receipt"
                    ):
                        self.send_read_receipt(pubkey, event_id)
                        # Forward to BLE mesh if bridge active (skip loops)
                        if not decrypted.startswith(
                            "[mesh]"
                        ) and not decrypted.startswith("[nostr/"):
                            try:
                                from .pybitchat_shared import (
                                    enqueue_send as _es,
                                    _NOSTR_BRIDGE,
                                )

                                if _NOSTR_BRIDGE:
                                    _es(
                                        "text",
                                        f"[nostr/dm] {nick}: {decrypted}",
                                        via="ble",
                                    )
                            except Exception:
                                pass
                else:
                    _notify_display(f"[nostr] {nick}: {decrypted}")
            elif is_for_us:
                _notify_display(
                    f"[nostr] Decrypt failed for kind-1059 from {pubkey[:8]}"
                )
            else:
                # Public kind-1059 (non-encrypted)
                nick = pubkey[:8]
                if self.on_message:
                    self.on_message(nick, content, kind)
                _notify_display(f"[nostr] {nick}: {content}")

    async def _process_outbound(self) -> None:
        """Process outbound message queue and send to all connected relays."""
        while not self._stop_event.is_set():
            try:
                item = self._outbound.get(timeout=0.5)
            except queue.Empty:
                await asyncio.sleep(0.1)
                continue

            try:
                msg_type = item.get("type")
                if msg_type == "kind1":
                    event = _make_text_event(
                        content=item["text"],
                        priv_hex=self._priv_hex,
                        pub_hex=self._pub_hex,
                        tags=item.get("tags"),
                    )
                elif msg_type == "kind1059":
                    event = _make_kind1059_event(
                        content=item["text"],
                        priv_hex=self._priv_hex,
                        pub_hex=self._pub_hex,
                        recipient_pub_hex=item.get("recipient"),
                        tags=item.get("tags"),
                    )
                else:
                    continue

                event_json = json.dumps(["EVENT", event])
                for url, ws in list(self._relay_connections.items()):
                    try:
                        await ws.send(event_json)
                    except Exception:
                        pass
            except Exception:
                continue

    def get_pubkey_hex(self) -> str:
        return self._pub_hex


# ---- Module-level helper functions ------------------------------------------


def _notify_display(msg: str) -> None:
    """Display notification (not sent to LLM)."""
    try:
        print(msg, flush=True)
    except Exception:
        pass


def get_nostr_instance() -> NostrTransport | None:
    """Get the global NostrTransport instance."""
    global _NOSTR_INSTANCE
    with _NOSTR_LOCK:
        return _NOSTR_INSTANCE


def start_nostr(
    *,
    relays: list[str] | None = None,
    priv_hex: str | None = None,
    pub_hex: str | None = None,
    nickname: str = "",
    on_message: Callable | None = None,
    on_kind1059: Callable | None = None,
) -> dict:
    """Start the global Nostr transport."""
    global _NOSTR_INSTANCE
    with _NOSTR_LOCK:
        if _NOSTR_INSTANCE and _NOSTR_INSTANCE.is_running:
            return {
                "ok": True,
                "state": "running",
                "pubkey": _NOSTR_INSTANCE.pubkey_hex,
            }

        # Silently check deps — if missing they'll fail at connect time
        try:
            ensure_dependencies()
        except Exception:
            pass

        _NOSTR_INSTANCE = NostrTransport(
            relays=relays,
            priv_hex=priv_hex,
            pub_hex=pub_hex,
            nickname=nickname,
            on_message=on_message,
            on_kind1059=on_kind1059,
        )
        return _NOSTR_INSTANCE.start()


def stop_nostr() -> dict:
    """Stop the global Nostr transport."""
    global _NOSTR_INSTANCE
    with _NOSTR_LOCK:
        if _NOSTR_INSTANCE:
            result = _NOSTR_INSTANCE.stop()
            _NOSTR_INSTANCE = None
            return result
        return {"ok": True, "state": "stopped"}


def nostr_status() -> dict:
    """Get global Nostr transport status."""
    inst = get_nostr_instance()
    if inst and inst.is_running:
        return inst.status()
    return {"ok": True, "state": "stopped"}


def nostr_send_text(text: str, tags: list[list[str]] | None = None) -> dict:
    """Send a kind-1 text message via Nostr."""
    inst = get_nostr_instance()
    if not inst or not inst.is_running:
        return {"ok": False, "error": "Nostr transport not running"}
    inst.send_text(text, tags)
    return {"ok": True, "via": "nostr", "kind": 1}


def nostr_send_kind1059(
    text: str,
    recipient_pub_hex: str | None = None,
) -> dict:
    """Send a kind-1059 message via Nostr."""
    inst = get_nostr_instance()
    if not inst or not inst.is_running:
        return {"ok": False, "error": "Nostr transport not running"}
    inst.send_kind1059(text, recipient_pub_hex)
    return {"ok": True, "via": "nostr", "kind": 1059}


def nostr_pubkey() -> str:
    """Get our Nostr public key hex."""
    inst = get_nostr_instance()
    if inst:
        return inst.pubkey_hex
    return ""
