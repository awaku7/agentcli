"""Windows x64 MXC ProcessContainer adapter for explicitly opted-in local sessions.

This adapter is deliberately unavailable to Remote profiles.  The SDK and the
persistent worker protocol stay behind this module; tool functions receive only
plain JSON-like values and strings.
"""

from __future__ import annotations

import atexit
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from queue import Empty, Queue
from typing import Any

from .execution_broker import (
    IsolationLevel,
    SandboxCapabilities,
    SandboxCapability,
    TrustedSandboxScope,
)

SDK_VERSION = "1.0.0"
NODE_MINIMUM = (24, 21, 0)
PROBE_TIMEOUT_SECONDS = 15
MAX_FRAME_BYTES = 1_100_000
MAX_STDERR_BYTES = 16_384
JOB_MEMORY_LIMIT_BYTES = 1_073_741_824
JOB_PROCESS_LIMIT = 64
MAX_ACTIVE_SESSIONS = 4
JOB_USER_TIME_LIMIT_100NS = 4 * 60 * 60 * 10_000_000
_PROCESS_SCOPE_NONCE = uuid.uuid4().hex

TOOL_NAMES = frozenset({"create_file", "file_exists", "read_file", "python_exec"})

# Static schemas prevent a sandbox-enabled turn from importing host plugins just
# to construct the LLM tool catalog.
TOOL_SPECS: tuple[dict[str, Any], ...] = (
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create or overwrite a UTF-8 text file inside this isolated session workspace. Paths must be relative.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string"},
                    "content": {"type": "string"},
                    "encoding": {"type": "string"},
                    "overwrite": {"type": "boolean"},
                },
                "required": ["content"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "file_exists",
            "description": "Check for a file or directory inside this isolated session workspace. Paths must be relative.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file from this isolated session workspace. Paths must be relative.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "start_line": {"type": "integer", "minimum": 1},
                    "max_lines": {"type": ["integer", "null"], "minimum": 1},
                    "max_bytes": {"type": "integer", "minimum": 1, "maximum": 1000000},
                    "encoding": {"type": "string"},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "python_exec",
            "description": "Execute Python code inside the isolated session. Files and dependencies are session-local; network access is blocked.",
            "parameters": {
                "type": "object",
                "properties": {"code": {"type": "string"}},
                "required": ["code"],
                "additionalProperties": False,
            },
        },
    },
)


def sandbox_tool_specs() -> list[dict[str, Any]]:
    return json.loads(json.dumps(TOOL_SPECS))


def _local_app_data() -> Path:
    root = os.environ.get("LOCALAPPDATA")
    if not root:
        raise RuntimeError(
            "LOCALAPPDATA is unavailable; MXC needs a per-user runtime directory"
        )
    return Path(root)


def _node_candidates() -> list[Path]:
    candidates: list[Path] = []
    configured = os.environ.get("UAGENT_MXC_NODE", "").strip()
    if configured:
        candidates.append(Path(configured))
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        candidates.extend(
            [
                Path(local) / "uagent" / "toolchains" / "node-v24.22.0" / "node.exe",
                Path(local) / "Programs" / "nodejs" / "node.exe",
            ]
        )
    found = shutil.which("node.exe") or shutil.which("node")
    if found:
        candidates.append(Path(found))
    return candidates


def _find_node() -> Path:
    for candidate in _node_candidates():
        try:
            if candidate.is_file():
                return candidate.resolve()
        except OSError:
            continue
    raise RuntimeError(
        "Node.js 24.21+ x64 is required for MXC. Install a user-local Node 24 runtime "
        "or set UAGENT_MXC_NODE to node.exe; no host-level installation is attempted."
    )


def _node_version(node: Path) -> tuple[int, int, int]:
    result = subprocess.run(
        [str(node), "--version"],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
        shell=False,
        env={
            "SystemRoot": os.environ.get("SystemRoot", r"C:\Windows"),
            "WINDIR": os.environ.get("WINDIR", r"C:\Windows"),
            "PATH": os.environ.get("PATH", r"C:\Windows\System32"),
        },
    )
    raw = result.stdout.strip().lstrip("v")
    try:
        parts = tuple(int(part) for part in raw.split(".")[:3])
    except ValueError as exc:
        raise RuntimeError(f"could not parse Node.js version {raw!r}") from exc
    return (parts + (0, 0, 0))[:3]


