"""Keyed identities for provider-neutral round contracts.

Canonical JSON is deliberately kept outside this module: callers provide the
already-canonical bytes they intend to identify.  This keeps key management and
HMAC construction testable without coupling them to a JSON implementation.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import unicodedata
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from ..auth.credential_store import (
    Credential,
    CredentialKind,
    CredentialStore,
    get_default_credential_store,
)


class WorkspaceKeyUnavailable(RuntimeError):
    """Raised when a stable workspace key cannot be loaded or created."""


class CanonicalJsonError(ValueError):
    """Raised when a value cannot be represented in an identity payload."""


def canonical_json(value: Any) -> bytes:
    """Serialize JSON values deterministically for identity HMAC input.

    Strings and object keys are normalized to Unicode NFC; object keys use
    UTF-16 ordering, matching the ordering rule in RFC 8785. Runtime-only
    values and non-string object keys are rejected instead of coerced.
    """

    def encode(item: Any) -> str:
        if item is None:
            return "null"
        if item is True:
            return "true"
        if item is False:
            return "false"
        if isinstance(item, int) and not isinstance(item, bool):
            return str(item)
        if isinstance(item, float):
            if item != item or item in (float("inf"), float("-inf")):
                raise CanonicalJsonError("non-finite numbers are not valid JSON")
            if item.is_integer():
                return str(int(item))
            # json's encoder provides the runtime's shortest IEEE-754 spelling.
            # Float policy/version must be carried by the caller's payload.
            return json.dumps(item, ensure_ascii=False, allow_nan=False)
        if isinstance(item, str):
            return json.dumps(unicodedata.normalize("NFC", item), ensure_ascii=False)
        if isinstance(item, Mapping):
            pairs: list[tuple[str, Any]] = []
            normalized_keys: set[str] = set()
            for key, child in item.items():
                if not isinstance(key, str):
                    raise CanonicalJsonError("object keys must be strings")
                normalized_key = unicodedata.normalize("NFC", key)
                if normalized_key in normalized_keys:
                    raise CanonicalJsonError(
                        "object keys collide after Unicode NFC normalization"
                    )
                normalized_keys.add(normalized_key)
                pairs.append((normalized_key, child))
            pairs.sort(key=lambda pair: pair[0].encode("utf-16-be"))
            return (
                "{"
                + ",".join(f"{encode(key)}:{encode(child)}" for key, child in pairs)
                + "}"
            )
        if isinstance(item, Sequence) and not isinstance(item, (str, bytes)):
            return "[" + ",".join(encode(child) for child in item) + "]"
        raise CanonicalJsonError(f"unsupported identity value: {type(item).__name__}")

    return encode(value).encode("utf-8")


class WorkspaceKeyProvider(Protocol):
    """Return a stable secret key for a workspace-scoped identity namespace."""

    def get_key(self, workspace_id: str) -> bytes: ...


def _workspace_credential_name(workspace_id: str) -> str:
    normalized = (workspace_id or "").strip()
    if not normalized:
        raise ValueError("workspace_id must not be empty")
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"runtime/round-identity/{digest}"


class CredentialStoreWorkspaceKeyProvider:
    """Persist workspace keys through the configured credential store.

    The default store selects the operating-system keyring where available and
    otherwise uses UAG's encrypted credential store.  Secret bytes never enter
    telemetry or journal records; those records carry only a key identifier.
    """

    def __init__(self, store: CredentialStore | None = None) -> None:
        self._store = store or get_default_credential_store()

    def get_key(self, workspace_id: str) -> bytes:
        name = _workspace_credential_name(workspace_id)
        credential = self._store.get(name)
        if credential is None:
            raw_key = secrets.token_bytes(32)
            encoded = base64.urlsafe_b64encode(raw_key).decode("ascii")
            credential = Credential(
                name=name,
                kind=CredentialKind.OTHER,
                secret=encoded,
                metadata={"purpose": "round-identity-v1"},
            )
            self._store.set(credential)
            return raw_key
        try:
            raw_key = base64.urlsafe_b64decode(credential.secret.encode("ascii"))
        except Exception as exc:
            raise WorkspaceKeyUnavailable("stored workspace key is invalid") from exc
        if len(raw_key) < 32:
            raise WorkspaceKeyUnavailable("stored workspace key is too short")
        return raw_key


@dataclass(frozen=True)
class DeterministicTestWorkspaceKeyProvider:
    """Fixed-key provider for unit tests; never use it in production."""

    key: bytes = b"uagent-round-identity-test-key-v1"

    def get_key(self, workspace_id: str) -> bytes:
        if not (workspace_id or "").strip():
            raise ValueError("workspace_id must not be empty")
        return self.key


@dataclass(frozen=True)
class RoundIdentityFactory:
    """Create opaque HMAC-SHA-256 identifiers from canonical request bytes."""

    workspace_id: str
    key_provider: WorkspaceKeyProvider
    version: str = "v1"

    def _digest(self, namespace: str, canonical_payload: bytes) -> str:
        if not isinstance(canonical_payload, bytes):
            raise TypeError("canonical_payload must be bytes")
        key = self.key_provider.get_key(self.workspace_id)
        if not isinstance(key, bytes) or len(key) < 32:
            raise WorkspaceKeyUnavailable(
                "workspace key must contain at least 32 bytes"
            )
        message = b"uag/round-identity/" + self.version.encode("ascii")
        message += b"/" + namespace.encode("ascii") + b"\0" + canonical_payload
        return hmac.new(key, message, hashlib.sha256).hexdigest()

    def plan_id(self, canonical_plan: bytes) -> str:
        return self._digest("plan", canonical_plan)

    def plan_id_for(self, plan: Any) -> str:
        return self.plan_id(canonical_json(plan))

    def projection_id(self, canonical_projection: bytes) -> str:
        return self._digest("projection", canonical_projection)

    def projection_id_for(self, projection: Any) -> str:
        return self.projection_id(canonical_json(projection))

    def key_id(self) -> str:
        """Return a non-secret identifier safe to store in a recovery journal."""

        key = self.key_provider.get_key(self.workspace_id)
        return hashlib.sha256(b"uag/key-id/" + key).hexdigest()[:24]


__all__ = [
    "CanonicalJsonError",
    "CredentialStoreWorkspaceKeyProvider",
    "canonical_json",
    "DeterministicTestWorkspaceKeyProvider",
    "RoundIdentityFactory",
    "WorkspaceKeyProvider",
    "WorkspaceKeyUnavailable",
]
