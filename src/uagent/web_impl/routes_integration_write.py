"""Opt-in signed, project-scoped management membership write endpoint.

A bearer identifies a preconfigured UAG project admin *service principal*.
Separately, a pinned Ed25519 issuer must sign a short-lived, one-use assertion
identifying the UAG Admin operator. Neither grants authority alone.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
from dataclasses import dataclass
import hashlib
import hmac
import json
from pathlib import Path
import re
import sqlite3
import time
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import Request
from fastapi.responses import JSONResponse

from ..env_utils import env_get
from ..runtime.instance_identity import get_instance_id
from ..runtime.memory_access import MemoryAccessError
from ..runtime.memory_store import MemoryStore, MemoryStoreConflictError
from ..runtime.project_membership_mutation import (
    VerifiedOperator,
    apply_membership_change,
)
from ..tools import long_memory as _long_memory_mod
from .app import app
from .routes_integration import (
    INTEGRATION_API_VERSION,
    _read_protected_scope_file,
    _read_scopes,
)

_WRITE_PATH_PREFIX = "/api/admin/integration/v1/projects/"
_MAX_WRITE_BYTES = 262144
_MAX_SCOPE_COUNT = 64
_MAX_REQUEST_BYTES = 2048
_MAX_ASSERTION_BYTES = 4096
_NONCE_PATTERN = re.compile(r"[A-Za-z0-9_-]{16,128}")
_HEX_DIGEST = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class WriteScope:
    token: str
    project_id: str
    principal_id: str
    issuer_id: str
    public_key: bytes


def _decode_b64(value: str, maximum: int) -> bytes:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ValueError("invalid base64url")
    if re.fullmatch(r"[A-Za-z0-9_-]+", value) is None:
        raise ValueError("invalid base64url")
    try:
        return base64.b64decode(
            value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
        )
    except (binascii.Error, ValueError) as exc:
        raise ValueError("invalid base64url") from exc


def _write_scopes() -> tuple[WriteScope, ...]:
    """Reopen the secure file each request, so revocation takes effect at once."""
    config = str(env_get("UAGENT_MANAGEMENT_WRITE_SCOPES_FILE", "") or "").strip()
    if not config:
        return ()
    document_bytes = _read_protected_scope_file(Path(config))
    if len(document_bytes) > _MAX_WRITE_BYTES:
        raise ValueError("write configuration too large")
    try:
        document = json.loads(document_bytes)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("invalid write configuration") from exc
    if (
        not isinstance(document, dict)
        or set(document) != {"version", "scopes"}
        or type(document["version"]) is not int
        or document["version"] != 1
        or not isinstance(document["scopes"], list)
        or not 1 <= len(document["scopes"]) <= _MAX_SCOPE_COUNT
    ):
        raise ValueError("invalid write configuration")
    instance_id = get_instance_id()
    read_tokens = [scope.token for scope in _read_scopes()]
    manifest = str(env_get("UAGENT_MANAGEMENT_API_TOKEN", "") or "").strip()
    if manifest:
        read_tokens.append(manifest)
    scopes = []
    for item in document["scopes"]:
        if not isinstance(item, dict) or set(item) != {
            "instance_id",
            "project_id",
            "principal_id",
            "token",
            "issuer_id",
            "public_key",
        }:
            raise ValueError("invalid write scope")
        project = item["project_id"]
        principal = item["principal_id"]
        token = item["token"]
        issuer = item["issuer_id"]
        if (
            item["instance_id"] != instance_id
            or not isinstance(project, str)
            or not 1 <= len(project) <= 128
            or project.strip() != project
            or not isinstance(principal, str)
            or not 1 <= len(principal) <= 256
            or principal.strip() != principal
            or not isinstance(token, str)
            or not token.isascii()
            or not 32 <= len(token) <= 4096
            or any(ord(ch) < 33 or ord(ch) == 127 for ch in token)
            or not isinstance(issuer, str)
            or not 1 <= len(issuer) <= 128
            or issuer.strip() != issuer
            or any(ord(ch) < 33 or ord(ch) == 127 for ch in issuer)
        ):
            raise ValueError("invalid write scope values")
        public_key = _decode_b64(item["public_key"], 64)
        if len(public_key) != 32:
            raise ValueError("invalid issuer key")
        Ed25519PublicKey.from_public_bytes(public_key)
        if any(
            hmac.compare_digest(token.encode(), used.encode()) for used in read_tokens
        ):
            raise ValueError("write token overlaps read or manifest credential")
        read_tokens.append(token)
        scopes.append(WriteScope(token, project, principal, issuer, public_key))
    return tuple(scopes)


def _match_scope(request: Request, scopes: tuple[WriteScope, ...]) -> WriteScope | None:
    header = str(request.headers.get("authorization", "") or "")
    scheme, separator, supplied = header.strip().partition(" ")
    if scheme.lower() != "bearer" or not separator:
        return None
    secret = supplied.strip()
    if not 1 <= len(secret) <= 4096:
        return None
    matched = None
    for scope in scopes:
        if hmac.compare_digest(secret.encode(), scope.token.encode()):
            matched = scope
    return matched


def _verify_actor_assertion(
    assertion: str,
    scope: WriteScope,
    *,
    instance_id: str,
    project_id: str,
    path: str,
    body: bytes,
    now: int | None = None,
) -> VerifiedOperator:
    if not isinstance(assertion, str) or len(assertion) > _MAX_ASSERTION_BYTES:
        raise ValueError("actor assertion is missing or too large")
    parts = assertion.split(".")
    if len(parts) != 2:
        raise ValueError("invalid actor assertion")
    payload_raw = _decode_b64(parts[0], _MAX_ASSERTION_BYTES)
    signature = _decode_b64(parts[1], 128)
    if len(payload_raw) > 2048 or len(signature) != 64:
        raise ValueError("invalid actor assertion length")
    try:
        Ed25519PublicKey.from_public_bytes(scope.public_key).verify(
            signature, payload_raw
        )
    except InvalidSignature as exc:
        raise ValueError("invalid actor signature") from exc
    try:
        obj = json.loads(payload_raw)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("invalid actor assertion JSON") from exc
    keys = {
        "issuer_id",
        "actor_user_id",
        "session_version",
        "audience",
        "project_id",
        "method",
        "path",
        "body_sha256",
        "issued_at",
        "expires_at",
        "nonce",
    }
    if not isinstance(obj, dict) or set(obj) != keys:
        raise ValueError("invalid actor assertion claims")
    timestamp = int(time.time()) if now is None else now
    issued, expiry = obj["issued_at"], obj["expires_at"]
    uid, session_version = obj["actor_user_id"], obj["session_version"]
    nonce = obj["nonce"]
    if (
        obj["issuer_id"] != scope.issuer_id
        or obj["audience"] != instance_id
        or obj["project_id"] != project_id
        or obj["method"] != "POST"
        or obj["path"] != path
        or not isinstance(obj["body_sha256"], str)
        or _HEX_DIGEST.fullmatch(obj["body_sha256"]) is None
        or not hmac.compare_digest(obj["body_sha256"], hashlib.sha256(body).hexdigest())
        or type(uid) is not int
        or uid <= 0
        or type(session_version) is not int
        or session_version < 0
        or type(issued) is not int
        or type(expiry) is not int
        or issued > timestamp + 5
        or issued < timestamp - 60
        or expiry <= timestamp
        or expiry <= issued
        or expiry > issued + 60
        or not isinstance(nonce, str)
        or _NONCE_PATTERN.fullmatch(nonce) is None
    ):
        raise ValueError("untrusted or expired actor assertion")
    return VerifiedOperator(scope.issuer_id, uid, session_version, nonce)


def _parse_mutation(body: bytes) -> dict[str, Any]:
    if not body or len(body) > _MAX_REQUEST_BYTES:
        raise ValueError("invalid mutation body size")

    def unique_pairs(pairs):
        result = {}
        for name, value in pairs:
            if name in result:
                raise ValueError("duplicate mutation property")
            result[name] = value
        return result

    try:
        payload = json.loads(body, object_pairs_hook=unique_pairs)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("invalid mutation JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("invalid mutation structure")
    action = payload.get("action")
    allowed = {"action", "target_principal_id", "expected_revision"}
    if action == "grant":
        allowed.add("role")
    if set(payload) != allowed:
        raise ValueError("invalid mutation properties")
    return payload


def _write_membership(
    scope: WriteScope,
    operator: VerifiedOperator,
    payload: dict[str, Any],
):
    if not _long_memory_mod.is_sqlite_backend():
        raise FileNotFoundError("SQLite membership store required")
    path = Path(_long_memory_mod._sqlite_path())
    if not path.is_file():
        raise FileNotFoundError("membership store not initialized")
    # Open and close inside this worker thread; SQLite connections must not
    # cross thread boundaries. Existing C0 creates its audit/nonce tables.
    store = MemoryStore(path)
    try:
        return apply_membership_change(
            store.db,
            actor_principal_id=scope.principal_id,
            project_id=scope.project_id,
            target_principal_id=payload["target_principal_id"],
            expected_revision=payload["expected_revision"],
            action=payload["action"],
            role=payload.get("role"),
            operator=operator,
        )
    finally:
        store.close()


def _json_error(status: int, code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": code},
        headers={"Cache-Control": "no-store"},
    )


@app.post(
    "/api/admin/integration/v1/projects/{project_id}/memberships",
    include_in_schema=False,
)
async def mutate_integration_project_members(request: Request, project_id: str):
    if not 1 <= len(project_id) <= 128:
        return _json_error(400, "invalid_project")
    try:
        scopes = await asyncio.to_thread(_write_scopes)
    except (OSError, RuntimeError, ValueError):
        return _json_error(503, "write_configuration_unavailable")
    if not scopes:
        return _json_error(404, "not_supported")
    scope = _match_scope(request, scopes)
    if scope is None:
        return _json_error(401, "invalid_write_credential")
    if scope.project_id != project_id:
        return _json_error(403, "project_not_permitted")
    declared_size = request.headers.get("content-length")
    if declared_size is not None:
        try:
            if int(declared_size) > _MAX_REQUEST_BYTES:
                return _json_error(413, "mutation_too_large")
        except ValueError:
            return _json_error(400, "invalid_content_length")
    try:
        # A valid Content-Length is not guaranteed: bound streaming reads too.
        chunks = []
        consumed = 0
        async for chunk in request.stream():
            consumed += len(chunk)
            if consumed > _MAX_REQUEST_BYTES:
                return _json_error(413, "mutation_too_large")
            chunks.append(chunk)
        body = b"".join(chunks)
        payload = _parse_mutation(body)
    except ValueError:
        return _json_error(400, "invalid_mutation")
    try:
        operator = _verify_actor_assertion(
            str(request.headers.get("x-uag-actor-assertion", "") or ""),
            scope,
            instance_id=get_instance_id(),
            project_id=project_id,
            path=request.url.path,
            body=body,
        )
    except (OSError, ValueError):
        return _json_error(401, "invalid_actor_assertion")
    try:
        changed = await asyncio.to_thread(_write_membership, scope, operator, payload)
    except MemoryAccessError:
        return _json_error(403, "membership_not_permitted")
    except MemoryStoreConflictError:
        return _json_error(409, "membership_revision_conflict")
    except sqlite3.IntegrityError as exc:
        if "project_membership_mutation_nonces" in str(exc):
            return _json_error(409, "actor_assertion_replayed")
        return _json_error(503, "membership_store_unavailable")
    except ValueError:
        return _json_error(400, "invalid_mutation")
    except (sqlite3.DatabaseError, OSError, RuntimeError):
        return _json_error(503, "membership_store_unavailable")
    return JSONResponse(
        content={
            "api_version": INTEGRATION_API_VERSION,
            "instance_id": get_instance_id(),
            "project_id": changed.project_id,
            "principal_id": changed.principal_id,
            "role": changed.role,
            "status": changed.status,
            "revision": changed.revision,
        },
        headers={"Cache-Control": "no-store"},
    )
