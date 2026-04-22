from __future__ import annotations

"""Standalone helpers for encrypting/decrypting env values and files."""

import base64
import os
from pathlib import Path
from typing import Final

from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

MASTER_KEY_BYTES: Final[int] = 32
NONCE_BYTES: Final[int] = 12
DEFAULT_KEY_FILENAME: Final[str] = "uag_envsec_key"
DEFAULT_SEC_SUFFIX: Final[str] = ".sec"


def _home_dir() -> Path:
    return Path.home()


def default_key_path() -> Path:
    return _home_dir() / ".uag" / DEFAULT_KEY_FILENAME


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def save_key(path: str | Path | None = None, *, overwrite: bool = False) -> str:
    p = Path(path) if path is not None else default_key_path()
    ensure_parent(p)
    if p.exists() and not overwrite:
        return str(p)
    key = os.urandom(MASTER_KEY_BYTES)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    fd = os.open(str(p), flags, 0o600)
    try:
        os.write(fd, key)
    finally:
        os.close(fd)
    return str(p)


def load_key(path: str | Path | None = None) -> bytes:
    p = Path(path) if path is not None else default_key_path()
    key = p.read_bytes()
    if len(key) != MASTER_KEY_BYTES:
        raise ValueError(f"Invalid key length: {len(key)}")
    return key


def ensure_key_file(path: str | Path | None = None, *, overwrite: bool = False) -> str:
    p = Path(path) if path is not None else default_key_path()
    if p.exists() and not overwrite:
        return str(p)
    return save_key(p, overwrite=overwrite)


def _derive_subkey(master_key: bytes, *, purpose: str, length: int) -> bytes:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=None,
        info=("uag_envsec." + purpose).encode("utf-8"),
    )
    return hkdf.derive(master_key)


def encrypt_text(plaintext: str, *, key_path: str | Path | None = None) -> str:
    master = load_key(key_path)
    enc_key = _derive_subkey(master, purpose="enc", length=32)
    aesgcm = AESGCM(enc_key)
    nonce = os.urandom(NONCE_BYTES)
    ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ct).decode("ascii")


def decrypt_text(enc_b64: str, *, key_path: str | Path | None = None) -> str:
    master = load_key(key_path)
    enc_key = _derive_subkey(master, purpose="enc", length=32)
    aesgcm = AESGCM(enc_key)
    blob = base64.b64decode(enc_b64)
    if len(blob) < NONCE_BYTES + 16:
        raise ValueError("Invalid ciphertext")
    nonce = blob[:NONCE_BYTES]
    ct = blob[NONCE_BYTES:]
    pt = aesgcm.decrypt(nonce, ct, None)
    return pt.decode("utf-8")


def sign_text(message: str, *, key_path: str | Path | None = None) -> str:
    master = load_key(key_path)
    sign_key = _derive_subkey(master, purpose="sign", length=32)
    h = hmac.HMAC(sign_key, hashes.SHA256())
    h.update(message.encode("utf-8"))
    return base64.b64encode(h.finalize()).decode("ascii")


def verify_text(
    message: str, sig_b64: str, *, key_path: str | Path | None = None
) -> bool:
    master = load_key(key_path)
    sign_key = _derive_subkey(master, purpose="sign", length=32)
    sig = base64.b64decode(sig_b64)
    h = hmac.HMAC(sign_key, hashes.SHA256())
    h.update(message.encode("utf-8"))
    try:
        h.verify(sig)
        return True
    except Exception:
        return False
