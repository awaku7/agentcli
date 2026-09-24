"""Owner-scoped encrypted session transfer. No server paths in requests."""

from __future__ import annotations

import asyncio
import base64
import json

from fastapi import Request
from fastapi.responses import Response

from ..runtime.memory_access import MemoryAccessError
from ..runtime.session_portability import (
    MAX_PACKAGE,
    PortableSessionError,
    decrypt,
    encrypt,
    snapshot,
)
from .app import app

_transfer_lock = asyncio.Lock()
MAX_REQUEST = ((MAX_PACKAGE + 2) // 3) * 4 + 16384


async def bounded_body(request: Request) -> dict:
    if (
        request.headers.get("content-type", "").split(";", 1)[0].strip()
        != "application/json"
    ):
        raise PortableSessionError("application/json is required")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_REQUEST:
            raise PortableSessionError("request too large")
        body.extend(chunk)
    try:
        value = json.loads(body)
    except (ValueError, RecursionError):
        raise PortableSessionError("invalid request") from None
    if not isinstance(value, dict):
        raise PortableSessionError("request must be an object")
    return value


def require_session_owner(store, session_id, identity):
    from .connection_identity import require_room_access

    try:
        row = store.get_session(session_id)
    except RuntimeError:
        raise MemoryAccessError("session access denied") from None
    owner = row.get("principal_id")
    if owner != identity.principal_id and not (
        identity.authn_kind == "local" and not owner
    ):
        raise MemoryAccessError("session access denied")
    if row.get("room_id"):
        require_room_access(identity, row["room_id"])
    return row


@app.post("/api/sessions/{session_id}/export")
async def export_session(session_id: str, request: Request):
    from . import routes_api as api

    try:
        identity = api._request_identity(request)
        store = getattr(api.core, "session_store", None)
        if store is None:
            raise PortableSessionError("Session store is not enabled")
        require_session_owner(store, session_id, identity)
        body = await bounded_body(request)
        if set(body) != {"passphrase"}:
            raise PortableSessionError("expected passphrase only")
        if _transfer_lock.locked():
            return Response(status_code=429)
        async with _transfer_lock:
            payload = snapshot(store, session_id)
            package = await asyncio.to_thread(encrypt, payload, body["passphrase"])
            # Authorization can change while expensive crypto runs.
            require_session_owner(store, session_id, api._request_identity(request))
        return Response(
            package,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": 'attachment; filename="session.uag"',
                "Cache-Control": "no-store",
            },
        )
    except Exception as exc:
        return api._memory_error(exc)


@app.post("/api/sessions/import")
async def import_session(request: Request):
    from . import routes_api as api

    try:
        identity = api._request_identity(request)
        store = getattr(api.core, "session_store", None)
        if store is None:
            raise PortableSessionError("Session store is not enabled")
        body = await bounded_body(request)
        if set(body) != {"passphrase", "package"} or not isinstance(
            body["package"], str
        ):
            raise PortableSessionError("expected passphrase and base64 package")
        try:
            package = base64.b64decode(body["package"], validate=True)
        except ValueError:
            raise PortableSessionError("invalid package encoding") from None
        if _transfer_lock.locked():
            return Response(status_code=429)
        async with _transfer_lock:
            payload = await asyncio.to_thread(decrypt, package, body["passphrase"])
            current = api._request_identity(request)
            if current.principal_id != identity.principal_id:
                raise MemoryAccessError("identity changed")
            session = store.import_portable_payload(
                payload, principal_id=identity.principal_id
            )
        return {"session_id": session.session_id, "references_status": "unresolved"}
    except Exception as exc:
        return api._memory_error(exc)
