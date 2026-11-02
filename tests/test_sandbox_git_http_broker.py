"""Git HTTPS broker tests: remote binding and no credential disclosure."""

from __future__ import annotations

import base64
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
    _remote_url,
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
        scope, _REMOTE, service="git-upload-pack", advertise=True, store=store,
        opener=opener,
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
            scope, url, service="git-upload-pack", advertise=True,
            store=store, opener=opener,
        )
    assert opener.requests == []


@pytest.mark.parametrize("host", ["", "localhost", "x..y", "127.0.0.1", "a/b", "a:443", "ä.example"])
def test_invalid_registered_host_is_rejected(scope, host):
    with pytest.raises(ValueError):
        save_git_https_token(scope, "github", _TOKEN, remote_host=host,
                             store=InMemoryCredentialStore())


def test_receive_pack_requires_explicit_host_authorization(scope, store):
    opener = FakeOpener()
    with pytest.raises(PermissionError, match="push authorization"):
        exchange_git_smart_http(
            scope, _REMOTE, service="git-receive-pack", advertise=True,
            store=store, opener=opener,
        )
    assert opener.requests == []


def test_selected_credential_must_be_explicitly_bound(scope):
    store = InMemoryCredentialStore()
    save_git_https_token(scope, "legacy", _TOKEN, store=store)
    select_git_credential(scope, "user", "legacy", store=store)
    with pytest.raises(PermissionError, match="not bound"):
        exchange_git_smart_http(
            scope, _REMOTE, service="git-upload-pack", advertise=True,
            store=store, opener=FakeOpener(),
        )


def test_never_fallback_to_other_principal_or_realm(scope, store):
    other = TrustedSandboxScope(
        "web", scope.principal_id, "project", "web-room", "room",
        settings_session_id="room",
    )
    with pytest.raises(PermissionError, match="not selected"):
        exchange_git_smart_http(
            other, _REMOTE, service="git-upload-pack", advertise=True,
            store=store, opener=FakeOpener(),
        )


def test_reject_redirect_without_leaking_credentials(scope, store):
    opener = FakeOpener(
        error=HTTPError(
            _REMOTE, 302, "Redirect", {"Location": "https://attacker.example"},
            None,
        )
    )
    with pytest.raises(RuntimeError, match="HTTP 302") as exc:
        exchange_git_smart_http(
            scope, _REMOTE, service="git-upload-pack", advertise=True,
            store=store, opener=opener,
        )
    assert _TOKEN not in str(exc.value)


def test_unexpected_content_type_and_redirected_url_are_rejected(scope, store):
    with pytest.raises(RuntimeError, match="content type"):
        exchange_git_smart_http(
            scope, _REMOTE, service="git-upload-pack", advertise=True,
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
            scope, _REMOTE, service="git-upload-pack", advertise=True,
            store=store,
            opener=FakeOpener(
                FakeResponse(url="https://attacker.example/collect")
            ),
        )


def test_request_types_size_and_services_are_validated(scope, store):
    for parameters in (
        dict(service="https", advertise=True),
        dict(service="git-upload-pack", advertise=False),
        dict(service="git-upload-pack", advertise=True, body=b"unexpected"),
        dict(service="git-upload-pack", advertise=False, body=b"x" * (16 * 1024 * 1024 + 1)),
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
            scope, _REMOTE, service="git-upload-pack", advertise=True,
            store=store, opener=opener,
        )


def test_validate_git_remote_and_host_canonicalization():
    assert validate_git_host("GITHUB.com") == "github.com"
    assert _remote_url("https://github.com/acme/repo.git") == (
        "github.com", "https://github.com/acme/repo.git"
    )
