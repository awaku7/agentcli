"""ucp_ap2_tool

AP2 (Agent Payments Protocol) — autonomous payment management.

Enables the agent to create, list, and execute AP2 payment mandates
for autonomous checkout completion without user interaction.

Mandates are persisted to ~/.uag/ucp_mandates.json.
Optional Fernet encryption is applied when UCP_MANDATES_KEY is set.
"""

from __future__ import annotations

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

import json
import os
import time
from pathlib import Path
from typing import Any

from .ucp_shared import (
    discover_business,
    ucp_request,
    ap2_create_payment_mandate,
    ap2_execute_token,
    ap2_verify_payment_token,
    UCPError,
)

BUSY_LABEL = True
STATUS_LABEL = "tool:ucp_ap2"

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "web",
    "tool_level": 1,
    "type": "function",
    "function": {
        "name": "ucp_ap2",
        "description": _(
            "tool.description",
            default=(
                "AP2 (Agent Payments Protocol) — autonomous payment management.\n\n"
                "mode='mandate_create' — Create a new open payment mandate. "
                "This authorizes the agent to make autonomous purchases up to "
                "a specified limit. The user must approve this via continue_url.\n\n"
                "mode='mandate_list' — List all active payment mandates.\n\n"
                "mode='execute' — Execute a payment token using an existing mandate "
                "for a specific checkout. Returns a signed AP2 token that can be "
                "passed to ucp_checkout mode='complete' as ap2_token.\n\n"
                "mode='verify' — Verify an AP2 payment token and return its details."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["mandate_create", "mandate_list", "execute", "verify"],
                    "description": _(
                        "param.mode.description",
                        default="Operation mode.",
                    ),
                },
                "business_url": {
                    "type": "string",
                    "description": _(
                        "param.business_url.description",
                        default="Base URL of the business (required for mandate_create and execute).",
                    ),
                },
                "merchant_name": {
                    "type": "string",
                    "description": _(
                        "param.merchant_name.description",
                        default="Merchant name for the mandate (mode='mandate_create').",
                    ),
                },
                "max_amount": {
                    "type": "integer",
                    "description": _(
                        "param.max_amount.description",
                        default="Maximum payment amount in minor units (cents). "
                                "e.g. 50000 = $500.00 (mode='mandate_create').",
                    ),
                },
                "currency": {
                    "type": "string",
                    "description": _(
                        "param.currency.description",
                        default="ISO 4217 currency code (default 'USD').",
                    ),
                },
                "mandate_id": {
                    "type": "string",
                    "description": _(
                        "param.mandate_id.description",
                        default="Mandate ID from a previous mandate_create (for execute).",
                    ),
                },
                "checkout_id": {
                    "type": "string",
                    "description": _(
                        "param.checkout_id.description",
                        default="Checkout session ID to execute payment for (mode='execute').",
                    ),
                },
                "amount": {
                    "type": "integer",
                    "description": _(
                        "param.amount.description",
                        default="Payment amount in minor units (mode='execute').",
                    ),
                },
                "ap2_token": {
                    "type": "string",
                    "description": _(
                        "param.ap2_token.description",
                        default="Signed AP2 token JWT to verify (mode='verify').",
                    ),
                },
            },
            "required": ["mode"],
            "additionalProperties": False,
        },
    },
}


# ---------------------------------------------------------------------------
# File persistence
# ---------------------------------------------------------------------------

_MANDATES_PATH: Path | None = None
_ENCRYPTION_KEY: str | None = None


def _get_mandates_path() -> Path:
    """Get the full path to the mandates file (~/.uag/ucp_mandates.json)."""
    global _MANDATES_PATH
    if _MANDATES_PATH is not None:
        return _MANDATES_PATH

    base = Path.home() / ".uag"
    _MANDATES_PATH = base / "ucp_mandates.json"
    return _MANDATES_PATH


def _get_encryption_key() -> str | None:
    """Get the optional Fernet encryption key from environment."""
    global _ENCRYPTION_KEY
    if _ENCRYPTION_KEY is not None:
        return _ENCRYPTION_KEY or None

    key = os.getenv("UCP_MANDATES_KEY", "").strip()
    _ENCRYPTION_KEY = key or None
    return _ENCRYPTION_KEY


