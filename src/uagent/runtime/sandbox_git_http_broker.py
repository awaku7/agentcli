"""Trusted-host Git smart-HTTP transport with scope-bound credentials.

The caller must be the MXC host broker, after checking an active and authorized
TrustedSandboxScope. Nothing in this module runs in the untrusted Sandbox.
The Git transport IPC will use this primitive; it is not an LLM tool.
"""

from __future__ import annotations

import base64
import http.client
import ipaddress
import re
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlsplit

from ..auth.credential_store import (
    CredentialKind,
    CredentialStore,
    get_default_credential_store,
)
from .execution_broker import TrustedSandboxScope
from .sandbox_git_credentials import (
    _TOKEN_PURPOSE,
    _token_key,
    effective_git_credential_alias,
)

_MAX_REQUEST_BYTES = 16 * 1024 * 1024
_MAX_RESPONSE_BYTES = 64 * 1024 * 1024
_HOST_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
_USERNAME = re.compile(r"[A-Za-z0-9_.@-]{1,80}\Z")
_SERVICES = frozenset({"git-upload-pack", "git-receive-pack"})


@dataclass(frozen=True)
class GitHttpResponse:
    content_type: str
    body: bytes


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """Never forward a Git Authorization header through a redirect."""
        return None


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Pin the checked DNS result through TCP connect and TLS SNI."""

    def connect(self):
        addresses = socket.getaddrinfo(
            self.host,
            self.port,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
        if not addresses:
            raise OSError("Git HTTPS DNS returned no usable addresses")
        # Reject the whole resolution if any address reaches a local-only
        # destination, preventing fallback from a safe IP to loopback.
        for _, _, _, _, sockaddr in addresses:
            address = ipaddress.ip_address(sockaddr[0])
            if address.version == 6 and address.ipv4_mapped is not None:
                address = address.ipv4_mapped
            if (
                address.is_loopback
                or address.is_link_local
                or address.is_multicast
                or address.is_unspecified
            ):
                raise PermissionError("Git HTTPS destination is not permitted")
        for family, kind, proto, _, sockaddr in addresses:
            connection = socket.socket(family, kind, proto)
            try:
                connection.settimeout(self.timeout)
                if self.source_address:
                    connection.bind(self.source_address)
                # Never resolve again between the IP policy check and connect.
                connection.connect(sockaddr)
                self.sock = self._context.wrap_socket(
                    connection, server_hostname=self.host
                )
                return
            except OSError:
                connection.close()
        raise OSError("Git HTTPS destination could not be reached")


class _PinnedHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, request):
        return self.do_open(
            _PinnedHTTPSConnection,
            request,
            context=self._context,
            check_hostname=self._check_hostname,
        )


def _trusted_https_opener():
    # Implicit process HTTPS_PROXY could originate from an untrusted
    # project .env. Do not allow it to bypass the resolved-IP policy.
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        _NoRedirect(),
        _PinnedHTTPSHandler(),
    )


def validate_git_host(host: str) -> str:
    """Validate an exact, explicitly configured remote host (no URL or port)."""
    if not isinstance(host, str):
        raise ValueError("Git remote host must be a hostname")
    normalized = host.lower()
    if (
        not normalized
        or len(normalized) > 253
        or normalized in {"localhost", "localhost.localdomain"}
        or normalized.endswith(".localhost")
        or any(not _HOST_LABEL.fullmatch(label) for label in normalized.split("."))
    ):
        raise ValueError("Git remote host must be a valid DNS hostname")
    try:
        ipaddress.ip_address(normalized)
    except ValueError:
        return normalized
    raise ValueError("Git remote host must not be an IP literal")


def _remote_url(remote_url: str) -> tuple[str, str]:
    """Return (bound hostname, canonical HTTPS remote URL)."""
    if not isinstance(remote_url, str) or len(remote_url) > 2048:
        raise ValueError("invalid Git remote URL")
    try:
        parsed = urlsplit(remote_url)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("invalid Git remote URL") from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Git remote must be an uncredentialed HTTPS URL")
    host = validate_git_host(parsed.hostname)
    segments = parsed.path.split("/")
    if (
        len(segments) < 3
        or segments[0] != ""
        or any(
            not segment
            or segment in {".", ".."}
            or "%" in segment
            or "\\" in segment
            or any(ord(char) < 32 for char in segment)
            for segment in segments[1:]
        )
    ):
        raise ValueError("invalid Git repository path")
    return host, f"https://{host}{parsed.path}"


def _authorization(
    scope: TrustedSandboxScope, host: str, store: CredentialStore
) -> str:
    if not isinstance(scope, TrustedSandboxScope):
        raise TypeError("trusted scope is required")
    alias = effective_git_credential_alias(scope, store=store)
    if alias is None:
        raise PermissionError("Git credential is not selected")
    entry = store.get(_token_key(scope, alias))
    if (
        entry is None
        or entry.kind != CredentialKind.OTHER
        or entry.metadata.get("purpose") != _TOKEN_PURPOSE
        or entry.metadata.get("remote_host") != host
        or not isinstance(entry.secret, str)
        or not entry.secret
    ):
        raise PermissionError("selected Git credential is not bound to this remote")
    from time import time

    if entry.expires_at is not None and entry.expires_at <= int(time()):
        raise PermissionError("selected Git credential is expired")
    username = entry.metadata.get("username", "")
    if not isinstance(username, str) or not _USERNAME.fullmatch(username):
        raise PermissionError("Git credential username is not valid")
    raw = f"{username}:{entry.secret}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def exchange_git_smart_http(
    scope: TrustedSandboxScope,
    remote_url: str,
    *,
    service: str,
    advertise: bool,
    body: bytes = b"",
    store: CredentialStore | None = None,
    opener=None,
    push_authorized: bool = False,
    protocol_version: int = 0,
) -> GitHttpResponse:
    """Perform exactly one authenticated Git smart-HTTP request.

    The host caller is responsible for authorizing the live scope and Git
    operation; receive-pack additionally requires the host to assert the
    existing push authorization, including any required human approval.
    This function validates the credential's remote, forbids redirects and
    never returns credential bytes.
    """
    if service not in _SERVICES or type(advertise) is not bool:
        raise ValueError("unsupported Git smart-HTTP operation")
    if type(push_authorized) is not bool:
        raise ValueError("Git push authorization must be explicit")
    if type(protocol_version) is not int or protocol_version not in {0, 1, 2}:
        raise ValueError("unsupported Git protocol version")
    if service == "git-receive-pack" and not push_authorized:
        raise PermissionError("Git receive-pack requires trusted push authorization")
    if not isinstance(body, bytes) or len(body) > _MAX_REQUEST_BYTES:
        raise ValueError("Git HTTP request exceeds size limit")
    if advertise and body:
        raise ValueError("Git advertisement must not have a request body")
    if not advertise and not body:
        raise ValueError("Git RPC needs a request body")

    host, origin = _remote_url(remote_url)
    credentials = store if store is not None else get_default_credential_store()
    auth = _authorization(scope, host, credentials)
    endpoint = (
        f"{origin}/info/refs?service={service}" if advertise else f"{origin}/{service}"
    )
    headers = {
        "Authorization": auth,
        "Accept": (
            f"application/x-{service}-advertisement"
            if advertise
            else f"application/x-{service}-result"
        ),
        "Accept-Encoding": "identity",
        "Cache-Control": "no-cache",
    }
    if protocol_version:
        headers["Git-Protocol"] = f"version={protocol_version}"
    if not advertise:
        headers["Content-Type"] = f"application/x-{service}-request"
    request = urllib.request.Request(
        endpoint,
        data=None if advertise else body,
        headers=headers,
        method="GET" if advertise else "POST",
    )
    opener = opener or _trusted_https_opener()
    try:
        with opener.open(request, timeout=30) as response:
            code = getattr(response, "status", None)
            if code != 200 or response.geturl() != endpoint:
                raise RuntimeError("Git HTTP upstream rejected request")
            expected_type = (
                f"application/x-{service}-advertisement"
                if advertise
                else f"application/x-{service}-result"
            )
            content_type = (
                response.headers.get("Content-Type", "").split(";")[0].strip().lower()
            )
            if content_type != expected_type:
                raise RuntimeError("Git HTTP upstream returned an invalid content type")
            if (
                response.headers.get("Content-Encoding", "identity").lower()
                != "identity"
            ):
                raise RuntimeError(
                    "Git HTTP upstream returned unsupported content encoding"
                )
            data = response.read(_MAX_RESPONSE_BYTES + 1)
            if len(data) > _MAX_RESPONSE_BYTES:
                raise RuntimeError("Git HTTP response exceeds size limit")
            return GitHttpResponse(content_type=content_type, body=data)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Git HTTPS remote returned HTTP {exc.code}") from None
    except urllib.error.URLError:
        raise RuntimeError("Git HTTPS transport failed") from None
