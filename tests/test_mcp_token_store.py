from __future__ import annotations

import base64
from pathlib import Path

import pytest

from uagent.tools.mcp.token_store import StoredToken, TokenStore


def _store(path: Path) -> TokenStore:
    return TokenStore(
        path,
        encrypt=lambda value: base64.b64encode(value.encode()).decode(),
        decrypt=lambda value: base64.b64decode(value).decode(),
    )


def test_token_store_encrypts_and_keys_by_issuer_resource(tmp_path: Path) -> None:
    store = _store(tmp_path / "oauth_tokens.json")
    token = StoredToken("access-secret", "Bearer", expires_at=100, refresh_token="refresh-secret")
    store.save("https://auth.example", "https://mcp.example/mcp", token)

    raw = (tmp_path / "oauth_tokens.json").read_text(encoding="utf-8")
    assert "access-secret" not in raw
    assert "refresh-secret" not in raw
    assert store.load("https://auth.example", "https://mcp.example/mcp") == token
    assert store.load("https://other.example", "https://mcp.example/mcp") is None


def test_token_store_delete_and_expiry(tmp_path: Path) -> None:
    store = _store(tmp_path / "oauth_tokens.json")
    token = StoredToken("access", "Bearer", expires_at=10)
    assert token.expired(10)
    assert not token.expired(9)
    store.save("issuer", "resource", token)
    assert store.delete("issuer", "resource") is True
    assert store.delete("issuer", "resource") is False


def test_token_store_rejects_corrupt_data(tmp_path: Path) -> None:
    path = tmp_path / "oauth_tokens.json"
    path.write_text('{"version": 99}', encoding="utf-8")
    with pytest.raises(ValueError):
        _store(path).load("issuer", "resource")
