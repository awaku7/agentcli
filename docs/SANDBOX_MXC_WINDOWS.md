# Windows MXC ProcessContainer Sandbox

The Windows MXC ProcessContainer backend is the default baseline for Remote Web
and tool-enabled A2A; trusted local CLI/GUI and local-only Web remain opt-in or
off as documented below. It is **not** Windows Sandbox/Hyper-V VM isolation and
does not, by itself, establish Enterprise E0 completion or a production
multi-tenant security guarantee. See [Remote Web / A2A MXC default policy](REMOTE_MXC_DEFAULT.md)
for the current decision and explicit limits.

## Usage

- Trusted local CLI/GUI and trusted local-only Web retain Sandbox-off behavior
  unless explicitly enabled; when off, they do not probe MXC or install
  dependencies.
- Remote Web defaults to `--sandbox auto`; tool-enabled A2A initializes MXC at
  startup. Both use only an already-installed supported backend and fail closed
  if Node, the SDK, the host capability probe, or resource controls are
  unavailable. Remote startup never prompts to install dependencies and never
  falls back to Host tool execution. Remote Web is determined from trusted
  startup bind/identity configuration, not request headers or the client's IP.
- `uag --sandbox auto`, `uagg --sandbox auto`, and explicit local Web
  `--sandbox auto` also use an already-installed supported backend. The
  `--sandbox mxc` option on CLI/GUI or trusted local-only Web opts into Windows
  MXC ProcessContainer. On first interactive local use, UAG asks before
  installing the pinned SDK in the current user's profile (about 105 MB). Web
  startup refuses to install in non-interactive mode. Installation uses the Node
  runtime already available to the user and does not request elevation. If
  Node.js 24.21+ x64 or 26.8+ x64 is unavailable, startup stops; UAG does not
  install Node at machine scope.
- `--sandbox off` on Remote Web does not enable Host tools. `--no-use-tool` /
  `UAGENT_USE_TOOL=off` is the explicit tool-less mode for A2A and avoids MXC
  initialization.
