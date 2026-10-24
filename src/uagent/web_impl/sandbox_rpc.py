"""Private, bounded IPC client for parent-owned local Web Sandbox tools.

The Web process owns MXC sessions and Room scopes. Spawned per-turn workers
may request an allowlisted tool over their server-created pipe, but never receive
the MXC session manager or choose an execution scope.
"""

from __future__ import annotations

import json
import threading
import uuid
from typing import Any, Callable

from ..runtime.execution_broker import SandboxCapabilities, TrustedSandboxScope
from ..runtime.mxc_backend import MAX_FRAME_BYTES, TOOL_NAMES

RPC_TOOL_REQUEST = "sandbox_tool_request"
RPC_TOOL_RESPONSE = "sandbox_tool_response"
RPC_SCOPE_REVOKE = "sandbox_scope_revoke"
MAX_PENDING_RPC = 8
RPC_TIMEOUT_SECONDS = 120


def _json_frame_size(value: Any) -> int:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError("sandbox RPC payload must contain only JSON values") from exc
    return len(encoded)


def encode_rpc_message(message: dict[str, Any]) -> bytes:
    """Serialize one bounded RPC frame without pickle deserialization."""
    try:
        encoded = json.dumps(
            message,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError("sandbox RPC message must contain only JSON values") from exc
    if len(encoded) > MAX_FRAME_BYTES:
        raise ValueError("sandbox RPC message exceeds the IPC frame limit")
    return encoded


def decode_rpc_message(raw: bytes) -> dict[str, Any]:
    """Decode one size-bounded JSON frame and reject non-object payloads."""
    if not isinstance(raw, bytes) or len(raw) > MAX_FRAME_BYTES:
        raise ValueError("sandbox RPC frame exceeds the IPC frame limit")
    try:
        message = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValueError("sandbox RPC frame is not valid UTF-8 JSON") from exc
    if not isinstance(message, dict):
        raise ValueError("sandbox RPC frame must contain a JSON object")
    return message


def validate_tool_request(message: Any) -> tuple[str, str, dict[str, Any]]:
    """Validate the exact child-to-parent request envelope and its bounds."""
    if not isinstance(message, dict) or set(message) != {
        "type",
        "request_id",
        "name",
        "args",
    }:
        raise ValueError("invalid sandbox RPC request shape")
    request_id = message.get("request_id")
    name = message.get("name")
    args = message.get("args")
    if message.get("type") != RPC_TOOL_REQUEST:
        raise ValueError("invalid sandbox RPC request type")
    if (
        not isinstance(request_id, str)
        or not request_id
        or len(request_id) > 64
        or not isinstance(name, str)
        or name not in TOOL_NAMES
        or not isinstance(args, dict)
        or any(not isinstance(key, str) for key in args)
    ):
        raise ValueError("invalid sandbox RPC request fields")
    if _json_frame_size(message) > MAX_FRAME_BYTES:
        raise ValueError("sandbox RPC request exceeds the IPC frame limit")
    return request_id, name, args


class SandboxToolRPCClient:
    """Child-side proxy that sends sandbox tool calls to the owning Web process."""

    def __init__(
        self,
        *,
        scope: TrustedSandboxScope,
        capabilities: SandboxCapabilities,
        send: Callable[[dict[str, Any]], None],
        timeout: float = RPC_TIMEOUT_SECONDS,
    ) -> None:
        if scope.scope_kind != "web-room" or scope.deployment_id != "web":
            raise ValueError("Sandbox RPC requires a trusted Web Room scope")
        if not isinstance(capabilities, SandboxCapabilities):
            raise ValueError("Sandbox RPC requires observed backend capabilities")
        self.scope = scope
        self.capabilities = capabilities
        self._send = send
        self._timeout = timeout
        self._lock = threading.RLock()
        self._slots = threading.BoundedSemaphore(MAX_PENDING_RPC)
        self._pending: dict[str, tuple[threading.Event, str | None]] = {}
        self._closed = threading.Event()
        self._revoked = threading.Event()

    def activate_scope(self, scope: TrustedSandboxScope) -> None:
        """Accept only the exact parent-issued Room binding."""
        if scope != self.scope or self._closed.is_set() or self._revoked.is_set():
            raise RuntimeError("Sandbox RPC scope binding mismatch")

    def revoke_scope(self, scope: TrustedSandboxScope):
        """Stop local requests and ask the parent to fence the owning Room scope."""
        if scope != self.scope:
            return None
        self._revoked.set()
        self._fail_pending("[sandbox error] Web Room scope was revoked")
        try:
            self._send(
                {
                    "type": RPC_SCOPE_REVOKE,
                    "scope_id": self.scope.scope_id,
                    "binding_generation": self.scope.binding_generation,
                }
            )
        except Exception:
            pass
        return None

    def run_tool(
        self, scope: TrustedSandboxScope | None, name: str, args: dict[str, Any]
    ) -> str:
        if self._closed.is_set() or self._revoked.is_set():
            return "[sandbox error] Web Room Sandbox RPC is unavailable"
        if scope != self.scope:
            return "[sandbox error] Web Room Sandbox scope mismatch"
        if name not in TOOL_NAMES:
            return "[sandbox policy] tool is not in the local sandbox allowlist"
        if not isinstance(args, dict) or any(not isinstance(key, str) for key in args):
            return "[sandbox error] invalid Sandbox tool arguments"

        request_id = uuid.uuid4().hex
        request = {
            "type": RPC_TOOL_REQUEST,
            "request_id": request_id,
            "name": name,
            "args": args,
        }
        try:
            if _json_frame_size(request) > MAX_FRAME_BYTES:
                return (
                    "[sandbox error] Sandbox tool request exceeds the IPC frame limit"
                )
        except ValueError as exc:
            return f"[sandbox error] {exc}"

        if not self._slots.acquire(blocking=False):
            return "[sandbox error] too many pending Sandbox tool requests"
        event = threading.Event()
        with self._lock:
            if self._closed.is_set() or self._revoked.is_set():
                self._slots.release()
                return "[sandbox error] Web Room Sandbox RPC is unavailable"
            self._pending[request_id] = (event, None)
        try:
            self._send(request)
        except Exception:
            with self._lock:
                self._pending.pop(request_id, None)
            self._slots.release()
            return "[sandbox error] unable to contact the Web Sandbox broker"

        if not event.wait(self._timeout):
            with self._lock:
                self._pending.pop(request_id, None)
            self._slots.release()
            return "[sandbox error] Web Sandbox broker response timed out"
        with self._lock:
            pending = self._pending.pop(request_id, None)
        self._slots.release()
        if pending is None:
            return "[sandbox error] Web Sandbox broker request was cancelled"
        return pending[1] or ""

    def deliver_response(self, message: Any) -> None:
        """Resolve one pending call from a parent response; ignore stale IDs."""
        if not isinstance(message, dict) or set(message) != {
            "type",
            "request_id",
            "result",
        }:
            return
        if message.get("type") != RPC_TOOL_RESPONSE:
            return
        request_id = message.get("request_id")
        result = message.get("result")
        if not isinstance(request_id, str) or not isinstance(result, str):
            return
        if len(result.encode("utf-8", errors="replace")) > MAX_FRAME_BYTES:
            result = "[sandbox error] Web Sandbox broker returned an oversized result"
        with self._lock:
            pending = self._pending.get(request_id)
            if pending is None:
                return
            self._pending[request_id] = (pending[0], result)
            pending[0].set()

    def close_all(self) -> None:
        """Wake pending child calls without revoking the parent-owned Room lease."""
        self._closed.set()
        self._fail_pending("[sandbox error] Web Sandbox RPC client closed")

    def _fail_pending(self, result: str) -> None:
        with self._lock:
            pending = list(self._pending.values())
            for request_id, (event, _) in list(self._pending.items()):
                self._pending[request_id] = (event, result)
            for event, _ in pending:
                event.set()


def make_tool_response(request_id: str, result: str) -> dict[str, str]:
    """Build a response whose complete JSON envelope fits the IPC frame limit."""
    response = {"type": RPC_TOOL_RESPONSE, "request_id": request_id, "result": result}
    try:
        encode_rpc_message(response)
    except ValueError:
        response["result"] = (
            "[sandbox error] Web Sandbox broker returned an oversized result"
        )
        encode_rpc_message(response)
    return response


__all__ = [
    "MAX_FRAME_BYTES",
    "MAX_PENDING_RPC",
    "decode_rpc_message",
    "encode_rpc_message",
    "RPC_SCOPE_REVOKE",
    "RPC_TIMEOUT_SECONDS",
    "RPC_TOOL_REQUEST",
    "RPC_TOOL_RESPONSE",
    "SandboxToolRPCClient",
    "make_tool_response",
    "validate_tool_request",
]
