from __future__ import annotations

"""Standalone helpers for encrypting/decrypting env values and files."""

import base64
import os
import sys
from pathlib import Path
from typing import Final

from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from uagent.i18n import _

MASTER_KEY_BYTES: Final[int] = 32
NONCE_BYTES: Final[int] = 12
DEFAULT_KEY_FILENAME: Final[str] = "uag_envsec_key"
DEFAULT_SEC_SUFFIX: Final[str] = ".sec"
KEYRING_SERVICE: Final[str] = "uag-envsec"
KEYRING_USERNAME: Final[str] = "master-key"


def _home_dir() -> Path:
    return Path.home()


def default_key_path() -> Path:
    return _home_dir() / ".uag" / DEFAULT_KEY_FILENAME


def _keyring_module():
    try:
        import keyring
    except ImportError:
        # keyring is optional; install it only when envsec needs the OS
        # keyring backend. The shared policy honors UAGENT_AUTO_INSTALL.
        try:
            from uagent._pip_auto import install_with_status

            if not install_with_status("keyring", "keyring", version_spec=">=25.0.0"):
                return None
            import keyring
        except Exception:
            return None
    return keyring


def _key_backend() -> str:
    backend = os.getenv("UAGENT_ENVSEC_KEY_BACKEND", "auto") or "auto"
    backend = backend.strip().lower()
    if backend not in {"auto", "file", "keyring", "os"}:
        raise ValueError(
            "UAGENT_ENVSEC_KEY_BACKEND must be one of: auto, file, keyring"
        )
    return "keyring" if backend == "os" else backend


def _decode_key(raw: str) -> bytes:
    try:
        key = base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise ValueError("Invalid keyring key encoding") from exc
    if len(key) != MASTER_KEY_BYTES:
        raise ValueError(f"Invalid key length: {len(key)}")
    return key


def _load_keyring_key() -> bytes | None:
    keyring = _keyring_module()
    if keyring is None:
        return None
    try:
        raw = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
    except Exception:
        return None
    return _decode_key(raw) if raw else None


def _save_keyring_key(key: bytes) -> str:
    keyring = _keyring_module()
    if keyring is None:
        raise RuntimeError(
            "python-keyring is not installed; install it or use file backend"
        )
    keyring.set_password(
        KEYRING_SERVICE,
        KEYRING_USERNAME,
        base64.b64encode(key).decode("ascii"),
    )
    return f"keyring://{KEYRING_SERVICE}/{KEYRING_USERNAME}"


def _migrate_file_key_to_keyring(path: Path) -> bool:
    keyring = _keyring_module()
    if keyring is None:
        return False
    try:
        key = path.read_bytes()
        if len(key) != MASTER_KEY_BYTES:
            return False
        raw = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
        if raw:
            try:
                if _decode_key(raw) == key:
                    path.unlink()
                    return True
            except ValueError:
                # Replace an invalid keyring entry with the valid file key.
                pass
        # The file key is the key that protects the existing .env.sec data.
        # Make it authoritative during migration, then remove the duplicate.
        keyring.set_password(
            KEYRING_SERVICE,
            KEYRING_USERNAME,
            base64.b64encode(key).decode("ascii"),
        )
        stored = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
        if _decode_key(stored or "") != key:
            return False
        path.unlink()
        return True

    except Exception:
        # Auto migration must never prevent startup; the file remains usable.
        return False


def migrate_key_file_to_keyring() -> bool:
    """Migrate the default envsec key file when the automatic backend allows it.

    This is intentionally a no-op when the user selected the file backend or
    when no legacy key file exists.
    """
    if _key_backend() != "auto":
        return False
    path = default_key_path()
    if not path.exists():
        return False
    return _migrate_file_key_to_keyring(path)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def save_key(path: str | Path | None = None, *, overwrite: bool = False) -> str:
    backend = _key_backend() if path is None else "file"
    if backend == "keyring":
        existing = _load_keyring_key()
        if existing is not None and not overwrite:
            return f"keyring://{KEYRING_SERVICE}/{KEYRING_USERNAME}"
        return _save_keyring_key(os.urandom(MASTER_KEY_BYTES))

    p = Path(path) if path is not None else default_key_path()
    if path is None and backend == "auto" and not p.exists():
        if _load_keyring_key() is not None and not overwrite:
            return f"keyring://{KEYRING_SERVICE}/{KEYRING_USERNAME}"
        if _keyring_module() is not None:
            try:
                return _save_keyring_key(os.urandom(MASTER_KEY_BYTES))
            except Exception:
                pass
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
    if path is None:
        backend = _key_backend()
        p = default_key_path()
        # In automatic mode the OS keyring is authoritative whenever it has
        # a key, even if a legacy file is still present.
        if backend in {"keyring", "auto"}:
            key = _load_keyring_key()
            if key is not None:
                return key
            if backend == "keyring":
                raise FileNotFoundError(
                    f"No envsec key in OS keyring ({KEYRING_SERVICE}/{KEYRING_USERNAME})"
                )
    else:
        p = Path(path)
    key = p.read_bytes()
    if len(key) != MASTER_KEY_BYTES:
        raise ValueError(f"Invalid key length: {len(key)}")
    return key


def ensure_key_file(path: str | Path | None = None, *, overwrite: bool = False) -> str:
    if path is None and _key_backend() in {"auto", "keyring"}:
        if _key_backend() == "keyring":
            return save_key(None, overwrite=overwrite)
        p = default_key_path()
        if p.exists():
            if _migrate_file_key_to_keyring(p):
                print(
                    _(
                        "[INFO] Migrated envsec key to OS keyring; legacy key file removed."
                    ),
                    file=sys.stderr,
                )
                return f"keyring://{KEYRING_SERVICE}/{KEYRING_USERNAME}"
            if _load_keyring_key() is not None:
                return f"keyring://{KEYRING_SERVICE}/{KEYRING_USERNAME}"
            if not overwrite:
                return str(p)
        if not p.exists() and _load_keyring_key() is not None:
            return f"keyring://{KEYRING_SERVICE}/{KEYRING_USERNAME}"
        if not p.exists() and _keyring_module() is not None:
            return save_key(None, overwrite=overwrite)
    p = Path(path) if path is not None else default_key_path()
    if p.exists() and not overwrite:
        return str(p)
    return save_key(p, overwrite=overwrite)


def _derive_subkey(master_key: bytes, *, purpose: str, length: int) -> bytes:
    _ensure_cryptography()
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
