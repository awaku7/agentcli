"""Encrypted Portable Session Format v1; no filesystem extraction or authority."""

from __future__ import annotations

from collections import Counter
import json
import math
import os
import re
import struct
from pathlib import Path
from typing import Any

from ..utils.secret_mask import looks_like_secret_key

MAGIC = b"UAGSESSION"
# magic, format version, suite, Argon2 version, memory KiB, iterations, lanes,
# salt, wrap nonce, payload nonce. All bytes are authenticated as AAD.
HEADER = struct.Struct(">10sBBBIII16s12s12s")
KDF = (65536, 3, 4)
MAX_PAYLOAD = 16 * 1024 * 1024
MAX_PACKAGE = HEADER.size + 48 + MAX_PAYLOAD + 16
MAX_MESSAGES = 10000
MAX_TEXT = 1024 * 1024
MAX_REFS = 10000
_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
_REF = re.compile(
    r"(?:artifact://[0-9a-f]{32}|memory:[A-Za-z0-9_-]{1,128}@[0-9]{1,10})\Z"
)
_PRIVATE_KEY = re.compile(
    r"-----BEGIN [^-\r\n]*PRIVATE KEY-----.*?(?:-----END [^-\r\n]*PRIVATE KEY-----|\Z)",
    re.DOTALL,
)
# Conservative: remove the entire message, including quoted/multiline credential
# assignments. Arbitrary unlabelled secrets cannot be recognized semantically.
_CREDENTIAL = re.compile(
    r"(?i)api[ _-]?key|oauth|oidc|token|password|passwd|passphrase|"
    r"private[ _-]?key|secret|credential|authorization|cookie|bearer|"
    r"access[ _-]?key|client[ _-]?secret|\bsk-[\w-]+|\bgh[pousr]_[\w]+|"
    r"\beyJ[\w-]+\.[\w-]+\.[\w-]+|://[^\s/]+@"
)


class PortableSessionError(ValueError):
    """A package is invalid or cannot be authenticated."""


def _json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PortableSessionError("duplicate JSON field")
        result[key] = value
    return result


