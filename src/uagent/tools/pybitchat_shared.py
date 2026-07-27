"""pybitchat shared: BLE transport, auto-install, threaded scanner, display notification."""

from __future__ import annotations

import asyncio
import atexit as _atexit
import os
import queue
import threading
import time as _time
from typing import Any

from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives import serialization

# Nostr transport globals
_NOSTR = None  # module reference, set on first use
_NOSTR_RUNNING = False
# LLM inject queue (set by cli.py for chat_mode="llm")
_LLM_EVENT_QUEUE: "queue.Queue[dict[str, Any]] | None" = None
_NOSTR_RELAYS: list[str] | None = None
_NOSTR_BRIDGE = False  # forward BLE messages to Nostr
_LISTENER_THREAD: threading.Thread | None = None
_STOP_EVENT = threading.Event()
_RUNNING = False

SERVICE_UUID_TESTNET = "F47B5E2D-4A9E-4C5A-9B3F-8E1D2C3A4B5A"
SERVICE_UUID_MAINNET = "F47B5E2D-4A9E-4C5A-9B3F-8E1D2C3A4B5C"
CHARACTERISTIC_UUID = "A1B2C3D4-E5F6-4A5B-8C9D-0E1F2A3B4C5D"
MESSAGE_TTL_DEFAULT = 7

_BITCHAT_DIR = os.path.join(os.path.expanduser("~"), ".uag", "bitchat")
_DOWNLOAD_DIR = os.path.join(_BITCHAT_DIR, "downloads")
_ANNOUNCE_INTERVAL = 30.0
_MAX_FRAME_SIZE = 480
_FRAGMENT_PACING = 0.005
_CONNECTION_TIMEOUT = 15.0
_MAX_CONNECT_ATTEMPTS = 3
_RETRY_COOLDOWN = 15.0


def _atexit_cleanup() -> None:
    try:
        stop()
    except Exception:
        pass


_atexit.register(_atexit_cleanup)


def _notify_display(msg: str) -> None:
    """Display a notification on screen (NOT sent to the LLM)."""
    try:
        print(msg, flush=True)
    except Exception:
        pass


def ensure_dependencies() -> bool:
    """Auto-install bleak, cryptography, bitchat-protocol via _pip_auto."""
    from .._pip_auto import install_with_status as _auto

    if not _auto("bleak"):
        return False
    if not _auto("cryptography"):
        return False
    if not _auto("bitchat-protocol", module_name="bitchat_protocol"):
        return False
    return True


_PEER_NICKNAMES: dict[str, str] = {}
_PEER_NOISE_KEYS: dict[str, bytes] = {}  # peer_id_hex → noise_public_key (32 bytes)
_CLIENTS: dict[str, Any] = {}
_CONNECTING: set[str] = set()
_IGNORED: set[str] = set()
_ATTEMPTS: dict[str, int] = {}
_COOLDOWN_UNTIL: dict[str, float] = {}
_OUTBOUND_QUEUE: "queue.Queue[dict] | None" = None


# ---- Node Identity ---------------------------------------------------------

from dataclasses import dataclass

_IDENTITY: "NodeIdentity | None" = None


@dataclass
class NodeIdentity:
    noise_private: bytes
    noise_public: bytes
    signing_private: bytes
    signing_public: bytes

    @property
    def peer_id_bytes(self) -> bytes:
        from bitchat_protocol import peer_id_from_noise_key, peer_id_to_bytes

        return peer_id_to_bytes(peer_id_from_noise_key(self.noise_public))

    @property
    def peer_id_hex(self) -> str:
        from bitchat_protocol import peer_id_from_noise_key

        return peer_id_from_noise_key(self.noise_public)


def _generate_keypair() -> tuple[bytes, bytes]:
    private_key = x25519.X25519PrivateKey.generate()
    private_bytes = private_key.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    public_bytes = private_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return private_bytes, public_bytes


def _generate_signing_keypair() -> tuple[bytes, bytes]:
    private_key = ed25519.Ed25519PrivateKey.generate()
    private_bytes = private_key.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    public_bytes = private_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return private_bytes, public_bytes


def _create_identity() -> NodeIdentity:
    noise_priv, noise_pub = _generate_keypair()
    sign_priv, sign_pub = _generate_signing_keypair()
    return NodeIdentity(
        noise_private=noise_priv,
        noise_public=noise_pub,
        signing_private=sign_priv,
        signing_public=sign_pub,
    )


def get_identity() -> NodeIdentity:
    global _IDENTITY
    if _IDENTITY is None:
        _IDENTITY = _create_identity()
    return _IDENTITY


BLOCK_SIZES = (256, 512, 1024, 2048)


def _optimal_block_size(data_size: int) -> int:
    total = data_size + 16
    for block in BLOCK_SIZES:
        if total <= block:
            return block
    return data_size


def _pkcs7_pad(data: bytes, target_size: int) -> bytes:
    if len(data) >= target_size:
        return data
    needed = target_size - len(data)
    if needed <= 0 or needed > 255:
        return data
    return data + bytes([needed]) * needed


