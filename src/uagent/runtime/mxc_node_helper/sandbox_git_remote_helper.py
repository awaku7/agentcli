"""Read-only Git protocol-v2 remote helper for the isolated MXC workspace.

Installed in the isolated runtime, not the trusted host process. All
authentication is performed by the trusted host GitHttpIPC; this helper
only exchanges bounded Git packet bytes through its per-command mailbox.
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
import time
from pathlib import Path

_REQUEST_CHUNK = 96_000
_MAX_RPC_BYTES = 16 * 1024 * 1024
_MAX_RESPONSE_BYTES = 64 * 1024 * 1024
_MAX_REQUESTS = 64
_IPC_TIMEOUT = 22.0
_NAME = re.compile(r"[0-9]{6}\.resp\Z")


class _RemoteHelper:
    def __init__(self, remote: str, directory: Path) -> None:
        self.remote = remote.removeprefix("uag::")
        self.directory = directory
        self.counter = 0
        self.deadline = time.monotonic() + _IPC_TIMEOUT

    def _ipc(self, message: dict) -> dict:
        self.counter += 1
        if self.counter > 8192:
            raise RuntimeError("Git bridge IPC frame budget exceeded")
        name = f"{self.counter:06d}"
        temporary = self.directory / (name + ".tmp")
        request = self.directory / (name + ".req")
        response = self.directory / (name + ".resp")
        data = json.dumps(message, separators=(",", ":"), ensure_ascii=True)
        if len(data) > 180_000:
            raise ValueError("Git IPC request frame too large")
        with temporary.open("x", encoding="ascii") as stream:
            stream.write(data)
        os.replace(temporary, request)
        while True:
            if time.monotonic() >= self.deadline:
                raise TimeoutError("Git remote helper IPC deadline expired")
            try:
                # The bridge directory exists only for the command's lifetime.
                # Never accept response paths outside its fixed numeric naming.
                if not _NAME.fullmatch(response.name):
                    raise RuntimeError("invalid Git response path")
                payload = response.read_bytes()
            except FileNotFoundError:
                time.sleep(0.005)
                continue
            if len(payload) > 190_000:
                raise RuntimeError("Git IPC response frame too large")
            response.unlink()
            result = json.loads(payload)
            if not isinstance(result, dict) or result.get("bridge") != "git_http":
                raise RuntimeError("invalid Git IPC response")
            return result

    def http(self, *, advertise: bool, body: bytes = b"") -> bytes:
        if len(body) > _MAX_RPC_BYTES:
            raise ValueError("Git protocol request exceeds the 16 MiB limit")
        begin = self._ipc(
            {
                "bridge": "git_http",
                "op": "begin",
                "remote_url": self.remote,
                "service": "git-upload-pack",
                "advertise": advertise,
                "protocol_version": 2,
            }
        )
        if begin.get("op") != "ready":
            raise RuntimeError("Git IPC begin rejected")
        for offset in range(0, len(body), _REQUEST_CHUNK):
            ready = self._ipc(
                {
                    "bridge": "git_http",
                    "op": "body",
                    "data": base64.b64encode(
                        body[offset : offset + _REQUEST_CHUNK]
                    ).decode("ascii"),
                }
            )
            if ready.get("op") != "ready":
                raise RuntimeError("Git IPC body rejected")
        metadata = self._ipc({"bridge": "git_http", "op": "execute"})
        if metadata.get("op") != "response":
            raise RuntimeError("Git IPC request rejected")
        expected = metadata.get("length")
        if type(expected) is not int or not 0 <= expected <= _MAX_RESPONSE_BYTES:
            raise RuntimeError("invalid Git response size")
        accumulated = bytearray()
        while True:
            packet = self._ipc({"bridge": "git_http", "op": "next"})
            if packet.get("op") != "data" or type(packet.get("done")) is not bool:
                raise RuntimeError("invalid Git IPC response data")
            chunk = base64.b64decode(packet.get("data", ""), validate=True)
            if len(chunk) > 128 * 1024 or len(accumulated) + len(chunk) > expected:
                raise RuntimeError("Git IPC response exceeds declared size")
            accumulated.extend(chunk)
            if packet["done"]:
                if len(accumulated) != expected:
                    raise RuntimeError("Git IPC response size mismatch")
                break
        return bytes(accumulated)


def _read_exact(stream, count: int) -> bytes:
    result = bytearray()
    while len(result) < count:
        chunk = stream.read(count - len(result))
        if not chunk:
            raise EOFError("incomplete Git packet")
        result.extend(chunk)
    return bytes(result)


def _request_message(stream) -> bytes | None:
    """Read protocol-v2 request packets through their flush marker."""
    try:
        header = stream.read(4)
    except BrokenPipeError:
        return None
    if not header:
        return None
    if len(header) != 4:
        raise EOFError("incomplete Git pkt-line header")
    result = bytearray()
    size = int(header, 16)
    while True:
        if size > 65520 or size in {3, 4}:
            raise ValueError("invalid Git pkt-line size")
        result.extend(header)
        if size > 4:
            result.extend(_read_exact(stream, size - 4))
        if len(result) > _MAX_RPC_BYTES:
            raise ValueError("Git request exceeded 16 MiB")
        if size == 0:
            return bytes(result)
        header = _read_exact(stream, 4)
        size = int(header, 16)


def main() -> int:
    if len(sys.argv) < 3:
        raise ValueError("Git helper requires remote name and URL")
    mailbox = os.environ.get("UAG_GIT_BRIDGE_DIR")
    if not mailbox:
        raise RuntimeError("Git authentication bridge is not enabled")
    helper = _RemoteHelper(sys.argv[-1], Path(mailbox))
    source = sys.stdin.buffer
    output = sys.stdout.buffer
    while True:
        command = source.readline()
        if not command:
            break
        if command == b"capabilities\n":
            output.write(b"stateless-connect\n\n")
            output.flush()
            continue
        if command != b"stateless-connect git-upload-pack\n":
            raise PermissionError("only Git upload-pack protocol v2 is supported")
        advertisement = helper.http(advertise=True)
        # A protocol-v2 HTTP server advertises capabilities directly, while
        # legacy smart-HTTP discovery may include a service banner first.
        banner = b"001e# service=git-upload-pack\n0000"
        capability_data = (
            advertisement[len(banner) :]
            if advertisement.startswith(banner)
            else advertisement
        )
        if not capability_data.startswith(b"000eversion 2\n"):
            raise RuntimeError("Git remote did not negotiate protocol v2")
        output.write(b"\n" + capability_data)
        output.flush()
        for _ in range(_MAX_REQUESTS):
            body = _request_message(source)
            if body is None:
                return 0
            response = helper.http(advertise=False, body=body)
            # Git's stateless-connect transport requires response-end after
            # each complete HTTP response, not just the server flush packet.
            output.write(response + b"0002")
            output.flush()
        raise RuntimeError("Git remote helper request limit exceeded")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, PermissionError, TimeoutError) as exc:
        print(f"git-remote-uag: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
