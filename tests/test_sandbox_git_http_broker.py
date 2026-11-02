"""Git HTTPS broker tests: remote binding and no credential disclosure."""

from __future__ import annotations

import base64
import socket
import ssl
from io import BytesIO
from urllib.error import HTTPError

import pytest

from uagent.auth.credential_store import InMemoryCredentialStore
from uagent.runtime.execution_broker import TrustedSandboxScope
from uagent.runtime.sandbox_git_credentials import (
    save_git_https_token,
    select_git_credential,
)
from uagent.runtime.sandbox_git_http_broker import (
    _PinnedHTTPSConnection,
    _PinnedHTTPSHandler,
    _remote_url,
    _trusted_https_opener,
    _trusted_ssl_context,
    exchange_git_smart_http,
    validate_git_host,
)

_REMOTE = "https://github.com/acme/private.git"
_TOKEN = "SECRET-not-for-sandbox"


@pytest.fixture
def scope():
    return TrustedSandboxScope(
        "cli",
        "os-uid:42",
        "project",
        "cli-session",
        "session",
        settings_session_id="session",
    )


@pytest.fixture
def store(scope):
    store = InMemoryCredentialStore()
    save_git_https_token(
        scope,
        "github",
        _TOKEN,
        remote_host="github.com",
        store=store,
    )
    select_git_credential(scope, "user", "github", store=store)
    return store


class FakeResponse:
    def __init__(
        self,
        *,
        url,
        body=b"0000",
        status=200,
        content_type="application/x-git-upload-pack-advertisement",
        encoding="identity",
    ):
        self.url = url
        self.status = status
        self.headers = {
            "Content-Type": content_type,
            "Content-Encoding": encoding,
        }
        self.stream = BytesIO(body)

    def geturl(self):
        return self.url

    def read(self, length):
        return self.stream.read(length)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeOpener:
    def __init__(self, response=None, error=None):
        self.requests = []
        self.response = response
        self.error = error

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        if self.error is not None:
            raise self.error
        return self.response or FakeResponse(url=request.full_url)


def test_advertisement_uses_scoped_https_header_without_exposing_secret(scope, store):
    opener = FakeOpener()
    result = exchange_git_smart_http(
        scope,
        _REMOTE,
        service="git-upload-pack",
        advertise=True,
        store=store,
        opener=opener,
        protocol_version=2,
    )
    request, timeout = opener.requests[0]
    assert request.get_method() == "GET"
    assert request.full_url == _REMOTE + "/info/refs?service=git-upload-pack"
    assert timeout == 30
    assert request.get_header("Git-protocol") == "version=2"
    assert request.get_header("Authorization") == "Basic " + base64.b64encode(
        f"x-access-token:{_TOKEN}".encode("utf-8")
    ).decode("ascii")
    assert result.body == b"0000"
    assert _TOKEN not in repr(result)


def test_push_rpc_uses_post_and_does_not_inject_git_protocol_v2(scope, store):
    payload = b"0123abc0000"
    response = FakeResponse(
        url=_REMOTE + "/git-receive-pack",
        body=b"0000",
        content_type="application/x-git-receive-pack-result",
    )
    opener = FakeOpener(response)
    result = exchange_git_smart_http(
        scope,
        _REMOTE,
        service="git-receive-pack",
        advertise=False,
        body=payload,
        opener=opener,
        store=store,
        push_authorized=True,
    )
    request, _ = opener.requests[0]
    assert request.get_method() == "POST"
    assert request.data == payload
    assert request.get_header("Git-protocol") is None
    assert result.body == b"0000"


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/acme/private.git",
        "https://github.com.evil.example/acme/private.git",
        "https://alice:secret@github.com/acme/private.git",
        "https://github.com:444/acme/private.git",
        "https://github.com/acme/private.git#fragment",
        "https://github.com/acme/private.git?query=1",
        "https://github.com/acme/../private.git",
        "https://github.com/acme/%2e%2e/private.git",
        "https://localhost/acme/private.git",
        "https://127.0.0.1/acme/private.git",
        "https://github.com/",
        "file:///etc/passwd",
    ],
)
def test_invalid_or_mismatched_remotes_fail_without_network(scope, store, url):
    opener = FakeOpener()
    with pytest.raises((ValueError, PermissionError)):
        exchange_git_smart_http(
            scope,
            url,
            service="git-upload-pack",
            advertise=True,
            store=store,
            opener=opener,
        )
    assert opener.requests == []


@pytest.mark.parametrize(
    "host", ["", "localhost", "x..y", "127.0.0.1", "a/b", "a:443", "ä.example"]
)
def test_invalid_registered_host_is_rejected(scope, host):
    with pytest.raises(ValueError):
        save_git_https_token(
            scope, "github", _TOKEN, remote_host=host, store=InMemoryCredentialStore()
        )