def _helper_source_dir() -> Path:
    return Path(__file__).with_name("mxc_node_helper")


def _runtime_dir() -> Path:
    configured = os.environ.get("UAGENT_MXC_RUNTIME_DIR", "").strip()
    return (
        Path(configured).expanduser().resolve()
        if configured
        else _local_app_data() / "uagent" / "mxc_runtime"
    )


def prepare_mxc_runtime(*, allow_install: bool = False) -> tuple[Path, Path]:
    """Prepare the per-user helper and, only with opt-in consent, install the pinned SDK."""
    if os.name != "nt" or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise RuntimeError(
            "MXC ProcessContainer is supported only on verified Windows x64 in this release"
        )
    node = _find_node()
    node_version = _node_version(node)
    version_supported = (node_version[0] == 24 and node_version >= NODE_MINIMUM) or (
        node_version[0] == 26 and node_version >= (26, 8, 0)
    )
    if not version_supported:
        raise RuntimeError("MXC requires Node.js 24.21.0+ or 26.8.0+ on Windows")
    runtime = _runtime_dir()
    runtime.mkdir(parents=True, exist_ok=True)
    source = _helper_source_dir()
    for filename in ("mxc_adapter.mjs", "package.json", "package-lock.json"):
        src = source / filename
        if not src.is_file():
            raise RuntimeError(f"MXC helper package is incomplete: missing {filename}")
        dst = runtime / filename
        if not dst.exists() or dst.read_bytes() != src.read_bytes():
            shutil.copy2(src, dst)
    sdk_package = runtime / "node_modules" / "@microsoft" / "mxc-sdk" / "package.json"
    sdk_version = ""
    if sdk_package.is_file():
        try:
            sdk_version = json.loads(sdk_package.read_text(encoding="utf-8")).get(
                "version", ""
            )
        except (OSError, ValueError):
            sdk_version = ""
    if sdk_version != SDK_VERSION:
        if not allow_install:
            raise RuntimeError(
                "The pinned MXC SDK is not installed. Re-run with --sandbox mxc interactively "
                "to review and install the per-user dependency (about 105 MB), or provision "
                "the runtime with npm ci in UAGENT_MXC_RUNTIME_DIR."
            )
        npm = node.with_name("npm.cmd")
        if not npm.is_file():
            raise RuntimeError(
                "npm.cmd was not found alongside the selected Node.js runtime"
            )
        install = subprocess.run(
            [str(npm), "ci", "--ignore-scripts", "--no-audit", "--no-fund"],
            cwd=str(runtime),
            capture_output=True,
            text=True,
            timeout=600,
            shell=False,
            env={
                "SystemRoot": os.environ.get("SystemRoot", r"C:\Windows"),
                "WINDIR": os.environ.get("WINDIR", r"C:\Windows"),
                "PATH": f"{node.parent};{os.environ.get('PATH', '')}",
                "LOCALAPPDATA": os.environ.get("LOCALAPPDATA", ""),
                "TEMP": os.environ.get("TEMP", ""),
                "TMP": os.environ.get("TMP", ""),
                "APPDATA": os.environ.get("APPDATA", ""),
                "USERPROFILE": os.environ.get("USERPROFILE", ""),
            },
        )
        if install.returncode != 0:
            detail = (install.stderr or install.stdout or "npm ci failed")[-4000:]
            raise RuntimeError(f"MXC SDK installation failed: {detail}")
        installed = json.loads(sdk_package.read_text(encoding="utf-8")).get(
            "version", ""
        )
        if installed != SDK_VERSION:
            raise RuntimeError(
                f"installed MXC SDK version mismatch: expected {SDK_VERSION}, got {installed!r}"
            )
    return node, runtime


