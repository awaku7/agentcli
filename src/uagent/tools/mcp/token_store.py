"""Compatibility import path for the shared OAuth token store."""

from ...auth.token_store import StoredToken, TokenStore

__all__ = ["StoredToken", "TokenStore"]
