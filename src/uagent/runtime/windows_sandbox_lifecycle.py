"""Low-level, owner-bound client for MXC's experimental Windows Sandbox lifecycle.

This client is deliberately not wired to Remote routing yet. It provides only
explicit provision/start/exec/stop/deprovision operations with a returned MXC
sandbox ID; it never uses proofless ``--force-reclaim`` and never claims Remote
acceptance or resource-limit capabilities.
"""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal, Sequence

PINNED_MXC_VERSION = "1.0.0"
WINDOWS_SANDBOX_SCHEMA = "1.1.0-alpha"
_SANDBOX_ID_RE = re.compile(r"^wsb:[0-9a-f]{8}$")
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


class WindowsSandboxLifecycleError(RuntimeError):
    """An MXC lifecycle operation failed or returned an invalid result."""


class WindowsSandboxCommandTimeout(WindowsSandboxLifecycleError):
    """The executor timed out; the lease must be cleaned up by its owner ID."""


@dataclass(frozen=True)
class WxcCommandResult:
    returncode: int
    stdout: str
    stderr: str


CommandRunner = Callable[[Sequence[str], float], WxcCommandResult]


@dataclass(eq=False)
class WindowsSandboxLease:
    """Opaque in-process lease handle; arbitrary caller-supplied IDs are rejected."""

    sandbox_id: str
    workspace: Path
    state: Literal["provisioned", "running", "uncertain", "closed"] = "provisioned"
    _owner_token: object = field(default_factory=object, repr=False)


def _minimal_executor_environment() -> dict[str, str]:
    """Do not forward agent/provider credentials to the executor process."""
    keep = ("SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LOCALAPPDATA", "PATH")
    return {key: os.environ[key] for key in keep if os.environ.get(key)}


def _default_command_runner(
    argv: Sequence[str], timeout_seconds: float
) -> WxcCommandResult:
    completed = subprocess.run(
        list(argv),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        check=False,
        env=_minimal_executor_environment(),
    )
    return WxcCommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )


def _extract_sandbox_id(output: str) -> str:
    """Extract one documented opaque ID from JSON output; never guess an ID."""
    decoder = json.JSONDecoder()
    found: set[str] = set()
    for index, char in enumerate(output):
        if char != "{":
            continue
        try:
            value, _end = decoder.raw_decode(output[index:])
        except json.JSONDecodeError:
            continue
        if not isinstance(value, dict):
            continue
        candidates = [value.get("sandboxId"), value.get("containerId")]
        for key in ("result", "provision", "data"):
            nested = value.get(key)
            if isinstance(nested, dict):
                candidates.extend((nested.get("sandboxId"), nested.get("containerId")))
        found.update(
            candidate
            for candidate in candidates
            if isinstance(candidate, str) and _SANDBOX_ID_RE.fullmatch(candidate)
        )
    if len(found) != 1:
        raise WindowsSandboxLifecycleError(
            "MXC provision did not return exactly one valid wsb sandbox ID"
        )
    return next(iter(found))


