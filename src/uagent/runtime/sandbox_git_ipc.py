"""Bounded, host-only Git HTTP frames for a live MXC command invocation.

The untrusted process never receives a credential or opens a host credential
store. This protocol carries opaque Git packet bytes, not arbitrary HTTP
headers, URLs, redirects or filesystem paths. Push stays disabled until the
host's human-approval path is connected in a separate change.
"""

from __future__ import annotations

import base64
import binascii
from typing import Any, Callable

from .execution_broker import TrustedSandboxScope
from .sandbox_git_http_broker import GitHttpResponse, exchange_git_smart_http

_REQUEST_LIMIT = 16 * 1024 * 1024
_FRAME_CHUNK_LIMIT = 128 * 1024
_MAX_EXCHANGES = 64
_FRAME_TAG = "git_http"


class GitHttpIPC:
    """One exchange state machine per authorized MXC tool invocation."""

    def __init__(
        self,
        scope: TrustedSandboxScope,
        *,
        revoked: Callable[[], bool],
        exchange: Callable[..., GitHttpResponse] = exchange_git_smart_http,
    ) -> None:
        if not isinstance(scope, TrustedSandboxScope):
            raise TypeError("a trusted MXC scope is required")
        self._scope = scope
        self._revoked = revoked
        self._exchange = exchange
        self._count = 0
        self._reset()

    def _reset(self) -> None:
        self._stage = "idle"
        self._request: dict[str, Any] = {}
        self._body = bytearray()
        self._response = b""
        self._offset = 0

    @property
    def is_idle(self) -> bool:
        """Only a fully finished or explicitly aborted exchange is idle."""
        return self._stage == "idle"

    def handle(self, message: dict[str, Any]) -> dict[str, Any]:
        """Handle one untrusted frame; raise on malformed/incomplete sequences.

        The caller must terminate the MXC tool execution on errors, rather than
        trying to resynchronize a potentially malicious byte stream.
        """
        if self._revoked():
            raise PermissionError("Sandbox execution scope was revoked")
        if not isinstance(message, dict) or message.get("bridge") != _FRAME_TAG:
            raise ValueError("invalid Git IPC frame")
        op = message.get("op")
        if op == "begin":
            if self._stage != "idle" or self._count >= _MAX_EXCHANGES:
                raise ValueError("Git IPC exchange is already active or exhausted")
            if set(message) != {
                "bridge",
                "op",
                "remote_url",
                "service",
                "advertise",
                "protocol_version",
            }:
                raise ValueError("invalid Git IPC request shape")
            if message["service"] != "git-upload-pack":
                raise PermissionError("Git IPC receive-pack is not authorized")
            if type(message["advertise"]) is not bool:
                raise ValueError("invalid Git IPC advertisement type")
            version = message["protocol_version"]
            if type(version) is not int or version not in {0, 1, 2}:
                raise ValueError("invalid Git IPC protocol version")
            remote = message["remote_url"]
            if not isinstance(remote, str) or len(remote) > 2048:
                raise ValueError("invalid Git IPC remote URL")
            self._request = {
                "remote_url": remote,
                "service": message["service"],
                "advertise": message["advertise"],
                "protocol_version": version,
            }
            self._stage = "upload"
            self._count += 1
            return {"bridge": _FRAME_TAG, "op": "ready"}

        if op == "body":
            if self._stage != "upload" or set(message) != {
                "bridge",
                "op",
                "data",
            }:
                raise ValueError("invalid Git IPC request body frame")
            encoded = message["data"]
            if not isinstance(encoded, str) or len(encoded) > 175000:
                raise ValueError("Git IPC request chunk is too large")
            try:
                data = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise ValueError("invalid Git IPC base64 request") from exc
            if len(data) > _FRAME_CHUNK_LIMIT or len(self._body) + len(data) > _REQUEST_LIMIT:
                raise ValueError("Git IPC request exceeds configured budget")
            self._body.extend(data)
            return {"bridge": _FRAME_TAG, "op": "ready"}

        if op == "execute":
            if self._stage != "upload" or set(message) != {"bridge", "op"}:
                raise ValueError("Git IPC request is not ready")
            parameters = self._request
            # Never grant push merely because a sandbox frame requested it.
            result = self._exchange(
                self._scope,
                parameters["remote_url"],
                service=parameters["service"],
                advertise=parameters["advertise"],
                protocol_version=parameters["protocol_version"],
                body=bytes(self._body),
            )
            if not isinstance(result, GitHttpResponse) or len(result.body) > 64 * 1024 * 1024:
                raise ValueError("Git IPC response exceeds configured budget")
            self._response = result.body
            self._offset = 0
            self._body.clear()
            self._stage = "download"
            return {
                "bridge": _FRAME_TAG,
                "op": "response",
                "content_type": result.content_type,
                "length": len(result.body),
            }

        if op == "next":
            if self._stage != "download" or set(message) != {"bridge", "op"}:
                raise ValueError("invalid Git IPC response sequence")
            chunk = self._response[
                self._offset : self._offset + _FRAME_CHUNK_LIMIT
            ]
            self._offset += len(chunk)
            complete = self._offset >= len(self._response)
            reply = {
                "bridge": _FRAME_TAG,
                "op": "data",
                "data": base64.b64encode(chunk).decode("ascii"),
                "done": complete,
            }
            if complete:
                self._reset()
            return reply

        if op == "abort":
            if set(message) != {"bridge", "op"}:
                raise ValueError("invalid Git IPC abort frame")
            self._reset()
            return {"bridge": _FRAME_TAG, "op": "aborted"}

        raise ValueError("unsupported Git IPC operation")
