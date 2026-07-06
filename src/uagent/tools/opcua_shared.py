"""OPC UA shared resources."""
from __future__ import annotations

import asyncio
from typing import Any, Callable


def _asyncua_import():
    try:
        from asyncua import Client, ua
    except ImportError:
        from .._pip_auto import install_with_status as _install_ua
        if not _install_ua("asyncua"):
            raise ImportError("asyncua library could not be installed.")
        from asyncua import Client, ua
    return Client, ua


def sync_run(coro_factory: Callable, url: str, timeout: int = 10) -> Any:
    """Run an async coroutine factory synchronously with OPC UA client.

    coro_factory(client, ua) is called after connect.
    Client is disconnected after completion.
    """
    Client, ua = _asyncua_import()

    async def _run():
        async with Client(url, timeout=timeout) as client:
            return await coro_factory(client, ua)

    return asyncio.run(_run())
