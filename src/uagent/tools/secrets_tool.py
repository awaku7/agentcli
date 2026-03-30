from __future__ import annotations

# src/uagent/tools/secrets_tool.py

import base64
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from ..utils.paths import get_state_dir
from .arg_util import get_bool, get_list, get_path, get_str
from .context import get_callbacks
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

MASTER_KEY_BYTES = 32  # 256-bit
NONCE_BYTES = 12  # AES-GCM recommended


def _key_path() -> Path:
    return get_state_dir() / "uagent_secret_key"


def _ensure_parent(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)


def _json_ok(**obj: Any) -> str:
    out: Dict[str, Any] = {"ok": True}
    out.update(obj)
    return json.dumps(out, ensure_ascii=False)


def _json_err(message: str, **extra: Any) -> str:
    out: Dict[str, Any] = {"ok": False, "error": message}
    out.update(extra)
    return json.dumps(out, ensure_ascii=False)


def _read_master_key() -> bytes:
    p = _key_path()
    if not p.exists():
        raise FileNotFoundError(str(p))
    key = p.read_bytes()
    if len(key) != MASTER_KEY_BYTES:
        raise ValueError(f"Invalid key length: {len(key)}")
    return key


def _derive_subkey(master_key: bytes, *, purpose: str, length: int) -> bytes:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=None,
        info=("uagent.secrets." + purpose).encode("utf-8"),
    )
    return hkdf.derive(master_key)


def init_key(*, overwrite: bool = False) -> str:
    p = _key_path()
    _ensure_parent(p)
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


def encrypt_to_b64(plaintext: str) -> str:
    master = _read_master_key()
    enc_key = _derive_subkey(master, purpose="enc", length=32)
    aesgcm = AESGCM(enc_key)
    nonce = os.urandom(NONCE_BYTES)
    ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ct).decode("ascii")


def decrypt_from_b64(enc_b64: str) -> str:
    master = _read_master_key()
    enc_key = _derive_subkey(master, purpose="enc", length=32)
    aesgcm = AESGCM(enc_key)
    blob = base64.b64decode(enc_b64)
    if len(blob) < NONCE_BYTES + 16:
        raise ValueError("Invalid ciphertext")
    nonce = blob[:NONCE_BYTES]
    ct = blob[NONCE_BYTES:]
    pt = aesgcm.decrypt(nonce, ct, None)
    return pt.decode("utf-8")


def sign_to_b64(message: str) -> str:
    master = _read_master_key()
    sign_key = _derive_subkey(master, purpose="sign", length=32)
    h = hmac.HMAC(sign_key, hashes.SHA256())
    h.update(message.encode("utf-8"))
    return base64.b64encode(h.finalize()).decode("ascii")


def verify_b64(message: str, sig_b64: str) -> bool:
    master = _read_master_key()
    sign_key = _derive_subkey(master, purpose="sign", length=32)
    sig = base64.b64decode(sig_b64)
    h = hmac.HMAC(sign_key, hashes.SHA256())
    h.update(message.encode("utf-8"))
    try:
        h.verify(sig)
        return True
    except Exception:
        return False


def _get_parent_and_key(obj: Any, dotted_path: str) -> Tuple[Any, str]:
    cur = obj
    parts = [p for p in dotted_path.split(".") if p]
    if not parts:
        raise ValueError("Empty path")
    for p in parts[:-1]:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            raise KeyError(dotted_path)
    return cur, parts[-1]


