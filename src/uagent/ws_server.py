from __future__ import annotations

"""
WebSocket server for VSCode extension integration.

Provides a local-only WebSocket server that exposes uag tools and chat
capabilities to the VSCode extension via JSON messages.

Usage:
    python -m uagent.ws_server
    python -m uagent.ws_server --port 18765 --log-level DEBUG
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
from typing import Any

from uagent.ws_handler import WsHandler

logger = logging.getLogger("uag.ws_server")

DEFAULT_PORT = 18765


class UagWebSocketServer:
    """WebSocket server bound to 127.0.0.1 only."""

    def __init__(self, port: int = DEFAULT_PORT):
        self.port = port
        self.handler = WsHandler()
        self._server: Any = None
        self._cleanup_done = False

    async def start(self) -> None:
        """Start the WebSocket server."""
        import websockets

        self._server = await websockets.serve(
            self.on_connect,
            host="127.0.0.1",
            port=self.port,
            ping_interval=20,
            ping_timeout=10,
            max_size=10 * 1024 * 1024,  # 10 MB
            compression=None,
        )
        logger.info(
            "uag WebSocket server started on 127.0.0.1:%d", self.port
        )
        # Signal readiness to parent process (VSCode extension)
        print(f"UAG_WS_READY:{self.port}", flush=True)

        await asyncio.Future()  # Run forever

    async def on_connect(self, websocket: Any) -> None:
        """Handle a new client connection."""
        remote = websocket.remote_address
        logger.info("Client connected: %s", remote)
        try:
            async for raw in websocket:
                await self._handle_message(websocket, raw)
        except Exception:
            logger.exception("Connection error")
        finally:
            logger.info("Client disconnected: %s", remote)

    async def _handle_message(self, websocket: Any, raw: str) -> None:
        """Parse and dispatch a single message."""
        try:
            msg = json.loads(raw)
            if not isinstance(msg, dict):
                raise ValueError("Message must be a JSON object")
        except (json.JSONDecodeError, ValueError) as e:
            await websocket.send(
                json.dumps(
                    {
                        "id": None,
                        "ok": False,
                        "error": {"code": "INVALID_JSON", "message": str(e)},
                    }
                )
            )
            return

        response = await self.handler.dispatch(msg)
        try:
            await websocket.send(json.dumps(response, ensure_ascii=False))
        except Exception as e:
            logger.error("Failed to send response: %s", e)

    async def cleanup(self) -> None:
        """Clean up server resources."""
        if self._cleanup_done:
            return
        self._cleanup_done = True
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        logger.info("Server cleaned up")


def setup_logging(level: str = "INFO") -> None:
    """Configure logging for the server process."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,  # stderr so stdout is clean for UAG_WS_READY signal
    )
    # Suppress noisy library logs
    logging.getLogger("websockets").setLevel(logging.WARNING)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="uag WebSocket Server for VSCode extension"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"WebSocket port (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    args = parse_args(argv)
    setup_logging(args.log_level)

    server = UagWebSocketServer(port=args.port)

    # Handle shutdown signals
    if sys.platform != "win32":
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda: asyncio.ensure_future(server.cleanup()))
            except NotImplementedError:
                pass
    else:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(server.start())
    except OSError as e:
        logger.error("Failed to start server on port %d: %s", args.port, e)
        return 1
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    finally:
        loop.run_until_complete(server.cleanup())
        loop.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
