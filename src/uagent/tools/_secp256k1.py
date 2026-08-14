"""Pure-Python secp256k1 operations for Nostr (BIP340 Schnorr + ECDH).

Dependencies: ecdsa (pure Python, already installed)
"""

from __future__ import annotations

import hashlib
import os

from .._pip_auto import install_with_status

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

SECP256k1 = SigningKey = Point = None
curve = G = order = half_order = None
_ecdsa_initialized = False


def _ensure_ecdsa() -> bool:
    global SECP256k1, SigningKey, Point, curve, G, order, half_order
    global _ecdsa_initialized
    if _ecdsa_initialized:
        return SECP256k1 is not None
    _ecdsa_initialized = True
    if not install_with_status("ecdsa"):
        return False
    try:
        from ecdsa import SECP256k1 as _SECP256k1, SigningKey as _SigningKey
        from ecdsa.ellipticcurve import Point as _Point

        SECP256k1, SigningKey, Point = _SECP256k1, _SigningKey, _Point
        curve = SECP256k1.curve
        G = SECP256k1.generator
        order = SECP256k1.order
        half_order = order // 2
    except Exception:
        SECP256k1 = SigningKey = Point = None
    return SECP256k1 is not None


def _tagged_hash(tag: str, data: bytes) -> bytes:
    """Compute BIP340 tagged hash: SHA256(SHA256(tag) || SHA256(tag) || data)"""
    tag_hash = hashlib.sha256(tag.encode()).digest()
    return hashlib.sha256(tag_hash + tag_hash + data).digest()


def _int_from_bytes(b: bytes) -> int:
    return int.from_bytes(b, "big")


def _bytes_from_int(i: int, length: int = 32) -> bytes:
    return i.to_bytes(length, "big")


def _xonly_point(pub_bytes: bytes) -> bytes:
    """Convert 64-byte uncompressed public key to 32-byte x-only."""
    # Uncompressed pubkey from ecdsa is 64 bytes: x || y
    return pub_bytes[:32]


def generate_private_key() -> bytes:
    """Generate a random 32-byte secp256k1 private key."""
    return os.urandom(32)


def private_to_public(priv_bytes: bytes) -> bytes:
    if not _ensure_ecdsa():
        raise RuntimeError(
            _(
                "secp256k1.ecdsa_missing",
                default="ecdsa is not installed or could not be imported",
            )
        )
    """Derive 32-byte x-only public key from 32-byte private key."""
    sk = SigningKey.from_string(priv_bytes, curve=SECP256k1)
    vk = sk.get_verifying_key()
    return vk.to_string()[:32]  # x-only


def schnorr_sign(priv_bytes: bytes, msg: bytes) -> bytes:
    if not _ensure_ecdsa():
        raise RuntimeError(
            _(
                "secp256k1.ecdsa_missing",
                default="ecdsa is not installed or could not be imported",
            )
        )
    """Create a BIP340 Schnorr signature.

    Args:
        priv_bytes: 32-byte private key
        msg: 32-byte message hash (event id)

    Returns:
        64-byte signature (r || s)
    """
    if len(msg) != 32:
        msg = hashlib.sha256(msg).digest()

    d = _int_from_bytes(priv_bytes)
    if d >= order or d == 0:
        raise ValueError(_("secp256k1.invalid_privkey", default="Invalid private key"))

    # Public key point
    sk = SigningKey.from_string(priv_bytes, curve=SECP256k1)
    vk = sk.get_verifying_key()
    pub_point = vk.pubkey.point

    # BIP340: if P.y is odd, negate d
    if pub_point.y() % 2 != 0:
        d = order - d
        Px = _bytes_from_int(pub_point.x())  # x coordinate unchanged
    else:
        Px = _bytes_from_int(pub_point.x())

    # Generate random k
    k = int.from_bytes(os.urandom(32), "big") % order
    if k == 0:
        k = 1

    # Compute R = k * G
    R_point = G * k
    # BIP340: if R.y is odd, negate k
    if R_point.y() % 2 != 0:
        k = order - k
        R_point = G * k
    Rx = _bytes_from_int(R_point.x())

    # Challenge: e = tagged_hash("BIP0340/challenge", R.x || P.x || msg) mod n
    challenge_data = Rx + Px + msg
    e = _int_from_bytes(_tagged_hash("BIP0340/challenge", challenge_data)) % order

    # s = k + e * d mod n
    s = (k + e * d) % order

    return Rx + _bytes_from_int(s)


