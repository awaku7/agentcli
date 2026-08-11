"""Encrypted, file-backed storage for MCP OAuth tokens.

Only encrypted token payloads are written. The store does not log token
contents and callers must still avoid putting access tokens in request logs.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator


@dataclass(frozen=True)
class StoredToken:
    access_token: str
    token_type: str
    expires_at: int | None = None
    refresh_token: str | None = None
    scope: str | None = None

    def expired(self, now: int) -> bool:
        return self.expires_at is not None and now >= self.expires_at


class TokenStore:
    """Store OAuth credentials encrypted and keyed by issuer/resource."""

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        encrypt: Callable[[str], str] | None = None,
        decrypt: Callable[[str], str] | None = None,
    ) -> None:
        if path is None:
            from uagent.utils.paths import get_state_dir

            path = get_state_dir() / "mcps" / "oauth_tokens.json"
        self.path = Path(path).expanduser()
        if encrypt is None or decrypt is None:
            from ..secrets_tool import decrypt_from_b64, encrypt_to_b64

            encrypt = encrypt or encrypt_to_b64
            decrypt = decrypt or decrypt_from_b64
        self._encrypt = encrypt
        self._decrypt = decrypt

    @staticmethod
    def _key(issuer: str, resource: str) -> str:
        if not issuer or not resource:
            raise ValueError("issuer and resource are required")
        return hashlib.sha256(f"{issuer}\n{resource}".encode()).hexdigest()

    def _read(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ValueError("invalid OAuth token store") from exc
        if not isinstance(data, dict) or data.get("version") != 1:
            raise ValueError("unsupported OAuth token store")
        records = data.get("records", {})
        if not isinstance(records, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in records.items()
        ):
            raise ValueError("invalid OAuth token records")
        return records

    def _write(self, records: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = (
            json.dumps({"version": 1, "records": records}, ensure_ascii=False, indent=2)
            + "\n"
        )
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", dir=str(self.path.parent)
        )
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
            os.replace(temp_name, self.path)
        except Exception:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
            raise

    @contextmanager
    def _write_lock(
        self, *, timeout: float = 10.0, stale_after: float = 60.0
    ) -> Iterator[None]:
        """Serialize read-modify-write operations across processes."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_name(f".{self.path.name}.lock")
        deadline = time.monotonic() + timeout
        acquired = False
        while not acquired:
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                try:
                    os.write(fd, str(os.getpid()).encode("ascii"))
                finally:
                    os.close(fd)
                acquired = True
            except (FileExistsError, PermissionError):
                try:
                    if time.time() - lock_path.stat().st_mtime > stale_after:
                        lock_path.unlink()
                        continue
                except FileNotFoundError:
                    continue
                if time.monotonic() >= deadline:
                    raise TimeoutError("timed out waiting for OAuth token store lock")
                time.sleep(0.05)
        try:
            yield
        finally:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass

    def write_lock(self) -> AbstractContextManager[None]:
        """Acquire the cross-process lock for a compound token operation."""
        return self._write_lock()

    def save_locked(self, issuer: str, resource: str, token: StoredToken) -> None:
        """Save a token while the caller already holds ``write_lock()``."""
        key = self._key(issuer, resource)
        plaintext = json.dumps(
            {
                "access_token": token.access_token,
                "token_type": token.token_type,
                "expires_at": token.expires_at,
                "refresh_token": token.refresh_token,
                "scope": token.scope,
            },
            separators=(",", ":"),
        )
        records = self._read()
        records[key] = self._encrypt(plaintext)
        self._write(records)

    def save(self, issuer: str, resource: str, token: StoredToken) -> None:
        with self._write_lock():
            self.save_locked(issuer, resource, token)

    def load(self, issuer: str, resource: str) -> StoredToken | None:
        encrypted = self._read().get(self._key(issuer, resource))
        if encrypted is None:
            return None
        try:
            payload = json.loads(self._decrypt(encrypted))
        except Exception as exc:
            raise ValueError("invalid encrypted OAuth token") from exc
        if not isinstance(payload, dict) or not payload.get("access_token"):
            raise ValueError("invalid OAuth token payload")
        return StoredToken(
            access_token=str(payload["access_token"]),
            token_type=str(payload.get("token_type") or "Bearer"),
            expires_at=(
                int(payload["expires_at"])
                if payload.get("expires_at") is not None
                else None
            ),
            refresh_token=(
                str(payload["refresh_token"]) if payload.get("refresh_token") else None
            ),
            scope=(str(payload["scope"]) if payload.get("scope") else None),
        )

    def delete(self, issuer: str, resource: str) -> bool:
        with self._write_lock():
            records = self._read()
            removed = records.pop(self._key(issuer, resource), None) is not None
            if removed:
                self._write(records)
            return removed
