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


def test_git_ipc_rechecks_revocation_after_blocking_http(scope):
    state = {"revoked": False}

    def exchange(*_args, **_kwargs):
        state["revoked"] = True
        return GitHttpResponse("application/x-git-upload-pack-advertisement", b"0000")

    broker = GitHttpIPC(
        scope,
        revoked=lambda: state["revoked"],
        exchange=exchange,
    )
    broker.handle(_begin(advertise=True))
    with pytest.raises(PermissionError, match="revoked"):
        broker.handle(_frame("execute"))


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
    with pytest.raises(ValueError, match="budget"):
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


def test_mxc_command_execution_forwards_git_frames_to_host(monkeypatch, scope):
    import json
    import threading

    from uagent.runtime import mxc_backend, sandbox_git_ipc

    session = object.__new__(mxc_backend._MxcSession)
    session._scope = scope
    session._lock = threading.RLock()
    session._revoked = threading.Event()
    session._mac_scope = None
    received = [
        {"bridge": "git_http", "op": "begin"},
        {"ok": True, "result": {"returncode": 0, "stdout": "ok"}},
    ]
    sent = []
    session._write_line = sent.append
    session._read_response = lambda **kwargs: received.pop(0)

    class StubGitIPC:
        def __init__(self, received_scope, *, revoked, deadline=None):
            assert received_scope == scope
            assert not revoked()
            self.is_idle = True

        def handle(self, frame):
            assert frame == {"bridge": "git_http", "op": "begin"}
            return {"bridge": "git_http", "op": "ready"}

    monkeypatch.setattr(sandbox_git_ipc, "GitHttpIPC", StubGitIPC)
    result = session.run("command_exec", {"argv": ["git", "--version"]})
    assert json.loads(result)["stdout"] == "ok"
    assert sent[0]["payload"]["name"] == "command_exec"
    assert sent[1] == {"bridge": "git_http", "op": "ready"}


def test_mxc_command_rejects_incomplete_git_exchange(monkeypatch, scope):
    import threading

    from uagent.runtime import mxc_backend, sandbox_git_ipc

    session = object.__new__(mxc_backend._MxcSession)
    session._scope = scope
    session._lock = threading.RLock()
    session._revoked = threading.Event()
    session._mac_scope = None
    session._write_line = lambda _message: None
    incoming = [
        _begin(advertise=True),
        {"ok": True, "result": {"returncode": 0}},
    ]
    session._read_response = lambda **_kwargs: incoming.pop(0)
    closed = []
    session.close = lambda: closed.append(True)

    class NoNetworkGitIPC(GitHttpIPC):
        def __init__(self, received_scope, *, revoked):
            super().__init__(
                received_scope,
                revoked=revoked,
                exchange=lambda *_args, **_kwargs: GitHttpResponse(
                    "application/x-git-upload-pack-advertisement", b"0000"
                ),
            )

    monkeypatch.setattr(sandbox_git_ipc, "GitHttpIPC", NoNetworkGitIPC)
    with pytest.raises(ValueError, match="before completion"):
        session.run("command_exec", {"argv": ["git", "--version"]})
    assert session._revoked.is_set()
    assert closed
