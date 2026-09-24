"""Server-side project contexts for authenticated non-OIDC Web sessions."""

from __future__ import annotations

import hashlib
import secrets
import time

from ..env_utils import env_get
from .identity_context import IdentityContext, IdentityResolutionError
from .memory_store import MemoryStore

PROJECT_CONTEXT_COOKIE = "uag_project_context"
_DEFAULT_TTL_SECONDS = 8 * 60 * 60
_DEFAULT_MAX_SESSIONS = 4096


def _positive_setting(name: str, default: int) -> int:
    raw = str(env_get(name, str(default)) or "").strip()
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def project_context_ttl() -> int:
    return _positive_setting("UAGENT_PROJECT_CONTEXT_TTL", _DEFAULT_TTL_SECONDS)


def _configuration_fingerprint() -> str:
    from .auth_management import authentication_configuration_fingerprint

    authentication = authentication_configuration_fingerprint()
    ttl = str(env_get("UAGENT_PROJECT_CONTEXT_TTL", str(_DEFAULT_TTL_SECONDS)) or "")
    capacity = str(
        env_get("UAGENT_PROJECT_CONTEXT_MAX", str(_DEFAULT_MAX_SESSIONS)) or ""
    )
    payload = "\0".join((authentication, ttl.strip(), capacity.strip()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ProjectContextStore:
    """Persist opaque browser bindings to a project, scoped to one principal.

    Only a hash of the browser token is stored. Every resolution re-checks the
    authenticated principal, expiration, and authentication configuration.
    The backing SQLite database lets workers sharing the Memory database use
    the same server-side binding.
    """

    def __init__(self, store: MemoryStore) -> None:
        self._db = store.db

    @staticmethod
    def _key(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def bind(
        self,
        token: str,
        identity: IdentityContext,
        project_id: str,
    ) -> tuple[str, int]:
        project_id = str(project_id or "").strip()
        if not identity.authenticated or not project_id:
            raise ValueError("authenticated identity and project_id are required")
        if identity.authn_kind == "local":
            raise IdentityResolutionError(
                "project context sessions are not used in local identity mode"
            )

        ttl = project_context_ttl()
        max_sessions = _positive_setting(
            "UAGENT_PROJECT_CONTEXT_MAX", _DEFAULT_MAX_SESSIONS
        )
        fingerprint = _configuration_fingerprint()
        now = time.time()
        token = str(token or "").strip()
        token_key = self._key(token) if token else ""
        self._db.execute("BEGIN IMMEDIATE")
        try:
            self._db.execute(
                "DELETE FROM project_context_sessions "
                "WHERE expires_at <= ? OR configuration_fingerprint <> ?",
                (now, fingerprint),
            )
            existing = (
                self._db.execute(
                    "SELECT principal_id FROM project_context_sessions "
                    "WHERE token_hash = ?",
                    (token_key,),
                ).fetchone()
                if token_key
                else None
            )
            if (
                existing is not None
                and str(existing["principal_id"]) == identity.principal_id
            ):
                self._db.execute(
                    "UPDATE project_context_sessions SET project_id=?, expires_at=? "
                    "WHERE token_hash=?",
                    (project_id, now + ttl, token_key),
                )
                result_token = token
            else:
                count = self._db.execute(
                    "SELECT COUNT(*) FROM project_context_sessions"
                ).fetchone()[0]
                if int(count) >= max_sessions:
                    raise RuntimeError("project context session capacity reached")
                result_token = secrets.token_urlsafe(32)
                self._db.execute(
                    "INSERT INTO project_context_sessions "
                    "(token_hash, principal_id, project_id, configuration_fingerprint, "
                    "expires_at, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        self._key(result_token),
                        identity.principal_id,
                        project_id,
                        fingerprint,
                        now + ttl,
                        now,
                    ),
                )
            self._db.commit()
            return result_token, ttl
        except Exception:
            self._db.rollback()
            raise

    def resolve(self, token: str, identity: IdentityContext) -> str | None:
        token = str(token or "").strip()
        if not token or not identity.authenticated or identity.authn_kind == "local":
            return None
        key = self._key(token)
        now = time.time()
        fingerprint = _configuration_fingerprint()
        row = self._db.execute(
            "SELECT principal_id, project_id, configuration_fingerprint, expires_at "
            "FROM project_context_sessions WHERE token_hash = ?",
            (key,),
        ).fetchone()
        if row is None:
            return None
        if (
            str(row["principal_id"]) != identity.principal_id
            or str(row["configuration_fingerprint"]) != fingerprint
            or float(row["expires_at"]) <= now
        ):
            if (
                str(row["configuration_fingerprint"]) != fingerprint
                or float(row["expires_at"]) <= now
            ):
                self._db.execute(
                    "DELETE FROM project_context_sessions WHERE token_hash = ?", (key,)
                )
                self._db.commit()
            return None
        return str(row["project_id"])

    def revoke(self, token: str) -> None:
        token = str(token or "").strip()
        if token:
            self._db.execute(
                "DELETE FROM project_context_sessions WHERE token_hash = ?",
                (self._key(token),),
            )
            self._db.commit()


__all__ = ["PROJECT_CONTEXT_COOKIE", "ProjectContextStore", "project_context_ttl"]