def data_for_signing(packet) -> bytes:
    from bitchat_protocol import BitchatPacket, encode

    unsigned = BitchatPacket(
        version=packet.version,
        type=packet.type,
        ttl=0,
        timestamp=packet.timestamp,
        flags=0,
        sender_id=packet.sender_id,
        recipient_id=packet.recipient_id,
        payload=packet.payload,
    )
    raw = encode(unsigned, padding=False)
    block = _optimal_block_size(len(raw))
    return _pkcs7_pad(raw, block)


def sign_packet(packet) -> bytes:
    data = data_for_signing(packet)
    identity = get_identity()
    priv = ed25519.Ed25519PrivateKey.from_private_bytes(identity.signing_private)
    return priv.sign(data)


# ---- Fragment Assembly -----------------------------------------------------

_FRAGMENT_HEADER_SIZE = 13


class FragmentHeader:
    def __init__(
        self,
        fragment_id: bytes,
        fragment_index: int,
        total_fragments: int,
        message_type: int = 0,
    ):
        self.fragment_id = fragment_id
        self.fragment_index = fragment_index
        self.total_fragments = total_fragments
        self.message_type = message_type


class FragmentAssemblyBuffer:
    def __init__(self, max_inflight: int = 16, lifetime_seconds: float = 60.0):
        self._transfers: dict[tuple[bytes, bytes], dict] = {}
        self.max_inflight = max_inflight
        self._lifetime = lifetime_seconds

    def append(
        self, sender_id: bytes, header: FragmentHeader, data: bytes
    ) -> bytes | None:
        key = (sender_id, header.fragment_id)
        now = _time.time()
        if key not in self._transfers:
            if len(self._transfers) >= self.max_inflight:
                return None
            self._transfers[key] = {
                "total": header.total_fragments,
                "fragments": {},
                "started": now,
            }
        transfer = self._transfers[key]
        transfer["fragments"][header.fragment_index] = data
        if len(transfer["fragments"]) == transfer["total"]:
            assembled = b"".join(
                transfer["fragments"][i] for i in range(transfer["total"])
            )
            del self._transfers[key]
            return assembled
        return None

    def inflight_count(self) -> int:
        return len(self._transfers)

    def remove_expired(self, before: float | None = None) -> list[tuple[bytes, bytes]]:
        if before is None:
            before = _time.time() - self._lifetime
        expired = [key for key, t in self._transfers.items() if t["started"] < before]
        for key in expired:
            del self._transfers[key]
        return expired


def parse_fragment_payload(payload: bytes) -> tuple[bytes, int, int, int, bytes] | None:
    if len(payload) < _FRAGMENT_HEADER_SIZE:
        return None
    fragment_id = payload[0:8]
    index = int.from_bytes(payload[8:10], "big")
    total = int.from_bytes(payload[10:12], "big")
    original_type = payload[12]
    fragment_data = payload[13:]
    if total == 0 or index >= total:
        return None
    return fragment_id, index, total, original_type, fragment_data


# ---- File Transfer TLV -----------------------------------------------------

_FILE_TAG_FILE_NAME = 0x01
_FILE_TAG_FILE_SIZE = 0x02
_FILE_TAG_MIME_TYPE = 0x03
_FILE_TAG_CONTENT = 0x04
_MAX_FILE_BYTES = 1_048_576


def encode_file_payload(
    file_path: str,
) -> tuple[bytes, str, int] | tuple[None, str, int]:
    import mimetypes

    path = os.path.expanduser(file_path)
    try:
        data = open(path, "rb").read()
    except OSError as exc:
        return None, f"Cannot read '{file_path}': {exc}", 0
    if not data:
        return None, f"'{os.path.basename(path)}' is empty", 0
    if len(data) > _MAX_FILE_BYTES:
        return (
            None,
            f"'{os.path.basename(path)}' is {len(data)} bytes (max {_MAX_FILE_BYTES})",
            0,
        )
    fname = os.path.basename(path)
    fname_b = fname.encode("utf-8")
    mime_type, _ = mimetypes.guess_type(path)
    if mime_type is None:
        mime_type = "application/octet-stream"
    mime_b = mime_type.encode("utf-8")
    fsize = len(data)
    out = bytearray()
    if len(fname_b) <= 0xFFFF:
        out.append(_FILE_TAG_FILE_NAME)
        out += len(fname_b).to_bytes(2, "big")
        out += fname_b
    out.append(_FILE_TAG_FILE_SIZE)
    out += (4).to_bytes(2, "big")
    out += fsize.to_bytes(4, "big")
    if len(mime_b) <= 0xFFFF:
        out.append(_FILE_TAG_MIME_TYPE)
        out += len(mime_b).to_bytes(2, "big")
        out += mime_b
    out.append(_FILE_TAG_CONTENT)
    out += len(data).to_bytes(4, "big")
    out += data
    return bytes(out), fname, fsize