class WindowsSandboxLifecycleClient:
    """Narrow wrapper for the documented direct ``wxc-exec`` lifecycle contract.

    The client permits one live lease per instance. The native MXC backend also
    serializes the host's single Windows Sandbox VM; this Python guard prevents
    accidental overlapping work through this client. A timeout or uncertain
    teardown poisons the lease instead of reclaiming an unknown VM.
    """

    def __init__(
        self,
        runtime_dir: str | Path,
        *,
        command_runner: CommandRunner | None = None,
        command_timeout_seconds: float = 300.0,
    ) -> None:
        if command_timeout_seconds <= 0:
            raise ValueError("command timeout must be positive")
        self.runtime_dir = Path(runtime_dir).resolve()
        package_dir = self.runtime_dir / "node_modules" / "@microsoft" / "mxc-sdk"
        try:
            manifest = json.loads(
                (package_dir / "package.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise WindowsSandboxLifecycleError(
                "pinned MXC package manifest is unavailable"
            ) from exc
        if manifest.get("version") != PINNED_MXC_VERSION:
            raise WindowsSandboxLifecycleError(
                f"expected pinned @microsoft/mxc-sdk {PINNED_MXC_VERSION}"
            )
        self.executor_path = package_dir / "bin" / "x64" / "wxc-exec.exe"
        if not self.executor_path.is_file():
            raise WindowsSandboxLifecycleError("pinned x64 wxc-exec.exe is unavailable")
        self.command_timeout_seconds = float(command_timeout_seconds)
        self._command_runner = command_runner or _default_command_runner
        self._lock = threading.RLock()
        self._leases: dict[str, WindowsSandboxLease] = {}
        self._uncertain_provision = False

    @staticmethod
    def _validate_workspace(workspace: str | Path) -> Path:
        path = Path(workspace)
        if not path.is_absolute():
            raise ValueError("Windows Sandbox workspace must be absolute")
        try:
            info = path.lstat()
        except OSError as exc:
            raise ValueError("Windows Sandbox workspace must exist") from exc
        if not stat.S_ISDIR(info.st_mode) or path.is_symlink():
            raise ValueError("Windows Sandbox workspace must be a real directory")
        if getattr(info, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError("Windows Sandbox workspace cannot be a reparse point")
        resolved = path.resolve(strict=True)
        if resolved == Path(resolved.anchor):
            raise ValueError("Windows Sandbox workspace cannot be a filesystem root")
        return resolved

    @staticmethod
    def _validate_sandbox_id(sandbox_id: str) -> None:
        if not isinstance(sandbox_id, str) or not _SANDBOX_ID_RE.fullmatch(sandbox_id):
            raise WindowsSandboxLifecycleError("invalid MXC Windows Sandbox ID")

    def _check_owned_lease(self, lease: WindowsSandboxLease) -> None:
        self._validate_sandbox_id(lease.sandbox_id)
        if self._leases.get(lease.sandbox_id) is not lease:
            raise WindowsSandboxLifecycleError(
                "sandbox lease is not owned by this client"
            )
        if lease.state == "closed":
            raise WindowsSandboxLifecycleError("sandbox lease is closed")

    def _invoke(
        self,
        operation: str,
        *,
        sandbox_id: str | None = None,
        config: dict[str, object] | None = None,
    ) -> WxcCommandResult:
        if operation not in {"provision", "start", "exec", "stop", "deprovision"}:
            raise ValueError("unsupported Windows Sandbox lifecycle operation")
        argv = [str(self.executor_path), "--experimental", "--operation", operation]
        if sandbox_id is not None:
            self._validate_sandbox_id(sandbox_id)
            argv.extend(("--container-id", sandbox_id))
        try:
            if config is None:
                result = self._command_runner(argv, self.command_timeout_seconds)
            else:
                with tempfile.TemporaryDirectory(prefix="uag-wxc-config-") as temp_dir:
                    config_path = Path(temp_dir) / "request.json"
                    config_path.write_text(
                        json.dumps(config, ensure_ascii=False, separators=(",", ":")),
                        encoding="utf-8",
                    )
                    result = self._command_runner(
                        [*argv, "--config", str(config_path)],
                        self.command_timeout_seconds,
                    )
        except subprocess.TimeoutExpired as exc:
            raise WindowsSandboxCommandTimeout(
                f"MXC {operation} timed out; do not reuse the lease until owner-bound cleanup succeeds"
            ) from exc
        except OSError as exc:
            raise WindowsSandboxLifecycleError(
                f"could not start MXC {operation}"
            ) from exc
        if not isinstance(result, WxcCommandResult):
            raise WindowsSandboxLifecycleError(
                "MXC command runner returned an invalid result"
            )
        return result

    @staticmethod
    def _require_success(operation: str, result: WxcCommandResult) -> None:
        if result.returncode != 0:
            raise WindowsSandboxLifecycleError(
                f"MXC {operation} failed with exit code {result.returncode}"
            )

    def provision(self, workspace: str | Path) -> WindowsSandboxLease:
        """Provision one dedicated workspace; MXC does not launch a VM yet."""
        root = self._validate_workspace(workspace)
        with self._lock:
            if self._uncertain_provision:
                raise WindowsSandboxLifecycleError(
                    "previous provision outcome is uncertain; refusing another VM"
                )
            if self._leases:
                raise WindowsSandboxLifecycleError(
                    "this client already owns the single Windows Sandbox lease"
                )
            # The v1.1-alpha lifecycle provision schema rejects `fallback`;
            # it is supported by the one-shot execution request, not here.
            config: dict[str, object] = {
                "version": WINDOWS_SANDBOX_SCHEMA,
                "containment": "windows_sandbox",
                "filesystem": {"readwritePaths": [str(root)], "readonlyPaths": []},
            }
            try:
                result = self._invoke("provision", config=config)
            except WindowsSandboxLifecycleError:
                self._uncertain_provision = True
                raise
            if result.returncode != 0:
                self._uncertain_provision = True
                self._require_success("provision", result)
            try:
                sandbox_id = _extract_sandbox_id(result.stdout)
            except WindowsSandboxLifecycleError:
                self._uncertain_provision = True
                raise
            lease = WindowsSandboxLease(sandbox_id=sandbox_id, workspace=root)
            self._leases[sandbox_id] = lease
            return lease

    def start(self, lease: WindowsSandboxLease) -> None:
        with self._lock:
            self._check_owned_lease(lease)
            if lease.state != "provisioned":
                raise WindowsSandboxLifecycleError("sandbox is not provisioned")
            try:
                result = self._invoke("start", sandbox_id=lease.sandbox_id)
            except WindowsSandboxLifecycleError:
                lease.state = "uncertain"
                raise
            if result.returncode != 0:
                lease.state = "uncertain"
                self._require_success("start", result)
            lease.state = "running"

    def execute(
        self,
        lease: WindowsSandboxLease,
        *,
        command_line: str,
        timeout_ms: int,
    ) -> WxcCommandResult:
        if not isinstance(command_line, str) or not command_line.strip():
            raise ValueError("command line must be a non-empty trusted string")
        if type(timeout_ms) is not int or not 1 <= timeout_ms <= 3_600_000:
            raise ValueError("guest timeout must be between 1ms and 1 hour")
        with self._lock:
            self._check_owned_lease(lease)
            if lease.state != "running":
                raise WindowsSandboxLifecycleError("sandbox is not running")
            try:
                return self._invoke(
                    "exec",
                    sandbox_id=lease.sandbox_id,
                    # Lifecycle exec has its own narrow schema and rejects
                    # the one-shot-only `fallback` field as well.
                    config={
                        "version": WINDOWS_SANDBOX_SCHEMA,
                        "process": {
                            "commandLine": command_line,
                            "timeout": timeout_ms,
                        },
                    },
                )
            except WindowsSandboxCommandTimeout:
                lease.state = "uncertain"
                try:
                    result = self._invoke("deprovision", sandbox_id=lease.sandbox_id)
                    self._require_success("deprovision after exec timeout", result)
                    lease.state = "closed"
                    self._leases.pop(lease.sandbox_id, None)
                except WindowsSandboxLifecycleError:
                    raise WindowsSandboxLifecycleError(
                        "MXC exec timed out and owner-bound deprovision was not confirmed"
                    )
                raise

    def stop(self, lease: WindowsSandboxLease) -> None:
        with self._lock:
            self._check_owned_lease(lease)
            if lease.state not in {"running", "uncertain"}:
                raise WindowsSandboxLifecycleError("sandbox is not running")
            try:
                result = self._invoke("stop", sandbox_id=lease.sandbox_id)
            except WindowsSandboxLifecycleError:
                lease.state = "uncertain"
                raise
            if result.returncode != 0:
                lease.state = "uncertain"
                self._require_success("stop", result)
            lease.state = "provisioned"

    def deprovision(self, lease: WindowsSandboxLease) -> None:
        """Deprovision only a lease issued by this client; MXC stops if needed."""
        with self._lock:
            self._check_owned_lease(lease)
            try:
                result = self._invoke("deprovision", sandbox_id=lease.sandbox_id)
            except WindowsSandboxLifecycleError:
                lease.state = "uncertain"
                raise
            if result.returncode != 0:
                lease.state = "uncertain"
                self._require_success("deprovision", result)
            lease.state = "closed"
            self._leases.pop(lease.sandbox_id, None)

    def terminate(self, lease: WindowsSandboxLease) -> None:
        """Owner-bound cleanup. Never falls back to proofless force-reclaim."""
        self.deprovision(lease)