- `UAGENT_SANDBOX_MODE=off|auto|mxc` is the environment equivalent (including
  the selected workdir's dotenv files). CLI arguments take precedence and mode
  resolution occurs after the workdir environment is loaded.
- `UAGENT_MXC_NODE` and `UAGENT_MXC_RUNTIME_DIR`, when used, are trusted
  process-startup overrides only; values from a project's `.env`/`.env.sec` are
  ignored. Relative override paths are rejected. Node/npm subprocesses use a
  minimal PATH containing only the selected Node directory and Windows System32.
- `uag realtime` is not supported with `--sandbox auto|mxc` or an equivalent
  environment setting. Realtime dependencies may be installed/executed on the
  Host; Sandbox-enabled realtime startup is refused before the realtime runner.

The verified PoC target is Windows 11 x64 with MXC Node SDK `1.0.0`, Node
`24.22.0`, and the MXC `base-container` ProcessContainer tier. The adapter rejects
other operating systems/architectures, unsupported Windows builds, probe
warnings, DACL-augmentation requirements, and missing deny-path support. There
is no fallback to Host execution.

This PoC assumes that UAG itself, the Host Python interpreter and dependencies,
and the Python startup/import path are trusted. Running `python -m uagent`
with an untrusted project on Python's import path can execute project-supplied
modules on the Host before MXC isolation begins (including shadowed `win32api`
or `win32job` modules). Do not treat Sandbox mode as protection against
untrusted Host startup/import code; launch UAG from a trusted environment.
Hardening that entire startup boundary is outside this local tool-execution PoC.

## Execution boundary

The LLM receives only four locally sandboxed tools: `create_file`, `file_exists`,
`read_file`, and `python_exec`. The first three use relative paths under a
per-scope workspace in the user's local application data directory; they do
not read or publish the host project tree. Absolute paths, traversal, symlinks,
and oversized files/results are rejected. `read_file` returns at most 128,000
source bytes per call so JSON-escaped content stays below the IPC response cap.
`python_exec` runs in its own
short-lived ProcessContainer using the same scope workspace, so files created
by one tool remain visible to later tools. Its stdout/stderr are capped at 64 KiB
per stream and execution is forcibly stopped after 30 seconds. The completion
marker is normally emitted from an `atexit` handler registered before user
code, but it is an in-process stdout marker that sandboxed Python can inspect
and spoof. It is therefore not an authenticated guarantee that user shutdown
handlers completed or that execution ended normally. This is a known PoC
limitation of result/completion reporting, not a claim of MXC isolation escape.
The workspace quota watchdog remains active until the ProcessContainer has
been stopped. MXC's ProcessContainer assigns the suspended root process to a
Job Object before it is resumed; its native `wait()`/`kill()` path terminates
and reaps that process tree.
The adapter uses those SDK lifecycle operations rather than host PID-based
termination. If MXC cannot confirm process cleanup, quota scanning fails, or the
completion marker is missing, execution is rejected; unverified cleanup tears
down the session. Both probe and execution requests explicitly forbid MXC's
host-DACL-mutation fallback.

The worker receives a minimal environment, not the Host's `os.environ`. Its
filesystem policy grants write access only to the session workspace and read
access only to the Python runtime, adapter files, and Windows system runtime.
Recursive read roots are rejected if they are filesystem roots or contain the
selected work directory or per-user data roots. This prevents a project-root venv
from exposing the project recursively. Sandbox startup also skips the host-side
Laya/PyTorch preload.
Network egress, ingress, and host loopback are denied. A Windows Job Object
around the adapter enforces a 1 GiB aggregate memory cap, a 64-process limit, a
four-hour aggregate user-CPU limit, and kill-on-close cleanup. A 256 MiB / 5,000
entry workspace watchdog stops the Python execution and tears down the session
when it detects an over-limit workspace. That workspace guard is an application
watchdog, not an NTFS hard quota; a short write burst can temporarily exceed the
threshold. Quota scans skip child entries concurrently removed from the workspace,
including during NTFS alternate-stream inspection; partial stream counts for a
vanished entry are discarded. A missing root or any other scan error still fails
closed. A host-side OS lock lease is held for each workspace and released during
normal cleanup; on startup, only directories with an unlocked lease are scavenged,
so workspaces abandoned by a crashed process are reclaimed on the next startup,
without removing live sessions. Removal clears read-only attributes; an otherwise
unremovable workspace is skipped rather than blocking startup. Legacy directories
without lease metadata are left untouched. CLI session transitions close the previous CLI worker. At most four MXC worker
processes are live at once. When all slots are occupied, the least-recently-used
idle Web Room worker is closed while its room-specific workspace is parked and
reused on that Room's next tool call. Revoking a parked Room scope deletes its
workspace. Non-Web scopes are not evicted; if no idle Web worker can be parked,
the request fails closed. Failure to create or assign the Job Object rejects the
operation.

Web and A2A use the same static MXC tool allowlist. Web Room scopes are bound
to authenticated server-created Room/Principal context. Spawned per-turn workers
send fixed-schema Sandbox tool requests over a size-bounded private JSON pipe;
the parent revalidates the active Room scope and authorization for each request
before dispatching to its MXC session. A2A receives a server-created per-task
scope and closes it at task completion. The MXC manager caps active sessions.
Sandbox mode also blocks Host plugin imports, Host hooks, tool-genre changes,
general Web commands, and non-allowlisted tools.

Remote Web and tool-enabled A2A now use ProcessContainer by default. This is a
process/container boundary, **not** VM isolation and not a claim of completed
Enterprise E0 acceptance. The high-assurance VM tier remains deferred; setting
`UAGENT_REMOTE_SANDBOX_MIN_ISOLATION=vm` requires a future VM-capable backend and
fails closed with the current ProcessContainer. The recorded Windows 11 Home
smoke test below exercised the local Web route, not a real Remote Web/A2A
production flow.

## Windows 11 x64 validation record

Validation on this machine: Windows 11 25H2, build `26200.9457`, AMD64;
MXC SDK `@microsoft/mxc-sdk@1.0.0`; Node `24.22.0`; MXC probe selected
`base-container`, reported no warnings, and reported deny-path support with no
DACL augmentation required.

A real ProcessContainer run validated:

1. `create_file` → `python_exec` → `read_file` against the same session workspace.
1. Python code could not read a Host canary file under the repository tree.
1. Python code could not connect to a Host `127.0.0.1` listener.
1. A Python child process sleeping for 300 seconds was no longer present after
   its one-shot ProcessContainer completed.
1. A 45-second Python program returned a timeout result at about 31 seconds.
1. Explicit Session cleanup and adapter cancellation removed the worker and
   its child processes.

These are host-specific PoC results, not evidence of Hyper-V/VM isolation or a
production multi-tenant security guarantee. Windows ARM64 and all non-Windows
platforms remain unsupported in this PR.

### Windows 11 Home smoke test (2026-10-24)

Separate local PoC validation on Windows 11 Home, build `26300`, AMD64; MXC
SDK `@microsoft/mxc-sdk@1.0.0`; Node `24.22.0`. The MXC probe selected
`base-container`, reported no warnings, and reported that DACL augmentation was
not required. Node was installed at `F:\Program Files\nodejs\node.exe` and
was supplied through the trusted process-startup `UAGENT_MXC_NODE` override; the
SDK was already installed in the per-user runtime.

A direct local MXC session smoke test successfully ran `create_file`,
`read_file`, and `python_exec`. With the local Web UI started using
`--sandbox mxc --host 127.0.0.1`, `/` served the frontend and the status API
reported Sandbox enabled. Web-originated checks confirmed:

1. `create_file` → `read_file` returned the expected `Web MXC test` content.
1. A `python_exec` attempt to read the host repository's `README.md` returned
   `BLOCKED`.
1. A 35-second `python_exec` sleep returned a timeout response.
1. A `python_exec` connection attempt to the host's listening
   `127.0.0.1:8000` returned `BLOCKED`.

These are host-specific local ProcessContainer smoke-test results, not evidence
of VM isolation, complete network-egress enforcement, comprehensive resource
limit verification, or a production multi-tenant security guarantee.
