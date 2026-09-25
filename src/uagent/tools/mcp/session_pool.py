"""Process-local reuse of MCP Streamable HTTP sessions.

The normal tool entry point is synchronous, while the MCP SDK transport is
async. A small dedicated event-loop thread lets successive tool calls reuse
one initialized MCPClient without leaking an event loop across ``asyncio.run``
invocations.
"""

from __future__ import annotations

import asyncio
import atexit
import json
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

from .client import MCPClient


class MCPSessionCancelled(RuntimeError):
    """Raised when the host cancels a pooled MCP request."""


class MCPSessionStale(RuntimeError):
    """Raised when a pooled MCP response belongs to an older request."""


@dataclass
class _Entry:
    client: MCPClient
    tools_result: Any
    lock: asyncio.Lock


class MCPHTTPSessionPool:
    """Reuse initialized HTTP MCP sessions within one process.

    The pool is deliberately HTTP-only. Stdio transports keep their existing
    per-call lifecycle because their process ownership and shutdown semantics
    are different.
    """

    def __init__(self) -> None:
        self._state_lock = threading.Lock()
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._entries: dict[str, _Entry] = {}
        self._client_factory: Any = MCPClient

    def set_client_factory(self, factory: Any) -> None:
        """Set the client constructor (also useful for isolated tests)."""
        if callable(factory):
            self._client_factory = factory

    def _ensure_worker(self) -> None:
        with self._state_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._ready.clear()
            self._thread = threading.Thread(
                target=self._worker_main,
                name="uagent-mcp-http-session-pool",
                daemon=True,
            )
            self._thread.start()
        self._ready.wait(timeout=5)
        if self._loop is None:
            raise RuntimeError("MCP session pool worker did not start")

    def _worker_main(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._ready.set()
        loop.run_forever()
        try:
            loop.run_until_complete(self._close_all())
        finally:
            loop.close()
            self._loop = None

    async def _discard_entry(self, key: str) -> None:
        entry = self._entries.pop(key, None)
        if entry is None:
            return
        try:
            await entry.client.__aexit__(None, None, None)
        except Exception:
            pass

    def _discard_entry_sync(self, key: str) -> None:
        try:
            self._submit(self._discard_entry(key)).result(timeout=2)
        except Exception:
            pass

    @staticmethod
    def _generation_value(callback: Callable[[], Any] | None) -> Any:
        if not callable(callback):
            return None
        try:
            return callback()
        except Exception:
            return None

    def _wait_for_future(
        self,
        future: Any,
        *,
        key: str,
        is_cancelled: Callable[[], bool] | None,
        request_generation: Callable[[], Any] | None,
    ) -> Any:
        initial_generation = self._generation_value(request_generation)
        try:
            while not future.done():
                if callable(is_cancelled) and is_cancelled():
                    future.cancel()
                    self._discard_entry_sync(key)
                    raise MCPSessionCancelled()
                if (
                    callable(request_generation)
                    and self._generation_value(request_generation) != initial_generation
                ):
                    future.cancel()
                    self._discard_entry_sync(key)
                    raise MCPSessionStale()
                time.sleep(0.05)
            result = future.result()
            if callable(is_cancelled) and is_cancelled():
                self._discard_entry_sync(key)
                raise MCPSessionStale()
            if (
                callable(request_generation)
                and self._generation_value(request_generation) != initial_generation
            ):
                self._discard_entry_sync(key)
                raise MCPSessionStale()
            return result
        except (MCPSessionCancelled, MCPSessionStale):
            future.cancel()
            raise

    def _submit(self, coroutine: Any):
        self._ensure_worker()
        assert self._loop is not None
        return asyncio.run_coroutine_threadsafe(coroutine, self._loop)

    @staticmethod
    def _key(
        url: str,
        headers: dict[str, str],
        protocol_mode: str,
        factory_id: int,
        trusted_trace_propagation: bool = False,
    ) -> str:
        return json.dumps(
            {
                "url": str(url),
                "headers": sorted((str(k), str(v)) for k, v in headers.items()),
                "protocol_mode": str(protocol_mode),
                "factory_id": factory_id,
                "trusted_trace_propagation": bool(trusted_trace_propagation),
            },
            sort_keys=True,
            ensure_ascii=False,
        )

    async def _get_entry(
        self,
        key: str,
        *,
        url: str,
        headers: dict[str, str],
        protocol_mode: str,
        trusted_trace_propagation: bool = False,
    ) -> _Entry:
        entry = self._entries.get(key)
        if entry is not None:
            return entry
        client = self._client_factory(
            url=url,
            headers=headers,
            protocol_mode=protocol_mode,
            trusted_trace_propagation=trusted_trace_propagation,
        )
        await client.__aenter__()
        try:
            tools_result = await client.list_tools()
        except Exception:
            tools_result = None
        entry = _Entry(client=client, tools_result=tools_result, lock=asyncio.Lock())
        self._entries[key] = entry
        return entry

    async def _call_tool(
        self,
        key: str,
        *,
        url: str,
        name: str,
        arguments: dict[str, Any],
        headers: dict[str, str],
        protocol_mode: str,
        trusted_trace_propagation: bool = False,
    ) -> tuple[Any, Any]:
        entry = await self._get_entry(
            key,
            url=url,
            headers=headers,
            protocol_mode=protocol_mode,
            trusted_trace_propagation=trusted_trace_propagation,
        )
        async with entry.lock:
            result = await entry.client.call_tool(name, arguments)
        return entry.tools_result, result

    def list_tools(
        self,
        *,
        url: str,
        headers: dict[str, str],
        protocol_mode: str,
        is_cancelled: Callable[[], bool] | None = None,
        request_generation: Callable[[], Any] | None = None,
    ) -> Any:
        """Return the cached tool list, initializing the session if needed."""
        key = self._key(url, headers, protocol_mode, id(self._client_factory))
        future = self._submit(
            self._get_entry(
                key,
                url=url,
                headers=headers,
                protocol_mode=protocol_mode,
            )
        )
        return self._wait_for_future(
            future,
            key=key,
            is_cancelled=is_cancelled,
            request_generation=request_generation,
        ).tools_result

    def call_tool(
        self,
        *,
        url: str,
        name: str,
        arguments: dict[str, Any],
        headers: dict[str, str],
        protocol_mode: str,
        is_cancelled: Callable[[], bool] | None = None,
        request_generation: Callable[[], Any] | None = None,
    ) -> tuple[Any, Any]:
        """Call an MCP tool, reusing the initialized HTTP session."""
        key = self._key(url, headers, protocol_mode, id(self._client_factory))
        future = self._submit(
            self._call_tool(
                key,
                url=url,
                name=name,
                arguments=arguments,
                headers=headers,
                protocol_mode=protocol_mode,
            )
        )
        return self._wait_for_future(
            future,
            key=key,
            is_cancelled=is_cancelled,
            request_generation=request_generation,
        )

    async def _close_all(self) -> None:
        entries = list(self._entries.values())
        self._entries.clear()
        for entry in entries:
            try:
                await entry.client.__aexit__(None, None, None)
            except Exception:
                pass

    def close(self) -> None:
        with self._state_lock:
            loop = self._loop
            thread = self._thread
            self._thread = None
        if loop is None or thread is None:
            return
        try:
            loop.call_soon_threadsafe(loop.stop)
            thread.join(timeout=5)
        except Exception:
            pass


_POOL = MCPHTTPSessionPool()
atexit.register(_POOL.close)


def get_mcp_http_session_pool() -> MCPHTTPSessionPool:
    return _POOL


__all__ = [
    "MCPSessionCancelled",
    "MCPSessionStale",
    "MCPHTTPSessionPool",
    "get_mcp_http_session_pool",
]
