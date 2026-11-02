"""Trusted-host Git smart-HTTP transport with scope-bound credentials.

The caller must be the MXC host broker, after checking an active and authorized
TrustedSandboxScope. Nothing in this module runs in the untrusted Sandbox.
The Git transport IPC will use this primitive; it is not an LLM tool.
"""

from __future__ import annotations

import base64
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlsplit

from ..auth.credential_store import CredentialKind, CredentialStore, get_default_credential_store
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
    return normalized


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


def _authorization(scope: TrustedSandboxScope, host: str, store: CredentialStore) -> str:
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
) -> GitHttpResponse:
    """Perform exactly one authenticated Git smart-HTTP request.

    The host caller is responsible for authorizing the live scope and Git
    operation; this function validates the remote bound to the selected
    credential, does not follow redirects and never returns credential bytes.
    """
    if service not in _SERVICES or type(advertise) is not bool:
        raise ValueError("unsupported Git smart-HTTP operation")
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
        f"{origin}/info/refs?service={service}"
        if advertise
        else f"{origin}/{service}"
    )
    headers = {
        "Authorization": auth,
        "Accept": f"application/x-{service}-advertisement"
        if advertise
        else f"application/x-{service}-result",
        "Accept-Encoding": "identity",
        "Cache-Control": "no-cache",
    }
    if service == "git-upload-pack":
        headers["Git-Protocol"] = "version=2"
    if not advertise:
        headers["Content-Type"] = f"application/x-{service}-request"
    request = urllib.request.Request(
        endpoint,
        data=None if advertise else body,
        headers=headers,
        method="GET" if advertise else "POST",
    )
    opener = opener or urllib.request.build_opener(_NoRedirect())
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
            content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if content_type != expected_type:
                raise RuntimeError("Git HTTP upstream returned an invalid content type")
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise RuntimeError("Git HTTP upstream returned unsupported content encoding")
            data = response.read(_MAX_RESPONSE_BYTES + 1)
            if len(data) > _MAX_RESPONSE_BYTES:
                raise RuntimeError("Git HTTP response exceeds size limit")
            return GitHttpResponse(content_type=content_type, body=data)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Git HTTPS remote returned HTTP {exc.code}") from None
    except urllib.error.URLError:
        raise RuntimeError("Git HTTPS transport failed") from None
