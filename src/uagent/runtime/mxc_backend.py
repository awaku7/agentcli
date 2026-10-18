"""Windows x64 MXC ProcessContainer adapter for explicitly opted-in local sessions.

This adapter is deliberately unavailable to Remote profiles.  The SDK and the
persistent worker protocol stay behind this module; tool functions receive only
plain JSON-like values and strings.
"""

from __future__ import annotations

import atexit
import errno
import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Callable

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
                    "max_bytes": {"type": "integer", "minimum": 1, "maximum": 128000},
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
    path = Path(root).expanduser()
    if not path.is_absolute():
        raise RuntimeError("LOCALAPPDATA must be an absolute per-user path")
    return path.resolve()


def _trusted_startup_uagent_value(name: str) -> str:
    """Read a UAGENT override captured before project dotenv files are loaded."""
    try:
        from .runtime_init import get_startup_uagent_env_snapshot

        snapshot = get_startup_uagent_env_snapshot()
    except Exception:
        snapshot = None
    if not isinstance(snapshot, dict):
        return ""
    return str(snapshot.get(name) or "").strip()


def _node_candidates() -> list[Path]:
    candidates: list[Path] = []
    # This executable runs outside the container. Never let a selected
    # project's .env choose host code to execute.
    configured = _trusted_startup_uagent_value("UAGENT_MXC_NODE")
    if configured:
        configured_path = Path(configured).expanduser()
        if not configured_path.is_absolute():
            raise RuntimeError("UAGENT_MXC_NODE must be an absolute executable path")
        candidates.append(configured_path.resolve())
    local = _local_app_data()
    candidates.extend(
        [
            local / "uagent" / "toolchains" / "node-v24.22.0" / "node.exe",
            local / "Programs" / "nodejs" / "node.exe",
        ]
    )
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
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    safe_path = os.pathsep.join((str(node.parent), str(Path(system_root) / "System32")))
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
            "PATH": safe_path,
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
    # Runtime files contain executable helper/SDK code; project dotenv values
    # must not redirect execution into the project checkout.
    configured = _trusted_startup_uagent_value("UAGENT_MXC_RUNTIME_DIR")
    if configured:
        configured_path = Path(configured).expanduser()
        if not configured_path.is_absolute():
            raise RuntimeError("UAGENT_MXC_RUNTIME_DIR must be an absolute path")
        return configured_path.resolve()
    return _local_app_data() / "uagent" / "mxc_runtime"


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
    runtime = _validate_sandbox_read_root(
        _runtime_dir(), require_existing_directory=False
    )
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
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        safe_path = os.pathsep.join(
            (str(node.parent), str(Path(system_root) / "System32"))
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
                "PATH": safe_path,
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
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    safe_path = os.pathsep.join((str(node.parent), str(Path(system_root) / "System32")))
    env = {
        "SystemRoot": os.environ.get("SystemRoot", r"C:\Windows"),
        "WINDIR": os.environ.get("WINDIR", r"C:\Windows"),
        "PATH": safe_path,
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


def _is_reparse_point(path: Path) -> bool:
    try:
        path_stat = Path(path).lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(path_stat.st_mode) or bool(
        getattr(path_stat, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _remove_workspace_tree(workspace: Path) -> None:
    """Remove a workspace, clearing read-only bits without following reparse points."""
    workspace = Path(workspace)
    if _is_reparse_point(workspace):
        raise RuntimeError("sandbox workspace root cannot be a reparse point")
    root = os.path.normcase(os.path.abspath(workspace))

    def onerror(func, failed_path, exc_info):
        error = exc_info[1]
        if isinstance(error, FileNotFoundError):
            return
        if func not in (os.unlink, os.rmdir):
            raise error
        failed = os.path.normcase(os.path.abspath(failed_path))
        try:
            inside = os.path.commonpath((root, failed)) == root
        except ValueError:
            inside = False
        if not inside or _is_reparse_point(Path(failed_path)):
            raise error
        try:
            os.chmod(failed_path, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)
            func(failed_path)
        except OSError:
            raise error

    shutil.rmtree(workspace, onerror=onerror)


def _workspace_lease_path(sandbox_root: Path, key: str) -> Path:
    return sandbox_root / ".leases" / f"{key}.lock"


def _acquire_workspace_lease(sandbox_root: Path, key: str, *, create: bool = True):
    """Acquire an OS-backed owner lease for one workspace, or return None if busy."""
    if len(key) != 64 or any(char not in "0123456789abcdef" for char in key):
        raise ValueError("invalid sandbox workspace key")
    sandbox_root = Path(sandbox_root)
    lease_root = sandbox_root / ".leases"
    if _is_reparse_point(sandbox_root) or _is_reparse_point(lease_root):
        raise RuntimeError("sandbox workspace lease directory cannot be a symlink")
    if create:
        lease_root.mkdir(parents=True, exist_ok=True)
    lease_path = _workspace_lease_path(sandbox_root, key)
    if _is_reparse_point(lease_path):
        raise RuntimeError("sandbox workspace lease cannot be a symlink")
    flags = os.O_RDWR | getattr(os, "O_BINARY", 0)
    if create:
        flags |= os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(lease_path, flags, 0o600)
    except FileNotFoundError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise RuntimeError("sandbox workspace lease must be a regular file")
        if os.fstat(fd).st_size == 0:
            os.write(fd, b"\0")
        try:
            if os.name == "nt":
                import msvcrt

                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK} or getattr(
                exc, "winerror", None
            ) in {32, 33}:
                os.close(fd)
                return None
            raise
        return os.fdopen(fd, "r+b", buffering=0)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise


def _release_workspace_lease(lease) -> None:
    if lease is None:
        return
    try:
        if os.name == "nt":
            import msvcrt

            lease.seek(0)
            msvcrt.locking(lease.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lease.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        lease.close()
    except OSError:
        pass


def _scavenge_orphaned_workspaces(sandbox_root: Path) -> None:
    """Remove abandoned workspaces only when their OS owner lease is unlocked."""
    sandbox_root = Path(sandbox_root)
    if not sandbox_root.exists():
        return
    if _is_reparse_point(sandbox_root):
        raise RuntimeError("sandbox workspace root cannot be a symlink")
    lease_root = sandbox_root / ".leases"
    if not lease_root.exists():
        return
    if _is_reparse_point(lease_root):
        raise RuntimeError("sandbox workspace lease directory cannot be a symlink")

    live_keys: set[str] = set()
    for workspace in sandbox_root.iterdir():
        key = workspace.name
        if len(key) != 64 or any(char not in "0123456789abcdef" for char in key):
            continue
        try:
            mode = workspace.lstat().st_mode
        except FileNotFoundError:
            continue
        if not stat.S_ISDIR(mode) or _is_reparse_point(workspace):
            continue
        lease = _acquire_workspace_lease(sandbox_root, key, create=False)
        if lease is None:
            live_keys.add(key)
            continue
        try:
            try:
                _remove_workspace_tree(workspace)
            except (OSError, RuntimeError):
                continue
        finally:
            _release_workspace_lease(lease)
        if workspace.exists():
            continue
        try:
            _workspace_lease_path(sandbox_root, key).unlink()
        except OSError:
            pass

    for lease_path in lease_root.glob("*.lock"):
        key = lease_path.stem
        if (
            key in live_keys
            or len(key) != 64
            or any(char not in "0123456789abcdef" for char in key)
        ):
            continue
        if (sandbox_root / key).exists():
            continue
        lease = _acquire_workspace_lease(sandbox_root, key, create=False)
        if lease is None:
            continue
        _release_workspace_lease(lease)
        try:
            lease_path.unlink()
        except OSError:
            pass


def _validate_sandbox_read_root(
    prefix: Path, *, require_existing_directory: bool = True
) -> Path:
    root = Path(prefix).resolve()
    if require_existing_directory and not root.is_dir():
        raise RuntimeError("Sandbox runtime read root is unavailable")
    if os.path.normcase(str(root)) == os.path.normcase(root.anchor):
        raise RuntimeError("Sandbox recursive read roots cannot be filesystem roots")
    protected_paths = [Path.cwd().resolve(), Path.home().resolve()]
    for variable in ("USERPROFILE", "LOCALAPPDATA", "APPDATA"):
        value = os.environ.get(variable)
        if value:
            protected_paths.append(Path(value).expanduser().resolve())
    for protected_path in protected_paths:
        try:
            common = os.path.commonpath((str(root), str(protected_path)))
        except ValueError:
            continue
        if os.path.normcase(common) == os.path.normcase(str(root)):
            raise RuntimeError(
                "Sandbox recursive read roots must not contain the selected work "
                "directory or per-user data; use a narrower runtime path"
            )
    return root


def _python_root() -> Path:
    return _validate_sandbox_read_root(Path(sys.base_prefix))


def _python_env_root() -> Path:
    return _validate_sandbox_read_root(Path(sys.prefix))


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
        self._workspace_lease = _acquire_workspace_lease(
            self.workspace.parent, self.workspace.name
        )
        if self._workspace_lease is None:
            raise RuntimeError("sandbox workspace already has an active owner")
        if self.workspace.exists() and _is_reparse_point(self.workspace):
            raise RuntimeError("sandbox workspace root cannot be a symlink")
        self.workspace.mkdir(parents=True, exist_ok=True)
        # A new scope hash is created for this process/session; don't reuse on-disk
        # state that could have been replaced while the owner was not running.
        if any(self.workspace.iterdir()):
            _remove_workspace_tree(self.workspace)
            self.workspace.mkdir(parents=True)
        worker_script = runtime / "sandbox_worker.py"
        source_worker = Path(__file__).with_name("sandbox_worker.py")
        shutil.copy2(source_worker, worker_script)
        python_exe = Path(sys.executable).resolve()
        if not python_exe.is_file():
            raise RuntimeError("current Python executable is unavailable")
        python_root = _python_root()
        python_env_root = _python_env_root()
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
            try:
                _remove_workspace_tree(self.workspace)
            except (OSError, RuntimeError):
                pass
            _release_workspace_lease(self._workspace_lease)
            self._workspace_lease = None
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
            "pythonRoot": str(python_root),
            "pythonEnvRoot": str(python_env_root),
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
            response = self._read_response(timeout=60 if name == "python_exec" else 45)
            if response.get("terminate"):
                self.close()
                error = response.get("error")
                if isinstance(error, str) and error:
                    return f"[sandbox error] {error}"
                return "[sandbox error] execution timed out; the isolated session was terminated"
            if response.get("ok") is not True:
                error = str(response.get("error", "execution failed"))
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
                _remove_workspace_tree(self.workspace)
            except (OSError, RuntimeError):
                pass
            _release_workspace_lease(self._workspace_lease)
            self._workspace_lease = None


class MxcSessionManager:
    """Own one persistent ProcessContainer Worker per trusted local scope."""

    def __init__(
        self, *, node: Path, runtime: Path, capabilities: SandboxCapabilities
    ) -> None:
        self.node = node
        self.runtime = runtime
        self.capabilities = capabilities
        self._sessions: dict[str, _MxcSession] = {}
        self._active_local_scopes: dict[tuple[str, str, str], TrustedSandboxScope] = {}
        self._active_web_scopes: set[TrustedSandboxScope] = set()
        self._lock = threading.RLock()
        if os.name == "nt":
            _scavenge_orphaned_workspaces(_local_app_data() / "uagent" / "sandboxes")
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

    def _close_obsolete_local_sessions(
        self, current_key: str, scope: TrustedSandboxScope
    ) -> None:
        """Release prior CLI/GUI leases after session or project changes."""
        local_session_kinds = {"cli-session", "gui-session"}
        if scope.scope_kind not in local_session_kinds:
            return
        for key, session in list(self._sessions.items()):
            previous_scope = getattr(session, "_scope", None)
            if (
                key != current_key
                and getattr(previous_scope, "scope_kind", None) == scope.scope_kind
                and getattr(previous_scope, "deployment_id", None)
                == scope.deployment_id
                and getattr(previous_scope, "principal_id", None) == scope.principal_id
            ):
                self._sessions.pop(key, None)
                session.close()

    def activate_scope(self, scope: TrustedSandboxScope) -> None:
        """Activate a trusted CLI/GUI scope or bind a Web Room lease."""
        if scope.scope_kind == "web-room":
            if not scope.binding_generation:
                raise ValueError("Web Room scope requires a binding generation")
            with self._lock:
                self._active_web_scopes.add(scope)
            return
        if scope.scope_kind not in {"cli-session", "gui-session"}:
            return
        with self._lock:
            self._close_obsolete_local_sessions(_scope_key(scope), scope)
            self._prune_inactive_sessions()
            self._active_local_scopes[
                (scope.deployment_id, scope.principal_id, scope.scope_kind)
            ] = scope

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
            if scope.scope_kind == "web-room" and scope not in self._active_web_scopes:
                return "[sandbox error] revoked or unbound Web Room scope rejected"
            if scope.scope_kind in {"cli-session", "gui-session"}:
                active_scope = self._active_local_scopes.get(
                    (scope.deployment_id, scope.principal_id, scope.scope_kind)
                )
                if active_scope is not None and active_scope != scope:
                    return "[sandbox error] stale local execution scope rejected"
            self._close_obsolete_local_sessions(key, scope)
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

    def revoke_scope(self, scope: TrustedSandboxScope) -> Callable[[], None] | None:
        """Fence a scope immediately and return its detached-session cleanup."""
        key = _scope_key(scope)
        with self._lock:
            if scope.scope_kind == "web-room":
                self._active_web_scopes.discard(scope)
            session = self._sessions.pop(key, None)
        return session.close if session is not None else None

    def close_scope(self, scope: TrustedSandboxScope) -> None:
        cleanup = self.revoke_scope(scope)
        if cleanup is not None:
            cleanup()

    def close_all(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
            self._active_local_scopes.clear()
            self._active_web_scopes.clear()
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


def _process_scope_id(scope_id: str, *, generation: str = "") -> str:
    """Salt a trusted session/Room identifier to this live server process."""
    generation_suffix = f"-{generation}" if generation else ""
    return f"{scope_id}-{os.getpid()}-{_PROCESS_SCOPE_NONCE}{generation_suffix}"


def local_web_room_scope(
    *,
    principal_id: str,
    project_id: str,
    room_id: str,
    room_generation: str,
) -> TrustedSandboxScope:
    """Return an isolated MXC scope for one trusted Web Room incarnation."""
    if not principal_id or not project_id or not room_id or not room_generation:
        raise ValueError("local Web Room scope fields must be non-empty")
    return TrustedSandboxScope(
        deployment_id="web",
        principal_id=principal_id,
        project_id=project_id,
        scope_kind="web-room",
        scope_id=_process_scope_id(room_id, generation=room_generation),
        binding_generation=room_generation,
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
