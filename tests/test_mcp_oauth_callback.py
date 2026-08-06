from __future__ import annotations

import asyncio

from uagent.tools.mcp.oauth_callback import OAuthCallbackListener


def test_callback_listener_receives_code_and_state() -> None:
    async def scenario() -> None:
        async with OAuthCallbackListener() as listener:
            host, port = listener.redirect_uri.split("://", 1)[1].split(":")
            port = int(port.split("/", 1)[0])
            reader, writer = await asyncio.open_connection(host, port)
            writer.write(
                b"GET /callback?code=abc-1&state=state-1 HTTP/1.1\r\n"
                b"Host: localhost\r\n\r\n"
            )
            await writer.drain()
            callback = await listener.wait(timeout=1)
            assert callback.code == "abc-1"
            assert callback.state == "state-1"
            assert callback.error is None
            assert b"200 OK" in await reader.read(1024)
            writer.close()
            await writer.wait_closed()

    asyncio.run(scenario())


def test_callback_listener_rejects_wrong_path() -> None:
    async def scenario() -> None:
        async with OAuthCallbackListener() as listener:
            _, address = listener.redirect_uri.split("://", 1)
            host, remainder = address.split(":", 1)
            port = int(remainder.split("/", 1)[0])
            reader, writer = await asyncio.open_connection(host, port)
            writer.write(b"GET /wrong HTTP/1.1\r\nHost: localhost\r\n\r\n")
            await writer.drain()
            assert b"404 Not Found" in await reader.read(1024)
            writer.close()
            await writer.wait_closed()

    asyncio.run(scenario())
