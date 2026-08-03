"""pybitchat shared: BLE transport, auto-install, threaded scanner, display notification."""

from __future__ import annotations

import asyncio
import atexit as _atexit
import hashlib
import os
import queue
from collections import deque
import random
import re as _re
import threading
import time as _time
import uuid
from typing import Any

from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives import serialization

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

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
_SEEN_MESSAGE_KEYS: dict[bytes, float] = {}
_SEEN_MESSAGE_TTL = 120.0

SERVICE_UUID_TESTNET = "F47B5E2D-4A9E-4C5A-9B3F-8E1D2C3A4B5A"
SERVICE_UUID_MAINNET = "F47B5E2D-4A9E-4C5A-9B3F-8E1D2C3A4B5C"
CHARACTERISTIC_UUID = "A1B2C3D4-E5F6-4A5B-8C9D-0E1F2A3B4C5D"
MESSAGE_TTL_DEFAULT = 7

# Noise Android
# (HANDSHAKE_TIMEOUT_MS=10)  DM
#
_NOISE_HANDSHAKE_MAX_ATTEMPTS = 3

_BITCHAT_DIR = os.path.join(os.path.expanduser("~"), ".uag", "bitchat")
_DOWNLOAD_DIR = os.path.join(_BITCHAT_DIR, "downloads")
_IDENTITY_FILE = os.path.join(_BITCHAT_DIR, "identity.json")
_ANNOUNCE_INTERVAL = 30.0
_MAX_FRAME_SIZE = 480
# BLE writes without response can be dropped by Android when fragments are
# sent back-to-back. Keep a conservative gap between fragments so the peer's
# reassembler receives the complete message.
_FRAGMENT_PACING = 0.05
# Packet pacing: BLE
_PACKET_PACING = 0.1
_CONNECTION_TIMEOUT = 15.0
_MAX_CONNECT_ATTEMPTS = 3
_RETRY_COOLDOWN = 15.0


def _atexit_cleanup() -> None:
    try:
        stop()
    except Exception:
        pass


_atexit.register(_atexit_cleanup)

# : BLE  print_lock
# BLE  put
_DISPLAY_QUEUE: "queue.Queue[str]" = queue.Queue()
_DISPLAY_THREAD: threading.Thread | None = None
_DISPLAY_THREAD_STARTED = False
# LLM  [bitchat]
#
_DISPLAY_WAIT_STREAM_SEC = 2.0

# BLE :  Noise
#
_EVENT_LOOP: "asyncio.AbstractEventLoop | None" = None

# Opt-in debug logging: only emitted when UAGENT_BITCHAT_DEBUG=1.
_DEBUG = os.environ.get("UAGENT_BITCHAT_DEBUG", "") == "1"


def _display_worker() -> None:
    """表示専用ワーカー: キューから取り出して print_lock 直列化で表示."""
    while True:
        try:
            msg = _DISPLAY_QUEUE.get()
        except Exception:
            return
        try:
            #  core  (from import
            # core  _stream_line_open )
            from .. import core as _core

            # LLM  Reasoning/assistant  [bitchat]
            #  _DISPLAY_WAIT_STREAM_SEC
            #  [bitchat]
            #
            deadline = _time.time() + _DISPLAY_WAIT_STREAM_SEC
            # Never interrupt a reasoning stream. Reasoning uses a separate
            # flag because its deltas are written without a trailing newline.
            while getattr(_core, "_reasoning_stream_open", False):
                _time.sleep(0.02)
            # After reasoning ends, give ordinary streamed answer text a
            # short grace period before inserting the bitchat message.
            while _core._stream_line_open and _time.time() < deadline:
                _time.sleep(0.02)

            #    print_lock
            #  print_stream_delta  LLM
            # [bitchat]
            # Reasoning/assistant
            with _core.print_lock:
                if _core._stream_line_open:
                    _core.print_stream_delta(chr(10))
                if getattr(_core, "_prompt_line_open", False):
                    #  [bitchat]
                    # agentcli> [bitchat] ...
                    #
                    _core.print_stream_delta(chr(10))
                    _core._prompt_line_open = False
                    try:
                        _core.prompt_needs_redraw = True
                    except Exception:
                        pass
                _core.print_stream_delta(msg + chr(10))
        except Exception:
            try:
                print(msg, flush=True)
            except Exception:
                pass


def _ensure_display_thread() -> None:
    """表示ワーカーを一度だけ起動する（daemon なのでプロセス終了で消える）."""
    global _DISPLAY_THREAD, _DISPLAY_THREAD_STARTED
    if _DISPLAY_THREAD_STARTED:
        return
    _DISPLAY_THREAD_STARTED = True
    _DISPLAY_THREAD = threading.Thread(
        target=_display_worker,
        daemon=True,
        name="bitchat-display",
    )
    _DISPLAY_THREAD.start()


