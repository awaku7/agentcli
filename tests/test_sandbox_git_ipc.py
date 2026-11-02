"""Git host IPC must remain bounded, scope-locked and read-only."""

from __future__ import annotations

import base64

import pytest

from uagent.runtime.execution_broker import TrustedSandboxScope
from uagent.runtime.sandbox_git_http_broker import GitHttpResponse
from uagent.runtime.sandbox_git_ipc import GitHttpIPC

_REMOTE = "https://github.com/org/repo.git"


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


def _begin(*, service="git-upload-pack", advertise=False, version=0):
    return {
        "bridge": "git_http",
        "op": "begin",
        "remote_url": _REMOTE,
        "service": service,
        "advertise": advertise,
        "protocol_version": version,
    }


def _frame(op, **extra):
    return {"bridge": "git_http", "op": op, **extra}


def test_git_ipc_uses_trusted_scope_and_streams_binary(scope):
    captured = []
    content = bytes(range(256)) * 1500

    def exchange(received_scope, remote, **kwargs):
        captured.append((received_scope, remote, kwargs))
        return GitHttpResponse(
            content_type="application/x-git-upload-pack-result",
            body=content,
        )

    broker = GitHttpIPC(scope, revoked=lambda: False, exchange=exchange)
    assert broker.handle(_begin(version=2)) == _frame("ready")
    request_body = b"abcd\x00\xff" * 64
    assert broker.handle(
        _frame("body", data=base64.b64encode(request_body).decode("ascii"))
    ) == _frame("ready")
    meta = broker.handle(_frame("execute"))
    assert meta == {
        "bridge": "git_http",
        "op": "response",
        "content_type": "application/x-git-upload-pack-result",
        "length": len(content),
    }
    result = bytearray()
    while True:
        piece = broker.handle(_frame("next"))
        assert len(piece["data"]) <= 175000
        result.extend(base64.b64decode(piece["data"], validate=True))
        if piece["done"]:
            break
    assert bytes(result) == content
    assert captured == [
        (
            scope,
            _REMOTE,
            {
                "service": "git-upload-pack",
                "advertise": False,
                "protocol_version": 2,
                "body": request_body,
            },
        )
    ]
    assert broker.handle(_begin(advertise=True)) == _frame("ready")


def test_git_ipc_denies_receive_pack_without_host_approval(scope):
    broker = GitHttpIPC(scope, revoked=lambda: False)
    with pytest.raises(PermissionError, match="receive-pack"):
        broker.handle(_begin(service="git-receive-pack"))


def test_git_ipc_checks_revocation_before_each_frame(scope):
    flag = {"revoked": False}
    broker = GitHttpIPC(scope, revoked=lambda: flag["revoked"])
    assert broker.handle(_begin()) == _frame("ready")
    flag["revoked"] = True
    with pytest.raises(PermissionError, match="revoked"):
        broker.handle(_frame("execute"))


@pytest.mark.parametrize(
    "invalid",
    [
        _frame("execute"),
        _frame("next"),
        _begin(version=3),
        _begin(version=True),
        _begin(service="git-receive-pack"),
        {**_begin(), "secret": "untrusted"},
        {"bridge": "other", "op": "begin"},
        "git_http",
    ],
)
def test_git_ipc_rejects_unsolicited_or_malformed_frames(scope, invalid):
    broker = GitHttpIPC(scope, revoked=lambda: False)
    with pytest.raises((ValueError, PermissionError)):
        broker.handle(invalid)


def test_git_ipc_rejects_bad_request_chunk_and_oversized_data(scope):
    broker = GitHttpIPC(scope, revoked=lambda: False)
    broker.handle(_begin())
    with pytest.raises(ValueError, match="base64"):
        broker.handle(_frame("body", data="?not base64?"))
    with pytest.raises(ValueError, match="large"):
        broker.handle(_frame("body", data=base64.b64encode(b"x" * 131073).decode()))
    assert broker.handle(_frame("abort")) == _frame("aborted")


def test_git_ipc_rejects_interleaved_exchanges(scope):
    broker = GitHttpIPC(scope, revoked=lambda: False)
    broker.handle(_begin())
    with pytest.raises(ValueError, match="active"):
        broker.handle(_begin())


def test_git_ipc_rejects_oversized_or_unexpected_response(scope):
    broker = GitHttpIPC(
        scope,
        revoked=lambda: False,
        exchange=lambda *_a, **_k: GitHttpResponse(
            content_type="x",
            body=b"x" * (64 * 1024 * 1024 + 1),
        ),
    )
    broker.handle(_begin(advertise=True))
    with pytest.raises(ValueError, match="budget"):
        broker.handle(_frame("execute"))


def test_git_ipc_never_receives_model_selected_scope(scope):
    with pytest.raises(TypeError):
        GitHttpIPC("model-supplied-principal", revoked=lambda: False)