def json_encrypt_fields(*, json_path: str, fields: List[str]) -> None:
    p = Path(json_path)
    data = json.loads(p.read_text(encoding="utf-8"))
    for f in fields:
        parent, last = _get_parent_and_key(data, f)
        if not (isinstance(parent, dict) and last in parent):
            raise KeyError(f)
        v = parent[last]
        if v is None:
            continue
        if not isinstance(v, str):
            raise TypeError(f)
        parent[last] = {"enc_v1": encrypt_to_b64(v)}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def json_decrypt_fields(*, json_path: str, fields: List[str]) -> None:
    p = Path(json_path)
    data = json.loads(p.read_text(encoding="utf-8"))
    for f in fields:
        parent, last = _get_parent_and_key(data, f)
        if not (isinstance(parent, dict) and last in parent):
            raise KeyError(f)
        v = parent[last]
        if v is None:
            continue
        if isinstance(v, dict) and isinstance(v.get("enc_v1"), str):
            parent[last] = decrypt_from_b64(v["enc_v1"])
        else:
            raise TypeError(f)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "secrets",
        "description": _(
            "tool.description",
            default="Manage local secrets using a shared key file under the uagent state dir.",
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "Manage local secrets. Return JSON only. "
                "Key file is stored under the uagent state dir (default: ~/.uag)."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": _(
                        "param.action.description",
                        default="Action: init/encrypt/decrypt/sign/verify/json_encrypt/json_decrypt",
                    ),
                },
                "overwrite": {
                    "type": "boolean",
                    "description": _(
                        "param.overwrite.description",
                        default="(init) Overwrite existing key file.",
                    ),
                    "default": False,
                },
                "text": {
                    "type": "string",
                    "description": _(
                        "param.text.description",
                        default="Plaintext input (encrypt/sign/verify).",
                    ),
                },
                "enc_b64": {
                    "type": "string",
                    "description": _(
                        "param.enc_b64.description",
                        default="Ciphertext input (decrypt).",
                    ),
                },
                "sig_b64": {
                    "type": "string",
                    "description": _(
                        "param.sig_b64.description",
                        default="Signature input (verify).",
                    ),
                },
                "json_path": {
                    "type": "string",
                    "description": _(
                        "param.json_path.description",
                        default="Path to JSON file to operate on.",
                    ),
                },
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _(
                        "param.fields.description",
                        default="List of dotted paths to fields.",
                    ),
                },
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()
    if cb.set_status:
        cb.set_status(True, "tool:secrets")
    try:
        action = get_str(args, "action", "").lower()

        if action == "init":
            overwrite = get_bool(args, "overwrite", False)
            p = init_key(overwrite=overwrite)
            return _json_ok(key_path=p)

        if action == "encrypt":
            text = get_str(args, "text", "")
            if not text:
                return _json_err(_("err.missing_text", default="Missing 'text'."))
            return _json_ok(enc_b64=encrypt_to_b64(text))

        if action == "decrypt":
            enc_b64 = get_str(args, "enc_b64", "")
            if not enc_b64:
                return _json_err(_("err.missing_enc_b64", default="Missing 'enc_b64'."))
            return _json_ok(text=decrypt_from_b64(enc_b64))

        if action == "sign":
            text = get_str(args, "text", "")
            if not text:
                return _json_err(_("err.missing_text", default="Missing 'text'."))
            return _json_ok(sig_b64=sign_to_b64(text))

        if action == "verify":
            text = get_str(args, "text", "")
            sig_b64 = get_str(args, "sig_b64", "")
            if not text or not sig_b64:
                return _json_err(
                    _("err.missing_text_or_sig", default="Missing 'text' or 'sig_b64'.")
                )
            return _json_ok(ok=verify_b64(text, sig_b64))

        if action == "json_encrypt":
            json_path = get_path(args, "json_path", "")
            fields = [str(x) for x in get_list(args, "fields")]
            if not json_path or not fields:
                return _json_err(
                    _(
                        "err.missing_json_path_or_fields",
                        default="Missing 'json_path' or 'fields'.",
                    )
                )
            json_encrypt_fields(json_path=json_path, fields=fields)
            return _json_ok(written=json_path)

        if action == "json_decrypt":
            json_path = get_path(args, "json_path", "")
            fields = [str(x) for x in get_list(args, "fields")]
            if not json_path or not fields:
                return _json_err(
                    _(
                        "err.missing_json_path_or_fields",
                        default="Missing 'json_path' or 'fields'.",
                    )
                )
            json_decrypt_fields(json_path=json_path, fields=fields)
            return _json_ok(written=json_path)

        return _json_err(_("err.unknown_action", default="Unknown action."), action=action)

    except FileNotFoundError:
        return _json_err(
            _(
                "err.key_not_found",
                default="Secret key file not found. Run action=init first.",
            ),
            key_path=str(_key_path()),
        )
    except Exception as e:
        return _json_err(_("err.exception", default="Exception"), exception=type(e).__name__, detail=str(e))
    finally:
        if cb.set_status:
            cb.set_status(False, "tool:secrets")