def _notify_display(msg: str) -> None:
    """Display a notification on screen (NOT sent to the LLM).

    BLE 受信スレッドをブロックしないよう、表示キューに put するだけ。
    実際の表示は専用ワーカースレッドが core の print_lock で直列化する。
    """
    if not _DEBUG and msg.startswith("[bitchat] [debug]"):
        return
    try:
        _ensure_display_thread()
        _DISPLAY_QUEUE.put_nowait(msg)
    except Exception:
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
_PEER_NOISE_KEYS: dict[str, bytes] = {}  # peer_id_hex -> noise_public_key (32 bytes)
_PEER_SIGNING_KEYS: dict[str, bytes] = {}  # peer_id_hex -> Ed25519 public key
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

    def to_dict(self) -> dict:
        """Serialize identity keys to a dict (hex strings)."""
        return {
            "noise_private": self.noise_private.hex(),
            "noise_public": self.noise_public.hex(),
            "signing_private": self.signing_private.hex(),
            "signing_public": self.signing_public.hex(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NodeIdentity":
        """Restore identity keys from a dict (hex strings)."""
        return cls(
            noise_private=bytes.fromhex(data["noise_private"]),
            noise_public=bytes.fromhex(data["noise_public"]),
            signing_private=bytes.fromhex(data["signing_private"]),
            signing_public=bytes.fromhex(data["signing_public"]),
        )


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
        _IDENTITY = _load_identity() or _create_identity()
        if _IDENTITY is not None:
            try:
                os.makedirs(_BITCHAT_DIR, exist_ok=True)
                with open(_IDENTITY_FILE, "w", encoding="utf-8") as f:
                    import json as _json

                    _json.dump(_IDENTITY.to_dict(), f)
            except Exception:
                pass
    return _IDENTITY


def _load_identity() -> NodeIdentity | None:
    """Load a persisted identity (stable peer ID across restarts)."""
    try:
        if not os.path.exists(_IDENTITY_FILE):
            return None
        import json as _json

        with open(_IDENTITY_FILE, "r", encoding="utf-8") as f:
            data = _json.load(f)
        ident = NodeIdentity.from_dict(data)
        # Sanity check: stored keys must be consistent
        if (
            len(ident.noise_private) != 32
            or len(ident.noise_public) != 32
            or len(ident.signing_private) != 32
            or len(ident.signing_public) != 32
        ):
            return None
        return ident
    except Exception:
        return None


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


def verify_packet_signature(packet, signing_public_key: bytes | None) -> bool:
    """Verify a signed public/file packet against its announced key."""
    if not signing_public_key or packet.signature is None:
        return False
    try:
        key = ed25519.Ed25519PublicKey.from_public_bytes(bytes(signing_public_key))
        key.verify(bytes(packet.signature), data_for_signing(packet))
        return True
    except Exception:
        return False


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


class NotificationStreamAssembler:
    """Reassemble BLE notification chunks into protocol frames."""

    _MAX_BUFFER = 2 * 1024 * 1024
    _SENDER_ID_SIZE = 8
    _SIGNATURE_SIZE = 64

    def __init__(self) -> None:
        self._buffer = bytearray()

    @staticmethod
    def _frame_length(buffer: bytearray) -> int | None:
        if not buffer or buffer[0] not in (1, 2):
            return 0
        if len(buffer) < 14:
            return None
        version = buffer[0]
        flags = buffer[11]
        if version == 1:
            payload_length = int.from_bytes(buffer[12:14], "big")
            header_end = 14
        else:
            if len(buffer) < 16:
                return None
            payload_length = int.from_bytes(buffer[12:16], "big")
            header_end = 16
        length = header_end + NotificationStreamAssembler._SENDER_ID_SIZE
        if flags & 0x01:  # HAS_RECIPIENT
            length += 8
        if version == 2 and flags & 0x08:  # HAS_ROUTE
            route_offset = length
            if len(buffer) <= route_offset:
                return None
            length += 1 + buffer[route_offset] * 8
        length += payload_length
        if flags & 0x02:  # HAS_SIGNATURE
            length += NotificationStreamAssembler._SIGNATURE_SIZE
        if length > NotificationStreamAssembler._MAX_BUFFER:
            return 0
        return length

    @staticmethod
    def _discard_padding(buffer: bytearray) -> None:
        if not buffer or buffer[0] in (1, 2):
            return
        pad = buffer[0]
        if 0 < pad <= len(buffer) and all(b == pad for b in buffer[:pad]):
            del buffer[:pad]

    def append(self, chunk: bytes) -> list[bytes]:
        if not chunk:
            return []
        self._buffer.extend(chunk)
        if len(self._buffer) > self._MAX_BUFFER:
            self._buffer.clear()
            return []
        frames: list[bytes] = []
        while self._buffer:
            self._discard_padding(self._buffer)
            if not self._buffer:
                break
            length = self._frame_length(self._buffer)
            if length == 0:
                del self._buffer[0]
                continue
            if length is None or len(self._buffer) < length:
                break
            frames.append(bytes(self._buffer[:length]))
            del self._buffer[:length]
        return frames


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


# BLE v1 bitchat_protocol codec  v1
#  uint16  65535
#  (struct.error: 'H' format)
#
_TEXT_MAX_BYTES = 0xFFFF

# Keep ordinary text packets small enough for Android BLE MTUs. With the
# protocol's block padding, 40 UTF-8 payload bytes produce a 128-byte packet
# (including the v1 header and signature), avoiding characteristic truncation.
_TEXT_CHUNK_BYTES = 40


def _split_text_chunks(text: str, max_bytes: int = _TEXT_CHUNK_BYTES) -> list[str]:
    """UTF-8 バイト単位で max_bytes 以下になるようテキストを分割する。

    マルチバイト文字を跨がないよう、UTF-8 エンコード済みバイト列の
    境界で調整する。Windows コンソール入力等で孤立サロゲートが混入
    しても落ちないよう errors="replace" でエンコードする (U+FFFD に置換)。
    """
    if not text:
        return []
    raw = text.encode("utf-8", errors="replace")
    if len(raw) <= max_bytes:
        #  U+FFFD
        return [raw.decode("utf-8", errors="replace")]
    chunks: list[str] = []
    start = 0
    n = len(raw)
    while start < n:
        end = min(start + max_bytes, n)
        if end < n:
            #
            while end > start:
                try:
                    raw[start:end].decode("utf-8")
                    break
                except UnicodeDecodeError:
                    end -= 1
            # : max_bytes  1
            if end == start:
                end = start + 1
        chunks.append(raw[start:end].decode("utf-8", errors="replace"))
        start = end
    return chunks


def enqueue_send(
    type_: str,
    payload: str | bytes,
    recipient: str | None = None,
    via: str = "ble",
    plain: bool = False,
) -> None:
    """Queue a message for delivery.

    via: 'ble' (BLE Mesh), 'nostr' (Nostr relays), 'both' (both transports).

    テキストは BLE 単一フレームで送れるサイズ (_TEXT_CHUNK_BYTES) に
    分割して送信する。フラグメント化・圧縮を避けて Android アプリとの
    互換性を保つ。Nostr (1MB) とファイル (1MB) は上限が大きいため
    分割不要。
    """
    if type_ == "text":
        if isinstance(payload, bytes):
            try:
                payload_text = payload.decode("utf-8")
            except UnicodeDecodeError:
                payload_text = payload.hex()
        else:
            payload_text = str(payload)
        for chunk in _split_text_chunks(payload_text):
            _enqueue_send_one(type_, chunk, recipient, via, plain=plain)
        return
    _enqueue_send_one(type_, payload, recipient, via, plain=plain)


def _enqueue_send_one(
    type_: str,
    payload: str | bytes,
    recipient: str | None = None,
    via: str = "ble",
    plain: bool = False,
) -> None:
    """単一メッセージをキュー/リレーへ投入する (enqueue_send の内部処理)。"""
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
            item: dict = {
                "type": type_,
                "payload": payload,
                "plain": plain,
                "noise_attempts": 0,
            }
            if recipient:
                item["recipient"] = recipient
            _OUTBOUND_QUEUE.put_nowait(item)
        except Exception:
            pass


# ---- BLE service -----------------------------------------------------------


def _resolve_recipient_hex(recipient: str | None) -> str | None:
    """recipient 引数を peer_id_hex に解決する。

    - 既に有効な hex ならそのまま返す
    - ニックネームなら _PEER_NICKNAMES から peer_id_hex を逆引き
    - 解決不可なら None（呼び出し側でドロップ通知する）
    """
    if not recipient:
        return None
    r = recipient.strip()
    try:
        bytes.fromhex(r)
        return r
    except ValueError:
        pass
    for pid, nick in _PEER_NICKNAMES.items():
        if nick == r:
            return pid
    return None


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
    global _OUTBOUND_QUEUE, _EVENT_LOOP
    _OUTBOUND_QUEUE = queue.Queue()
    _EVENT_LOOP = asyncio.get_running_loop()

    identity = get_identity()
    ann_payload = encode_announcement(
        AnnouncementPacket(
            nickname=nickname,
            noise_public_key=identity.noise_public,
            signing_public_key=identity.signing_public,
        )
    )
    _reassembler = FragmentAssemblyBuffer()
    _notification_assemblers: dict[str, NotificationStreamAssembler] = {}

    async def _fragment_and_send(
        wire: bytes, original_type: int = 2, exclude_addr: str | None = None
    ) -> list[tuple[str, str]]:
        fragmented = len(wire) > _MAX_FRAME_SIZE
        if fragmented:
            fid = os.urandom(8)
            #  _MAX_FRAME_SIZE
            #  (v186 + 13 = 99)
            #  (480-40=440)  539
            # BLE MTU / Android MAX_FRAGMENT_SIZE(469)
            chunk_size = _MAX_FRAME_SIZE - 99
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
            if exclude_addr is not None and addr == exclude_addr:
                continue
            try:
                _mtu = getattr(client, "mtu_size", "?")
            except Exception:
                _mtu = "?"
            _notify_display(
                "[bitchat] [debug] send to %s wire=%d mtu=%s" % (addr, len(wire), _mtu)
            )
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
        if failed:
            _notify_display(
                "[bitchat] [debug] send FAILED type=%d wire=%d -> %s"
                % (packet.type, len(wire), failed)
            )
        for addr, reason in failed:
            client = _CLIENTS.pop(addr, None)
            if client is None:
                continue
            _COOLDOWN_UNTIL[addr] = _time.monotonic() + _RETRY_COOLDOWN
            try:
                await client.disconnect()
            except Exception:
                pass

    async def _relay_packet(packet: BitchatPacket, source_addr: str | None) -> None:
        """Forward a verified signed packet without replacing its signature."""
        if packet.ttl <= 1:
            return
        relay = BitchatPacket(
            version=packet.version,
            type=packet.type,
            ttl=int(packet.ttl) - 1,
            timestamp=packet.timestamp,
            flags=packet.flags,
            sender_id=packet.sender_id,
            recipient_id=packet.recipient_id,
            route=getattr(packet, "route", None),
            is_rsr=getattr(packet, "is_rsr", False),
            payload=packet.payload,
            signature=packet.signature,
        )
        if relay.type in (
            int(MessageType.NOISE_HANDSHAKE),
            int(MessageType.NOISE_ENCRYPTED),
        ):
            raw = encode(relay, padding=False)
            wire = _pkcs7_pad(raw, _optimal_block_size(len(raw)))
        else:
            wire = encode(relay, padding=True)
        await _fragment_and_send(
            wire, original_type=int(relay.type), exclude_addr=source_addr
        )

    async def _send_announce() -> None:
        nonlocal _last_announce
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
        _last_announce = _time.time()

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
        """Send a NOISE_HANDSHAKE or NOISE_ENCRYPTED packet.

        NOISE フレームは署名なし・パディングなしで送る。理由:
        - Android の SecurityManager は NOISE_HANDSHAKE / NOISE_ENCRYPTED を
          署名検証対象外とする (verifyPacketSignature の setOf に含まれない)
        - 署名・パディングを省くと wire が小さくなり、BLE フレームとして
          確実に収まる
        - Android の decode はパディングなしも処理できる
        """
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
        # Android's BLEPacketPaddingPolicy uses MessagePadding block sizes
        # [256, 512, ...] for NOISE_HANDSHAKE/NOISE_ENCRYPTED. The codec's
        # generic padding is 128-byte based, so apply the Android-compatible
        # PKCS#7 padding explicitly here.
        wire = encode(pkt, padding=False)
        target = 256
        while len(wire) + 16 > target:
            target *= 2
        pad_len = target - len(wire)
        if 0 < pad_len <= 255:
            wire += bytes([pad_len]) * pad_len
        failed = await _fragment_and_send(wire, original_type=int(pkt.type))
        if failed:
            _notify_display(
                "[bitchat] [debug] noise send FAILED type=%d wire=%d -> %s"
                % (pkt_type, len(wire), failed)
            )
            for addr, reason in failed:
                client = _CLIENTS.pop(addr, None)
                if client is None:
                    continue
                _COOLDOWN_UNTIL[addr] = _time.monotonic() + _RETRY_COOLDOWN
                try:
                    await client.disconnect()
                except Exception:
                    pass

    async def _handle_noise_handshake(peer_hex: str, payload: bytes) -> None:
        """Process an incoming Noise handshake message."""
        from . import bitchat_noise as _noise

        rs = _PEER_NOISE_KEYS.get(peer_hex)
        if rs is None:
            _notify_display("[bitchat] [debug] HS: no noise key for %s" % peer_hex[:8])
            return  # unknown peer, can't handshake

        existing = _noise.get_session(peer_hex)
        pending = _noise._NOISE_PENDING.get(peer_hex)
        _notify_display(
            "[bitchat] [debug] HS in from %s len=%d existing=%s pending=%s"
            % (peer_hex[:8], len(payload), existing is not None, pending is not None)
        )

        if pending is None and existing is None:
            # Responder: Android  msg1 (-> e)
            _notify_display("[bitchat] [debug] HS: responder msg1 path")
            state = _noise.NoiseHandshakeState(False, _noise_static_key(), rs)
            if not state.process_message_1(payload):
                _notify_display("[bitchat] [debug] HS: process_message_1 FAILED")
                return
            _notify_display("[bitchat] [debug] HS: process_message_1 OK")
            msg2 = state.build_message_2()
            _noise._NOISE_PENDING[peer_hex] = state
            _notify_display("[bitchat] [debug] HS: sending msg2 len=%d" % len(msg2))
            await _send_noise_packet(int(MessageType.NOISE_HANDSHAKE), msg2, peer_hex)
            _notify_display("[bitchat] [debug] HS: msg2 sent")
            return

        if pending is not None:
            # A repeated 32-byte msg1 means the peer did not accept the prior
            # msg2 (or restarted its handshake). Do not misclassify it as msg3.
            if not pending.initiator and len(payload) == 32:
                _notify_display(
                    "[bitchat] [debug] HS: repeated msg1; restarting responder"
                )
                _noise.remove_session(peer_hex)
                state = _noise.NoiseHandshakeState(False, _noise_static_key(), rs)
                if not state.process_message_1(payload):
                    _notify_display("[bitchat] [debug] HS: repeated msg1 rejected")
                    return
                _noise._NOISE_PENDING[peer_hex] = state
                msg2 = state.build_message_2()
                _notify_display(
                    "[bitchat] [debug] HS: resending msg2 len=%d" % len(msg2)
                )
                await _send_noise_packet(
                    int(MessageType.NOISE_HANDSHAKE), msg2, peer_hex
                )
                return
            if pending.initiator:
                # Initiator: msg2  -> msg3
                _notify_display("[bitchat] [debug] HS: initiator msg2 path")
                if not pending.process_message_2(payload):
                    _notify_display("[bitchat] [debug] HS: process_message_2 FAILED")
                    _noise.remove_session(peer_hex)
                    return
                msg3 = pending.build_message_3()
                _noise.complete_session(peer_hex, pending)
                _notify_display("[bitchat] [debug] HS: sending msg3 len=%d" % len(msg3))
                await _send_noise_packet(
                    int(MessageType.NOISE_HANDSHAKE), msg3, peer_hex
                )
                _notify_display(
                    _(
                        "bitchat.handshake_complete",
                        default="[bitchat] Noise handshake complete with %(nick)s",
                    )
                    % {"nick": _PEER_NICKNAMES.get(peer_hex, peer_hex[:8])}
                )
            else:
                # Responder: msg3  ->
                _notify_display("[bitchat] [debug] HS: responder msg3 path")
                if not pending.process_message_3(payload):
                    _notify_display("[bitchat] [debug] HS: process_message_3 FAILED")
                    # Drop the failed responder transcript so the next msg1
                    # starts a fresh XX handshake.
                    _noise.remove_session(peer_hex)
                    return
                _noise.complete_session(peer_hex, pending)
                _notify_display(
                    _(
                        "bitchat.handshake_complete",
                        default="[bitchat] Noise handshake complete with %(nick)s",
                    )
                    % {"nick": _PEER_NICKNAMES.get(peer_hex, peer_hex[:8])}
                )
            return

    def _handle_noise_encrypted(peer_hex: str, payload: bytes) -> None:
        """Decrypt and display an incoming Noise-encrypted DM."""
        from . import bitchat_noise as _noise

        session = _noise.get_session(peer_hex)
        if session is None:
            _notify_display(
                _(
                    "bitchat.noise_dm_no_session",
                    default="[bitchat] [Noise DM] from %(sender)s -- no session (dropped)",
                )
                % {"sender": _PEER_NICKNAMES.get(peer_hex, peer_hex[:8])}
            )
            return
        pt = _noise.decrypt_dm(session, payload)
        if pt is None:
            _notify_display(
                _(
                    "bitchat.noise_dm_decrypt_failed",
                    default="[bitchat] [Noise DM] from %(sender)s -- decrypt failed",
                )
                % {"sender": _PEER_NICKNAMES.get(peer_hex, peer_hex[:8])}
            )
            return
        # Android/iOS  NoisePayload + PrivateMessagePacket TLV
        #  (ACK / read receipt)
        decoded = _noise.decode_private_message(pt)
        if decoded is not None:
            text = decoded[1]
        else:
            try:
                text = pt.decode("utf-8")
            except Exception:
                return  #
        sender = _PEER_NICKNAMES.get(peer_hex, peer_hex[:8])
        _notify_display(
            _(
                "bitchat.noise_dm_msg",
                default="[bitchat] [Noise DM] %(sender)s: %(text)s",
            )
            % {"sender": sender, "text": text}
        )
        if _CHAT_MODE == "llm":
            _inject_to_llm(
                _(
                    "bitchat.noise_dm_msg",
                    default="[bitchat] [Noise DM] %(sender)s: %(text)s",
                )
                % {"sender": sender, "text": text}
            )

    # ---- End Noise DM handlers ---------------------------------------------

    def _dispatch(pkt: BitchatPacket, source_addr: str | None = None) -> None:
        if pkt.sender_id == identity.peer_id_bytes:
            return
        peer_hex = pkt.sender_id.hex()
        if pkt.type == int(MessageType.ANNOUNCE):
            announced = decode_announcement(pkt.payload)
            if announced is None or not verify_packet_signature(
                pkt, announced.signing_public_key
            ):
                _notify_display(
                    "[bitchat] Dropping ANNOUNCE with missing/invalid signature"
                )
                return
            _PEER_SIGNING_KEYS[peer_hex] = announced.signing_public_key
        elif pkt.type in (
            int(MessageType.MESSAGE),
            int(MessageType.FILE_TRANSFER),
            int(MessageType.FRAGMENT),
            int(MessageType.LEAVE),
        ):
            if not verify_packet_signature(pkt, _PEER_SIGNING_KEYS.get(peer_hex)):
                _notify_display(
                    "[bitchat] Dropping unsigned/invalid packet from %s" % peer_hex[:8]
                )
                return

        if pkt.type == int(MessageType.FRAGMENT):
            now = _time.time()
            key = hashlib.sha256(
                pkt.sender_id
                + bytes([pkt.type])
                + int(pkt.timestamp).to_bytes(8, "big", signed=False)
                + pkt.payload
            ).digest()
            if key in _SEEN_MESSAGE_KEYS:
                return
            _SEEN_MESSAGE_KEYS[key] = now
            if pkt.ttl > 1:
                asyncio.create_task(_relay_packet(pkt, source_addr))

            parsed = parse_fragment_payload(pkt.payload)
            if parsed is not None:
                frag_id, index, total, orig_type, frag_data = parsed
                header = FragmentHeader(frag_id, index, total, orig_type)
                inner = _reassembler.append(pkt.sender_id, header, frag_data)
                if inner is not None:
                    inner_pkt = decode(inner)
                    if inner_pkt is not None:
                        _dispatch(inner_pkt, source_addr)
            return
        if pkt.type in (
            int(MessageType.ANNOUNCE),
            int(MessageType.MESSAGE),
            int(MessageType.FILE_TRANSFER),
            int(MessageType.FRAGMENT),
            int(MessageType.LEAVE),
            int(MessageType.NOISE_HANDSHAKE),
            int(MessageType.NOISE_ENCRYPTED),
        ):
            # BLE mesh retransmission can deliver the same packet more than
            # once. Deduplicate before display and LLM injection so one user
            # message produces one event and one response.
            now = _time.time()
            key = hashlib.sha256(
                pkt.sender_id
                + bytes([pkt.type])
                + int(pkt.timestamp).to_bytes(8, "big", signed=False)
                + pkt.payload
            ).digest()
            expired = [
                k for k, t in _SEEN_MESSAGE_KEYS.items() if now - t > _SEEN_MESSAGE_TTL
            ]
            for old_key in expired:
                _SEEN_MESSAGE_KEYS.pop(old_key, None)
            if key in _SEEN_MESSAGE_KEYS:
                return
            _SEEN_MESSAGE_KEYS[key] = now
        if (
            pkt.type
            in (
                int(MessageType.ANNOUNCE),
                int(MessageType.MESSAGE),
                int(MessageType.FILE_TRANSFER),
                int(MessageType.FRAGMENT),
                int(MessageType.LEAVE),
                int(MessageType.NOISE_HANDSHAKE),
                int(MessageType.NOISE_ENCRYPTED),
            )
            and pkt.ttl > 1
        ):
            asyncio.create_task(_relay_packet(pkt, source_addr))
        if pkt.type == int(MessageType.ANNOUNCE):
            ann = decode_announcement(pkt.payload)
            if ann is not None:
                old = _PEER_NICKNAMES.get(peer_hex)
                _PEER_NICKNAMES[peer_hex] = ann.nickname
                _PEER_NOISE_KEYS[peer_hex] = ann.noise_public_key
                if old is None:
                    _notify_display(
                        _(
                            "bitchat.peer_online",
                            default="[bitchat] ++ %(nick)s is now online",
                        )
                        % {"nick": ann.nickname}
                    )
        elif pkt.type == int(MessageType.MESSAGE):
            try:
                text = pkt.payload.decode("utf-8")
            except Exception:
                return
            sender = _PEER_NICKNAMES.get(peer_hex, peer_hex[:8])
            # Broadcast (all 0xFF) = #mesh channel; specific recipient = DM
            if pkt.recipient_id is not None and pkt.recipient_id != b"\xff" * 8:
                _notify_display(
                    _("bitchat.dm_msg", default="[bitchat] [DM] %(sender)s: %(text)s")
                    % {"sender": sender, "text": text}
                )
                if _CHAT_MODE == "llm":
                    _inject_to_llm(
                        _(
                            "bitchat.dm_msg",
                            default="[bitchat] [DM] %(sender)s: %(text)s",
                        )
                        % {"sender": sender, "text": text}
                    )
            else:
                if _NOSTR_BRIDGE and _NOSTR_RUNNING and _NOSTR is not None:
                    try:
                        _NOSTR.nostr_send_text(text)
                    except Exception:
                        pass
                _notify_display(
                    _("bitchat.mesh_msg", default="[bitchat] %(sender)s: %(text)s")
                    % {"sender": sender, "text": text}
                )
                if _CHAT_MODE == "llm":
                    _inject_to_llm(
                        _("bitchat.mesh_msg", default="[bitchat] %(sender)s: %(text)s")
                        % {"sender": sender, "text": text}
                    )
        elif pkt.type == int(MessageType.NOISE_HANDSHAKE):
            _notify_display(
                _(
                    "bitchat.debug_noise_hs",
                    default="[bitchat] [debug] NOISE_HANDSHAKE from %(sender)s len=%(n)d",
                )
                % {
                    "sender": _PEER_NICKNAMES.get(peer_hex, peer_hex[:8]),
                    "n": len(pkt.payload),
                }
            )
            loop = _EVENT_LOOP
            if loop is not None:
                asyncio.run_coroutine_threadsafe(
                    _handle_noise_handshake(peer_hex, pkt.payload), loop
                )
        elif pkt.type == int(MessageType.NOISE_ENCRYPTED):
            _notify_display(
                _(
                    "bitchat.debug_noise_enc",
                    default="[bitchat] [debug] NOISE_ENCRYPTED from %(sender)s len=%(n)d",
                )
                % {
                    "sender": _PEER_NICKNAMES.get(peer_hex, peer_hex[:8]),
                    "n": len(pkt.payload),
                }
            )
            _handle_noise_encrypted(peer_hex, pkt.payload)
        elif pkt.type == int(MessageType.LEAVE):
            nick = _PEER_NICKNAMES.pop(peer_hex, peer_hex[:8])
            _PEER_NOISE_KEYS.pop(peer_hex, None)
            _PEER_SIGNING_KEYS.pop(peer_hex, None)
            _notify_display(
                _("bitchat.peer_offline", default="[bitchat] -- %(nick)s went offline")
                % {"nick": nick}
            )
        elif pkt.type == int(MessageType.FILE_TRANSFER):
            file_info = decode_file_payload(pkt.payload)
            if file_info is not None:
                sender = _PEER_NICKNAMES.get(peer_hex, peer_hex[:8])
                fname = file_info["file_name"]
                fdata = file_info["content"]
                try:
                    os.makedirs(_DOWNLOAD_DIR, exist_ok=True)
                    safe_name = os.path.basename(fname) if fname else ""
                    safe_name = (
                        safe_name.replace("\\", "_")
                        .replace("/", "_")
                        .replace("\x00", "")
                        .strip()
                        .lstrip(".")
                    )
                    if not safe_name:
                        safe_name = f"received_{int(_time.time() * 1000)}"
                    base, ext = os.path.splitext(safe_name)
                    candidate = safe_name
                    suffix = 1
                    while os.path.exists(os.path.join(_DOWNLOAD_DIR, candidate)):
                        candidate = f"{base}_{suffix}{ext}"
                        suffix += 1
                    safe_name = candidate
                    save_path = os.path.join(_DOWNLOAD_DIR, safe_name)
                    with open(save_path, "xb") as f:
                        f.write(fdata)
                    _notify_display(
                        _(
                            "bitchat.file_received",
                            default="[bitchat] %(sender)s sent file: %(fname)s (%(size)d bytes) -> %(safe)s",
                        )
                        % {
                            "sender": sender,
                            "fname": fname,
                            "size": len(fdata),
                            "safe": safe_name,
                        }
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
                        _(
                            "bitchat.file_save_failed",
                            default="[bitchat] Failed to save file from %(sender)s: %(exc)s",
                        )
                        % {"sender": sender, "exc": exc}
                    )

    def _on_notify(addr: str, _characteristic, data: bytearray) -> None:
        try:
            if _STOP_EVENT.is_set():
                return
            assembler = _notification_assemblers.setdefault(
                addr, NotificationStreamAssembler()
            )
            for frame in assembler.append(bytes(data)):
                pkt = decode(frame)
                if pkt is not None:
                    _dispatch(pkt, addr)
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
            _notification_assemblers[addr] = NotificationStreamAssembler()
            await client.start_notify(
                char_uuid,
                lambda characteristic, data: _on_notify(addr, characteristic, data),
            )
            _notify_display(
                _(
                    "bitchat.peer_connected",
                    default="[bitchat] Connected to peer at %(addr)s",
                )
                % {"addr": addr}
            )
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
        _notification_assemblers.pop(addr, None)
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
            pass  # no name advertised - skip display
        else:
            rssi = getattr(device, "rssi", 0)
            _notify_display(
                _(
                    "bitchat.peer_discovered",
                    default="[bitchat] Discovered peer: %(name)s (%(addr)s) RSSI=%(rssi)s",
                )
                % {"name": name, "addr": addr, "rssi": rssi}
            )
        _CONNECTING.add(addr)
        asyncio.create_task(_connect(device))

    scanner = BleakScanner(detection_callback=_on_detection, service_uuids=[svc_uuid])
    try:
        await scanner.start()
    except BleakError as exc:
        _notify_display(
            _("bitchat.scan_failed", default="[bitchat] BLE scan start failed: %(exc)s")
            % {"exc": exc}
        )
        return

    _notify_display(
        _(
            "bitchat.service_started",
            default="[bitchat] BLE service started (network=%(network)s, nickname=%(nickname)s)",
        )
        % {"network": network, "nickname": nickname}
    )
    _last_announce = 0.0

    #  FIFOqueue.Queue
    #  deque
    # BLE
    _pending: deque = deque()

    try:
        while not _STOP_EVENT.is_set():
            if _OUTBOUND_QUEUE is None:
                await asyncio.sleep(0.2)
                continue
            #
            while not _OUTBOUND_QUEUE.empty():
                try:
                    _pending.append(_OUTBOUND_QUEUE.get_nowait())
                except Exception:
                    break
            if not _pending:
                await asyncio.sleep(0.2)
                continue
            if not _CLIENTS:
                # :
                await asyncio.sleep(0.2)
                continue
            while True:
                if not _pending:
                    break
                try:
                    item = _pending[0]
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
                            failed = await _send_packet(pkt)
                            if failed:
                                # :
                                await asyncio.sleep(0.5)
                                break
                        _pending.popleft()
                        continue
                    recipient_raw = item.get("recipient")
                    recipient_hex = (
                        _resolve_recipient_hex(recipient_raw) if recipient_raw else None
                    )
                    if recipient_raw and not recipient_hex:
                        _notify_display(
                            _(
                                "bitchat.unknown_recipient",
                                default=(
                                    "[bitchat] Unknown recipient %(recipient)s -- "
                                    "message dropped"
                                ),
                            )
                            % {"recipient": recipient_raw}
                        )
                        _pending.popleft()
                        continue
                    payload_bytes = (
                        payload.encode("utf-8") if isinstance(payload, str) else payload
                    )

                    # If a recipient is specified, try Noise DM (unless plain forced)
                    if recipient_hex and send_type == "text" and not item.get("plain"):
                        # Check for existing Noise session
                        from . import bitchat_noise as _noise

                        session = _noise.get_session(recipient_hex)
                        if session is not None:
                            # Encrypt with Noise. Android/iOS  NoisePayload +
                            # PrivateMessagePacket TLV
                            text = (
                                payload_bytes.decode("utf-8", errors="replace")
                                if isinstance(payload_bytes, bytes)
                                else str(payload_bytes)
                            )
                            dm_payload = _noise.encode_private_message(
                                str(uuid.uuid4()), text
                            )
                            ct = (
                                _noise.encrypt_dm(session, dm_payload)
                                if dm_payload is not None
                                else None
                            )
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
                                failed = await _send_packet(pkt)
                                if failed:
                                    # :
                                    await asyncio.sleep(0.5)
                                    break
                                _pending.popleft()
                                continue
                            _notify_display(
                                _(
                                    "bitchat.noise_dm_failed",
                                    default=(
                                        "[bitchat] Failed to encrypt DM to %(recipient)s; "
                                        "message dropped"
                                    ),
                                )
                                % {"recipient": recipient_hex[:8]}
                            )
                            _pending.popleft()
                            continue
                        else:
                            # Initiate Noise handshake first, then queue message for later
                            rs = _PEER_NOISE_KEYS.get(recipient_hex)
                            attempts = int(item.get("noise_attempts", 0))
                            if (
                                rs is not None
                                and attempts < _NOISE_HANDSHAKE_MAX_ATTEMPTS
                            ):
                                # Start handshake
                                pending = _noise.get_or_create_session(
                                    recipient_hex,
                                    initiator=True,
                                    our_static=_noise_static_key(),
                                    their_static_pub=rs,
                                )
                                if pending is not None:
                                    _notify_display(
                                        _(
                                            "bitchat.debug_hs_start",
                                            default="[bitchat] [debug] start Noise HS -> %(recipient)s rs=%(rs)s",
                                        )
                                        % {
                                            "recipient": recipient_hex[:8],
                                            "rs": "yes" if rs is not None else "no",
                                        }
                                    )
                                    msg1 = pending.build_message_1()
                                    _noise._NOISE_PENDING[recipient_hex] = pending
                                    await _send_noise_packet(
                                        int(MessageType.NOISE_HANDSHAKE),
                                        msg1,
                                        recipient_hex,
                                    )
                                    _notify_display(
                                        _(
                                            "bitchat.debug_hs_msg1_sent",
                                            default="[bitchat] [debug] msg1 sent to %(recipient)s len=%(n)d",
                                        )
                                        % {
                                            "recipient": recipient_hex[:8],
                                            "n": len(msg1),
                                        }
                                    )
                                    #
                                    item["noise_attempts"] = attempts + 1
                                    await asyncio.sleep(0.5)
                                    continue
                            _notify_display(
                                _(
                                    "bitchat.debug_hs_skip",
                                    default="[bitchat] [debug] HS skip rs=%(rs)s attempts=%(a)d",
                                )
                                % {
                                    "rs": "yes" if rs is not None else "no",
                                    "a": attempts,
                                }
                            )
                            _notify_display(
                                _(
                                    "bitchat.noise_dm_dropped",
                                    default=(
                                        "[bitchat] No Noise session for DM to %(recipient)s; "
                                        "message dropped"
                                    ),
                                )
                                % {"recipient": recipient_hex[:8]}
                            )
                            _pending.popleft()
                            continue

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
                    failed = await _send_packet(pkt)
                    if failed:
                        # :
                        #
                        await asyncio.sleep(0.5)
                        break
                    _pending.popleft()
                    #  pacing: BLE
                    #
                    await asyncio.sleep(_PACKET_PACING)
                except Exception as _exc:
                    import traceback as _tb

                    _tb.print_exc()
                    #
                    await asyncio.sleep(0.5)
                    break
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
    global _RUNNING
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_run_ble_service(nickname, network))
    except Exception as exc:
        if not _STOP_EVENT.is_set():
            _notify_display(
                "[bitchat] BLE service stopped unexpectedly: %s" % type(exc).__name__
            )
    finally:
        if not _STOP_EVENT.is_set():
            _RUNNING = False


# ---- Nostr message callback ------------------------------------------------


def _on_nostr_message(nick: str, text: str, kind: int) -> None:
    """Callback when a Nostr message arrives."""
    kind_label = "kind-1059" if kind == 1059 else "kind-1"
    _notify_display(
        _("bitchat.nostr_msg", default="[nostr/%(kind)s] %(nick)s: %(text)s")
        % {"kind": kind_label, "nick": nick, "text": text}
    )
    if _CHAT_MODE == "llm":
        _inject_to_llm(
            _("bitchat.nostr_msg", default="[nostr/%(kind)s] %(nick)s: %(text)s")
            % {"kind": kind_label, "nick": nick, "text": text}
        )


def _pin_bitchat_tools() -> None:
    """Pin bitchat tools against auto-unload while the node is running."""
    try:
        from ._genre_control_util import pin_tool

        pin_tool("pybitchat_subscribe", reason="bitchat node running")
        pin_tool("pybitchat_send", reason="bitchat node running")
    except Exception:
        pass


def _unpin_bitchat_tools() -> None:
    """Unpin bitchat tools once the node has stopped."""
    try:
        from ._genre_control_util import unpin_tool

        unpin_tool("pybitchat_subscribe")
        unpin_tool("pybitchat_send")
    except Exception:
        pass


def start(
    nickname: str = "",
    network: str = "mainnet",
    nostr: bool = False,
    nostr_relays: list[str] | None = None,
) -> dict[str, Any]:
    global _LISTENER_THREAD, _RUNNING, _NOSTR, _NOSTR_RUNNING, _NOSTR_RELAYS, _NOSTR_BRIDGE
    if _RUNNING:
        # Re-assert pins even when the node is already running.
        _pin_bitchat_tools()
        if not nostr:
            return {"ok": True, "state": "running", "message": "Already running"}
        if _NOSTR_RUNNING:
            return {
                "ok": True,
                "state": "running",
                "nostr": "running",
                "message": "Already running",
            }
        return {
            "ok": False,
            "state": "running",
            "error": "Node is already running; stop it before changing Nostr settings",
        }
    global _IGNORED, _CONNECTING, _ATTEMPTS, _COOLDOWN_UNTIL, _CLIENTS, _PEER_NICKNAMES, _PEER_SIGNING_KEYS
    _IGNORED = set()
    _CONNECTING = set()
    _ATTEMPTS = {}
    _COOLDOWN_UNTIL = {}
    _CLIENTS = {}
    _PEER_NICKNAMES = {}
    _PEER_NOISE_KEYS = {}
    _PEER_SIGNING_KEYS = {}
    _STOP_EVENT.clear()
    _LISTENER_THREAD = threading.Thread(
        target=_listener_loop,
        args=(nickname or "anonymous", network),
        daemon=True,
        name="pybitchat-ble",
    )
    _LISTENER_THREAD.start()
    _RUNNING = True
    _pin_bitchat_tools()
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
                _NOSTR_BRIDGE = True  # enable BLE->Nostr forwarding
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
    _unpin_bitchat_tools()
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
            # src=bitchat : cli.py  LLM  mesh
            q.put_nowait({"kind": "user", "text": text, "src": "bitchat"})
        except Exception:
            pass


def forward_to_mesh(text: str) -> None:
    """Forward user text to the BLE Mesh (and Nostr if enabled) if chat mode is active."""
    global _NOSTR_RUNNING
    if _CHAT_MODE in ("on", "llm") and _RUNNING and text.strip():
        via = "both" if _NOSTR_RUNNING else "ble"
        enqueue_send("text", text, via=via)


_ANSI_ESCAPE_RE = _re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_MESH_JUNK_PREFIXES = ("[STATE]", "[TOOL]", "[INFO]", "[WARN]", "[ERROR]")


def _sanitize_mesh_text(text: str) -> str:
    """LLM 応答を mesh に送る前に、不要な制御文字・ログ行を除去する。

    - ANSI エスケープシーケンス (ESC[90m 等) を除去
    - [STATE] / [TOOL] / [INFO] / [WARN] / [ERROR] で始まる行を除去
    """
    text = _ANSI_ESCAPE_RE.sub("", text)
    cleaned = [
        ln for ln in text.splitlines() if not ln.strip().startswith(_MESH_JUNK_PREFIXES)
    ]
    return chr(10).join(cleaned).strip()


def reply_to_mesh(text: str) -> None:
    """Send an LLM reply back to the mesh (and Nostr if enabled).

    Active only in chat_mode='llm' (LLM injection active). Text is
    auto-split by enqueue_send if it exceeds the BLE v1 packet limit.
    """
    global _NOSTR_RUNNING
    if _CHAT_MODE == "llm" and _RUNNING and text and text.strip():
        via = "both" if _NOSTR_RUNNING else "ble"
        enqueue_send("text", _sanitize_mesh_text(text), via=via)


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
    if _CHAT_MODE == "llm" and _LLM_EVENT_QUEUE is None:
        # CLI startup normally supplies the queue. Also bind it here for
        # tool-driven starts so DM/mesh messages are injected when bitchat is
        # enabled after the main loop has already been initialized.
        try:
            from .. import core as _core

            set_llm_event_queue(_core.event_queue)
        except Exception:
            pass
    return {"ok": True, "chat_mode": _CHAT_MODE}


def set_llm_event_queue(q: "queue.Queue[dict[str, Any]] | None") -> None:
    """Set the event queue for LLM injection (called from cli.py)."""
    global _LLM_EVENT_QUEUE
    _LLM_EVENT_QUEUE = q


# ---- Courier / Store-and-Forward -------------------------------------------


class CourierEnvelope:
    """A store-and-forward envelope for offline bitchat peers.

    Encapsulates a payload addressed to a recipient. Envelopes expire after
    ``ttl_seconds`` from ``created_at`` and are skipped by ``CourierStore``.
    """

    def __init__(
        self,
        recipient_id: str,
        sender_id: str,
        payload: bytes,
        *,
        envelope_id: str | None = None,
        created_at: float | None = None,
        ttl_seconds: float = 3600.0,
    ) -> None:
        self.recipient_id = recipient_id
        self.sender_id = sender_id
        self.payload = payload if isinstance(payload, bytes) else bytes(payload or b"")
        self.envelope_id = envelope_id or uuid.uuid4().hex
        self.created_at = created_at if created_at is not None else _time.time()
        self.ttl_seconds = float(ttl_seconds)

    def is_expired(self, *, now: float | None = None) -> bool:
        """Return True when the envelope is past its TTL."""
        now = now if now is not None else _time.time()
        return now > (self.created_at + self.ttl_seconds)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict (payload as hex)."""
        return {
            "envelope_id": self.envelope_id,
            "recipient_id": self.recipient_id,
            "sender_id": self.sender_id,
            "payload_hex": self.payload.hex(),
            "created_at": self.created_at,
            "ttl_seconds": self.ttl_seconds,
        }


class CourierStore:
    """In-memory store-and-forward mailbox for offline bitchat peers."""

    def __init__(self) -> None:
        self._envelopes: list[CourierEnvelope] = []

    def store(self, env: CourierEnvelope) -> None:
        """Queue an envelope for delivery."""
        if isinstance(env, dict):
            env = CourierEnvelope(**env)
        elif not isinstance(env, CourierEnvelope):
            # Accept envelopes created before this module was reloaded
            # (tools.reload_plugins() re-imports helper modules).
            env = CourierEnvelope(
                recipient_id=env.recipient_id,
                sender_id=env.sender_id,
                payload=env.payload,
                envelope_id=getattr(env, "envelope_id", None),
                created_at=getattr(env, "created_at", None),
                ttl_seconds=getattr(env, "ttl_seconds", 3600.0),
            )
        self._envelopes.append(env)

    def _active(self, *, now: float | None = None) -> list[CourierEnvelope]:
        now = now if now is not None else _time.time()
        return [e for e in self._envelopes if not e.is_expired(now=now)]

    def retrieve(self, recipient_id: str) -> list[CourierEnvelope]:
        """Return undelivered (non-expired) envelopes for a recipient.

        Retrieval does not remove envelopes; callers remove them after the
        recipient acknowledges delivery (see remove()).
        """
        return [e for e in self._active() if e.recipient_id == recipient_id]

    def remove(self, envelope_id: str) -> bool:
        """Remove a delivered envelope by id. Returns True when removed."""
        for i, e in enumerate(self._envelopes):
            if e.envelope_id == envelope_id:
                self._envelopes.pop(i)
                return True
        return False

    def count(self) -> int:
        """Number of active (non-expired) envelopes."""
        return len(self._active())


# ---- Noise XX handshake (Phase 2) ------------------------------------------

_NOISE_PROTOCOL_NAME = b"Noise_XX_25519_ChaChaPoly_SHA256"
_NOISE_PROTOCOL_HASH = hashlib.sha256(_NOISE_PROTOCOL_NAME).digest()


def _noise_hmac(key: bytes, data: bytes) -> bytes:
    import hmac as _hmac_mod

    return _hmac_mod.new(key, data, hashlib.sha256).digest()


def _noise_hkdf(
    chaining_key: bytes, input_key_material: bytes, num_outputs: int
) -> list[bytes]:
    """Noise HKDF: HMAC-SHA256 based, returns num_outputs keys."""
    temp_key = _noise_hmac(chaining_key, input_key_material)
    output1 = _noise_hmac(temp_key, b"\x01")
    if num_outputs == 1:
        return [output1]
    output2 = _noise_hmac(temp_key, output1 + b"\x02")
    if num_outputs == 2:
        return [output1, output2]
    output3 = _noise_hmac(temp_key, output2 + b"\x03")
    return [output1, output2, output3]


def _generate_keypair() -> tuple[bytes, bytes]:
    """Generate an X25519 key pair; returns (private_bytes, public_bytes)."""
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


class TransportCipher:
    """ChaCha20-Poly1305 transport cipher with an incrementing nonce."""

    def __init__(self, key: bytes):
        self.k = bytes(key)
        self.n = 0
        self._cipher = ChaCha20Poly1305(self.k)

    def encrypt_with_ad(self, ad: bytes, plaintext: bytes) -> bytes:
        nonce = self.n.to_bytes(12, "little")
        self.n += 1
        return self._cipher.encrypt(nonce, plaintext, ad)

    def decrypt_with_ad(self, ad: bytes, ciphertext: bytes) -> bytes:
        nonce = self.n.to_bytes(12, "little")
        self.n += 1
        return self._cipher.decrypt(nonce, ciphertext, ad)


class NoiseXXStateMachine:
    """Noise XX (Noise_XX_25519_ChaChaPoly_SHA256) handshake state machine.

    Wire-compatible with the official bitchat app. The handshake derives two
    TransportCipher objects (tx/rx) for authenticated DM transport.
    """

    def __init__(
        self,
        static_private: bytes,
        static_public: bytes,
        prologue: bytes = b"bitchat-noise-xx",
        initiator: bool = False,
    ) -> None:
        self.static_private = bytes(static_private)
        self.static_public = bytes(static_public)
        self.prologue = prologue or b""
        self.initiator = bool(initiator)

        self.e: bytes | None = None  # local ephemeral public key
        self.re: bytes | None = None  # remote ephemeral public key
        self.rs: bytes | None = None  # remote static public key
        self._e_priv: Any = None
        self.h = _NOISE_PROTOCOL_HASH
        self.ck = _NOISE_PROTOCOL_HASH
        self._cipher: Any = None
        self.tx: TransportCipher | None = None
        self.rx: TransportCipher | None = None

        if self.prologue:
            self._mix_hash(self.prologue)

    def _mix_hash(self, data: bytes) -> None:
        self.h = hashlib.sha256(self.h + data).digest()

    def _mix_key(self, dh_result: bytes) -> None:
        outputs = _noise_hkdf(self.ck, dh_result, 2)
        self.ck = outputs[0]
        self._cipher = ChaCha20Poly1305(outputs[1])

    def _encrypt_and_hash(self, plaintext: bytes) -> bytes:
        nonce = (0).to_bytes(12, "little")
        ct = self._cipher.encrypt(nonce, plaintext, self.h)
        self._mix_hash(ct)
        return ct

    def _decrypt_and_hash(self, ciphertext: bytes) -> bytes:
        nonce = (0).to_bytes(12, "little")
        pt = self._cipher.decrypt(nonce, ciphertext, self.h)
        self._mix_hash(ciphertext)
        return pt

    def _split(self) -> None:
        outputs = _noise_hkdf(self.ck, b"", 2)
        if self.initiator:
            self.tx = TransportCipher(outputs[0])
            self.rx = TransportCipher(outputs[1])
        else:
            self.tx = TransportCipher(outputs[1])
            self.rx = TransportCipher(outputs[0])

    def process_message_1(self, data: bytes | None = None) -> bytes:
        """Build message 1 (initiator) or process message 1 and build message 2.

        With no argument: returns ``e`` (the initiator's ephemeral public key).
        With ``data`` (responder): processes ``-> e`` and returns message 2.
        """
        if data is None:
            # Initiator: -> e
            self._e_priv = x25519.X25519PrivateKey.generate()
            self.e = self._e_priv.public_key().public_bytes_raw()
            self._mix_hash(self.e)
            return self.e
        # Responder: <- e
        if len(data) < 32:
            raise ValueError(_("noise.err_msg1_short", default="message 1 too short"))
        self.re = data[:32]
        self._mix_hash(self.re)
        return self._build_message_2()

    def _build_message_2(self) -> bytes:
        # <- e, ee, s, es
        self._e_priv = x25519.X25519PrivateKey.generate()
        e_pub = self._e_priv.public_key().public_bytes_raw()
        re_key = x25519.X25519PublicKey.from_public_bytes(self.re)
        ee = self._e_priv.exchange(re_key)
        self._mix_key(ee)
        # e token: mix_hash(e_pub) before encrypting
        self._mix_hash(e_pub)
        # s token: encrypt own static with the current key (after ee)
        encrypted_s = self._encrypt_and_hash(self.static_public)
        # es token (sender side): DH(own static, remote ephemeral)
        s_priv = x25519.X25519PrivateKey.from_private_bytes(self.static_private)
        es = s_priv.exchange(re_key)
        self._mix_key(es)
        return e_pub + encrypted_s

    def process_message_2(self, data: bytes) -> bytes | None:
        """Process message 2 and build message 3 (initiator), or finalize (responder).

        As initiator: processes ``<- e, ee, s, es``, derives the remote static
        key from the encrypted payload, and returns message 3.
        As responder: processes ``-> s, se`` and finalizes the handshake.
        """
        if self.initiator:
            if len(data) < 80:
                raise ValueError(
                    _("noise.err_msg2_short", default="message 2 too short")
                )
            e_pub = data[:32]
            encrypted_s = data[32:80]
            self.re = e_pub
            self._mix_hash(e_pub)
            re_key = x25519.X25519PublicKey.from_public_bytes(self.re)
            ee = self._e_priv.exchange(re_key)
            self._mix_key(ee)
            # Decrypt remote static key and finish es = DH(e, rs)
            self.rs = self._decrypt_and_hash(encrypted_s)
            es = self._e_priv.exchange(
                x25519.X25519PublicKey.from_public_bytes(self.rs)
            )
            self._mix_key(es)
            return self._build_message_3()
        # Responder: <- s, se (finalize)
        if len(data) < 48:
            raise ValueError(_("noise.err_msg3_short", default="message 3 too short"))
        encrypted_s = data[:48]
        self.rs = self._decrypt_and_hash(encrypted_s)
        se = self._e_priv.exchange(x25519.X25519PublicKey.from_public_bytes(self.rs))
        self._mix_key(se)
        self._split()
        return None

    def _build_message_3(self) -> bytes:
        # -> s, se
        re_key = x25519.X25519PublicKey.from_public_bytes(self.re)
        s_priv = x25519.X25519PrivateKey.from_private_bytes(self.static_private)
        encrypted_s = self._encrypt_and_hash(self.static_public)
        se = s_priv.exchange(re_key)
        self._mix_key(se)
        self._split()
        return encrypted_s


# ---- Announce / Discovery (Phase 3) ----------------------------------------


def _announce_canonical(data: dict[str, Any]) -> bytes:
    """Canonical byte representation of an announce payload for signing."""
    parts: list[bytes] = []
    for key in ("nickname", "noise_public_key", "signing_public_key", "timestamp"):
        val = data.get(key)
        if isinstance(val, str):
            parts.append(val.encode("utf-8"))
        elif isinstance(val, bytes):
            parts.append(val)
        else:
            parts.append(str(val).encode("utf-8"))
    return b"|".join(parts)


def sign_announce(announce_data: dict[str, Any], sign_priv: bytes) -> bytes:
    """Sign an announce payload with an Ed25519 private key."""
    key = ed25519.Ed25519PrivateKey.from_private_bytes(bytes(sign_priv))
    return key.sign(_announce_canonical(announce_data))


def verify_announce(
    announce_data: dict[str, Any], signature: bytes, sign_pub: bytes
) -> bool:
    """Verify an Ed25519 signature over the canonical announce payload."""
    try:
        key = ed25519.Ed25519PublicKey.from_public_bytes(bytes(sign_pub))
        key.verify(bytes(signature), _announce_canonical(announce_data))
        return True
    except Exception:
        return False


class PeerRegistry:
    """Registry of discovered bitchat peers with TTL expiry and connection state."""

    def __init__(self, ttl_seconds: float = 3600.0):
        self._peers: dict[str, dict[str, Any]] = {}
        self._states: dict[str, str] = {}
        self._ttl_seconds = float(ttl_seconds)

    def add_peer(
        self,
        peer_id: str,
        nickname: str,
        noise_public_key: bytes,
        signing_public_key: bytes,
    ) -> None:
        self._peers[peer_id] = {
            "peer_id": peer_id,
            "nickname": nickname,
            "noise_public_key": bytes(noise_public_key),
            "signing_public_key": bytes(signing_public_key),
            "last_seen": _time.time(),
        }
        self._states.setdefault(peer_id, "discovered")

    def get_peer(self, peer_id: str) -> dict[str, Any] | None:
        peer = self._peers.get(peer_id)
        if peer is None:
            return None
        if _time.time() - peer["last_seen"] > self._ttl_seconds:
            self.remove_peer(peer_id)
            return None
        return peer

    def list_peers(self) -> list[dict[str, Any]]:
        return [
            p
            for p in (self.get_peer(pid) for pid in list(self._peers.keys()))
            if p is not None
        ]

    def get_peer_state(self, peer_id: str) -> str:
        return self._states.get(peer_id, "discovered")

    def set_peer_state(self, peer_id: str, state: str) -> None:
        self._states[peer_id] = state

    def remove_peer(self, peer_id: str) -> None:
        self._peers.pop(peer_id, None)
        self._states.pop(peer_id, None)


# ---- Message routing: dedup + relay (Phase 4) ------------------------------


class MessageDeduplicator:
    """Time-windowed duplicate suppression for flooded mesh messages."""

    def __init__(self, window_seconds: float = 10.0):
        self._seen: dict[str, float] = {}
        self._window = float(window_seconds)

    def is_duplicate(self, msg_id: str) -> bool:
        now = _time.time()
        ts = self._seen.get(msg_id)
        if ts is not None and now - ts <= self._window:
            return True
        self._seen[msg_id] = now
        return False

    def count(self) -> int:
        self.cleanup()
        return len(self._seen)

    def cleanup(self) -> None:
        now = _time.time()
        expired = [mid for mid, ts in self._seen.items() if now - ts > self._window]
        for mid in expired:
            self._seen.pop(mid, None)


class RelayController:
    """Flooding relay controller with delay jitter and degree-based suppression."""

    def __init__(
        self,
        base_probability: float = 0.5,
        min_delay_ms: float = 100.0,
        max_delay_ms: float = 500.0,
        degree_threshold: int = 5,
    ):
        self.base_probability = float(base_probability)
        self.min_delay_ms = float(min_delay_ms)
        self.max_delay_ms = float(max_delay_ms)
        self.degree_threshold = int(degree_threshold)

    def should_relay(self, degree: int = 0) -> bool:
        if self.base_probability <= 0.0:
            return False
        if degree >= self.degree_threshold:
            # High-degree nodes suppress more aggressively.
            if self.base_probability >= 1.0:
                return random.random() > 0.5
            return random.random() < (self.base_probability * 0.5)
        if self.base_probability >= 1.0:
            return True
        return random.random() < self.base_probability

    def get_delay(self) -> float:
        return random.uniform(self.min_delay_ms, self.max_delay_ms)