def _assign_job_object(proc: subprocess.Popen[bytes]):
    """Put a helper process in a kill-on-close Windows Job Object with hard limits."""
    try:
        import win32api
        import win32job
    except ImportError as exc:
        raise RuntimeError("pywin32 Job Object support is required for MXC") from exc
    job = win32job.CreateJobObject(None, "")
    try:
        info = win32job.QueryInformationJobObject(
            job, win32job.JobObjectExtendedLimitInformation
        )
        flags = (
            win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            | win32job.JOB_OBJECT_LIMIT_JOB_MEMORY
            | win32job.JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            | win32job.JOB_OBJECT_LIMIT_JOB_TIME
        )
        basic = info["BasicLimitInformation"]
        basic["LimitFlags"] = flags
        basic["ActiveProcessLimit"] = JOB_PROCESS_LIMIT
        basic["PerJobUserTimeLimit"] = JOB_USER_TIME_LIMIT_100NS
        info["JobMemoryLimit"] = JOB_MEMORY_LIMIT_BYTES
        win32job.SetInformationJobObject(
            job, win32job.JobObjectExtendedLimitInformation, info
        )
        win32job.AssignProcessToJobObject(job, proc._handle)
        return win32api, job
    except Exception:
        win32api.CloseHandle(job)
        raise


