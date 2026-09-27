"""Phase 4B pseudonymous correlation for canonical Agent spans."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct

from ...auth.credential_store import (
    Credential,
    CredentialKind,
    CredentialStore,
    get_default_credential_store,
)
from ..identity_context import TurnContext
from .settings import ObservabilitySettings

_PURPOSE = "observability_pseudonym_v1"
_MAGIC = b"uag-otel-pseudo-v1"
_ALLOWED_KINDS = frozenset({"principal", "room", "project"})
_BASE64URL_ALPHABET = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
)


def _has_surrogate(value: str) -> bool:
    return any(0xD800 <= ord(char) <= 0xDFFF for char in value)


def _has_control(value: str) -> bool:
    return any(ord(char) < 0x20 or 0x7F <= ord(char) <= 0x9F for char in value)


def _valid_bounded_text(value: object, *, max_chars: int) -> bool:
    if type(value) is not str or not 1 <= len(value) <= max_chars:
        return False
    if value[0].isspace() or value[-1].isspace():
        return False
    return not _has_control(value) and not _has_surrogate(value)


def _valid_key_version(value: object) -> bool:
    if type(value) is not str or not 1 <= len(value) <= 32:
        return False
    first = value[0]
    if not ("a" <= first <= "z" or "0" <= first <= "9"):
        return False
    for char in value[1:]:
        if not (
            "a" <= char <= "z"
            or "0" <= char <= "9"
            or char in {".", "_", "-"}
        ):
            return False
    return True


def _validate_runtime_settings(
    settings: ObservabilitySettings,
) -> tuple[str, str, str] | None:
    if type(settings) is not ObservabilitySettings:
        return None
    if not settings.enabled or not settings.pseudonymous_correlation:
        return None
    if not _valid_bounded_text(settings.deployment_scope, max_chars=128):
        return None
    if not _valid_bounded_text(settings.correlation_key_name, max_chars=128):
        return None
    if not _valid_key_version(settings.correlation_key_version):
        return None
    return (
        settings.deployment_scope,
        settings.correlation_key_name,
        settings.correlation_key_version,
    )


def _valid_metadata(metadata: object) -> bool:
    if type(metadata) is not dict or len(metadata) > 16:
        return False
    for key, value in metadata.items():
        if type(key) is not str or type(value) is not str:
            return False
        if len(key) > 64 or len(value) > 128:
            return False
        if _has_surrogate(key) or _has_surrogate(value):
            return False
    return True


def _decode_key_secret(secret: object) -> bytes | None:
    if type(secret) is not str or len(secret) != 43:
        return None
    if any(char not in _BASE64URL_ALPHABET for char in secret):
        return None
    try:
        raw = base64.urlsafe_b64decode((secret + "=").encode("ascii"))
    except Exception:
        return None
    if len(raw) != 32:
        return None
    canonical = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    if canonical != secret:
        return None
    return raw


def _validate_credential(
    credential: object,
    *,
    requested_name: str,
    key_version: str,
) -> bytes | None:
    if type(credential) is not Credential:
        return None
    if type(credential.kind) is not CredentialKind:
        return None
    if type(credential.name) is not str:
        return None
    if type(credential.secret) is not str:
        return None
    if not _valid_metadata(credential.metadata):
        return None
    if not _valid_bounded_text(credential.name, max_chars=128):
        return None
    if credential.name != requested_name:
        return None
    if credential.kind is not CredentialKind.OTHER:
        return None

    metadata = dict(credential.metadata)
    if metadata.get("purpose") != _PURPOSE:
        return None
    if metadata.get("key_version") != key_version:
        return None
    return _decode_key_secret(credential.secret)


def _provision_credential(name: str, key_version: str) -> Credential:
    raw = secrets.token_bytes(32)
    secret = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return Credential(
        name=name,
        kind=CredentialKind.OTHER,
        secret=secret,
        metadata={"purpose": _PURPOSE, "key_version": key_version},
    )


def _load_correlation_key(
    *,
    store: CredentialStore,
    name: str,
    key_version: str,
) -> bytes | None:
    try:
        credential = store.get(name)
    except Exception:
        return None

    if credential is None:
        try:
            store.set(_provision_credential(name, key_version))
            credential = store.get(name)
        except Exception:
            return None
    return _validate_credential(
        credential,
        requested_name=name,
        key_version=key_version,
    )


def _valid_identifier(value: object) -> str | None:
    if type(value) is not str or not 1 <= len(value) <= 256:
        return None
    if _has_surrogate(value):
        return None
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        return None
    if not 1 <= len(encoded) <= 1024:
        return None
    return value


def _frame(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return struct.pack(">I", len(encoded)) + encoded


def make_pseudonym(
    key: bytes,
    *,
    deployment_scope: str,
    kind: str,
    raw_identifier: str,
) -> str | None:
    """Return the exact Phase 4B 128-bit HMAC pseudonym, or None when invalid."""

    if type(key) is not bytes or len(key) != 32:
        return None
    if not _valid_bounded_text(deployment_scope, max_chars=128):
        return None
    if type(kind) is not str or kind not in _ALLOWED_KINDS:
        return None
    identifier = _valid_identifier(raw_identifier)
    if identifier is None:
        return None

    message = _MAGIC + _frame(deployment_scope) + _frame(kind) + _frame(identifier)
    return hmac.new(key, message, hashlib.sha256).digest()[:16].hex()


def build_correlation_attributes(
    turn_context: TurnContext,
    settings: ObservabilitySettings,
    *,
    credential_store: CredentialStore | None = None,
) -> dict[str, str]:
    """Build the closed Phase 4B attribute set without exposing raw identifiers."""

    if type(turn_context) is not TurnContext:
        return {}
    validated = _validate_runtime_settings(settings)
    if validated is None:
        return {}
    deployment_scope, key_name, key_version = validated

    try:
        store = credential_store or get_default_credential_store()
        key = _load_correlation_key(
            store=store,
            name=key_name,
            key_version=key_version,
        )
    except Exception:
        return {}
    if key is None:
        return {}

    attributes: dict[str, str] = {}
    for kind, raw_identifier in (
        ("principal", turn_context.principal_id),
        ("room", turn_context.room_id),
        ("project", turn_context.project_id),
    ):
        pseudonym = make_pseudonym(
            key,
            deployment_scope=deployment_scope,
            kind=kind,
            raw_identifier=raw_identifier,
        )
        if pseudonym is not None:
            attributes[f"uag.correlation.{kind}"] = pseudonym

    if attributes:
        attributes["uag.correlation.key_version"] = key_version
    return attributes


def attach_pseudonymous_correlation(
    span: object,
    turn_context: TurnContext,
    settings: ObservabilitySettings,
    *,
    credential_store: CredentialStore | None = None,
) -> bool:
    """Attach the closed correlation set to one canonical invoke_agent root span."""

    attributes = build_correlation_attributes(
        turn_context,
        settings,
        credential_store=credential_store,
    )
    if not attributes:
        return False
    try:
        for key, value in attributes.items():
            span.set_attribute(key, value)  # type: ignore[attr-defined]
    except Exception:
        return False
    return True


__all__ = [
    "attach_pseudonymous_correlation",
    "build_correlation_attributes",
    "make_pseudonym",
]
