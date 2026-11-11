"""QR-assisted local public-key pairing for experimental Nostr remote CLI.

QR content is always untrusted until parsed as a strictly validated NIP-19
public key. A decoded QR never grants access without local confirmation.
"""

from __future__ import annotations

import json

_BECH32_ALPHABET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


def decode_pairing_pubkey(value: str) -> str:
    """Accept a bare x-only hex key, npub, or nostr:npub URI, never a secret."""
    from .nostr_remote_pairing import _normalize_pubkey
    from .tools.nostr_transport import _bech32_hrp_expand, _bech32_polymod, _convertbits

    if not isinstance(value, str) or len(value) > 128:
        raise ValueError("expected a Nostr public key")
    key = value.strip()
    if key.lower().startswith("nostr:"):
        key = key[6:]
    if len(key) == 64:
        return _normalize_pubkey(key)
    if key != key.lower() and key != key.upper():
        raise ValueError("mixed-case NIP-19 public key")
    key = key.lower()
    if not key.startswith("npub1") or len(key) != 63:
        raise ValueError("QR must contain a public npub, not a secret or URL")
    try:
        digits = [_BECH32_ALPHABET.index(char) for char in key[5:]]
    except ValueError as exc:
        raise ValueError("invalid NIP-19 public key characters") from exc
    if _bech32_polymod(_bech32_hrp_expand("npub") + digits) != 1:
        raise ValueError("invalid NIP-19 public key checksum")
    decoded = _convertbits(digits[:-6], 5, 8, False)
    if decoded is None or len(decoded) != 32:
        raise ValueError("invalid NIP-19 public key length")
    return _normalize_pubkey(bytes(decoded).hex())


def show_public_key_qr(npub: str) -> bool:
    """Print an optional terminal QR containing only the public NIP-19 URI."""
    try:
        import qrcode
        from qrcode.constants import ERROR_CORRECT_L
    except ImportError:
        return False

    qr = qrcode.QRCode(border=2, error_correction=ERROR_CORRECT_L)
    qr.add_data(f"nostr:{npub}")
    qr.make(fit=True)
    for pixels in qr.get_matrix():
        print("".join("██" if pixel else "  " for pixel in pixels))
    return True


def scan_mobile_pubkey() -> str | None:
    """Reuse the local QR reader camera/image window; never trust its raw text."""
    from .tools.qr_reader_tool import run_tool

    result = json.loads(run_tool({}))
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise RuntimeError("QR reader could not start or read a public key")
    data = result.get("data")
    if not isinstance(data, dict) or data.get("cancelled") is True:
        return None
    return decode_pairing_pubkey(data.get("text"))


def confirm_local_pairing(pubkey: str) -> bool:
    """Require explicit confirmation on the PC before granting full CLI access."""
    from .tools.nostr_transport import encode_npub

    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        try:
            return messagebox.askyesno(
                "UAG Nostr remote pairing",
                "Authorize this device for full control of this UAG CLI session?\n\n"
                f"Phone public key:\n{encode_npub(pubkey)}\n\n"
                "Only approve a key displayed by a phone you control. "
                "Existing Sandbox and confirmation policies still apply.\n\n"
                "The Nostr remote feature is experimental.",
                parent=root,
            )
        finally:
            root.destroy()
    except Exception:
        # Headless environments must not silently authorize a scanned key.
        return False