def test_receive_pack_requires_explicit_host_authorization(scope, store):
    opener = FakeOpener()
    with pytest.raises(PermissionError, match="push authorization"):
        exchange_git_smart_http(
            scope,
            _REMOTE,
            service="git-receive-pack",
            advertise=True,
            store=store,
            opener=opener,
        )
    assert opener.requests == []


def test_selected_credential_must_be_explicitly_bound(scope):
    store = InMemoryCredentialStore()
    save_git_https_token(scope, "legacy", _TOKEN, store=store)
    select_git_credential(scope, "user", "legacy", store=store)
    with pytest.raises(PermissionError, match="not bound"):
        exchange_git_smart_http(
            scope,
            _REMOTE,
            service="git-upload-pack",
            advertise=True,
            store=store,
            opener=FakeOpener(),
        )


def test_never_fallback_to_other_principal_or_realm(scope, store):
    other = TrustedSandboxScope(
        "web",
        scope.principal_id,
        "project",
        "web-room",
        "room",
        settings_session_id="room",
    )
    with pytest.raises(PermissionError, match="not selected"):
        exchange_git_smart_http(
            other,
            _REMOTE,
            service="git-upload-pack",
            advertise=True,
            store=store,
            opener=FakeOpener(),
        )


def test_reject_redirect_without_leaking_credentials(scope, store):
    opener = FakeOpener(
        error=HTTPError(
            _REMOTE,
            302,
            "Redirect",
            {"Location": "https://attacker.example"},
            None,
        )
    )
    with pytest.raises(RuntimeError, match="HTTP 302") as exc:
        exchange_git_smart_http(
            scope,
            _REMOTE,
            service="git-upload-pack",
            advertise=True,
            store=store,
            opener=opener,
        )
    assert _TOKEN not in str(exc.value)


def test_unexpected_content_type_and_redirected_url_are_rejected(scope, store):
    with pytest.raises(RuntimeError, match="content type"):
        exchange_git_smart_http(
            scope,
            _REMOTE,
            service="git-upload-pack",
            advertise=True,
            store=store,
            opener=FakeOpener(
                FakeResponse(
                    url=_REMOTE + "/info/refs?service=git-upload-pack",
                    content_type="text/html",
                )
            ),
        )
    with pytest.raises(RuntimeError, match="rejected request"):
        exchange_git_smart_http(
            scope,
            _REMOTE,
            service="git-upload-pack",
            advertise=True,
            store=store,
            opener=FakeOpener(FakeResponse(url="https://attacker.example/collect")),
        )


def test_request_types_size_and_services_are_validated(scope, store):
    for parameters in (
        dict(service="https", advertise=True),
        dict(service="git-upload-pack", advertise=False),
        dict(service="git-upload-pack", advertise=True, body=b"unexpected"),
        dict(
            service="git-upload-pack",
            advertise=False,
            body=b"x" * (16 * 1024 * 1024 + 1),
        ),
    ):
        opener = FakeOpener()
        with pytest.raises(ValueError):
            exchange_git_smart_http(
                scope, _REMOTE, store=store, opener=opener, **parameters
            )
        assert not opener.requests


def test_reject_oversized_git_response(scope, store):
    opener = FakeOpener(
        FakeResponse(
            url=_REMOTE + "/info/refs?service=git-upload-pack",
            body=b"a" * (64 * 1024 * 1024 + 1),
        )
    )
    with pytest.raises(RuntimeError, match="size limit"):
        exchange_git_smart_http(
            scope,
            _REMOTE,
            service="git-upload-pack",
            advertise=True,
            store=store,
            opener=opener,
        )


def test_protocol_v0_does_not_claim_version_2(scope, store):
    opener = FakeOpener()
    exchange_git_smart_http(
        scope,
        _REMOTE,
        service="git-upload-pack",
        advertise=True,
        store=store,
        opener=opener,
        protocol_version=0,
    )
    assert opener.requests[0][0].get_header("Git-protocol") is None
    opener.requests.clear()
    exchange_git_smart_http(
        scope,
        _REMOTE,
        service="git-upload-pack",
        advertise=True,
        store=store,
        opener=opener,
        protocol_version=1,
    )
    assert opener.requests[0][0].get_header("Git-protocol") == "version=1"
    with pytest.raises(ValueError, match="protocol"):
        exchange_git_smart_http(
            scope,
            _REMOTE,
            service="git-upload-pack",
            advertise=True,
            store=store,
            opener=opener,
            protocol_version=3,
        )