def decode_file_payload(payload: bytes) -> dict | None:
    result = {}
    offset = 0
    end = len(payload)
    while offset < end:
        tlv_type = payload[offset]
        offset += 1
        if tlv_type == _FILE_TAG_CONTENT:
            length = None
            if end - offset >= 4:
                candidate = int.from_bytes(payload[offset : offset + 4], "big")
                if candidate <= end - offset - 4:
                    length = candidate
                    offset += 4
            if length is None:
                if end - offset < 2:
                    return None
                length = int.from_bytes(payload[offset : offset + 2], "big")
                offset += 2
        else:
            if end - offset < 2:
                return None
            length = int.from_bytes(payload[offset : offset + 2], "big")
            offset += 2
        if length < 0 or end - offset < length:
            return None
        value = payload[offset : offset + length]
        offset += length
        if tlv_type == _FILE_TAG_FILE_NAME:
            result["file_name"] = value.decode("utf-8", errors="replace")
        elif tlv_type == _FILE_TAG_FILE_SIZE:
            result["file_size"] = int.from_bytes(value, "big")
        elif tlv_type == _FILE_TAG_MIME_TYPE:
            result["mime_type"] = value.decode("utf-8", errors="replace")
        elif tlv_type == _FILE_TAG_CONTENT:
            result["content"] = bytes(value)
    if "content" not in result:
        return None
    result.setdefault("file_name", "")
    result.setdefault("mime_type", "application/octet-stream")
    result.setdefault("file_size", len(result.get("content", b"")))
    return result


def enqueue_send(
    type_: str,
    payload: str | bytes,
    recipient: str | None = None,
    via: str = "ble",
) -> None:
    """Queue a message for delivery.

    via: 'ble' (BLE Mesh), 'nostr' (Nostr relays), 'both' (both transports).
    """
    if via in ("both", "nostr"):
        global _NOSTR, _NOSTR_RUNNING, _NOSTR_BRIDGE
        if _NOSTR_RUNNING and _NOSTR is not None:
            try:
                text = (
                    payload.decode("utf-8")
                    if isinstance(payload, bytes)
                    else str(payload)
                )
                if type_ == "text":
                    # If recipient is a 64-char hex (Nostr pubkey), use encrypted kind-1059
                    if recipient and len(recipient) == 64:
                        try:
                            bytes.fromhex(recipient)
                            _NOSTR.nostr_send_kind1059(text, recipient)
                        except ValueError:
                            _NOSTR.nostr_send_text(text)
                    else:
                        _NOSTR.nostr_send_text(text)
                elif type_ == "file":
                    # Encode file as TLV and send via kind-1059
                    file_payload, fname, fsize = encode_file_payload(str(payload))
                    if file_payload:
                        import base64 as _b64

                        b64data = _b64.b64encode(file_payload).decode("ascii")
                        file_meta = f"/file {fname} {fsize}"
                        _NOSTR.nostr_send_kind1059(f"{file_meta}:{b64data}")
                    else:
                        _NOSTR.nostr_send_kind1059(f"/file {text}")
            except Exception:
                pass

    if via in ("both", "ble"):
        global _OUTBOUND_QUEUE
        if _OUTBOUND_QUEUE is None:
            return
        try:
            item: dict = {"type": type_, "payload": payload}
            if recipient:
                item["recipient"] = recipient
            _OUTBOUND_QUEUE.put_nowait(item)
        except Exception:
            pass


# ---- BLE service -----------------------------------------------------------