def _text(value: Any, maximum: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or len(value.encode("utf-8")) > maximum:
        raise PortableSessionError("invalid or oversized text")
    return value


def _keys(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise PortableSessionError("invalid portable schema")


def validate_payload(payload: Any) -> dict:
    """Reject unknown fields, active roles, paths and unbounded collections."""
    _keys(payload, ("format", "version", "session", "conversation", "references"))
    if (
        payload["format"] != "uag-session"
        or type(payload["version"]) is not int
        or payload["version"] != 1
    ):
        raise PortableSessionError("unsupported portable format")
    metadata = payload["session"]
    _keys(metadata, ("source_session_id", "created_at", "entry_point", "project_hint"))
    for value in metadata.values():
        _text(value, 256)
    if not _ID.fullmatch(metadata["source_session_id"]):
        raise PortableSessionError("invalid source session ID")
    messages = payload["conversation"]
    if not isinstance(messages, list) or len(messages) > MAX_MESSAGES:
        raise PortableSessionError("too many messages")
    for message in messages:
        _keys(message, ("role", "content"))
        if message["role"] not in ("user", "assistant"):
            raise PortableSessionError("noncanonical message role")
        _text(message["content"])
    refs = payload["references"]
    _keys(refs, ("memory", "artifacts"))
    for kind, prefix in (("memory", "memory:"), ("artifacts", "artifact://")):
        items = refs[kind]
        if not isinstance(items, list) or len(items) > MAX_REFS:
            raise PortableSessionError("too many references")
        for ref in items:
            if (
                not isinstance(ref, str)
                or not ref.startswith(prefix)
                or not _REF.fullmatch(ref)
            ):
                raise PortableSessionError(
                    "invalid reference (paths are not supported)"
                )
    if len(_json(payload)) > MAX_PAYLOAD:
        raise PortableSessionError("payload too large")
    return payload


def _is_high_entropy_secret(value: str) -> bool:
    """Avoid global replacement of short/common values that corrupt dialogue."""
    if len(value) < 16 or any(char.isspace() for char in value):
        return False
    counts = Counter(value)
    if len(counts) < 8:
        return False
    entropy = -sum(
        (count / len(value)) * math.log2(count / len(value))
        for count in counts.values()
    )
    return entropy >= 3.5


def _known_secrets(value: Any, found: set[str], depth: int = 0) -> None:
    if depth > 32:
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if (
                looks_like_secret_key(str(key))
                and isinstance(item, str)
                and _is_high_entropy_secret(item)
            ):
                found.add(item)
            _known_secrets(item, found, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _known_secrets(item, found, depth + 1)


def _clean(text: str, secrets: set[str]) -> str:
    for secret in sorted(secrets, key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    text = _PRIVATE_KEY.sub("[REDACTED PRIVATE KEY]", text)
    # Structured credential values can span lines; parse before line filtering.
    try:
        structured = json.loads(text)
        values: set[str] = set()
        _known_secrets(structured, values)
        for secret in sorted(values, key=len, reverse=True):
            text = text.replace(secret, "[REDACTED]")
            text = text.replace(json.dumps(secret)[1:-1], "[REDACTED]")
    except (ValueError, RecursionError):
        pass
    # Drop a whole credential-bearing message, including YAML/fenced/multiline
    # values whose continuation lines cannot safely be classified on their own.
    return "[REDACTED]" if _CREDENTIAL.search(text) else text


def snapshot(store, session_id: str) -> dict:
    """Project an allowlist, never copy provider/auth/tool state or read files."""
    metadata = store.get_session(session_id)
    messages = store.list_messages(session_id)
    secrets: set[str] = set()
    # PWD/OLDPWD are ordinary workspace paths, not credentials, despite the
    # generic secret-key matcher recognizing the substring "pwd".
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper() not in {"PWD", "OLDPWD"}
    }
    _known_secrets(environment, secrets)
    _known_secrets(messages, secrets)
    # A secret supplied to a tool may be echoed later in plain conversation.
    _known_secrets(store.list_tool_calls(session_id), secrets)
    conversation = []
    for message in messages:
        role = message.get("role")
        if role not in {"user", "assistant", "tool"}:
            continue
        content = message.get("content", "")
        if isinstance(content, list):
            content = "\n".join(
                part["text"]
                for part in content
                if isinstance(part, dict)
                and part.get("type") in {"text", "input_text", "output_text"}
                and isinstance(part.get("text"), str)
            )
        if not isinstance(content, str) or not content:
            continue
        if role == "tool":
            role, content = (
                "assistant",
                "[Historical tool result; not executable]\n" + content,
            )
        conversation.append({"role": role, "content": _clean(content, secrets)})
    previous = store.get_portable_metadata(session_id) or {}
    refs = previous.get("references", {"memory": [], "artifacts": []})
    memory = set(refs["memory"])
    artifacts = set(refs["artifacts"])
    for decision in store.list_context_decisions(session_id, limit=10000):
        ref = str(decision.get("reference") or "")
        if _REF.fullmatch(ref) and ref.startswith("memory:"):
            memory.add(ref)
    for result in store.list_tool_results(session_id, limit=10000):
        ref = str(result.get("artifact_ref") or "")
        if _REF.fullmatch(ref) and ref.startswith("artifact://"):
            artifacts.add(ref)
    project = str(metadata.get("project") or "")
    # Project names are display hints only, never a path or binding.
    project = project if _ID.fullmatch(project) else ""
    return validate_payload(
        {
            "format": "uag-session",
            "version": 1,
            "session": {
                "source_session_id": session_id,
                "created_at": str(metadata.get("created_at") or ""),
                "entry_point": _clean(str(metadata.get("entry_point") or ""), secrets),
                "project_hint": _clean(project, secrets),
            },
            "conversation": conversation,
            "references": {"memory": sorted(memory), "artifacts": sorted(artifacts)},
        }
    )


def _derive(passphrase: str, salt: bytes) -> bytes:
    from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

    if (
        not isinstance(passphrase, str)
        or not passphrase
        or len(passphrase.encode("utf-8")) > 1024
    ):
        raise PortableSessionError("passphrase must contain 1 to 1024 UTF-8 bytes")
    return Argon2id(
        salt=salt, length=32, memory_cost=KDF[0], iterations=KDF[1], lanes=KDF[2]
    ).derive(passphrase.encode("utf-8"))


def encrypt(payload: dict, passphrase: str) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    plaintext = _json(validate_payload(payload))
    salt, wrap_nonce, nonce, dek = (
        os.urandom(16),
        os.urandom(12),
        os.urandom(12),
        os.urandom(32),
    )
    header = HEADER.pack(MAGIC, 1, 1, 19, *KDF, salt, wrap_nonce, nonce)
    wrapped = AESGCM(_derive(passphrase, salt)).encrypt(
        wrap_nonce, dek, header + b"/DEK"
    )
    return (
        header
        + wrapped
        + AESGCM(dek).encrypt(nonce, plaintext, header + wrapped + b"/payload")
    )


def decrypt(package: bytes, passphrase: str) -> dict:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if (
        not isinstance(package, bytes)
        or not HEADER.size + 48 + 16 < len(package) <= MAX_PACKAGE
    ):
        raise PortableSessionError("invalid package size")
    fields = HEADER.unpack(package[: HEADER.size])
    if fields[:7] != (MAGIC, 1, 1, 19, *KDF):
        raise PortableSessionError("unsupported header or KDF parameters")
    salt, wrap_nonce, nonce = fields[7:]
    header, wrapped = package[: HEADER.size], package[HEADER.size : HEADER.size + 48]
    try:
        dek = AESGCM(_derive(passphrase, salt)).decrypt(
            wrap_nonce, wrapped, header + b"/DEK"
        )
        plaintext = AESGCM(dek).decrypt(
            nonce, package[HEADER.size + 48 :], header + wrapped + b"/payload"
        )
    except InvalidTag:
        raise PortableSessionError("wrong passphrase or damaged package") from None
    try:
        return validate_payload(json.loads(plaintext, object_pairs_hook=_unique_pairs))
    except (ValueError, TypeError, KeyError, RecursionError, UnicodeError):
        raise PortableSessionError("invalid portable payload") from None


def export_file(store, session_id: str, path: str | Path, passphrase: str) -> None:
    destination = Path(path)
    if destination.suffix.lower() != ".uag":
        raise PortableSessionError("portable packages require the .uag extension")
    package = encrypt(snapshot(store, session_id), passphrase)
    # Exclusive create prevents overwrite and following a destination symlink.
    with destination.open("xb") as stream:
        stream.write(package)


def import_file(store, path: str | Path, passphrase: str):
    with Path(path).open("rb") as stream:
        package = stream.read(MAX_PACKAGE + 1)
    return store.import_portable_payload(decrypt(package, passphrase))