@pytest.mark.parametrize(
    "sockaddrs",
    [
        [("127.0.0.1", 443)],
        [("::1", 443)],
        [("::ffff:127.0.0.1", 443)],
        [("169.254.169.254", 443)],
        [("203.0.113.10", 443), ("127.0.0.1", 443)],
    ],
)
def test_pinned_https_rejects_local_destinations_before_socket_creation(
    monkeypatch, sockaddrs
):
    from uagent.runtime import sandbox_git_http_broker as broker

    monkeypatch.setattr(
        broker.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (
                socket.AF_INET6 if ":" in address else socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                (address, port),
            )
            for address, port in sockaddrs
        ],
    )
    opened = []
    monkeypatch.setattr(broker.socket, "socket", lambda *args: opened.append(args))
    connection = _PinnedHTTPSConnection("github.com", timeout=1)
    with pytest.raises(PermissionError, match="not permitted"):
        connection.connect()
    assert opened == []


def test_pinned_https_connects_to_validated_ip_without_reresolution(monkeypatch):
    from uagent.runtime import sandbox_git_http_broker as broker

    events = []

    def resolve(*args, **kwargs):
        events.append("dns")
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("203.0.113.11", 443),
            )
        ]

    class FakeSocket:
        def settimeout(self, timeout):
            events.append(("timeout", timeout))

        def connect(self, sockaddr):
            events.append(("connect", sockaddr))

        def close(self):
            events.append("close")

    class FakeContext:
        def wrap_socket(self, sock, server_hostname):
            events.append(("sni", server_hostname))
            return sock

    monkeypatch.setattr(broker.socket, "getaddrinfo", resolve)
    monkeypatch.setattr(broker.socket, "socket", lambda *args: FakeSocket())
    connection = _PinnedHTTPSConnection("github.com", timeout=2)
    connection._context = FakeContext()
    connection.connect()
    assert events == [
        "dns",
        ("timeout", 2),
        ("connect", ("203.0.113.11", 443)),
        ("sni", "github.com"),
    ]


def test_default_https_opener_disables_implicit_proxy(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://attacker.example:8080")
    opener = _trusted_https_opener()
    # An empty ProxyHandler is intentionally not retained by build_opener.
    # The absence of any proxy_open handler confirms no implicit proxy path.
    assert not any(hasattr(handler, "proxy_open") for handler in opener.handlers)


def test_project_ssl_cert_file_cannot_override_system_trust(monkeypatch, tmp_path):
    custom_ca = tmp_path / "untrusted-ca.pem"
    custom_ca.write_text("not a valid CA certificate", encoding="ascii")
    monkeypatch.setenv("SSL_CERT_FILE", str(custom_ca))
    monkeypatch.setenv("SSL_CERT_DIR", str(tmp_path))
    context = _trusted_ssl_context()
    assert context.check_hostname
    assert context.verify_mode == ssl.CERT_REQUIRED


def test_https_handler_does_not_pass_removed_python314_keyword(monkeypatch):
    context = object()
    handler = _PinnedHTTPSHandler(context=context)
    captured = []
    monkeypatch.setattr(
        handler,
        "do_open",
        lambda connection, request, **options: captured.append(options),
    )
    handler.https_open(object())
    assert captured == [{"context": context}]


def test_socket_deadline_stops_trickling_response_reads(monkeypatch):
    from uagent.runtime import sandbox_git_http_broker as broker

    now = {"time": 10.0}
    monkeypatch.setattr(broker.time, "monotonic", lambda: now["time"])

    class FakeSocket:
        def __init__(self):
            self.timeouts = []
            self.read_count = 0

        def settimeout(self, seconds):
            self.timeouts.append(seconds)

        def recv_into(self, buffer):
            self.read_count += 1
            buffer[0] = 1
            return 1

    connection = _PinnedHTTPSConnection("github.com", timeout=30)
    connection._uag_deadline = 13.0
    connection.sock = FakeSocket()
    connection._install_deadline_guards()
    assert connection.sock.recv_into(bytearray(1)) == 1
    assert connection.sock.timeouts == [3.0]
    now["time"] = 12.5
    assert connection.sock.recv_into(bytearray(1)) == 1
    assert connection.sock.timeouts[-1] == 0.5
    now["time"] = 13.0
    with pytest.raises(TimeoutError, match="deadline"):
        connection.sock.recv_into(bytearray(1))
    assert connection.sock.read_count == 2


def test_dns_resolution_has_absolute_deadline(monkeypatch):
    import time as realtime

    from uagent.runtime import sandbox_git_http_broker as broker

    def slow_resolver(*_args, **_kwargs):
        realtime.sleep(0.1)
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP,
                 "", ("203.0.113.10", 443))]

    monkeypatch.setattr(broker.socket, "getaddrinfo", slow_resolver)
    with pytest.raises(TimeoutError, match="DNS deadline"):
        broker._resolve_git_addresses(
            "github.com",
            443,
            deadline=realtime.monotonic() + 0.01,
        )


def test_validate_git_remote_and_host_canonicalization():
    assert validate_git_host("GITHUB.com") == "github.com"
    assert _remote_url("https://github.com/acme/repo.git") == (
        "github.com",
        "https://github.com/acme/repo.git",
    )