async def _run_ble_service(nickname: str, network: str) -> None:
    from bleak import BleakScanner, BleakClient, BleakError
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData
    from bitchat_protocol import (
        BitchatPacket,
        MessageType,
        PacketFlag,
        encode,
        decode,
        encode_announcement,
        decode_announcement,
        AnnouncementPacket,
    )

    svc_uuid = (
        SERVICE_UUID_TESTNET.lower()
        if network == "testnet"
        else SERVICE_UUID_MAINNET.lower()
    )
    char_uuid = CHARACTERISTIC_UUID.lower()
    global _OUTBOUND_QUEUE
    _OUTBOUND_QUEUE = queue.Queue()

    identity = get_identity()
    ann_payload = encode_announcement(
        AnnouncementPacket(
            nickname=nickname,
            noise_public_key=identity.noise_public,
            signing_public_key=identity.signing_public,
        )
    )
    _reassembler = FragmentAssemblyBuffer()

    async def _fragment_and_send(
        wire: bytes, original_type: int = 2
    ) -> list[tuple[str, str]]:
        fragmented = len(wire) > _MAX_FRAME_SIZE
        if fragmented:
            fid = os.urandom(8)
            chunk_size = _MAX_FRAME_SIZE - 40
            chunks = [wire[i : i + chunk_size] for i in range(0, len(wire), chunk_size)]
            frames = []
            for idx, chunk in enumerate(chunks):
                payload = (
                    fid
                    + idx.to_bytes(2, "big")
                    + len(chunks).to_bytes(2, "big")
                    + bytes([original_type])
                    + chunk
                )
                frag_pkt = BitchatPacket(
                    version=1,
                    type=int(MessageType.FRAGMENT),
                    ttl=MESSAGE_TTL_DEFAULT,
                    timestamp=int(_time.time() * 1000),
                    flags=0,
                    sender_id=identity.peer_id_bytes,
                    payload=payload,
                )
                frag_pkt.signature = sign_packet(frag_pkt)
                frames.append(encode(frag_pkt, padding=False))
        else:
            frames = [wire]
        failed = []
        for addr, client in list(_CLIENTS.items()):
            if not client.is_connected:
                failed.append((addr, "link down"))
                continue
            for frame in frames:
                try:
                    await client.write_gatt_char(char_uuid, frame, response=False)
                except Exception as exc:
                    failed.append((addr, str(exc)))
                    break
                if fragmented:
                    await asyncio.sleep(_FRAGMENT_PACING)
        return failed

    async def _send_packet(packet: BitchatPacket) -> None:
        packet.signature = sign_packet(packet)
        wire = encode(packet, padding=True)
        failed = await _fragment_and_send(wire, original_type=int(packet.type))
        for addr, reason in failed:
            client = _CLIENTS.pop(addr, None)
            if client is None:
                continue
            _COOLDOWN_UNTIL[addr] = _time.monotonic() + _RETRY_COOLDOWN
            try:
                await client.disconnect()
            except Exception:
                pass

    async def _send_announce() -> None:
        pkt = BitchatPacket(
            version=1,
            type=int(MessageType.ANNOUNCE),
            ttl=MESSAGE_TTL_DEFAULT,
            timestamp=int(_time.time() * 1000),
            flags=0,
            sender_id=identity.peer_id_bytes,
            payload=ann_payload,
        )
        await _send_packet(pkt)

    async def _send_leave() -> None:
        pkt = BitchatPacket(
            version=1,
            type=int(MessageType.LEAVE),
            ttl=MESSAGE_TTL_DEFAULT,
            timestamp=int(_time.time() * 1000),
            flags=0,
            sender_id=identity.peer_id_bytes,
            payload=nickname.encode("utf-8"),
        )
        await _send_packet(pkt)

    # ---- Noise DM handlers -------------------------------------------------

    from cryptography.hazmat.primitives.asymmetric.x25519 import (
        X25519PrivateKey as _X25519PrivateKey,
    )

    def _noise_static_key() -> _X25519PrivateKey:
        return _X25519PrivateKey.from_private_bytes(identity.noise_private)

    async def _send_noise_packet(
        pkt_type: int, payload: bytes, recipient_hex: str | None = None
    ) -> None:
        """Send a NOISE_HANDSHAKE or NOISE_ENCRYPTED packet."""
        recipient_bytes = bytes.fromhex(recipient_hex) if recipient_hex else None
        pkt = BitchatPacket(
            version=1,
            type=pkt_type,
            ttl=MESSAGE_TTL_DEFAULT,
            timestamp=int(_time.time() * 1000),
            flags=0,
            sender_id=identity.peer_id_bytes,
            recipient_id=recipient_bytes,
            payload=payload,
        )
        await _send_packet(pkt)

    def _handle_noise_handshake(peer_hex: str, payload: bytes) -> None:
        """Process an incoming Noise handshake message."""
        from . import bitchat_noise as _noise

        rs = _PEER_NOISE_KEYS.get(peer_hex)
        if rs is None:
            return  # unknown peer, can't handshake

        pending = _noise.get_or_create_session(
            peer_hex,
            initiator=not bool(
                _noise._NOISE_SESSIONS.get(peer_hex) is None
                and _noise._NOISE_PENDING.get(peer_hex) is None
            ),
            our_static=_noise_static_key(),
            their_static_pub=rs,
        )
        if pending is None:
            return

        # If we have no pending session and no existing session, we're responder
        has_existing = _noise.get_session(peer_hex) is not None
        has_pending = (
            peer_hex in _noise._NOISE_PENDING
            if hasattr(_noise, "_NOISE_PENDING")
            else False
        )

        if not has_pending and not has_existing:
            # Responder: process msg1, build msg2
            if pending.process_message_1(payload):
                msg2 = pending.build_message_2()
                _noise._NOISE_PENDING[peer_hex] = pending
                asyncio.run_coroutine_threadsafe(
                    _send_noise_packet(
                        int(MessageType.NOISE_HANDSHAKE), msg2, peer_hex
                    ),
                    asyncio.get_event_loop(),
                )
        elif has_pending:
            # Initiator: this should be msg2, process and build msg3
            existing = _noise._NOISE_PENDING.get(peer_hex)
            if existing and existing.initiator:
                if existing.process_message_2(payload):
                    msg3 = existing.build_message_3()
                    _noise.complete_session(peer_hex, existing)
                    asyncio.run_coroutine_threadsafe(
                        _send_noise_packet(
                            int(MessageType.NOISE_HANDSHAKE), msg3, peer_hex
                        ),
                        asyncio.get_event_loop(),
                    )
                    _notify_display(
                        f"[bitchat] Noise handshake complete with {_PEER_NICKNAMES.get(peer_hex, peer_hex[:8])}"
                    )
            elif existing:
                # Responder: this is msg3
                if existing.process_message_3(payload):
                    _noise.complete_session(peer_hex, existing)
                    _notify_display(
                        f"[bitchat] Noise handshake complete with {_PEER_NICKNAMES.get(peer_hex, peer_hex[:8])}"
                    )

    def _handle_noise_encrypted(peer_hex: str, payload: bytes) -> None:
        """Decrypt and display an incoming Noise-encrypted DM."""
        from . import bitchat_noise as _noise

        session = _noise.get_session(peer_hex)
        if session is None:
            _notify_display(
                f"[bitchat] [Noise DM] from {_PEER_NICKNAMES.get(peer_hex, peer_hex[:8])} — no session (dropped)"
            )
            return
        pt = _noise.decrypt_dm(session, payload)
        if pt is None:
            _notify_display(
                f"[bitchat] [Noise DM] from {_PEER_NICKNAMES.get(peer_hex, peer_hex[:8])} — decrypt failed"
            )
            return
        try:
            text = pt.decode("utf-8")
        except Exception:
            text = pt.hex()
        sender = _PEER_NICKNAMES.get(peer_hex, peer_hex[:8])
        _notify_display(f"[bitchat] [Noise DM] {sender}: {text}")
        if _CHAT_MODE == "llm":
            _inject_to_llm(f"[bitchat] [Noise DM] {sender}: {text}")

    # ---- End Noise DM handlers ---------------------------------------------

    def _dispatch(pkt: BitchatPacket) -> None:
        if pkt.sender_id == identity.peer_id_bytes:
            return
        peer_hex = pkt.sender_id.hex()
        if pkt.type == int(MessageType.FRAGMENT):
            parsed = parse_fragment_payload(pkt.payload)
            if parsed is not None:
                frag_id, index, total, orig_type, frag_data = parsed
                header = FragmentHeader(frag_id, index, total, orig_type)
                inner = _reassembler.append(pkt.sender_id, header, frag_data)
                if inner is not None:
                    inner_pkt = decode(inner)
                    if inner_pkt is not None:
                        _dispatch(inner_pkt)
            return
        if pkt.type == int(MessageType.ANNOUNCE):
            ann = decode_announcement(pkt.payload)
            if ann is not None:
                old = _PEER_NICKNAMES.get(peer_hex)
                _PEER_NICKNAMES[peer_hex] = ann.nickname
                _PEER_NOISE_KEYS[peer_hex] = ann.noise_public_key
                if old is None:
                    _notify_display(f"[bitchat] ++ {ann.nickname} is now online")
        elif pkt.type == int(MessageType.MESSAGE):
            try:
                text = pkt.payload.decode("utf-8")
            except Exception:
                return
            sender = _PEER_NICKNAMES.get(peer_hex, peer_hex[:8])
            # Broadcast (all 0xFF) = #mesh channel; specific recipient = DM
            if pkt.recipient_id is not None and pkt.recipient_id != b"\xff" * 8:
                _notify_display(f"[bitchat] [DM] {sender}: {text}")
                if _CHAT_MODE == "llm":
                    _inject_to_llm(f"[bitchat] [DM] {sender}: {text}")
            else:
                _notify_display(f"[bitchat] {sender}: {text}")
                if _CHAT_MODE == "llm":
                    _inject_to_llm(f"[bitchat] {sender}: {text}")
        elif pkt.type == int(MessageType.NOISE_HANDSHAKE):
            _handle_noise_handshake(peer_hex, pkt.payload)
        elif pkt.type == int(MessageType.NOISE_ENCRYPTED):
            _handle_noise_encrypted(peer_hex, pkt.payload)
        elif pkt.type == int(MessageType.LEAVE):
            nick = _PEER_NICKNAMES.pop(peer_hex, peer_hex[:8])
            _PEER_NOISE_KEYS.pop(peer_hex, None)
            _notify_display(f"[bitchat] -- {nick} went offline")
        elif pkt.type == int(MessageType.FILE_TRANSFER):
            file_info = decode_file_payload(pkt.payload)
            if file_info is not None:
                sender = _PEER_NICKNAMES.get(peer_hex, peer_hex[:8])
                fname = file_info["file_name"]
                fdata = file_info["content"]
                try:
                    os.makedirs(_DOWNLOAD_DIR, exist_ok=True)
                    safe_name = os.path.basename(fname) if fname else ""
                    safe_name = safe_name.replace("\x00", "").strip().lstrip(".")
                    if not safe_name:
                        safe_name = f"received_{int(_time.time() * 1000)}"
                    save_path = os.path.join(_DOWNLOAD_DIR, safe_name)
                    with open(save_path, "wb") as f:
                        f.write(fdata)
                    _notify_display(
                        f"[bitchat] {sender} sent file: {fname} ({len(fdata)} bytes) -> {safe_name}"
                    )
                    import subprocess as _sp
                    import sys as _sys

                    try:
                        if _sys.platform == "darwin":
                            _sp.Popen(
                                ["open", save_path],
                                stdout=_sp.DEVNULL,
                                stderr=_sp.DEVNULL,
                            )
                        elif _sys.platform.startswith("win"):
                            _sp.Popen(
                                ["cmd", "/c", "start", "", save_path],
                                stdout=_sp.DEVNULL,
                                stderr=_sp.DEVNULL,
                            )
                        else:
                            _sp.Popen(
                                ["xdg-open", save_path],
                                stdout=_sp.DEVNULL,
                                stderr=_sp.DEVNULL,
                            )
                    except Exception:
                        pass
                except OSError as exc:
                    _notify_display(
                        f"[bitchat] Failed to save file from {sender}: {exc}"
                    )

    def _on_notify(_characteristic, data: bytearray) -> None:
        try:
            if _STOP_EVENT.is_set():
                return
            pkt = decode(bytes(data))
            if pkt is not None:
                _dispatch(pkt)
        except Exception:
            pass

    async def _connect(device: BLEDevice) -> None:
        addr = device.address
        attempts = _ATTEMPTS.get(addr, 0) + 1
        _ATTEMPTS[addr] = attempts
        client = BleakClient(device, disconnected_callback=_on_disconnect)
        try:
            await asyncio.wait_for(client.connect(), timeout=_CONNECTION_TIMEOUT)
            _CLIENTS[addr] = client
            await client.start_notify(char_uuid, _on_notify)
            _notify_display(f"[bitchat] Connected to peer at {addr}")
            await _send_announce()
        except asyncio.TimeoutError:
            # Suppress TimeoutError display (frequent during BLE scan)
            pass
        except BleakError:
            # suppressed: connect failure display
            if attempts >= _MAX_CONNECT_ATTEMPTS:
                _IGNORED.add(addr)
            else:
                _COOLDOWN_UNTIL[addr] = _time.monotonic() + _RETRY_COOLDOWN
            try:
                await client.disconnect()
            except Exception:
                pass
        except Exception:
            # suppressed: _notify_display(f"[bitchat] Unexpected error with {addr}: {exc}")
            _IGNORED.add(addr)
            try:
                await client.disconnect()
            except Exception:
                pass
        finally:
            _CONNECTING.discard(addr)

    def _on_disconnect(client) -> None:
        addr = client.address
        _CLIENTS.pop(addr, None)
        _CONNECTING.discard(addr)

    def _on_detection(device: BLEDevice, adv: AdvertisementData) -> None:
        if _STOP_EVENT.is_set():
            return
        addr = device.address
        if addr in _CLIENTS or addr in _CONNECTING or addr in _IGNORED:
            return
        if _time.monotonic() < _COOLDOWN_UNTIL.get(addr, 0.0):
            return
        name = device.name
        if not name:
            pass  # no name advertised — skip display
        else:
            rssi = getattr(device, "rssi", 0)
            _notify_display(f"[bitchat] Discovered peer: {name} ({addr}) RSSI={rssi}")
        _CONNECTING.add(addr)
        asyncio.create_task(_connect(device))

    scanner = BleakScanner(detection_callback=_on_detection, service_uuids=[svc_uuid])
    try:
        await scanner.start()
    except BleakError as exc:
        _notify_display(f"[bitchat] BLE scan start failed: {exc}")
        return

    _notify_display(
        f"[bitchat] BLE service started (network={network}, nickname={nickname})"
    )
    _last_announce = 0.0

    try:
        while not _STOP_EVENT.is_set():
            if _OUTBOUND_QUEUE is None:
                await asyncio.sleep(0.2)
                continue
            while not _OUTBOUND_QUEUE.empty():
                try:
                    item = _OUTBOUND_QUEUE.get_nowait()
                    send_type = item.get("type", "text")
                    payload = item.get("payload", "")
                    pkt_type = int(MessageType.MESSAGE)
                    if send_type == "announce":
                        pkt_type = int(MessageType.ANNOUNCE)
                    elif send_type == "leave":
                        pkt_type = int(MessageType.LEAVE)
                    elif send_type == "file":
                        file_payload, fname, fsize = encode_file_payload(str(payload))
                        if file_payload is not None:
                            pkt = BitchatPacket(
                                version=2,
                                type=int(MessageType.FILE_TRANSFER),
                                ttl=MESSAGE_TTL_DEFAULT,
                                timestamp=int(_time.time() * 1000),
                                flags=0,
                                sender_id=identity.peer_id_bytes,
                                payload=file_payload,
                            )
                            await _send_packet(pkt)
                        continue
                    recipient_hex = item.get("recipient")
                    payload_bytes = (
                        payload.encode("utf-8") if isinstance(payload, str) else payload
                    )

                    # If a recipient is specified, try Noise DM
                    if recipient_hex and send_type == "text":
                        # Check for existing Noise session
                        from . import bitchat_noise as _noise

                        session = _noise.get_session(recipient_hex)
                        if session is not None:
                            # Encrypt with Noise
                            ct = _noise.encrypt_dm(session, payload_bytes)
                            if ct is not None:
                                pkt = BitchatPacket(
                                    version=1,
                                    type=int(MessageType.NOISE_ENCRYPTED),
                                    ttl=MESSAGE_TTL_DEFAULT,
                                    timestamp=int(_time.time() * 1000),
                                    flags=0,
                                    sender_id=identity.peer_id_bytes,
                                    recipient_id=bytes.fromhex(recipient_hex),
                                    payload=ct,
                                )
                                await _send_packet(pkt)
                                continue
                            # fall through to plain if encrypt fails
                        else:
                            # Initiate Noise handshake first, then queue message for later
                            rs = _PEER_NOISE_KEYS.get(recipient_hex)
                            if rs is not None:
                                # Start handshake
                                pending = _noise.get_or_create_session(
                                    recipient_hex,
                                    initiator=True,
                                    our_static=_noise_static_key(),
                                    their_static_pub=rs,
                                )
                                if pending is not None:
                                    msg1 = pending.build_message_1()
                                    _noise._NOISE_PENDING[recipient_hex] = pending
                                    await _send_noise_packet(
                                        int(MessageType.NOISE_HANDSHAKE),
                                        msg1,
                                        recipient_hex,
                                    )
                                    # Re-queue for later delivery after handshake
                                    _OUTBOUND_QUEUE.put_nowait(item)
                                    continue
                            # Fall through to plain-text DM
                            _notify_display(
                                f"[bitchat] No Noise session for DM to {recipient_hex[:8]} — "
                                "sending as plain text (unencrypted)"
                            )

                    # Plain text or non-DM send
                    flags = int(PacketFlag.HAS_RECIPIENT) if recipient_hex else 0
                    recipient_bytes = (
                        bytes.fromhex(recipient_hex) if recipient_hex else None
                    )
                    pkt = BitchatPacket(
                        version=1,
                        type=pkt_type,
                        ttl=MESSAGE_TTL_DEFAULT,
                        timestamp=int(_time.time() * 1000),
                        flags=flags,
                        sender_id=identity.peer_id_bytes,
                        recipient_id=recipient_bytes,
                        payload=payload_bytes,
                    )
                    await _send_packet(pkt)
                except Exception:
                    pass
            now_t = _time.time()
            if _CLIENTS and now_t - _last_announce > _ANNOUNCE_INTERVAL:
                await _send_announce()
                _last_announce = now_t
            await asyncio.sleep(0.2)
    finally:
        try:
            await _send_leave()
        except Exception:
            pass
        # Stop scanner first to prevent new callbacks
        try:
            await scanner.stop()
        except Exception:
            pass
        await asyncio.sleep(0.1)
        for addr, client in list(_CLIENTS.items()):
            try:
                await client.stop_notify(char_uuid)
            except Exception:
                pass
            try:
                await client.disconnect()
            except Exception:
                pass