def schnorr_verify(pub_xonly: bytes, msg: bytes, sig: bytes) -> bool:
    if not _ensure_ecdsa():
        raise RuntimeError(
            _(
                "secp256k1.ecdsa_missing",
                default="ecdsa is not installed or could not be imported",
            )
        )
    """Verify a BIP340 Schnorr signature.

    Args:
        pub_xonly: 32-byte x-only public key
        msg: 32-byte message hash
        sig: 64-byte signature (r || s)

    Returns:
        True if valid
    """
    if len(pub_xonly) != 32 or len(sig) != 64:
        return False
    if len(msg) != 32:
        msg = hashlib.sha256(msg).digest()

    r = _int_from_bytes(sig[:32])
    s_val = _int_from_bytes(sig[32:])

    # Basic checks
    if r >= order or s_val >= order:
        return False

    p_val = curve.p()

    # --- Helper: lift x to even-y point ---
    def _lift_x(x: int) -> Point | None:
        x3 = (x * x % p_val) * x % p_val
        y_sq = (x3 + 7) % p_val
        y = pow(y_sq, (p_val + 1) // 4, p_val)
        if (y * y) % p_val != y_sq:
            return None
        if y % 2 != 0:
            y = p_val - y
        return PointJacobi(curve, x, y, 1)

    from ecdsa.ellipticcurve import PointJacobi

    # Lift R
    R_point = _lift_x(r)
    if R_point is None:
        return False

    # Lift P
    P_point = _lift_x(_int_from_bytes(pub_xonly))
    if P_point is None:
        return False

    # e = tagged_hash("BIP0340/challenge", R.x || P.x || msg) mod n
    challenge_data = sig[:32] + pub_xonly + msg
    e = _int_from_bytes(_tagged_hash("BIP0340/challenge", challenge_data)) % order

    # Verify: s * G == R + e * P
    # Use PointJacobi for all operations to avoid type mismatch
    try:
        G_jacobi = PointJacobi(curve, G.x(), G.y(), 1)
        left = G_jacobi * s_val
        right = R_point + (P_point * e)
        return left.x() == right.x() and left.y() == right.y()
    except Exception:
        return False


def ecdh_shared_key(priv_bytes: bytes, pub_xonly: bytes) -> bytes:
    if not _ensure_ecdsa():
        raise RuntimeError(
            _(
                "secp256k1.ecdsa_missing",
                default="ecdsa is not installed or could not be imported",
            )
        )
    """Compute ECDH shared key (SHA-256) for kind-1059 encryption.

    Args:
        priv_bytes: 32-byte private key
        pub_xonly: 32-byte x-only public key of the other party

    Returns:
        32-byte SHA-256 hashed shared secret
    """
    p_val = curve.p()
    px = _int_from_bytes(pub_xonly)
    x3 = (px * px % p_val) * px % p_val
    y_sq = (x3 + 7) % p_val
    y = pow(y_sq, (p_val + 1) // 4, p_val)
    if (y * y) % p_val != y_sq:
        raise ValueError(
            _("secp256k1.invalid_pubkey", default="Invalid public key point")
        )
    # Any y works for shared secret derivation
    peer_point = Point(curve, px, y)

    shared_point = peer_point * _int_from_bytes(priv_bytes)
    shared_x = _bytes_from_int(shared_point.x())
    return hashlib.sha256(shared_x).digest()
