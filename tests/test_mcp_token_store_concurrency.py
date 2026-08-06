from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from uagent.tools.mcp.token_store import StoredToken, TokenStore


def test_concurrent_token_store_writes_preserve_all_records(tmp_path: Path) -> None:
    path = tmp_path / "tokens.json"

    def save(index: int) -> None:
        store = TokenStore(
            path,
            encrypt=lambda value: value[::-1],
            decrypt=lambda value: value[::-1],
        )
        store.save(
            f"https://issuer-{index}.example",
            f"https://mcp-{index}.example/mcp",
            StoredToken(f"access-{index}", "Bearer"),
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(save, range(8)))

    store = TokenStore(
        path,
        encrypt=lambda value: value[::-1],
        decrypt=lambda value: value[::-1],
    )
    for index in range(8):
        token = store.load(
            f"https://issuer-{index}.example",
            f"https://mcp-{index}.example/mcp",
        )
        assert token is not None
        assert token.access_token == f"access-{index}"
