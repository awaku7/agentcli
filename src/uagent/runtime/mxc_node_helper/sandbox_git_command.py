"""Git command wrapper and in-Sandbox mailbox for the read-only host broker.

The mailbox is entirely inside the isolated MXC process. The trusted Node
adapter only relays JSON on the existing process stdio; it never opens
Sandbox-controlled paths and never passes authentication secrets in frames.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

_REQUEST = re.compile(r"[0-9]{6}\.req\Z")
_MAX_FRAME = 180_000


def _launcher(directory: Path, python_exe: str, helper_script: str) -> None:
    if os.name == "nt":
        # Command file is only a launcher for the trusted, immutable helper;
        # it contains no token or host credential.
        launcher = directory / "git-remote-uag.cmd"
        if any(char in python_exe + helper_script for char in "\r\n%\""):
            raise ValueError("unsafe Git helper launcher path")
        launcher.write_text(
            f'@echo off\r\n"{python_exe}" -I -u "{helper_script}" %*\r\n',
            encoding="utf-8",
        )
    else:
        launcher = directory / "git-remote-uag"
        launcher.write_text(
            "#!/bin/sh\nexec "
            + shlex.quote(python_exe)
            + " -I -u "
            + shlex.quote(helper_script)
            + ' "$@"\n',
            encoding="utf-8",
        )
        launcher.chmod(0o700)


def _relay(mailbox: Path, marker: str, stop: threading.Event) -> None:
    """Forward read-only JSON frames via the isolated root process pipes."""
    while not stop.is_set():
        for request in sorted(mailbox.glob("*.req")):
            if not _REQUEST.fullmatch(request.name):
                continue
            if request.is_symlink() or request.stat().st_size > _MAX_FRAME:
                raise RuntimeError("unsafe or oversized Git bridge request")
            frame = json.loads(request.read_text(encoding="ascii"))
            if not isinstance(frame, dict) or frame.get("bridge") != "git_http":
                raise RuntimeError("invalid Git bridge request")
            # Only the trusted Node adapter recognizes this random per-call
            # marker; the command's regular stdout is forwarded unchanged.
            sys.stdout.write(marker + " " + json.dumps(frame, separators=(",", ":")) + "\n")
            sys.stdout.flush()
            answer = sys.stdin.buffer.readline(_MAX_FRAME + 1)
            if not answer or len(answer) > _MAX_FRAME:
                raise RuntimeError("Git bridge host response is missing or oversized")
            response = json.loads(answer)
            if not isinstance(response, dict) or response.get("bridge") != "git_http":
                raise RuntimeError("invalid Git bridge host response")
            target = request.with_suffix(".resp")
            temporary = request.with_suffix(".answer-tmp")
            temporary.write_text(
                json.dumps(response, separators=(",", ":")), encoding="ascii"
            )
            os.replace(temporary, target)
            request.unlink(missing_ok=True)
        time.sleep(0.005)


def execute(
    argv: list[str],
    cwd: str,
    host: str,
    helper_script: str,
    python_exe: str,
    marker: str,
) -> int:
    """Run Git with URL rewriting only for the user's bound HTTPS host."""
    if not argv or Path(argv[0]).name.lower() not in {"git", "git.exe"}:
        raise ValueError("Git bridge can only run a Git executable")
    if not re.fullmatch(r"[a-z0-9.-]{1,253}", host):
        raise ValueError("invalid trusted Git remote hostname")
    if not re.fullmatch(r"__UAG_GIT_BRIDGE_[0-9a-f]{32}__", marker):
        raise ValueError("invalid trusted Git frame marker")
    workspace = Path(cwd).resolve()
    with tempfile.TemporaryDirectory(prefix=".uag-git-", dir=workspace) as name:
        mailbox = Path(name)
        _launcher(mailbox, python_exe, helper_script)
        env = dict(os.environ)
        env["UAG_GIT_BRIDGE_DIR"] = str(mailbox)
        env["PATH"] = str(mailbox) + os.pathsep + env.get("PATH", "")
        # Git still uses its standard HTTPS URL externally. Only Git's own
        # transport selection switches the selected host to git-remote-uag.
        env["GIT_CONFIG_COUNT"] = "2"
        env["GIT_CONFIG_KEY_0"] = f"url.uag::https://{host}/.insteadOf"
        env["GIT_CONFIG_VALUE_0"] = f"https://{host}/"
        env["GIT_CONFIG_KEY_1"] = "protocol.version"
        env["GIT_CONFIG_VALUE_1"] = "2"
        stop = threading.Event()
        errors: list[BaseException] = []

        def relay() -> None:
            try:
                _relay(mailbox, marker, stop)
            except BaseException as exc:
                errors.append(exc)
                stop.set()

        thread = threading.Thread(target=relay, name="mxc-git-bridge", daemon=True)
        thread.start()
        try:
            process = subprocess.run(
                argv,
                cwd=workspace,
                env=env,
                stdin=subprocess.DEVNULL,
                timeout=25,
                check=False,
            )
        except subprocess.TimeoutExpired:
            print("Git command exceeded its MXC execution deadline", file=sys.stderr)
            return 124
        except OSError as exc:
            print(f"Git command could not start: {type(exc).__name__}", file=sys.stderr)
            return 127
        finally:
            stop.set()
            thread.join(timeout=0.5)
        if errors:
            raise RuntimeError("Git bridge failed while relaying a request") from errors[0]
        return process.returncode
