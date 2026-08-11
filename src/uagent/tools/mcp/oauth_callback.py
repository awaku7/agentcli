"""Short-lived localhost callback listener for MCP OAuth."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit


@dataclass(frozen=True)
class OAuthCallback:
    code: str | None
    state: str | None
    error: str | None
    error_description: str | None


class OAuthCallbackListener:
    """Receive one OAuth redirect on an ephemeral localhost port."""

    def __init__(self, *, path: str = "/callback", host: str = "127.0.0.1") -> None:
        if not path.startswith("/"):
            raise ValueError("callback path must start with '/'")
        self.host = host
        self.path = path
        self._server: asyncio.AbstractServer | None = None
        self._future: asyncio.Future[OAuthCallback] | None = None

    @property
    def redirect_uri(self) -> str:
        if self._server is None:
            raise RuntimeError("callback listener is not started")
        sockets = self._server.sockets or []
        if not sockets:
            raise RuntimeError("callback listener has no bound socket")
        return f"http://{self.host}:{sockets[0].getsockname()[1]}{self.path}"

    async def __aenter__(self) -> "OAuthCallbackListener":
        self._future = asyncio.get_running_loop().create_future()
        self._server = await asyncio.start_server(
            self._handle_connection,
            host=self.host,
            port=0,
        )
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.close()

    async def wait(self, *, timeout: float = 300) -> OAuthCallback:
        if self._future is None:
            raise RuntimeError("callback listener is not started")
        try:
            return await asyncio.wait_for(self._future, timeout=timeout)
        finally:
            await self.close()

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            request_line = await asyncio.wait_for(reader.readline(), timeout=5)
            parts = request_line.decode("ascii", errors="replace").split()
            if len(parts) < 2 or parts[0] != "GET":
                await self._respond(writer, 400, "Invalid callback request")
                return
            parsed = urlsplit(parts[1])
            if parsed.path != self.path:
                await self._respond(writer, 404, "Not found")
                return
            query = parse_qs(parsed.query, keep_blank_values=True)
            callback = OAuthCallback(
                code=query.get("code", [None])[0],
                state=query.get("state", [None])[0],
                error=query.get("error", [None])[0],
                error_description=query.get("error_description", [None])[0],
            )
            if self._future is not None and not self._future.done():
                self._future.set_result(callback)
            await self._respond(
                writer, 200, "Authorization received. You may close this window."
            )
        except (asyncio.TimeoutError, UnicodeError):
            await self._respond(writer, 400, "Invalid callback request")
        finally:
            writer.close()
            await writer.wait_closed()

    @staticmethod
    async def _respond(writer: asyncio.StreamWriter, status: int, body: str) -> None:
        payload = body.encode("utf-8")
        reason = (
            "OK" if status == 200 else "Bad Request" if status == 400 else "Not Found"
        )
        response = (
            f"HTTP/1.1 {status} {reason}\r\n"
            "Content-Type: text/plain; charset=utf-8\r\n"
            f"Content-Length: {len(payload)}\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii") + payload
        writer.write(response)
        await writer.drain()


__all__ = ["OAuthCallback", "OAuthCallbackListener"]