def _run_probe(node: Path, runtime: Path) -> dict[str, Any]:
    helper = runtime / "mxc_adapter.mjs"
    env = {
        "SystemRoot": os.environ.get("SystemRoot", r"C:\Windows"),
        "WINDIR": os.environ.get("WINDIR", r"C:\Windows"),
        "PATH": f"{node.parent};{os.environ.get('PATH', '')}",
        "LOCALAPPDATA": os.environ.get("LOCALAPPDATA", ""),
        "APPDATA": os.environ.get("APPDATA", ""),
        "TEMP": os.environ.get("TEMP", ""),
        "TMP": os.environ.get("TMP", ""),
        "USERPROFILE": os.environ.get("USERPROFILE", ""),
    }
    proc = subprocess.Popen(
        [str(node), str(helper), "probe"],
        cwd=str(runtime),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        env=env,
    )
    try:
        job_api, job = _assign_job_object(proc)
    except Exception:
        proc.kill()
        proc.wait(timeout=5)
        raise
    try:
        assert proc.stdin is not None
        proc.stdin.write('{"probe":true}\n')
        proc.stdin.flush()
        try:
            stdout, stderr = proc.communicate(timeout=PROBE_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired as exc:
            job_api.CloseHandle(job)
            job = None
            try:
                stdout, stderr = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
            raise RuntimeError(
                "MXC host probe exceeded the 15-second deadline"
            ) from exc
    finally:
        if job is not None:
            job_api.CloseHandle(job)
        if proc.poll() is None:
            proc.kill()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
    if len(stdout.encode("utf-8", errors="replace")) > MAX_FRAME_BYTES:
        raise RuntimeError("MXC host probe returned an oversized response")
    try:
        report = json.loads(stdout.splitlines()[0])
    except (IndexError, ValueError) as exc:
        raise RuntimeError(
            f"MXC host probe returned invalid JSON: {stderr[-1000:]}"
        ) from exc
    if proc.returncode != 0 or report.get("ok") is not True:
        raise RuntimeError(
            str(report.get("error") or "MXC ProcessContainer probe failed")
        )
    return report


def probe_mxc_backend(
    *, allow_install: bool = False
) -> tuple[SandboxCapabilities, dict[str, Any], Path, Path]:
    node, runtime = prepare_mxc_runtime(allow_install=allow_install)
    report = _run_probe(node, runtime)
    capabilities = SandboxCapabilities(
        isolation_level=IsolationLevel.CONTAINER,
        available=frozenset(SandboxCapability),
    )
    return capabilities, report, node, runtime


def mxc_sdk_is_installed() -> bool:
    """Check the user-local runtime without probing or performing filesystem writes."""
    try:
        manifest = (
            _runtime_dir() / "node_modules" / "@microsoft" / "mxc-sdk" / "package.json"
        )
        return (
            manifest.is_file()
            and json.loads(manifest.read_text(encoding="utf-8")).get("version")
            == SDK_VERSION
        )
    except (OSError, ValueError, RuntimeError):
        return False


def _scope_key(scope: TrustedSandboxScope) -> str:
    material = "\0".join(
        (
            scope.deployment_id,
            scope.principal_id,
            scope.project_id,
            scope.scope_kind,
            scope.scope_id,
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _workspace_for_scope(scope: TrustedSandboxScope) -> Path:
    return _local_app_data() / "uagent" / "sandboxes" / _scope_key(scope)


def _python_root() -> Path:
    root = Path(sys.base_prefix).resolve()
    if not root.is_dir():
        raise RuntimeError("Python standard-library root is unavailable")
    return root


def _python_env_root() -> Path:
    root = Path(sys.prefix).resolve()
    if not root.is_dir():
        raise RuntimeError("Python environment root is unavailable")
    return root


class _MxcSession:
    def __init__(
        self, *, scope: TrustedSandboxScope, node: Path, runtime: Path
    ) -> None:
        if os.name != "nt":
            raise RuntimeError(
                "MXC ProcessContainer session requested on a non-Windows host"
            )
        try:
            import win32api
            import win32job
        except ImportError as exc:
            raise RuntimeError(
                "pywin32 Job Object support is required for safe MXC cleanup and resource limits"
            ) from exc
        self._win32api = win32api
        self._win32job = win32job
        self._lock = threading.RLock()
        self._responses: Queue[str | None] = Queue()
        self._stderr = bytearray()
        self._stderr_lock = threading.Lock()
        self._closed = False
        self._scope = scope
        self.workspace = _workspace_for_scope(scope)
        if self.workspace.exists() and self.workspace.is_symlink():
            raise RuntimeError("sandbox workspace root cannot be a symlink")
        self.workspace.mkdir(parents=True, exist_ok=True)
        # A new scope hash is created for this process/session; don't reuse on-disk
        # state that could have been replaced while the owner was not running.
        if any(self.workspace.iterdir()):
            shutil.rmtree(self.workspace)
            self.workspace.mkdir(parents=True)
        worker_script = runtime / "sandbox_worker.py"
        source_worker = Path(__file__).with_name("sandbox_worker.py")
        shutil.copy2(source_worker, worker_script)
        python_exe = Path(sys.executable).resolve()
        if not python_exe.is_file():
            raise RuntimeError("current Python executable is unavailable")
        system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        helper_env = {
            "SystemRoot": str(system_root),
            "WINDIR": str(system_root),
            "PATH": f"{node.parent};{system_root / 'System32'}",
            "LOCALAPPDATA": os.environ.get("LOCALAPPDATA", ""),
            "APPDATA": os.environ.get("APPDATA", ""),
            "TEMP": os.environ.get("TEMP", ""),
            "TMP": os.environ.get("TMP", ""),
            "USERPROFILE": os.environ.get("USERPROFILE", ""),
        }
        self._proc = subprocess.Popen(
            [str(node), str(runtime / "mxc_adapter.mjs"), "worker"],
            cwd=str(runtime),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            bufsize=0,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            shell=False,
            env=helper_env,
        )
        try:
            self._job = self._create_job(self._proc)
        except Exception:
            self._proc.kill()
            self._proc.wait(timeout=5)
            shutil.rmtree(self.workspace, ignore_errors=True)
            raise
        threading.Thread(
            target=self._read_stdout, name="mxc-stdout", daemon=True
        ).start()
        threading.Thread(
            target=self._read_stderr, name="mxc-stderr", daemon=True
        ).start()
        config = {
            "workspace": str(self.workspace),
            "pythonExe": str(python_exe),
            "pythonRoot": str(_python_root()),
            "pythonEnvRoot": str(_python_env_root()),
            "workerScript": str(worker_script),
            "helperRoot": str(runtime),
            "deniedPaths": [],
        }
        try:
            self._write_line(config)
            ready = self._read_response(timeout=20)
            if not ready.get("ready"):
                raise RuntimeError(
                    str(ready.get("error") or "MXC worker did not become ready")
                )
        except Exception:
            self.close()
            raise

    def _create_job(self, proc: subprocess.Popen[bytes]):
        _api, job = _assign_job_object(proc)
        return job

    def _read_stdout(self) -> None:
        assert self._proc.stdout is not None
        while True:
            try:
                line = self._proc.stdout.readline(MAX_FRAME_BYTES + 1)
            except OSError:
                line = b""
            if not line:
                self._responses.put(None)
                return
            if len(line) > MAX_FRAME_BYTES or not line.endswith(b"\n"):
                self._responses.put(
                    json.dumps(
                        {
                            "ok": False,
                            "error": "oversized or unterminated adapter frame",
                        }
                    )
                )
                return
            self._responses.put(line.decode("utf-8", errors="replace").rstrip("\r\n"))

    def _read_stderr(self) -> None:
        assert self._proc.stderr is not None
        while True:
            chunk = self._proc.stderr.read(4096)
            if not chunk:
                return
            with self._stderr_lock:
                remaining = MAX_STDERR_BYTES - len(self._stderr)
                if remaining > 0:
                    self._stderr.extend(chunk[:remaining])

    def _write_line(self, value: dict[str, Any]) -> None:
        if self._closed or self._proc.poll() is not None or self._proc.stdin is None:
            raise RuntimeError("MXC session process is not running")
        payload = (
            json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            + b"\n"
        )
        if len(payload) > MAX_FRAME_BYTES:
            raise ValueError("sandbox request exceeds the 1 MB IPC frame limit")
        self._proc.stdin.write(payload)
        self._proc.stdin.flush()

    def _read_response(self, *, timeout: float) -> dict[str, Any]:
        try:
            raw = self._responses.get(timeout=timeout)
        except Empty as exc:
            self.close()
            raise TimeoutError(
                "MXC adapter did not respond before the deadline"
            ) from exc
        if raw is None:
            stderr = self._stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"MXC adapter exited unexpectedly: {stderr[-1000:]}")
        try:
            parsed = json.loads(raw)
        except ValueError as exc:
            self.close()
            raise RuntimeError("MXC adapter returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError("MXC adapter returned a non-object response")
        return parsed

    def run(self, name: str, args: dict[str, Any]) -> str:
        if name not in TOOL_NAMES:
            raise PermissionError("tool is not available in the local MXC PoC")
        with self._lock:
            self._write_line(
                {"operation": "run", "payload": {"name": name, "args": args}}
            )
            response = self._read_response(timeout=45)
            if response.get("terminate"):
                self.close()
                return "[sandbox error] execution timed out; the isolated session was terminated"
            if response.get("ok") is not True:
                error = str(response.get("error", "execution failed"))
                if "workspace limit exceeded" in error.lower():
                    self.close()
                return f"[sandbox error] {error}"
            result = response.get("result")
            if isinstance(result, (dict, list)):
                return json.dumps(result, ensure_ascii=False, default=str)
            return str(result if result is not None else "")

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            try:
                if self._proc.stdin:
                    self._proc.stdin.close()
            except OSError:
                pass
            try:
                self._win32api.CloseHandle(self._job)
            except Exception:
                pass
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                try:
                    self._proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
            try:
                shutil.rmtree(self.workspace, ignore_errors=True)
            except OSError:
                pass


class MxcSessionManager:
    """Own one persistent ProcessContainer Worker per trusted local scope."""

    def __init__(
        self, *, node: Path, runtime: Path, capabilities: SandboxCapabilities
    ) -> None:
        self.node = node
        self.runtime = runtime
        self.capabilities = capabilities
        self._sessions: dict[str, _MxcSession] = {}
        self._lock = threading.RLock()
        atexit.register(self.close_all)

    @classmethod
    def initialize(
        cls, *, allow_install: bool = False
    ) -> tuple["MxcSessionManager", dict[str, Any]]:
        capabilities, report, node, runtime = probe_mxc_backend(
            allow_install=allow_install
        )
        # Never expose the lightweight ProcessContainer as a Remote/VM backend.
        return cls(node=node, runtime=runtime, capabilities=capabilities), report

    def _prune_inactive_sessions(self) -> None:
        """Release closed or exited workers before enforcing the live-session cap."""
        for key, session in list(self._sessions.items()):
            if session._closed or session._proc.poll() is not None:
                self._sessions.pop(key, None)
                session.close()

    def run_tool(
        self, scope: TrustedSandboxScope | None, name: str, args: dict[str, Any]
    ) -> str:
        allowed_scope_deployments = {
            "cli-session": "cli",
            "gui-session": "gui",
            "web-room": "web",
        }
        if (
            scope is None
            or allowed_scope_deployments.get(scope.scope_kind) != scope.deployment_id
        ):
            return "[sandbox error] a trusted local CLI/GUI/Web Room scope is required"
        if name not in TOOL_NAMES:
            return "[sandbox policy] tool is not in the local sandbox allowlist"
        key = _scope_key(scope)
        with self._lock:
            self._prune_inactive_sessions()
            session = self._sessions.get(key)
            if session is None:
                if len(self._sessions) >= MAX_ACTIVE_SESSIONS:
                    return "[sandbox error] active session limit reached; restart UAG to release old scopes"
                try:
                    session = _MxcSession(
                        scope=scope, node=self.node, runtime=self.runtime
                    )
                except Exception as exc:
                    return f"[sandbox error] unable to create MXC session: {type(exc).__name__}: {exc}"
                self._sessions[key] = session
        try:
            return session.run(name, args)
        except Exception as exc:
            session.close()
            with self._lock:
                self._sessions.pop(key, None)
            return f"[sandbox error] isolated session terminated: {type(exc).__name__}: {exc}"

    def close_scope(self, scope: TrustedSandboxScope) -> None:
        key = _scope_key(scope)
        with self._lock:
            session = self._sessions.pop(key, None)
        if session is not None:
            session.close()

    def close_all(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            session.close()


_manager: MxcSessionManager | None = None
_manager_lock = threading.RLock()


def install_session_manager(manager: MxcSessionManager | None) -> None:
    global _manager
    with _manager_lock:
        old = _manager
        _manager = manager
    if old is not None and old is not manager:
        old.close_all()


def current_session_manager() -> MxcSessionManager | None:
    with _manager_lock:
        return _manager


def run_sandbox_tool(
    scope: TrustedSandboxScope | None, name: str, args: dict[str, Any]
) -> str:
    manager = current_session_manager()
    if manager is None:
        return "[sandbox error] the local MXC backend is not initialized"
    return manager.run_tool(scope, name, args)


def _process_scope_id(scope_id: str) -> str:
    """Salt a trusted session/Room identifier to this live server process."""
    return f"{scope_id}-{os.getpid()}-{_PROCESS_SCOPE_NONCE}"


def local_web_room_scope(
    *, principal_id: str, project_id: str, room_id: str
) -> TrustedSandboxScope:
    """Return an isolated MXC scope for a trusted local Web Room."""
    if not principal_id or not project_id or not room_id:
        raise ValueError("local Web Room scope fields must be non-empty")
    return TrustedSandboxScope(
        deployment_id="web",
        principal_id=principal_id,
        project_id=project_id,
        scope_kind="web-room",
        scope_id=_process_scope_id(room_id),
    )


def startup_scope(
    *, entry_point: str, project_path: str, session_id: str
) -> TrustedSandboxScope:
    if entry_point not in {"cli", "gui"}:
        raise ValueError("only local CLI/GUI sessions are supported by this MXC PoC")
    identity = os.environ.get("USERNAME") or os.environ.get("USER") or "local-user"
    project = str(Path(project_path).resolve())
    return TrustedSandboxScope(
        deployment_id=entry_point,
        principal_id=identity,
        project_id=hashlib.sha256(project.encode("utf-8")).hexdigest(),
        scope_kind="cli-session" if entry_point == "cli" else "gui-session",
        # Every live worker gets a process-instance component, even when a
        # persisted session ID exists. This backend deletes a scope workspace
        # when creating its first Worker, so sharing a persisted ID between
        # concurrently running processes would otherwise be destructive.
        scope_id=_process_scope_id(session_id or entry_point),
    )


def describe_probe(report: dict[str, Any]) -> str:
    return (
        f"MXC SDK {report.get('sdk')} / Node {report.get('node')} / "
        f"{report.get('platform')} {report.get('arch')} / tier "
        f"{(report.get('probe') or {}).get('tier')}"
    )