def _fernet_encrypt(data: bytes, key: str) -> bytes:
    """Encrypt data using Fernet (symmetric)."""
    import base64
    from cryptography.fernet import Fernet
    try:
        f = Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        salt = b"ucp_mandates_v1"
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
        raw_key = base64.urlsafe_b64encode(kdf.derive(key.encode() if isinstance(key, str) else key))
        f = Fernet(raw_key)
    return f.encrypt(data)


def _fernet_decrypt(data: bytes, key: str) -> bytes:
    """Decrypt Fernet-encrypted data."""
    import base64
    from cryptography.fernet import Fernet, InvalidToken
    try:
        f = Fernet(key.encode() if isinstance(key, str) else key)
        return f.decrypt(data)
    except (InvalidToken, Exception):
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        salt = b"ucp_mandates_v1"
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
        raw_key = base64.urlsafe_b64encode(kdf.derive(key.encode() if isinstance(key, str) else key))
        f = Fernet(raw_key)
        return f.decrypt(data)


def _load_mandates() -> dict[str, dict[str, Any]]:
    """Load mandates from ~/.uag/ucp_mandates.json (with optional decryption)."""
    path = _get_mandates_path()
    if not path.exists():
        return {}

    try:
        raw = path.read_bytes()
        key = _get_encryption_key()
        if key:
            raw = _fernet_decrypt(raw, key)
        data = json.loads(raw.decode("utf-8"))
        if isinstance(data, dict):
            return data
        return {}
    except Exception:
        return {}


def _save_mandates(mandates: dict[str, dict[str, Any]]) -> None:
    """Save mandates to ~/.uag/ucp_mandates.json (with optional encryption)."""
    path = _get_mandates_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    raw = json.dumps(mandates, ensure_ascii=False, indent=2).encode("utf-8")
    key = _get_encryption_key()
    if key:
        raw = _fernet_encrypt(raw, key)

    tmp = path.with_suffix(".json.tmp")
    tmp.write_bytes(raw)
    tmp.replace(path)


