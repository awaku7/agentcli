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

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

TOOL_SPEC: dict[str, Any] = {
    "tool_level": -1,  # Dynamic commands only
    "type": "function",
    "function": {
        "name": "nostr_transport_dummy",
        "description": "Dummy tool for Nostr transport CLI commands registration.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    return _("nostr.registered", default="Nostr transport CLI commands registered.")


def ensure_dependencies() -> bool:
    """Check required packages are importable and auto-install if missing."""
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
        from ._pip_auto import ensure_packages

        if ensure_packages(missing, "nostr"):
            return True
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


# ---- Bech32 / npub helpers --------------------------------------------------


def _bech32_polymod(values: list[int]) -> int:
    GEN = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for v in values:
        b = chk >> 25
        chk = ((chk & 0x1FFFFFF) << 5) ^ v
        for i in range(5):
            chk ^= GEN[i] if ((b >> i) & 1) else 0
    return chk


def _bech32_hrp_expand(hrp: str) -> list[int]:
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def _bech32_create_checksum(hrp: str, data: list[int]) -> list[int]:
    values = _bech32_hrp_expand(hrp) + data
    polymod = _bech32_polymod(values + [0, 0, 0, 0, 0, 0]) ^ 1
    return [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]


def _convertbits(
    data: bytes | list[int], frombits: int, tobits: int, pad: bool = True
) -> list[int] | None:
    acc = 0
    bits = 0
    ret = []
    maxv = (1 << tobits) - 1
    max_acc = (1 << (frombits + tobits - 1)) - 1
    for value in data:
        if value < 0 or (value >> frombits):
            return None
        acc = ((acc << frombits) | value) & max_acc
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if pad:
        if bits:
            ret.append((acc << (tobits - bits)) & maxv)
    elif bits >= frombits or ((acc << (tobits - bits)) & maxv):
        return None
    return ret


# ---- Key management ---------------------------------------------------------

_NOSTR_KEY_FILE = os.path.join(
    os.path.expanduser("~"), ".uag", "bitchat", "nostr_key.json"
)


class NostrKeyUnreadableError(RuntimeError):
    """The stored Nostr key file exists but cannot be decrypted or parsed.

    Raised instead of generating a replacement key, so a temporarily
    unavailable encryption backend (for example a locked OS keyring) can
    never silently destroy the stored identity.
    """


def _parse_key_text(text: str) -> tuple[str, str] | None:
    """Parse key-file JSON text into (private_key, public_key) hex."""
    try:
        data = json.loads(text)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    priv_hex = data.get("private_key", "")
    pub_hex = data.get("public_key", "")
    if priv_hex and pub_hex and len(priv_hex) == 64:
        return priv_hex, pub_hex
    return None


def _write_key_file(priv_hex: str, pub_hex: str) -> None:
    """Write the key file encrypted with uag_envsec, owner-only permissions.

    Falls back to plaintext JSON (still written with 0600 permissions) when
    the encryption helper is unavailable, so a key is never lost over a
    storage failure.
    """
    payload = json.dumps({"private_key": priv_hex, "public_key": pub_hex})
    text = payload
    try:
        from uag_envsec import encrypt_text, ensure_key_file

        ensure_key_file()
        text = encrypt_text(payload) + "\n"
    except Exception:
        pass
    os.makedirs(os.path.dirname(_NOSTR_KEY_FILE), exist_ok=True)
    tmp_path = _NOSTR_KEY_FILE + ".tmp"
    try:
        # Create the temp file owner-only from the outset (and tighten a
        # pre-existing temp file before writing), so the key material is
        # never briefly readable by other local users.
        fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            if os.name != "nt":
                try:
                    os.fchmod(fd, 0o600)
                except OSError:
                    pass
            handle = os.fdopen(fd, "w", encoding="utf-8", newline="\n")
        except BaseException:
            os.close(fd)
            raise
        with handle:
            handle.write(text)
        os.replace(tmp_path, _NOSTR_KEY_FILE)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _read_key_file() -> tuple[str, str] | None:
    """Read the stored key pair, migrating legacy plaintext files.

    New files hold a uag_envsec ciphertext token. A plaintext JSON file
    (written by older versions) is still accepted and is rewritten in
    encrypted form as a side effect of the read.

    Returns None only when no key file exists. When the file exists but
    cannot be decrypted or parsed, raises NostrKeyUnreadableError so the
    caller never replaces the stored identity with a fresh key.
    """
    try:
        with open(_NOSTR_KEY_FILE, "r", encoding="utf-8") as f:
            raw = f.read()
    except OSError:
        return None
    parsed = _parse_key_text(raw)
    if parsed is not None:
        try:
            _write_key_file(*parsed)
        except Exception:
            pass
        return parsed
    try:
        from uag_envsec import decrypt_text

        parsed = _parse_key_text(decrypt_text(raw.strip()))
    except Exception:
        parsed = None
    if parsed is None:
        raise NostrKeyUnreadableError(
            "stored Nostr key file exists but cannot be decrypted: " + _NOSTR_KEY_FILE
        )
    return parsed


def _load_or_create_key() -> tuple[str, str]:
    """Load existing Nostr key or generate a new secp256k1 key pair.

    Returns (nsec_hex, npub_hex) where nsec_hex is the 32-byte private key
    as hex, and npub_hex is the 32-byte x-only public key as hex.
    """
    if os.path.isfile(_NOSTR_KEY_FILE):
        existing = _read_key_file()
        if existing is not None:
            return existing

    _s = _import_secp()
    priv_bytes = _s.generate_private_key()
    pub_bytes = _s.private_to_public(priv_bytes)

    priv_hex = priv_bytes.hex()
    pub_hex = pub_bytes.hex()

    try:
        _write_key_file(priv_hex, pub_hex)
    except Exception:
        pass

    return priv_hex, pub_hex


def _get_ssl_context() -> Any:
    """Return SSLContext respecting UAGENT_SSL_VERIFY / util_providers setting."""
    import ssl
    from ..providers.util_providers import is_ssl_verify_disabled

    verify = (os.getenv("UAGENT_SSL_VERIFY") or "1").strip().lower()
    if is_ssl_verify_disabled() or verify in ("0", "false", "no", "off"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return None


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
            "wss://x.kojira.io",
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

        ssl_ctx = _get_ssl_context()
        while not self._stop_event.is_set():
            try:
                kwargs: dict[str, Any] = {
                    "ping_interval": 30,
                    "ping_timeout": 10,
                    "max_size": 2**20,
                }
                if ssl_ctx is not None:
                    kwargs["ssl"] = ssl_ctx
                async with websockets.connect(url, **kwargs) as ws:
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

        # Silently check deps -- if missing they'll fail at connect time
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


def encode_npub(pubkey_hex: str) -> str:
    """Encode a 32-byte hex public key to bech32 npub format."""
    if not pubkey_hex or len(pubkey_hex) != 64:
        return _("nostr.empty_pubkey", default="")
    try:
        data = bytes.fromhex(pubkey_hex)
        converted = _convertbits(data, 8, 5, True)
        checksum = _bech32_create_checksum("npub", converted)
        return "npub1" + "".join(
            "qpzry9x8gf2tvdw0s3jn54khce6mua7l"[p] for p in converted + checksum
        )
    except Exception:
        return _("nostr.empty_fallback", default="")


def nostr_pubkey() -> str:
    """Get our Nostr public key hex."""
    inst = get_nostr_instance()
    if inst and inst.pubkey_hex:
        return inst.pubkey_hex
    priv, pub = _load_or_create_key()
    return pub


# ---- CLI Command Specs (:nostr) --------------------------------------------


def _cmd_nostr_connect(arg: str, **kwargs: Any) -> Any:
    """Handle :nostr connect [relay_urls...]"""
    relays = (
        [r.strip() for r in arg.split(",") if r.strip()]
        if "," in arg
        else [r.strip() for r in arg.split() if r.strip()]
    )
    relays = relays or None
    res = start_nostr(relays=relays)
    if res.get("ok"):
        pubkey = res.get("pubkey", "")
        npub = encode_npub(pubkey)
        print(_("nostr.msg1", default="Nostr connected."))
        if pubkey:
            print(_("nostr.msg2", default=f"  pubkey (hex):  {pubkey}"))
            if npub:
                print(_("nostr.msg3", default=f"  pubkey (npub): {npub}"))
        r_list = res.get("relays", [])
        for r in r_list:
            print(_("nostr.msg4", default=f"  relay: {r}"))
    else:
        print(_("nostr.msg5", default=f"Error connecting to Nostr: {res.get('error')}"))
    from ..util_tools import CommandResult

    return CommandResult()


def _cmd_nostr_disconnect(arg: str, **kwargs: Any) -> Any:
    """Handle :nostr disconnect"""
    stop_nostr()
    print(_("nostr.msg6", default="Nostr disconnected."))
    from ..util_tools import CommandResult

    return CommandResult()


def _cmd_nostr_status(arg: str, **kwargs: Any) -> Any:
    """Handle :nostr status"""
    st = nostr_status()
    state = st.get("state", "stopped")
    pub = st.get("pubkey", "") or nostr_pubkey()
    npub = encode_npub(pub)
    print(_("nostr.msg7", default=f"Nostr status: {state}"))
    if pub:
        print(_("nostr.msg8", default=f"  pubkey (hex):  {pub}"))
        if npub:
            print(_("nostr.msg9", default=f"  pubkey (npub): {npub}"))
    print(_("nostr.msg10", default=f"  key file:      {_NOSTR_KEY_FILE}"))
    if state == "running":
        conns = st.get("connections", 0)
        relays = st.get("relays", [])
        print(_("nostr.msg11", default=f"  connections:   {conns}"))
        for r in relays:
            print(_("nostr.msg12", default=f"  relay:         {r}"))
    from ..util_tools import CommandResult

    return CommandResult()


def _cmd_nostr_post(arg: str, **kwargs: Any) -> Any:
    """Handle :nostr post <message>"""
    msg = arg.strip()
    if not msg:
        print(_("nostr.msg13", default="Usage: :nostr post <message>"))
        from ..util_tools import CommandResult

        return CommandResult()

    inst = get_nostr_instance()
    if not inst or not inst.is_running:
        res = start_nostr()
        if not res.get("ok"):
            print(_("nostr.msg14", default=f"Error starting Nostr: {res.get('error')}"))
            from ..util_tools import CommandResult

            return CommandResult()
        inst = get_nostr_instance()

    res = nostr_send_text(msg)
    if res.get("ok"):
        print(_("nostr.msg15", default=f"Posted note to Nostr: {msg}"))
    else:
        print(_("nostr.msg16", default=f"Error posting note: {res.get('error')}"))
    from ..util_tools import CommandResult

    return CommandResult()


def _cmd_nostr_timeline(arg: str, **kwargs: Any) -> Any:
    """Handle :nostr timeline [limit]"""
    limit = 20
    if arg.strip().isdigit():
        limit = int(arg.strip())

    inst = get_nostr_instance()
    if not inst or not inst.is_running:
        print(
            _("nostr.msg17", default="Starting Nostr connection to fetch timeline...")
        )
        res = start_nostr()
        if not res.get("ok"):
            print(_("nostr.msg18", default=f"Error starting Nostr: {res.get('error')}"))
            from ..util_tools import CommandResult

            return CommandResult()
        inst = get_nostr_instance()

    # Request global kind-1 notes from relays
    print(
        _("nostr.msg19", default=f"Fetching recent {limit} notes from Nostr relays...")
    )
    notes: list[dict] = []
    import websockets
    import asyncio

    async def _fetch():
        sub_filter = _make_subscription_filter(kinds=[1], limit=limit)
        req = json.dumps(["REQ", "timeline-fetch", sub_filter])
        for url in inst.relays:
            try:
                async with websockets.connect(url, timeout=5) as ws:
                    await ws.send(req)
                    while True:
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=2.5)
                            data = json.loads(msg)
                            if (
                                isinstance(data, list)
                                and len(data) >= 3
                                and data[0] == "EVENT"
                            ):
                                ev = data[2]
                                if ev.get("kind") == 1:
                                    notes.append(ev)
                            elif (
                                isinstance(data, list)
                                and len(data) >= 2
                                and data[0] in ("EOSE", "CLOSED")
                            ):
                                break
                        except asyncio.TimeoutError:
                            break
            except Exception:
                pass

    try:
        asyncio.run(_fetch())
    except Exception as e:
        print(_("nostr.msg20", default=f"Fetch timeline error: {e}"))

    # Deduplicate and sort by created_at
    seen = set()
    unique_notes = []
    for n in notes:
        nid = n.get("id")
        if nid and nid not in seen:
            seen.add(nid)
            unique_notes.append(n)

    unique_notes.sort(key=lambda x: x.get("created_at", 0))

    if not unique_notes:
        print(_("nostr.msg21", default="No recent notes found."))
    else:
        print(
            _(
                "nostr.msg22",
                default=f"--- Nostr Timeline ({len(unique_notes)} notes) ---",
            )
        )
        for n in unique_notes[-limit:]:
            pk = n.get("pubkey", "")
            npub = encode_npub(pk)
            short_author = npub[:16] + "..." if npub else pk[:8]
            ts = _time.strftime(
                "%Y-%m-%d %H:%M:%S", _time.localtime(n.get("created_at", 0))
            )
            text = n.get("content", "").strip().replace("\n", " ")
            print(_("nostr.msg23", default=f"[{ts}] {short_author}: {text}"))

    from ..util_tools import CommandResult

    return CommandResult()


def _pairing_database_path() -> Any:
    """Return the local pairing registry path under UAG's database directory."""
    from ..utils.paths import get_dbs_dir

    return get_dbs_dir() / "nostr_remote_pairings.sqlite3"


def _cmd_nostr_pair(arg: str, **kwargs: Any) -> Any:
    """Locally approve a Nostr device by its x-only public-key hex."""
    from ..nostr_remote_pairing import SQLitePairingStore
    from ..util_tools import CommandResult

    parts = arg.strip().split(maxsplit=1)
    if not parts:
        print(
            _(
                "nostr.pair_usage",
                default="Usage: :nostr pair <pubkey_hex> [label]",
            )
        )
        return CommandResult()

    try:
        path = _pairing_database_path()
        os.makedirs(os.path.dirname(os.fspath(path)), exist_ok=True)
        with SQLitePairingStore(path) as store:
            from ..nostr_setup import decode_pairing_pubkey

            record = store.pair(
                decode_pairing_pubkey(parts[0]),
                parts[1] if len(parts) > 1 else "",
                approved=True,
            )
        print(
            _(
                "nostr.pair_success",
                default="Paired Nostr device: %(pubkey)s (%(label)s)",
                pubkey=record.pubkey,
                label=record.label or "unnamed",
            )
        )
    except Exception as exc:
        print(
            _(
                "nostr.pair_error",
                default="Could not pair Nostr device: %(error)s",
                error=exc,
            )
        )
    return CommandResult()


def _cmd_nostr_revoke(arg: str, **kwargs: Any) -> Any:
    """Locally revoke a paired Nostr device by its x-only public-key hex."""
    from ..nostr_remote_pairing import SQLitePairingStore
    from ..util_tools import CommandResult

    pubkey = arg.strip()
    if not pubkey or any(char.isspace() for char in pubkey):
        print(
            _(
                "nostr.revoke_usage",
                default="Usage: :nostr revoke <pubkey_hex>",
            )
        )
        return CommandResult()

    try:
        path = _pairing_database_path()
        os.makedirs(os.path.dirname(os.fspath(path)), exist_ok=True)
        with SQLitePairingStore(path) as store:
            revoked = store.revoke(pubkey)
        print(
            _("nostr.device_revoked", default="Nostr device revoked.")
            if revoked
            else _(
                "nostr.no_active_pairing",
                default="No active pairing for that key.",
            )
        )
    except Exception as exc:
        print(
            _(
                "nostr.revoke_error",
                default="Could not revoke Nostr device: %(error)s",
                error=exc,
            )
        )
    return CommandResult()


def _cmd_nostr_devices(arg: str, **kwargs: Any) -> Any:
    """List locally paired Nostr devices; append 'all' to include revoked ones."""
    from ..nostr_remote_pairing import SQLitePairingStore
    from ..util_tools import CommandResult

    option = arg.strip().lower()
    if option not in ("", "all"):
        print(
            _(
                "nostr.devices_usage",
                default="Usage: :nostr devices [all]",
            )
        )
        return CommandResult()

    try:
        path = _pairing_database_path()
        os.makedirs(os.path.dirname(os.fspath(path)), exist_ok=True)
        with SQLitePairingStore(path) as store:
            records = store.list_devices(include_revoked=option == "all")
        if not records:
            print(
                _(
                    "nostr.no_paired_devices",
                    default="No paired Nostr devices.",
                )
            )
        for record in records:
            status = "revoked" if record.revoked_at is not None else "active"
            print(
                _(
                    "nostr.device_status",
                    default="%(pubkey)s  %(label)s  [%(status)s]",
                    pubkey=record.pubkey,
                    label=record.label or "unnamed",
                    status=status,
                )
            )
    except Exception as exc:
        print(
            _(
                "nostr.devices_error",
                default="Could not list Nostr devices: %(error)s",
                error=exc,
            )
        )
    return CommandResult()


CMD_SPECS = [
    {
        "command": "nostr",
        "subcommand": "connect",
        "handler": _cmd_nostr_connect,
        "help_text": "  :nostr connect [relay_urls]  Connect to Nostr relays",
    },
    {
        "command": "nostr",
        "subcommand": "disconnect",
        "handler": _cmd_nostr_disconnect,
        "help_text": "  :nostr disconnect            Disconnect from Nostr relays",
    },
    {
        "command": "nostr",
        "subcommand": "status",
        "handler": _cmd_nostr_status,
        "help_text": "  :nostr status                Show Nostr connection status",
    },
    {
        "command": "nostr",
        "subcommand": "post",
        "handler": _cmd_nostr_post,
        "help_text": "  :nostr post <message>        Post a public text note (Kind 1) to Nostr",
    },
    {
        "command": "nostr",
        "subcommand": "timeline",
        "handler": _cmd_nostr_timeline,
        "help_text": "  :nostr timeline [limit]      Fetch recent public notes (Kind 1) from relays",
    },
]


CMD_SPECS.extend(
    [
        {
            "command": "nostr",
            "subcommand": "pair",
            "handler": _cmd_nostr_pair,
            "help_text": "  :nostr pair <pubkey_or_npub> [label]  Locally approve a remote device",
        },
        {
            "command": "nostr",
            "subcommand": "revoke",
            "handler": _cmd_nostr_revoke,
            "help_text": "  :nostr revoke <pubkey_hex>    Revoke a remote device",
        },
        {
            "command": "nostr",
            "subcommand": "devices",
            "handler": _cmd_nostr_devices,
            "help_text": "  :nostr devices [all]         List paired devices",
        },
    ]
)


def _cmd_nostr_remote(arg: str, **kwargs: Any) -> Any:
    """Start, stop, or inspect the opt-in NIP-17 CLI inbox listener."""
    from ..util_tools import CommandResult

    parts = arg.strip().split()
    if not parts or parts[0].lower() not in {"start", "stop", "status", "verify"}:
        print(
            _(
                "nostr.remote_usage",
                default="Usage: :nostr remote start|stop|status|verify",
            )
        )
        return CommandResult()
    operation = parts[0].lower()
    core = kwargs.get("core")
    if core is None:
        print(
            _(
                "nostr.remote_requires_session",
                default="Nostr remote listener requires an active CLI session.",
            )
        )
        return CommandResult()

    if operation == "start":
        instance = get_nostr_instance()
        if instance is None or not instance.is_running:
            print(
                _(
                    "nostr.remote_connect_first",
                    default="Run :nostr connect first, then :nostr remote start.",
                )
            )
            return CommandResult()
        try:
            from ..nostr_nip17 import _public_key_x, _validate_private_key
            from ..nostr_remote_runtime import start_nostr_remote_runtime

            private_key = _validate_private_key(bytes.fromhex(instance._priv_hex))
            if _public_key_x(private_key).hex() != instance.pubkey_hex:
                raise ValueError(
                    _(
                        "nostr.active_key_mismatch",
                        default="active Nostr key does not match its public key",
                    )
                )
            runtime = start_nostr_remote_runtime(
                core,
                private_key=private_key,
                relays=list(instance.relays),
            )
            print(
                _(
                    "nostr.remote_started",
                    default="Nostr remote listener started on %(relays)s (session %(session_id)s).",
                    relays=", ".join(runtime.relays),
                    session_id=runtime.session_id,
                )
            )
        except Exception as exc:
            print(
                _(
                    "nostr.remote_start_error",
                    default="Could not start Nostr remote listener: %(error_type)s: %(error)s",
                    error_type=type(exc).__name__,
                    error=exc,
                )
            )
        return CommandResult()

    if operation == "stop":
        from ..nostr_remote_runtime import stop_nostr_remote_runtime

        result = stop_nostr_remote_runtime(core)
        message = (
            _(
                "nostr.remote_stopped",
                default="Nostr remote listener stopped.",
            )
            if result["stopped"]
            else _(
                "nostr.remote_still_stopping",
                default="Listener is still stopping.",
            )
        )
        print(message)
        return CommandResult()

    runtime = getattr(core, "_nostr_remote_runtime", None)
    if runtime is None:
        print(
            _(
                "nostr.remote_status_stopped",
                default="Nostr remote listener: stopped.",
            )
        )
        return CommandResult()
    if operation == "verify":
        try:
            readback = runtime.verify_latest_reply()
            state = readback.get("state")
            if state == "no_delivered_reply":
                print(
                    _(
                        "nostr.remote_verify_no_reply",
                        default="No delivered Nostr reply is available to verify.",
                    )
                )
            elif state != "complete":
                print(
                    _(
                        "nostr.remote_verify_unavailable",
                        default="Nostr reply readback unavailable: %(state)s",
                        state=state,
                    )
                )
            else:
                ids = readback["event_ids"]
                print(
                    _(
                        "nostr.remote_verify_recipient_id",
                        default="Latest recipient gift-wrap event ID: %(event_id)s",
                        event_id=ids[0],
                    )
                )
                print(
                    _(
                        "nostr.remote_verify_sender_id",
                        default="Latest sender-copy event ID: %(event_id)s",
                        event_id=ids[1],
                    )
                )
                for item in readback["relays"]:
                    print(
                        _(
                            "nostr.remote_verify_relay",
                            default=(
                                "  relay %(relay)s: recipient=%(recipient)s; "
                                "sender_copy=%(sender_copy)s"
                            ),
                            relay=item["relay"],
                            recipient=item["recipient"],
                            sender_copy=item["sender_copy"],
                        )
                    )
                print(
                    _(
                        "nostr.remote_verify_disclaimer",
                        default=(
                            "found=relay returned a valid signed event; "
                            "not_returned=EOSE without it; "
                            "unavailable=readback could not be determined. "
                            "This does not confirm delivery to 0xChat."
                        ),
                    )
                )
        except Exception as exc:
            print(
                _(
                    "nostr.remote_verify_error",
                    default="Nostr reply readback failed: %(error_type)s",
                    error_type=type(exc).__name__,
                )
            )
        return CommandResult()

    try:
        status = runtime.status()
        print(
            _(
                "nostr.remote_status",
                default="Nostr remote listener: %(state)s; pending=%(pending)s; dispatching=%(dispatching)s",
                state=status["state"],
                pending=status["pending"],
                dispatching=status["dispatching"],
            )
        )
        diagnostics = status.get("diagnostics")
        if isinstance(diagnostics, dict):
            print(
                _(
                    "nostr.remote_receive_diagnostics",
                    default=(
                        "  receive: connected=%(connected)s/%(total)s; "
                        "gift_wraps=%(gift_wraps)s; queued=%(queued)s"
                    ),
                    connected=diagnostics.get("connected_relays", 0),
                    total=len(status["relays"]),
                    gift_wraps=diagnostics.get("gift_wraps", 0),
                    queued=diagnostics.get("queued", 0),
                )
            )
            print(
                _(
                    "nostr.remote_rejection_diagnostics",
                    default=(
                        "  rejected: invalid=%(invalid)s; decrypt=%(decrypt)s; "
                        "unpaired=%(unpaired)s; stale=%(stale)s; "
                        "duplicate=%(duplicate)s; inbox=%(inbox)s"
                    ),
                    invalid=diagnostics.get("invalid", 0),
                    decrypt=diagnostics.get("decrypt_failed", 0),
                    unpaired=diagnostics.get("unauthorized", 0),
                    stale=diagnostics.get("stale", 0),
                    duplicate=diagnostics.get("duplicate", 0),
                    inbox=diagnostics.get("inbox_rejected", 0),
                )
            )
        outbox_summary = status.get("outbox_summary")
        if isinstance(outbox_summary, dict):
            print(
                _(
                    "nostr.remote_reply_outbox_summary",
                    default=(
                        "  replies: pending=%(pending)s; sending=%(sending)s; "
                        "delivered=%(delivered)s; failed=%(failed)s; "
                        "last_error=%(error)s"
                    ),
                    pending=outbox_summary.get("pending", 0),
                    sending=outbox_summary.get("sending", 0),
                    delivered=outbox_summary.get("delivered", 0),
                    failed=outbox_summary.get("failed", 0),
                    error=outbox_summary.get("last_error") or "-",
                )
            )
        if isinstance(diagnostics, dict):
            rejections = diagnostics.get("delivery_rejections")
            if isinstance(rejections, list):
                for item in rejections:
                    if isinstance(item, dict) and item.get("relay"):
                        print(
                            _(
                                "nostr.remote_delivery_rejection",
                                default=("  delivery rejected: %(relay)s: %(message)s"),
                                relay=item["relay"],
                                message=item.get("message") or "-",
                            )
                        )
            readback = diagnostics.get("delivery_readback")
            if isinstance(readback, list):
                for item in readback:
                    if isinstance(item, dict) and item.get("relay"):
                        print(
                            _(
                                "nostr.remote_delivery_readback",
                                default=(
                                    "  delivery readback: %(relay)s: "
                                    "recipient=%(recipient)s; "
                                    "sender_copy=%(sender_copy)s"
                                ),
                                relay=item["relay"],
                                recipient=item.get("recipient") or "-",
                                sender_copy=item.get("sender_copy") or "-",
                            )
                        )
        if status["error"]:
            print(
                _(
                    "nostr.remote_status_error",
                    default="  error: %(error)s",
                    error=status["error"],
                )
            )
        for relay in status["relays"]:
            print(
                _(
                    "nostr.remote_status_relay",
                    default="  relay: %(relay)s",
                    relay=relay,
                )
            )
    except Exception as exc:
        print(
            _(
                "nostr.remote_status_read_error",
                default="Could not read Nostr remote status: %(error_type)s: %(error)s",
                error_type=type(exc).__name__,
                error=exc,
            )
        )
    return CommandResult()


CMD_SPECS.append(
    {
        "command": "nostr",
        "subcommand": "remote",
        "handler": _cmd_nostr_remote,
        "help_text": "  :nostr remote start|stop|status|verify  Manage and diagnose the private inbox",
    }
)


def _cmd_nostr_setup(arg: str, **kwargs: Any) -> Any:
    """Run QR-assisted local pairing and opt in to the experimental CLI listener."""
    from ..nostr_remote_pairing import SQLitePairingStore
    from ..nostr_setup import (
        confirm_local_pairing,
        scan_mobile_pubkey,
        show_public_key_qr,
    )
    from ..util_tools import CommandResult

    if arg.strip():
        print(_("nostr.setup_usage", default="Usage: :nostr setup"))
        return CommandResult()
    if kwargs.get("core") is None:
        print(
            _(
                "nostr.setup_requires_session",
                default="Nostr setup requires an active local CLI session.",
            )
        )
        return CommandResult()

    instance = get_nostr_instance()
    if instance is None or not instance.is_running:
        result = start_nostr()
        if not result.get("ok"):
            print(
                _(
                    "nostr.setup_connect_error",
                    default="Could not connect to Nostr relays.",
                )
            )
            return CommandResult()
        instance = get_nostr_instance()
    if instance is None or not instance.is_running or not instance.pubkey_hex:
        print(_("nostr.setup_transport_error", default="Nostr transport is not ready."))
        return CommandResult()

    npub = encode_npub(instance.pubkey_hex)
    print(
        _(
            "nostr.setup_intro",
            default="Nostr remote setup (experimental; not approved for production).",
        )
    )
    print(
        _(
            "nostr.setup_legacy_key_warning",
            default="Warning: this currently reuses the legacy Nostr key stored in a JSON file.",
        )
    )
    print(
        _(
            "nostr.setup_security_warning",
            default=(
                "Remote-key isolation, secure storage, and real-relay "
                "interoperability remain pending."
            ),
        )
    )
    print(
        _(
            "nostr.setup_pc_pubkey",
            default="PC public key: %(npub)s",
            npub=npub,
        )
    )
    print(
        _(
            "nostr.setup_scan_pc_qr",
            default="Scan this public-only QR code with your Nostr app:",
        )
    )
    if not show_public_key_qr(npub):
        print(
            _(
                "nostr.setup_qr_display_unavailable",
                default="QR display unavailable; use the public key above.",
            )
        )
    print(
        _(
            "nostr.setup_scan_phone_qr",
            default="Show the PHONE'S public-key QR to the PC camera, or open its image.",
        )
    )
    print(
        _(
            "nostr.setup_never_scan_secret",
            default="Never scan or paste an nsec/private-key QR.",
        )
    )

    try:
        phone_pubkey = scan_mobile_pubkey()
    except (ValueError, RuntimeError, TypeError, KeyError) as exc:
        print(
            _(
                "nostr.setup_invalid_phone_qr",
                default="Could not read a valid public-key QR: %(error)s",
                error=exc,
            )
        )
        print(
            _(
                "nostr.setup_manual_pair_hint",
                default="Alternatively use :nostr pair <npub> phone",
            )
        )
        return CommandResult()
    if phone_pubkey is None:
        print(
            _(
                "nostr.setup_cancelled",
                default="Nostr setup cancelled; no device was paired.",
            )
        )
        return CommandResult()
    if phone_pubkey == instance.pubkey_hex:
        print(
            _(
                "nostr.setup_self_pair_rejected",
                default="Refusing to pair the PC's own public key.",
            )
        )
        return CommandResult()
    if not confirm_local_pairing(phone_pubkey):
        print(
            _(
                "nostr.setup_approval_declined",
                default="Local authorization was declined or unavailable; nothing was paired.",
            )
        )
        print(
            _(
                "nostr.setup_manual_pair",
                default="Manual alternative: :nostr pair %(npub)s phone",
                npub=encode_npub(phone_pubkey),
            )
        )
        return CommandResult()

    try:
        path = _pairing_database_path()
        os.makedirs(os.path.dirname(os.fspath(path)), exist_ok=True)
        with SQLitePairingStore(path) as store:
            store.pair(phone_pubkey, "phone", approved=True)
    except (OSError, ValueError, RuntimeError) as exc:
        print(
            _(
                "nostr.setup_pair_save_error",
                default="Could not save Nostr pairing: %(error_type)s",
                error_type=type(exc).__name__,
            )
        )
        return CommandResult()

    print(
        _(
            "nostr.setup_paired_phone",
            default="Paired phone public key: %(npub)s",
            npub=encode_npub(phone_pubkey),
        )
    )
    _cmd_nostr_remote("start", **kwargs)
    print(
        _(
            "nostr.setup_relay_warning",
            default=(
                "Note: automatic NIP-17 kind-10050 relay-list publication is not yet "
                "implemented. Configure matching receive relays on the phone; "
                "encrypted DM delivery is not yet verified."
            ),
        )
    )
    return CommandResult()


CMD_SPECS.append(
    {
        "command": "nostr",
        "subcommand": "setup",
        "handler": _cmd_nostr_setup,
        "help_text": "  :nostr setup                 QR-assisted local phone pairing",
    }
)
