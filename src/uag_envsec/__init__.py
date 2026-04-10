"""uag_envsec

Standalone helpers for encrypting/decrypting environment files and values.

This package is intentionally small and can be reused outside uagent.
"""

from .secret_core import (
    DEFAULT_KEY_FILENAME,
    DEFAULT_SEC_SUFFIX,
    decrypt_text,
    encrypt_text,
    ensure_key_file,
    load_key,
    save_key,
)

__all__ = [
    "DEFAULT_KEY_FILENAME",
    "DEFAULT_SEC_SUFFIX",
    "decrypt_text",
    "encrypt_text",
    "ensure_key_file",
    "load_key",
    "save_key",
]