def _delete_expired_mandates(mandates: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Remove expired mandates."""
    now = time.time()
    return {k: v for k, v in mandates.items() if v.get("expires_at", now) > now}


# ---------------------------------------------------------------------------
# Tool entry point
# ---------------------------------------------------------------------------


def run_tool(args: dict[str, Any]) -> str:
    mode = str(args.get("mode") or "mandate_list").strip()
    business_url = str(args.get("business_url") or "").strip()
    merchant_name = str(args.get("merchant_name") or "").strip()
    max_amount = args.get("max_amount")
    currency = str(args.get("currency") or "USD").strip()
    mandate_id = str(args.get("mandate_id") or "").strip()
    checkout_id = str(args.get("checkout_id") or "").strip()
    amount = args.get("amount")
    ap2_token = str(args.get("ap2_token") or "").strip()

    # Load mandates from file, purge expired
    mandates = _load_mandates()
    cleaned = _delete_expired_mandates(mandates)
    if len(cleaned) != len(mandates):
        _save_mandates(cleaned)
        mandates = cleaned

    if mode == "mandate_list":
        result_list = []
        for mid, m in mandates.items():
            result_list.append({
                "id": mid,
                "status": m.get("status"),
                "merchant": m.get("merchant", {}).get("name"),
                "max_amount": m.get("max_amount"),
                "currency": m.get("currency"),
                "created_at": m.get("created_at"),
                "expires_at": m.get("expires_at"),
            })
        return json.dumps({
            "ok": True,
            "mode": mode,
            "mandates": result_list,
        }, ensure_ascii=False, indent=2)

    if mode == "mandate_create":
        if not merchant_name:
            return json.dumps({
                "ok": False,
                "error": {"code": "invalid_argument", "message": "merchant_name is required for mandate_create."},
            }, ensure_ascii=False)
        if max_amount is None:
            return json.dumps({
                "ok": False,
                "error": {"code": "invalid_argument", "message": "max_amount is required for mandate_create."},
            }, ensure_ascii=False)

        mandate = ap2_create_payment_mandate(
            merchant_name=merchant_name,
            merchant_url=business_url or "https://unknown.merchant",
            max_amount=int(max_amount),
            currency=currency,
        )
        mandate["created_at"] = int(time.time())
        mandates[mandate["id"]] = mandate
        _save_mandates(mandates)

        result = {
            "ok": True,
            "mode": mode,
            "mandate": {
                "id": mandate["id"],
                "status": mandate["status"],
                "type": mandate["type"],
                "vct": mandate["vct"],
                "merchant": mandate["merchant"],
                "max_amount": mandate["max_amount"],
                "currency": mandate["currency"],
                "expires_at": mandate["expires_at"],
                "signed_jwt": mandate["signed_jwt"],
            },
            "user_action_required": True,
            "authorization_url": f"{business_url.rstrip('/')}/ap2/authorize/{mandate['id']}",
            "user_action_message": (
                "Open the authorization_url in your browser to approve "
                "the payment mandate. After approval, use ucp_ap2 with "
                "mode='execute' to use this mandate for a checkout."
            ),
        }
        return json.dumps(result, ensure_ascii=False, indent=2)

    if mode == "execute":
        if not mandate_id or not checkout_id or amount is None:
            return json.dumps({
                "ok": False,
                "error": {"code": "invalid_argument",
                          "message": "mandate_id, checkout_id, and amount are required for execute."},
            }, ensure_ascii=False)

        mandate = mandates.get(mandate_id)
        if not mandate:
            return json.dumps({
                "ok": False,
                "error": {"code": "mandate_not_found", "message": f"Mandate {mandate_id} not found."},
            }, ensure_ascii=False)

        if mandate.get("status") != "active":
            return json.dumps({
                "ok": False,
                "error": {"code": "mandate_not_active",
                          "message": f"Mandate {mandate_id} status is '{mandate.get('status')}', expected 'active'."},
            }, ensure_ascii=False)

        signed_jwt = mandate.get("signed_jwt", "")
        if not signed_jwt:
            return json.dumps({
                "ok": False,
                "error": {"code": "mandate_no_jwt", "message": "Mandate has no signed JWT."},
            }, ensure_ascii=False)

        token_result = ap2_execute_token(
            mandate_signed_jwt=signed_jwt,
            checkout_id=checkout_id,
            amount=int(amount),
            currency=currency,
        )

        if token_result.get("status") == "error":
            return json.dumps({
                "ok": False,
                "error": {"code": "token_execution_failed", "message": token_result.get("message")},
            }, ensure_ascii=False)

        result = {
            "ok": True,
            "mode": mode,
            "mandate_id": mandate_id,
            "checkout_id": checkout_id,
            "amount": amount,
            "currency": currency,
            "token": {
                "token_id": token_result.get("token_id"),
                "signed_token": token_result.get("signed_token"),
                "status": token_result.get("status"),
                "expires_at": token_result.get("expires_at"),
            },
            "usage_tip": "Pass the signed_token as ap2_token to ucp_checkout mode='complete'.",
        }
        return json.dumps(result, ensure_ascii=False, indent=2)

    if mode == "verify":
        if not ap2_token:
            return json.dumps({
                "ok": False,
                "error": {"code": "invalid_argument", "message": "ap2_token is required for verify."},
            }, ensure_ascii=False)

        payload = ap2_verify_payment_token(ap2_token)
        if not payload:
            return json.dumps({
                "ok": False,
                "error": {"code": "invalid_token", "message": "AP2 token verification failed."},
            }, ensure_ascii=False)

        return json.dumps({
            "ok": True,
            "mode": mode,
            "payload": {
                "vct": payload.get("vct"),
                "token_id": payload.get("token_id"),
                "checkout_id": payload.get("checkout_id"),
                "mandate_id": payload.get("mandate_id"),
                "amount": payload.get("amount"),
                "currency": payload.get("currency"),
                "iat": payload.get("iat"),
                "exp": payload.get("exp"),
            },
        }, ensure_ascii=False, indent=2)

    return json.dumps({
        "ok": False,
        "error": {"code": "invalid_mode", "message": f"Unknown mode: {mode}"},
    }, ensure_ascii=False)