def _listener_loop(nickname: str, network: str) -> None:
    """Background thread: asyncio event loop for BLE service.

    Do NOT close the loop here — winrt callbacks may still reference it.
    The daemon thread will be cleaned up on process exit.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_run_ble_service(nickname, network))
    except Exception:
        pass


# ---- Nostr message callback ------------------------------------------------


def _on_nostr_message(nick: str, text: str, kind: int) -> None:
    """Callback when a Nostr message arrives."""
    kind_label = "kind-1059" if kind == 1059 else "kind-1"
    _notify_display(f"[nostr/{kind_label}] {nick}: {text}")
    if _CHAT_MODE == "llm":
        _inject_to_llm(f"[nostr/{kind_label}] {nick}: {text}")


def start(
    nickname: str = "",
    network: str = "mainnet",
    nostr: bool = False,
    nostr_relays: list[str] | None = None,
) -> dict[str, Any]:
    global _LISTENER_THREAD, _RUNNING, _NOSTR, _NOSTR_RUNNING, _NOSTR_RELAYS, _NOSTR_BRIDGE
    if _RUNNING and not nostr:
        return {"ok": True, "state": "running", "message": "Already running"}
    if _RUNNING and nostr and _NOSTR_RUNNING:
        return {
            "ok": True,
            "state": "running",
            "nostr": "running",
            "message": "Already running",
        }
    global _IGNORED, _CONNECTING, _ATTEMPTS, _COOLDOWN_UNTIL, _CLIENTS, _PEER_NICKNAMES
    _IGNORED = set()
    _CONNECTING = set()
    _ATTEMPTS = {}
    _COOLDOWN_UNTIL = {}
    _CLIENTS = {}
    _PEER_NICKNAMES = {}
    _PEER_NOISE_KEYS = {}
    _STOP_EVENT.clear()
    _LISTENER_THREAD = threading.Thread(
        target=_listener_loop,
        args=(nickname or "anonymous", network),
        daemon=True,
        name="pybitchat-ble",
    )
    _LISTENER_THREAD.start()
    _RUNNING = True
    result: dict[str, Any] = {
        "ok": True,
        "state": "running",
        "network": network,
        "nickname": nickname or "anonymous",
    }

    # Start Nostr transport if requested
    if nostr:
        try:
            from . import nostr_transport as _nt

            _NOSTR = _nt
            nresult = _nt.start_nostr(
                relays=nostr_relays,
                nickname=nickname,
                on_message=_on_nostr_message,
                on_kind1059=_on_nostr_message,
            )
            if nresult.get("ok"):
                _NOSTR_RUNNING = True
                _NOSTR_RELAYS = nostr_relays
                _NOSTR_BRIDGE = True  # enable BLE→Nostr forwarding
                result["nostr"] = "running"
                result["nostr_pubkey"] = _nt.nostr_pubkey()
            else:
                result["nostr"] = f"failed: {nresult.get('error', '?')}"
        except Exception as e:
            result["nostr"] = f"error: {e}"

    return result


def stop() -> dict[str, Any]:
    global _LISTENER_THREAD, _RUNNING, _NOSTR, _NOSTR_RUNNING, _NOSTR_BRIDGE
    _STOP_EVENT.set()
    if _LISTENER_THREAD is not None:
        _LISTENER_THREAD.join(timeout=5)
        _LISTENER_THREAD = None
    _RUNNING = False
    # Clear Noise sessions
    try:
        import importlib as _il

        _nm = _il.import_module("uagent.tools.bitchat_noise")
        _nm._NOISE_SESSIONS.clear()
        _nm._NOISE_PENDING.clear()
    except Exception:
        pass
    # Stop Nostr transport
    if _NOSTR_RUNNING and _NOSTR is not None:
        try:
            _NOSTR.stop_nostr()
        except Exception:
            pass
        _NOSTR_RUNNING = False
        _NOSTR_BRIDGE = False
        _NOSTR = None
    return {"ok": True, "state": "stopped"}


def status() -> dict[str, Any]:
    global _RUNNING, _NOSTR, _NOSTR_RUNNING
    result = {"ok": True, "state": "running" if _RUNNING else "stopped"}
    if _RUNNING:
        result["peers"] = [
            {"id": pid, "nickname": nick} for pid, nick in _PEER_NICKNAMES.items()
        ]
        result["connections"] = len(_CLIENTS)
    # Nostr status
    if _NOSTR_RUNNING and _NOSTR is not None:
        try:
            nresult = _NOSTR.nostr_status()
            result["nostr"] = nresult.get("state", "?")
            result["nostr_pubkey"] = nresult.get("pubkey", "")
            result["nostr_relays"] = nresult.get("relays", [])
            result["nostr_connections"] = nresult.get("connections", 0)
        except Exception:
            result["nostr"] = "error"
    else:
        result["nostr"] = "stopped"
    return result


# ---- Chat Mode (":bitchat on" / ":bitchat off" / ":bitchat llm") -----------

# Mode: "off" = disabled, "on" = forward to mesh only, "llm" = forward to mesh + inject to LLM
_CHAT_MODE: str = "off"


def _inject_to_llm(text: str) -> None:
    """Inject a peer message into the LLM event queue (thread-safe)."""
    global _LLM_EVENT_QUEUE
    q = _LLM_EVENT_QUEUE
    if q is not None:
        try:
            q.put_nowait({"kind": "user", "text": text})
        except Exception:
            pass


def forward_to_mesh(text: str) -> None:
    """Forward user text to the BLE Mesh (and Nostr if enabled) if chat mode is active."""
    global _NOSTR_RUNNING
    if _CHAT_MODE in ("on", "llm") and _RUNNING and text.strip():
        via = "both" if _NOSTR_RUNNING else "ble"
        enqueue_send("text", text, via=via)


def is_chat_mode() -> str:
    """Return current chat mode: 'off', 'on', or 'llm'."""
    return _CHAT_MODE


def set_chat_mode(mode: bool | str) -> dict[str, Any]:
    """Enable/disable chat mode.

    Accepts bool (True->'on', False->'off') or str ('off','on','llm').
    'on' = forward to mesh only; 'llm' = forward to mesh + inject peer msgs to LLM.
    """
    global _CHAT_MODE
    if not _RUNNING:
        return {"ok": False, "error": "bitchat node is not running"}
    if isinstance(mode, bool):
        _CHAT_MODE = "on" if mode else "off"
    elif mode in ("off", "on", "llm"):
        _CHAT_MODE = mode
    else:
        return {"ok": False, "error": f"Invalid mode: {mode!r} (use 'off','on','llm')"}
    return {"ok": True, "chat_mode": _CHAT_MODE}


def set_llm_event_queue(q: "queue.Queue[dict[str, Any]] | None") -> None:
    """Set the event queue for LLM injection (called from cli.py)."""
    global _LLM_EVENT_QUEUE
    _LLM_EVENT_QUEUE = q
