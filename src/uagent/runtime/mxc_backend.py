"""MXC sandbox adapter for supported Windows, Linux and macOS sessions.

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
import time
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
_UNREAPED_LINUX_SESSIONS: list[Any] = []

TOOL_NAMES = frozenset(
    {
        "create_file",
        "file_exists",
        "read_file",
        "python_exec",
        "list_dir",
        "search_files",
        "file_grep",
        "file_hash",
        "wc",
        "rename_path",
        "delete_file",
        "replace_in_file",
        "diff_files",
        "archive_ops",
        "document_extract",
        "structured_data",
        "sqlite_query",
        "calculate",
        "python_ast",
        "parse_eml",
        "file_type",
        "image_ops",
        "qr_code",
        "binary_edit",
        "security_scan",
        "git_ops",
    }
)

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


def _sandbox_tool_spec(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required or [],
                "additionalProperties": False,
            },
        },
    }


TOOL_SPECS += (
    _sandbox_tool_spec(
        "list_dir",
        "List entries in the isolated workspace.",
        {
            "path": {"type": "string"},
            "show_hidden": {"type": "boolean"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 500},
            "page": {"type": "integer", "minimum": 1},
        },
    ),
    _sandbox_tool_spec(
        "search_files",
        "Search workspace filenames and optionally file contents.",
        {
            "path": {"type": "string"},
            "glob": {"type": "string", "maxLength": 256},
            "re_content": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 500},
            "page": {"type": "integer", "minimum": 1},
        },
    ),
    _sandbox_tool_spec(
        "file_grep",
        "Find bounded line-numbered regex matches in workspace text files.",
        {
            "pattern": {"type": "string"},
            "path": {"type": "string"},
            "glob": {"type": "string", "maxLength": 256},
            "recur": {"type": "boolean"},
            "ignore_case": {"type": "boolean"},
            "literal": {"type": "boolean"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            "context_lines": {"type": "integer", "minimum": 0, "maximum": 5},
        },
        ["pattern"],
    ),
    _sandbox_tool_spec(
        "file_hash",
        "Hash workspace files using SHA-256, SHA-1, or MD5.",
        {
            "paths": {"type": "array", "items": {"type": "string"}, "maxItems": 100},
            "algo": {"type": "string", "enum": ["sha256", "sha1", "md5"]},
        },
        ["paths"],
    ),
    _sandbox_tool_spec(
        "wc",
        "Count lines, words, bytes, and characters in workspace files.",
        {"paths": {"type": "array", "items": {"type": "string"}, "maxItems": 100}},
        ["paths"],
    ),
    _sandbox_tool_spec(
        "rename_path",
        "Rename or move a file or directory within the workspace.",
        {
            "src": {"type": "string"},
            "dst": {"type": "string"},
            "overwrite": {"type": "boolean"},
            "mkdirs": {"type": "boolean"},
        },
        ["src", "dst"],
    ),
    _sandbox_tool_spec(
        "delete_file",
        "Delete a workspace file/directory; requires confirmed=true.",
        {
            "filename": {"type": "string"},
            "confirmed": {"type": "boolean"},
            "skip": {"type": "boolean"},
        },
        ["filename", "confirmed"],
    ),
    _sandbox_tool_spec(
        "replace_in_file",
        "Replace literal UTF-8 text in a bounded workspace file.",
        {
            "path": {"type": "string"},
            "pattern": {"type": "string"},
            "replacement": {"type": "string"},
            "occurrence": {"type": "integer", "minimum": 0},
        },
        ["path", "pattern", "replacement"],
    ),
    _sandbox_tool_spec(
        "diff_files",
        "Show a bounded unified diff between two workspace files.",
        {
            "path1": {"type": "string"},
            "path2": {"type": "string"},
            "context_lines": {"type": "integer", "minimum": 0, "maximum": 20},
        },
        ["path1", "path2"],
    ),
)


TOOL_SPECS += (
    _sandbox_tool_spec(
        "archive_ops",
        "Create, list, view, or safely extract bounded ZIP archives inside the isolated workspace.",
        {
            "action": {"type": "string", "enum": ["list", "view", "create", "extract"]},
            "zip_path": {"type": "string"},
            "sources": {"type": "array", "items": {"type": "string"}, "maxItems": 500},
            "relative_to": {"type": "string"},
            "target_file": {"type": "string"},
            "dest_dir": {"type": "string"},
            "extract_files": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 100,
            },
            "strip_components": {"type": "integer", "minimum": 0, "maximum": 20},
            "max_files": {"type": "integer", "minimum": 1, "maximum": 500},
            "max_total_uncompressed_bytes": {
                "type": "integer",
                "minimum": 1,
                "maximum": 52428800,
            },
            "dry_run": {"type": "boolean"},
            "overwrite": {"type": "boolean"},
            "encoding": {"type": "string"},
        },
        ["action", "zip_path"],
    ),
    _sandbox_tool_spec(
        "document_extract",
        "Extract bounded text from workspace PDF, DOCX, PPTX, XLSX, ODT, EML, and RTF files without executing macros.",
        {
            "path": {"type": "string"},
            "max_chars": {"type": "integer", "minimum": 1000, "maximum": 128000},
        },
        ["path"],
    ),
    _sandbox_tool_spec(
        "structured_data",
        "Inspect JSON, CSV, XML, TOML, or YAML files stored in the isolated workspace.",
        {
            "path": {"type": "string"},
            "format": {
                "type": "string",
                "enum": ["json", "csv", "xml", "toml", "yaml", "yml"],
            },
            "mode": {"type": "string", "enum": ["summary", "section"]},
            "pointer": {"type": "string"},
            "start_row": {"type": "integer", "minimum": 0},
            "max_rows": {"type": "integer", "minimum": 1, "maximum": 50},
            "encoding": {"type": "string"},
        },
        ["path"],
    ),
    _sandbox_tool_spec(
        "sqlite_query",
        "Run a time- and row-limited read-only query against a workspace SQLite database.",
        {
            "path": {"type": "string"},
            "query": {"type": "string", "maxLength": 10000},
            "limit": {"type": "integer", "minimum": 1, "maximum": 20},
        },
        ["path", "query"],
    ),
    _sandbox_tool_spec(
        "calculate",
        "Evaluate a bounded arithmetic expression with a safe math-function allowlist.",
        {"expression": {"type": "string", "maxLength": 500}},
        ["expression"],
    ),
    _sandbox_tool_spec(
        "python_ast",
        "Parse a workspace Python file and list definitions and imports without executing it.",
        {"path": {"type": "string"}, "encoding": {"type": "string"}},
        ["path"],
    ),
    _sandbox_tool_spec(
        "parse_eml",
        "Extract bounded headers and plain-text body from a workspace EML file.",
        {
            "path": {"type": "string"},
            "max_body_length": {"type": "integer", "minimum": 0, "maximum": 128000},
        },
        ["path"],
    ),
    _sandbox_tool_spec(
        "file_type",
        "Identify a workspace file from its signature and extension without opening external resources.",
        {"path": {"type": "string"}},
        ["path"],
    ),
    _sandbox_tool_spec(
        "image_ops",
        "Inspect, resize, rotate, or grayscale workspace images using Pillow when installed.",
        {
            "path": {"type": "string"},
            "action": {
                "type": "string",
                "enum": ["info", "resize", "rotate", "grayscale"],
            },
            "output_path": {"type": "string"},
            "width": {"type": "integer", "minimum": 1, "maximum": 10000},
            "height": {"type": "integer", "minimum": 1, "maximum": 10000},
            "angle": {"type": "number", "minimum": -360, "maximum": 360},
            "overwrite": {"type": "boolean"},
        },
        ["path"],
    ),
    _sandbox_tool_spec(
        "qr_code",
        "Generate a PNG QR code for text locally inside the workspace, without network access.",
        {
            "text": {"type": "string", "maxLength": 2000},
            "output_path": {"type": "string"},
            "ecc": {"type": "string", "enum": ["L", "M", "Q", "H"]},
            "box_size": {"type": "integer", "minimum": 1, "maximum": 20},
            "border": {"type": "integer", "minimum": 0, "maximum": 10},
            "fill_color": {"type": "string"},
            "back_color": {"type": "string"},
            "overwrite": {"type": "boolean"},
        },
        ["text", "output_path"],
    ),
    _sandbox_tool_spec(
        "binary_edit",
        "Perform bounded hex-based byte write/replace/splice operations on workspace files; supports a no-write dry run.",
        {
            "path": {"type": "string"},
            "mode": {"type": "string", "enum": ["write", "replace", "splice"]},
            "offset": {"type": "integer", "minimum": 0},
            "data_hex": {"type": "string", "maxLength": 2000000},
            "search_hex": {"type": "string", "maxLength": 2000000},
            "replace_hex": {"type": "string", "maxLength": 2000000},
            "occurrence": {"type": "integer", "minimum": 0},
            "splice_op": {"type": "string", "enum": ["insert", "delete"]},
            "delete_len": {"type": "integer", "minimum": 0},
            "dry_run": {"type": "boolean"},
        },
        ["path", "mode"],
    ),
    _sandbox_tool_spec(
        "security_scan",
        "Scan workspace text files for common credential patterns and report locations only; secret values are never returned.",
        {
            "path": {"type": "string"},
            "glob": {"type": "string", "maxLength": 256},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        },
    ),
    _sandbox_tool_spec(
        "git_ops",
        "Inspect or mutate only a local Git repository inside the isolated workspace. Remote/network commands are excluded; mutations require confirmed=true.",
        {
            "command": {
                "type": "string",
                "enum": [
                    "status",
                    "diff",
                    "log",
                    "branch",
                    "rev-parse",
                    "rev-list",
                    "show",
                    "ls-files",
                    "grep",
                    "tag",
                    "reflog",
                    "blame",
                    "ls-tree",
                    "cat-file",
                    "init",
                    "add",
                    "commit",
                    "switch",
                    "checkout",
                    "reset",
                    "restore",
                    "merge",
                    "rebase",
                    "stash",
                    "rm",
                ],
            },
            "args": {
                "type": "array",
                "items": {"type": "string", "maxLength": 1000},
                "maxItems": 40,
            },
            "confirmed": {"type": "boolean"},
        },
        ["command"],
    ),
)


def sandbox_tool_specs() -> list[dict[str, Any]]:
    return json.loads(json.dumps(TOOL_SPECS))


def _trusted_home() -> Path:
    if sys.platform.startswith("linux") or sys.platform == "darwin":
        try:
            import pwd

            return Path(pwd.getpwuid(os.getuid()).pw_dir).resolve()
        except (ImportError, KeyError, OSError) as exc:
            raise RuntimeError(
                "Linux MXC requires a resolvable local user home"
            ) from exc
    return Path.home().resolve()


def _local_app_data() -> Path:
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA")
        if not root:
            raise RuntimeError(
                "LOCALAPPDATA is unavailable; MXC needs a per-user runtime directory"
            )
        path = Path(root).expanduser()
        if not path.is_absolute():
            raise RuntimeError("LOCALAPPDATA must be an absolute per-user path")
        return path.resolve()
    if sys.platform.startswith("linux"):
        # Ignore XDG_DATA_HOME/HOME from project dotenv; use the passwd entry.
        return _trusted_home() / ".local" / "share"
    if sys.platform == "darwin":
        return _trusted_home() / "Library" / "Application Support"
    raise RuntimeError("MXC runtime paths are unsupported on this operating system")


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


def _startup_path_node() -> Path | None:
    """Find Node only in PATH captured before project dotenv loading."""
    try:
        from .runtime_init import get_startup_path_snapshot

        startup_path = get_startup_path_snapshot()
    except Exception:
        startup_path = ""
    if not startup_path:
        return None
    executable = "node.exe" if os.name == "nt" else "node"
    found = shutil.which(executable, path=startup_path)
    if not found:
        return None
    try:
        return Path(found).resolve()
    except OSError:
        return Path(found)


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
    if os.name == "nt":
        candidates.extend(
            [
                local / "uagent" / "toolchains" / "node-v24.22.0" / "node.exe",
                local / "Programs" / "nodejs" / "node.exe",
            ]
        )
        # Use the trusted process-startup PATH as a final discovery location.
        # Do not consult os.environ['PATH'] here: project dotenv values are
        # loaded before MXC initialization and must not select host executables.
        startup_path_node = _startup_path_node()
        if startup_path_node is not None:
            candidates.append(startup_path_node)
    elif sys.platform.startswith("linux"):
        candidates.append(
            local / "uagent" / "toolchains" / "node-v24.22.0" / "bin" / "node"
        )
        system_node = shutil.which("node", path="/usr/local/bin:/usr/bin:/bin")
        if system_node:
            candidates.append(Path(system_node))
    elif sys.platform == "darwin":
        candidates.append(
            local / "uagent" / "toolchains" / "node-v24.22.0" / "bin" / "node"
        )
        system_node = shutil.which(
            "node", path="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
        )
        if system_node:
            candidates.append(Path(system_node))
    return candidates


def _find_node() -> Path:
    for candidate in _node_candidates():
        try:
            if candidate.is_file() and (
                os.name == "nt" or os.access(candidate, os.X_OK)
            ):
                return candidate.resolve()
        except OSError:
            continue
    if sys.platform.startswith("linux"):
        raise RuntimeError(
            "Node.js 24.21+ x64 is required for Linux MXC. Install Node.js in a trusted "
            "system path or user-local toolchain, or set the trusted startup override "
            "UAGENT_MXC_NODE; no host-level installation is attempted."
        )
    if sys.platform == "darwin":
        raise RuntimeError(
            "Node.js 24.21+ ARM64 is required for macOS MXC Seatbelt. "
            "Install trusted Node.js in /opt/homebrew/bin, /usr/local/bin, "
            "or set UAGENT_MXC_NODE at process startup."
        )
    raise RuntimeError(
        "Node.js 24.21+ x64 is required for MXC. Install a user-local Node 24 runtime "
        "or set UAGENT_MXC_NODE to node.exe; no host-level installation is attempted."
    )


def _node_version(node: Path) -> tuple[int, int, int]:
    if sys.platform.startswith("linux") or sys.platform == "darwin":
        safe_path = os.pathsep.join((str(node.parent), "/usr/local/bin:/usr/bin:/bin"))
        home = str(_trusted_home())
        env = {"PATH": safe_path, "HOME": home, "LANG": "C.UTF-8"}
    else:
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        safe_path = os.pathsep.join(
            (str(node.parent), str(Path(system_root) / "System32"))
        )
        env = {
            "SystemRoot": os.environ.get("SystemRoot", r"C:\Windows"),
            "WINDIR": os.environ.get("WINDIR", r"C:\Windows"),
            "PATH": safe_path,
        }
    result = subprocess.run(
        [str(node), "--version"],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
        shell=False,
        env=env,
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


def _npm_command(node: Path) -> list[str]:
    if os.name == "nt":
        npm = node.with_name("npm.cmd")
        if not npm.is_file():
            raise RuntimeError(
                "npm.cmd was not found alongside the selected Node.js runtime"
            )
        return [str(npm)]
    path = os.pathsep.join((str(node.parent), "/usr/local/bin:/usr/bin:/bin"))
    if sys.platform == "darwin":
        path = os.pathsep.join(
            (str(node.parent), "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin")
        )
    npm = shutil.which("npm", path=path)
    if not npm:
        raise RuntimeError("npm is required to provision the pinned MXC SDK")
    return [str(Path(npm).resolve())]


def prepare_mxc_runtime(*, allow_install: bool = False) -> tuple[Path, Path]:
    """Prepare the per-user helper and, only with opt-in consent, install the pinned SDK."""
    machine = platform.machine().lower()
    is_windows_x64 = os.name == "nt" and machine in {"amd64", "x86_64"}
    is_linux_x64 = sys.platform.startswith("linux") and machine in {
        "amd64",
        "x86_64",
    }
    is_macos_arm64 = sys.platform == "darwin" and machine in {"arm64", "aarch64"}
    if not (is_windows_x64 or is_linux_x64 or is_macos_arm64):
        raise RuntimeError(
            "MXC requires Windows/Linux x86_64 or macOS Apple Silicon ARM64"
        )
    node = _find_node()
    node_version = _node_version(node)
    version_supported = (node_version[0] == 24 and node_version >= NODE_MINIMUM) or (
        node_version[0] == 26 and node_version >= (26, 8, 0)
    )
    if not version_supported:
        raise RuntimeError(
            "MXC requires Node.js 24.21.0+ or 26.8.0+ on the supported host"
        )
    runtime = _validate_sandbox_read_root(
        _runtime_dir(), require_existing_directory=False
    )
    runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
    if is_linux_x64 or is_macos_arm64:
        runtime.chmod(0o700)
    source = _helper_source_dir()
    for filename in (
        "mxc_adapter.mjs",
        "seatbelt_smoke.mjs",
        "package.json",
        "package-lock.json",
    ):
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
        npm = _npm_command(node)
        if is_windows_x64:
            system_root = os.environ.get("SystemRoot", "C:/Windows")
            safe_path = os.pathsep.join(
                (str(node.parent), str(Path(system_root) / "System32"))
            )
            install_env = {
                "SystemRoot": os.environ.get("SystemRoot", "C:/Windows"),
                "WINDIR": os.environ.get("WINDIR", "C:/Windows"),
                "PATH": safe_path,
                "LOCALAPPDATA": os.environ.get("LOCALAPPDATA", ""),
                "TEMP": os.environ.get("TEMP", ""),
                "TMP": os.environ.get("TMP", ""),
                "APPDATA": os.environ.get("APPDATA", ""),
                "USERPROFILE": os.environ.get("USERPROFILE", ""),
            }
        else:
            npm_home = runtime / ".npm-home"
            npm_tmp = runtime / ".tmp"
            npm_cache = runtime / ".npm-cache"
            for directory in (npm_home, npm_tmp, npm_cache):
                directory.mkdir(parents=True, exist_ok=True, mode=0o700)
                directory.chmod(0o700)
            install_env = {
                "PATH": os.pathsep.join(
                    (str(node.parent), "/usr/local/bin:/usr/bin:/bin")
                ),
                "HOME": str(npm_home),
                "TMPDIR": str(npm_tmp),
                "npm_config_cache": str(npm_cache),
                "LANG": "C.UTF-8",
            }
            if is_macos_arm64:
                install_env["PATH"] = os.pathsep.join(
                    (str(node.parent), "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin")
                )
        install = subprocess.run(
            [*npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund"],
            cwd=str(runtime),
            capture_output=True,
            text=True,
            timeout=600,
            shell=False,
            env=install_env,
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
    linux_scope = None
    mac_scope = None
    if sys.platform.startswith("linux"):
        from .mxc_linux_scope import LinuxSystemdScope

        temp = runtime / ".tmp"
        temp.mkdir(parents=True, exist_ok=True, mode=0o700)
        env = {
            "PATH": os.pathsep.join((str(node.parent), "/usr/local/bin:/usr/bin:/bin")),
            "HOME": str(_trusted_home()),
            "TMPDIR": str(temp),
            "LANG": "C.UTF-8",
        }
        linux_scope = LinuxSystemdScope.launch(
            [str(node), str(helper), "probe"],
            cwd=runtime,
            env=env,
            unit_prefix="uagent-mxc-probe",
        )
        proc = linux_scope.process
    elif sys.platform == "darwin":
        from .mxc_macos_scope import MacosProcessGroup

        temp = runtime / ".tmp"
        temp.mkdir(parents=True, exist_ok=True, mode=0o700)
        env = {
            "PATH": os.pathsep.join(
                (str(node.parent), "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin")
            ),
            "HOME": str(_trusted_home()),
            "TMPDIR": str(temp),
            "LANG": "C",
        }
        mac_scope = MacosProcessGroup.launch(
            [str(node), str(helper), "probe"], cwd=runtime, env=env
        )
        proc = mac_scope.process
    else:
        system_root = os.environ.get("SystemRoot", "C:/Windows")
        safe_path = os.pathsep.join(
            (str(node.parent), str(Path(system_root) / "System32"))
        )
        env = {
            "SystemRoot": os.environ.get("SystemRoot", "C:/Windows"),
            "WINDIR": os.environ.get("WINDIR", "C:/Windows"),
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
    job_api = None
    job = None
    if linux_scope is None and mac_scope is None:
        try:
            job_api, job = _assign_job_object(proc)
        except Exception:
            proc.kill()
            proc.wait(timeout=5)
            raise
    try:
        assert proc.stdin is not None
        if linux_scope is not None or mac_scope is not None:
            proc.stdin.write(b'{"probe":true}' + bytes([10]))
        else:
            proc.stdin.write('{"probe":true}' + chr(10))
        proc.stdin.flush()
        try:
            if mac_scope is not None:
                # Popen.communicate() may reap the helper outside the macOS
                # watchdog lock. Drain pipes independently; lock only poll.
                stdout, stderr = mac_scope.communicate_bounded(
                    timeout=PROBE_TIMEOUT_SECONDS
                )
            else:
                stdout, stderr = proc.communicate(timeout=PROBE_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired as exc:
            if linux_scope is not None:
                linux_scope.close()
            elif mac_scope is not None:
                mac_scope.close()
            elif job is not None:
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
        if linux_scope is not None:
            linux_scope.close()
        elif mac_scope is not None:
            mac_scope.close()
        else:
            if job is not None:
                job_api.CloseHandle(job)
            if proc.poll() is None:
                proc.kill()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", errors="replace")
    if len(stdout.encode("utf-8", errors="replace")) > MAX_FRAME_BYTES:
        raise RuntimeError("MXC host probe returned an oversized response")
    try:
        report = json.loads(stdout.splitlines()[0])
    except (IndexError, ValueError) as exc:
        raise RuntimeError(
            f"MXC host probe returned invalid JSON: {stderr[-1000:]}"
        ) from exc
    if proc.returncode != 0 or report.get("ok") is not True:
        error = str(report.get("error") or "MXC backend probe failed")
        probe_details = report.get("probe")
        if isinstance(probe_details, dict):
            error += (
                " (probe details: "
                + json.dumps(probe_details, ensure_ascii=False)
                + ")"
            )
        raise RuntimeError(error)
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


def _remove_dormant_web_workspace(scope: TrustedSandboxScope) -> None:
    """Delete a parked Room workspace only after acquiring its owner lease."""
    workspace = _workspace_for_scope(scope)
    lease = _acquire_workspace_lease(workspace.parent, workspace.name)
    if lease is None:
        return
    try:
        if workspace.exists():
            _remove_workspace_tree(workspace)
    except (OSError, RuntimeError):
        # Cleanup failure must not follow a reparse point or abort Room teardown.
        pass
    finally:
        _release_workspace_lease(lease)


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
        sandbox_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        lease_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if sys.platform.startswith("linux"):
            sandbox_root.chmod(0o700)
            lease_root.chmod(0o700)
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
        if sys.platform.startswith("linux"):
            os.fchmod(fd, 0o600)
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
    """Remove abandoned workspaces only when cleanup is actually provable."""
    if sys.platform == "darwin":
        # Unlike Job Objects or cgroup scopes, a POSIX process group has no
        # kernel-owned stale scope to query after the controlling host exits.
        # Never reclaim a potentially still-writable workspace after a crash.
        return
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
                if sys.platform.startswith("linux"):
                    from .mxc_linux_scope import stop_stale_scope

                    stop_stale_scope(key)
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
    protected_paths = [Path.cwd().resolve(), _trusted_home()]
    for variable in (
        "USERPROFILE",
        "LOCALAPPDATA",
        "APPDATA",
        "HOME",
        "XDG_DATA_HOME",
        "XDG_RUNTIME_DIR",
    ):
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
        self,
        *,
        scope: TrustedSandboxScope,
        node: Path,
        runtime: Path,
        resume_workspace: bool = False,
    ) -> None:
        self._linux_scope = None
        self._mac_scope = None
        if os.name == "nt":
            try:
                import win32api
                import win32job
            except ImportError as exc:
                raise RuntimeError(
                    "pywin32 Job Object support is required for safe MXC cleanup and resource limits"
                ) from exc
            self._win32api = win32api
            self._win32job = win32job
        elif sys.platform.startswith("linux") and platform.machine().lower() in {
            "amd64",
            "x86_64",
        }:
            self._win32api = None
            self._win32job = None
        elif sys.platform == "darwin" and platform.machine().lower() in {
            "arm64",
            "aarch64",
        }:
            self._win32api = None
            self._win32job = None
        else:
            raise RuntimeError("MXC session requested on an unsupported host platform")
        self._lock = threading.RLock()
        self._responses: Queue[str | None] = Queue()
        self._stderr = bytearray()
        self._stderr_lock = threading.Lock()
        self._revoked = threading.Event()
        self._closed = False
        self._workspace_preserved = False
        self._scope = scope
        self.workspace = _workspace_for_scope(scope)
        self._workspace_lease = _acquire_workspace_lease(
            self.workspace.parent, self.workspace.name
        )
        if self._workspace_lease is None:
            raise RuntimeError("sandbox workspace already has an active owner")
        if self.workspace.exists() and _is_reparse_point(self.workspace):
            raise RuntimeError("sandbox workspace root cannot be a symlink")
        self.workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
        if sys.platform.startswith("linux"):
            self.workspace.chmod(0o700)
        # Web Room sessions may be parked by the owning manager. Only that
        # trusted in-process path opts into resuming its still-leased scope.
        if not resume_workspace and any(self.workspace.iterdir()):
            if sys.platform == "darwin":
                # A stale workspace can still be written by an orphan after a
                # host crash. Preserve evidence and refuse reuse or deletion.
                _release_workspace_lease(self._workspace_lease)
                self._workspace_lease = None
                raise RuntimeError(
                    "macOS MXC cannot safely reuse an unverified stale workspace"
                )
            _remove_workspace_tree(self.workspace)
            self.workspace.mkdir(parents=True, mode=0o700)
        if sys.platform.startswith("linux"):
            self.workspace.chmod(0o700)
        worker_script = runtime / "sandbox_worker.py"
        source_worker = Path(__file__).with_name("sandbox_worker.py")
        shutil.copy2(source_worker, worker_script)
        python_exe = Path(sys.executable).resolve()
        if not python_exe.is_file():
            raise RuntimeError("current Python executable is unavailable")
        python_root = _python_root()
        python_env_root = _python_env_root()
        if os.name == "nt":
            system_root = Path(os.environ.get("SystemRoot", "C:/Windows"))
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
                if not resume_workspace:
                    try:
                        _remove_workspace_tree(self.workspace)
                    except (OSError, RuntimeError):
                        pass
                _release_workspace_lease(self._workspace_lease)
                self._workspace_lease = None
                raise
        else:
            if sys.platform.startswith("linux"):
                from .mxc_linux_scope import LinuxSystemdScope
            else:
                from .mxc_macos_scope import MacosProcessGroup

            helper_tmp = runtime / ".tmp"
            helper_tmp.mkdir(parents=True, exist_ok=True, mode=0o700)
            helper_env = {
                "PATH": os.pathsep.join(
                    (str(node.parent), "/usr/local/bin:/usr/bin:/bin")
                ),
                "HOME": str(_trusted_home()),
                "TMPDIR": str(helper_tmp),
                "LANG": "C.UTF-8",
            }
            if sys.platform == "darwin":
                helper_env["PATH"] = os.pathsep.join(
                    (str(node.parent), "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin")
                )
            try:
                if sys.platform.startswith("linux"):
                    self._linux_scope = LinuxSystemdScope.launch(
                        [str(node), str(runtime / "mxc_adapter.mjs"), "worker"],
                        cwd=runtime,
                        env=helper_env,
                        unit=f"uagent-mxc-{_scope_key(scope)}.scope",
                    )
                    self._proc = self._linux_scope.process
                else:
                    self._mac_scope = MacosProcessGroup.launch(
                        [str(node), str(runtime / "mxc_adapter.mjs"), "worker"],
                        cwd=runtime,
                        env=helper_env,
                    )
                    self._proc = self._mac_scope.process
                self._job = None
            except Exception as exc:
                unreaped_scope = getattr(exc, "scope", None)
                if unreaped_scope is not None:
                    # Retain both the scope and its workspace lease: an
                    # unverified child must never overlap a reused workspace.
                    _UNREAPED_LINUX_SESSIONS.append(
                        (unreaped_scope, self._workspace_lease)
                    )
                    self._workspace_lease = None
                else:
                    if not resume_workspace:
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
            self.close(preserve_workspace=resume_workspace)
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
        if self._closed or self._proc.stdin is None:
            raise RuntimeError("MXC session process is not running")
        stopped = (
            self._mac_scope.poll() is not None
            if self._mac_scope is not None
            else self._proc.poll() is not None
        )
        if stopped:
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
            if self._mac_scope is not None and self._mac_scope.error:
                raise RuntimeError(
                    f"macOS MXC process-group watchdog failed closed: {self._mac_scope.error}"
                )
            if self._linux_scope is not None and self._linux_scope.cpu_exceeded:
                raise RuntimeError(
                    "Linux MXC aggregate CPU budget exceeded; the cgroup was stopped"
                )
            if self._linux_scope is not None and self._linux_scope.watchdog_error:
                raise RuntimeError(
                    f"Linux MXC cgroup watchdog failed closed: {self._linux_scope.watchdog_error}"
                )
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
            if self._revoked.is_set():
                raise PermissionError("sandbox scope has been revoked")
            mac_baseline = (
                self._mac_scope.snapshot()
                if self._mac_scope is not None and name == "python_exec"
                else None
            )
            self._write_line(
                {"operation": "run", "payload": {"name": name, "args": args}}
            )
            response = self._read_response(timeout=60 if name == "python_exec" else 45)
            if mac_baseline is not None:
                # Native MXC process-group kill alone may miss setsid children.
                # Fail closed if observed detached descendants cannot be reaped
                # before the tool result is made visible to the caller.
                self._mac_scope.reap_since(mac_baseline)
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

    def revoke(self) -> None:
        """Prevent queued requests from entering the worker after revocation."""
        self._revoked.set()

    def close(self, *, preserve_workspace: bool = False) -> None:
        with self._lock:
            if self._closed:
                return
            self._revoked.set()
            self._closed = True
            try:
                if self._proc.stdin:
                    self._proc.stdin.close()
            except OSError:
                pass
            cleanup_verified = True
            if self._linux_scope is not None or self._mac_scope is not None:
                try:
                    if self._linux_scope is not None:
                        self._linux_scope.close()
                    else:
                        self._mac_scope.close()
                except Exception:
                    # Keep the scope object and workspace lease alive. Releasing
                    # either after an unverified cgroup stop could let a live
                    # worker mutate a workspace that has been reused.
                    cleanup_verified = False
                    _UNREAPED_LINUX_SESSIONS.append(self)
            else:
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
                        cleanup_verified = False
            # Never park or delete a workspace unless the host process group is
            # confirmed stopped; otherwise it could keep mutating the directory.
            preserve_workspace = bool(
                cleanup_verified
                and preserve_workspace
                and (
                    self._mac_scope.poll() is not None
                    if self._mac_scope is not None
                    else self._proc.poll() is not None
                )
            )
            self._workspace_preserved = preserve_workspace
            if cleanup_verified:
                if not preserve_workspace:
                    try:
                        _remove_workspace_tree(self.workspace)
                    except (OSError, RuntimeError):
                        pass
                _release_workspace_lease(self._workspace_lease)
                self._workspace_lease = None


class MxcSessionManager:
    """Own bounded MXC workers and park idle Web Room workspaces for reuse."""

    def __init__(
        self, *, node: Path, runtime: Path, capabilities: SandboxCapabilities
    ) -> None:
        self.node = node
        self.runtime = runtime
        self.capabilities = capabilities
        self._sessions: dict[str, _MxcSession] = {}
        self._session_inflight: dict[str, int] = {}
        self._session_last_used: dict[str, float] = {}
        self._dormant_web_scopes: dict[str, TrustedSandboxScope] = {}
        self._active_local_scopes: dict[tuple[str, str, str], TrustedSandboxScope] = {}
        self._active_web_scopes: set[TrustedSandboxScope] = set()
        self._active_a2a_scopes: set[TrustedSandboxScope] = set()
        self._lock = threading.RLock()
        if (
            os.name == "nt"
            or sys.platform.startswith("linux")
            or sys.platform == "darwin"
        ):
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
        """Release exited workers, parking live Web Room workspaces for reuse."""
        for key, session in list(self._sessions.items()):
            if session._closed:
                exited = True
            else:
                mac_scope = getattr(session, "_mac_scope", None)
                exited = (
                    mac_scope.poll() is not None
                    if mac_scope is not None
                    else session._proc.poll() is not None
                )
            if exited:
                self._sessions.pop(key, None)
                self._session_last_used.pop(key, None)
                scope = getattr(session, "_scope", None)
                preserve = bool(
                    not session._closed
                    and getattr(scope, "scope_kind", None) == "web-room"
                    and scope in self._active_web_scopes
                )
                if preserve:
                    try:
                        session.close(preserve_workspace=True)
                    except TypeError:
                        session.close()
                        preserve = False
                    if preserve and getattr(session, "_workspace_preserved", True):
                        self._dormant_web_scopes[key] = scope
                else:
                    session.close()

    def _evict_idle_web_session(self) -> bool:
        """Park the least-recently-used idle Web session without losing its files."""
        candidates = [
            (self._session_last_used.get(key, 0.0), key, session)
            for key, session in self._sessions.items()
            if self._session_inflight.get(key, 0) == 0
            and getattr(getattr(session, "_scope", None), "scope_kind", None)
            == "web-room"
            and getattr(session, "_scope", None) in self._active_web_scopes
        ]
        if not candidates:
            return False
        _, key, session = min(candidates, key=lambda item: item[0])
        scope = session._scope
        self._sessions.pop(key, None)
        self._session_last_used.pop(key, None)
        try:
            session.close(preserve_workspace=True)
        except TypeError:
            # Unknown session implementations must not claim a reusable workspace.
            session.close()
            return False
        if not getattr(session, "_workspace_preserved", True):
            return False
        self._dormant_web_scopes[key] = scope
        return True

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
                revoke = getattr(session, "revoke", None)
                if callable(revoke):
                    revoke()
                self._sessions.pop(key, None)
                session.close()

    def activate_scope(self, scope: TrustedSandboxScope) -> None:
        """Activate a trusted local, Web Room, or A2A Task scope."""
        if scope.scope_kind == "web-room":
            if scope.deployment_id != "web" or not scope.binding_generation:
                raise ValueError("Web Room scope requires a binding generation")
            with self._lock:
                self._active_web_scopes.add(scope)
            return
        if scope.scope_kind == "a2a-task":
            if scope.deployment_id != "a2a":
                raise ValueError("A2A Task scope has an invalid deployment")
            with self._lock:
                self._active_a2a_scopes.add(scope)
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
            "a2a-task": "a2a",
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
            if scope.scope_kind == "a2a-task" and scope not in self._active_a2a_scopes:
                return "[sandbox error] revoked or unbound A2A Task scope rejected"
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
                    if (
                        scope.scope_kind != "web-room"
                        or not self._evict_idle_web_session()
                    ):
                        return (
                            "[sandbox error] active session limit reached; no idle "
                            "Web Room session can be parked safely"
                        )
                resume_workspace = self._dormant_web_scopes.get(key) == scope
                try:
                    session_args = {
                        "scope": scope,
                        "node": self.node,
                        "runtime": self.runtime,
                    }
                    if resume_workspace:
                        session_args["resume_workspace"] = True
                    session = _MxcSession(**session_args)
                except Exception as exc:
                    return f"[sandbox error] unable to create MXC session: {type(exc).__name__}: {exc}"
                self._sessions[key] = session
                self._session_last_used[key] = time.monotonic()
                if resume_workspace:
                    self._dormant_web_scopes.pop(key, None)
            self._session_inflight[key] = self._session_inflight.get(key, 0) + 1
        try:
            return session.run(name, args)
        except Exception as exc:
            revoke = getattr(session, "revoke", None)
            if callable(revoke):
                revoke()
            session.close()
            with self._lock:
                if self._sessions.get(key) is session:
                    self._sessions.pop(key, None)
                self._session_last_used.pop(key, None)
                self._dormant_web_scopes.pop(key, None)
            return f"[sandbox error] isolated session terminated: {type(exc).__name__}: {exc}"
        finally:
            with self._lock:
                in_flight = self._session_inflight.get(key, 0)
                if in_flight <= 1:
                    self._session_inflight.pop(key, None)
                else:
                    self._session_inflight[key] = in_flight - 1
                if self._sessions.get(key) is session:
                    self._session_last_used[key] = time.monotonic()

    def revoke_scope(self, scope: TrustedSandboxScope) -> Callable[[], None] | None:
        """Fence a scope and return cleanup for its active or parked workspace."""
        key = _scope_key(scope)
        with self._lock:
            if scope.scope_kind == "web-room":
                self._active_web_scopes.discard(scope)
            elif scope.scope_kind == "a2a-task":
                self._active_a2a_scopes.discard(scope)
            session = self._sessions.pop(key, None)
            self._session_last_used.pop(key, None)
            dormant_scope = self._dormant_web_scopes.pop(key, None)
            revoke = getattr(session, "revoke", None)
            if callable(revoke):
                revoke()
        if session is not None:
            return session.close
        if dormant_scope is not None:
            return lambda: _remove_dormant_web_workspace(dormant_scope)
        return None

    def close_scope(self, scope: TrustedSandboxScope) -> None:
        cleanup = self.revoke_scope(scope)
        if cleanup is not None:
            cleanup()

    def close_all(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            dormant_scopes = list(self._dormant_web_scopes.values())
            self._sessions.clear()
            self._session_inflight.clear()
            self._session_last_used.clear()
            self._dormant_web_scopes.clear()
            self._active_local_scopes.clear()
            self._active_web_scopes.clear()
            self._active_a2a_scopes.clear()
            for session in sessions:
                revoke = getattr(session, "revoke", None)
                if callable(revoke):
                    revoke()
        for session in sessions:
            session.close()
        for scope in dormant_scopes:
            _remove_dormant_web_workspace(scope)


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
