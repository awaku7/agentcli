"""Real Git protocol-v2 clone/fetch through the isolated remote-helper bridge.

A local Git upload-pack process stands in for the trusted HTTP server, so
the test needs neither network access nor a credential and proves the Git
client can consume the byte-for-byte IPC transport.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from uagent.runtime.execution_broker import TrustedSandboxScope
from uagent.runtime.sandbox_git_http_broker import GitHttpResponse
from uagent.runtime.sandbox_git_ipc import GitHttpIPC

_HELPERS = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "uagent"
    / "runtime"
    / "mxc_node_helper"
)
_REMOTE = "https://example.com/team/repo.git"
_MARKER = "__UAG_GIT_BRIDGE_0123456789abcdef0123456789abcdef__"


def _git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )


def _repository(tmp_path: Path) -> Path:
    repository = tmp_path / "server"
    repository.mkdir()
    _git("init", "--initial-branch=main", str(repository))
    (repository / "test.txt").write_text("first\n", encoding="utf-8")
    _git("add", "test.txt", cwd=repository)
    _git(
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.org",
        "commit",
        "-m",
        "First",
        cwd=repository,
    )
    return repository


def _bridge_git(
    directory: Path,
    repository: Path,
    argv: list[str],
) -> subprocess.CompletedProcess:
    scope = TrustedSandboxScope(
        "cli",
        "os-uid:42",
        "project",
        "cli-session",
        "test",
        settings_session_id="test",
    )
    operations = []

    def exchange(_scope, remote, **kwargs):
        assert _scope == scope
        assert remote == _REMOTE
        assert kwargs["service"] == "git-upload-pack"
        assert kwargs["protocol_version"] == 2
        operations.append(kwargs["advertise"])
        env = dict(os.environ, GIT_PROTOCOL="version=2")
        if kwargs["advertise"]:
            response = subprocess.run(
                [
                    "git",
                    "upload-pack",
                    "--stateless-rpc",
                    "--advertise-refs",
                    str(repository),
                ],
                env=env,
                capture_output=True,
                check=True,
            ).stdout
            data = response
            content_type = "application/x-git-upload-pack-advertisement"
        else:
            response = subprocess.run(
                ["git", "upload-pack", "--stateless-rpc", str(repository)],
                env=env,
                input=kwargs["body"],
                capture_output=True,
                check=True,
            )
            data = response.stdout
            content_type = "application/x-git-upload-pack-result"
        return GitHttpResponse(content_type, data)

    ipc = GitHttpIPC(scope, revoked=lambda: False, exchange=exchange)
    helper_script = _HELPERS / "sandbox_git_remote_helper.py"
    script = (
        "import sys\n"
        f"sys.path.insert(0, {str(_HELPERS)!r})\n"
        "from sandbox_git_command import execute\n"
        f"raise SystemExit(execute({argv!r}, {str(directory)!r}, "
        f"'example.com', {str(helper_script)!r}, {sys.executable!r}, "
        f"{_MARKER!r}))\n"
    )
    proc = subprocess.Popen(
        [sys.executable, "-I", "-u", "-c", script],
        cwd=directory,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )
    assert proc.stdin is not None and proc.stdout is not None
    try:
        for line in proc.stdout:
            if not line.startswith(_MARKER + " "):
                continue
            request = json.loads(line[len(_MARKER) + 1 :])
            response = ipc.handle(request)
            proc.stdin.write(json.dumps(response) + "\n")
            proc.stdin.flush()
        result = proc.wait(timeout=20)
        error = proc.stderr.read() if proc.stderr else ""
        assert result == 0, error
        assert ipc.is_idle
        assert operations and operations[0] is True
        return subprocess.CompletedProcess(argv, result, stderr=error)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
        proc.stdin.close()
        proc.stdout.close()
        if proc.stderr:
            proc.stderr.close()


@pytest.mark.skipif(shutil.which("git") is None, reason="Git not installed")
def test_git_https_clone_and_fetch_over_isolated_bridge(tmp_path):
    server = _repository(tmp_path)
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    _bridge_git(
        sandbox,
        server,
        ["git", "clone", _REMOTE, "checkout"],
    )
    checkout = sandbox / "checkout"
    assert (checkout / "test.txt").read_text(encoding="utf-8") == "first\n"
    assert _git("remote", "get-url", "origin", cwd=checkout).stdout.strip() == _REMOTE

    (server / "test.txt").write_text("second\n", encoding="utf-8")
    _git("add", "test.txt", cwd=server)
    _git(
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.org",
        "commit",
        "-m",
        "Second",
        cwd=server,
    )
    _bridge_git(sandbox, server, ["git", "-C", "checkout", "fetch", "origin"])
    head = _git("rev-parse", "origin/main", cwd=checkout).stdout.strip()
    server_head = _git("rev-parse", "main", cwd=server).stdout.strip()
    assert head == server_head

    # Git may start multiple upload-pack helpers concurrently. They share the
    # command's host GitHttpIPC, so the isolated helpers must serialize.
    _git("remote", "add", "backup", _REMOTE, cwd=checkout)
    _bridge_git(
        sandbox, server, ["git", "-C", "checkout", "fetch", "--all", "--jobs=2"]
    )


def test_mxc_node_adapter_relays_git_frames_without_host_file_reads():
    node = shutil.which("node")
    helper = _HELPERS / "mxc_adapter.mjs"
    source = helper.read_text(encoding="utf-8")
    assert "createHostLineQueue" in source
    assert "nextHostLine(30_000)" in source
    assert "gitBridgeMarker" in source
    assert "sandbox_git_remote_helper.py" in source
    if node:
        subprocess.run([node, "--check", str(helper)], check=True, capture_output=True)



def test_mxc_host_line_queue_has_no_idle_deadline():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is not installed")
    source = (_HELPERS / "mxc_adapter.mjs").read_text(encoding="utf-8")
    begin = source.index("function createHostLineQueue(lines) {")
    end = source.index("function quoteWindowsArgument(value) {", begin)
    js = source[begin:end] + """
const { EventEmitter } = require("node:events");
const lines = new EventEmitter();
const next = createHostLineQueue(lines);
const message = next();
lines.emit("line", '{"operation":"run"}');
message.then((value) => {
  if (value !== '{"operation":"run"}') process.exitCode = 1;
});
"""
    # A regular idle read must not schedule any timer at all.
    script = """
const vm = require("node:vm");
const context = {
  require,
  setTimeout() { throw new Error("idle host input scheduled a timeout"); },
  clearTimeout() {},
  Promise,
};
vm.runInNewContext(process.env.UAG_HOST_QUEUE_TEST, context);
"""
    subprocess.run(
        [node, "-e", script],
        env=dict(os.environ, UAG_HOST_QUEUE_TEST=js),
        check=True,
        capture_output=True,
        timeout=8,
    )
