"""Shared helper for encrypting dotenv documents with uag-envsec."""

from __future__ import annotations

from uag_envsec import encrypt_env_values, encrypt_text


def encrypt_env_document(plaintext: str) -> str:
    """Encrypt a complete dotenv document for storage as ``.env.sec``.

    The values-only format is used whenever the document can be
    represented that way, so variable names stay visible and single
    lines can be edited or deleted by hand. Documents the values-only
    format rejects (for example a value ending in an unescaped
    backslash) fall back to whole-file encryption. ``decrypt_text``
    reads both formats, and the result always ends with a newline.
    """
    try:
        encrypted = encrypt_env_values(plaintext)
    except ValueError:
        encrypted = encrypt_text(plaintext)
    if not encrypted.endswith("\n"):
        encrypted += "\n"
    return encrypted
