# Windows MXC Sandbox PoC (PR 2)

This is a local, opt-in proof of concept. It is **not** the production remote
isolation boundary and does not claim Windows Sandbox/Hyper-V VM isolation,
E0 completion, or cross-platform support.

## Usage

- Sandbox is off by default. `uag`, `uagg`, and `uagw` do not probe MXC, install
  Node/npm packages, or change the environment when Sandbox is off.
- `uag --sandbox auto`, `uagg --sandbox auto`, and trusted local-only
  `uagw --sandbox auto` use an already-installed supported backend. They fail
  closed if Node, the SDK, the host capability probe, or resource controls are
  unavailable. Local Web opt-in is accepted only for the exact `127.0.0.1` bind
  with local identity mode; a remote Web deployment does not use this backend.
- The `--sandbox mxc` option on CLI/GUI or trusted local-only Web opts into
  Windows MXC ProcessContainer. On first interactive use, UAG asks before
  installing the pinned SDK in the current user's profile (about 105 MB). Web
  startup refuses to install in non-interactive mode. Installation uses the Node
  runtime already available to the user and does not request elevation. If
  Node.js 24.21+ x64 or 26.8+ x64 is unavailable, startup stops; UAG does not
  install Node at machine scope.
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
marker is emitted from an `atexit` handler registered before user code, so
user-registered shutdown handlers complete before cleanup; the workspace quota
watchdog remains active until the ProcessContainer has been stopped. MXC's
ProcessContainer assigns the suspended root process to a Job Object before it is
resumed; its native `wait()`/`kill()` path terminates and reaps that process tree.
The adapter uses those SDK lifecycle operations rather than host PID-based
termination. If MXC cannot confirm process cleanup, quota scanning fails, or the
completion marker is missing, execution is rejected; unverified cleanup tears
down the session. Both probe and execution requests explicitly forbid MXC's
host-DACL-mutation fallback.

The worker receives a minimal environment, not the Host's `os.environ`. Its
filesystem policy grants write access only to the session workspace and read
access only to the Python runtime, adapter files, and Windows system runtime.
Network egress, ingress, and host loopback are denied. A Windows Job Object
around the adapter enforces a 1 GiB aggregate memory cap, a 64-process limit, a
four-hour aggregate user-CPU limit, and kill-on-close cleanup. A 256 MiB / 5,000
entry workspace watchdog stops the Python execution and tears down the session
when it detects an over-limit workspace. That workspace guard is an application
watchdog, not an NTFS hard quota; a short write burst can temporarily exceed the
threshold. Quota scans skip child entries concurrently removed from the workspace,
including during NTFS alternate-stream inspection; partial stream counts for a
vanished entry are discarded. A missing root or any other scan error still fails
closed. At most four distinct scopes may be active in one UAG process; a
fifth is denied instead of creating more host resource usage. Failure to create
or assign the Job Object rejects the operation.

Trusted local-only Web may opt in on Windows using a server-created `web-room`
scope, with the same static tool allowlist. Until PR 3 adds Room-owned worker
and lease recovery, sandboxed local Web is constrained to one in-process worker
and serial Room execution. This is a local PoC restriction, not production
multi-user isolation; Sandbox mode also blocks host plugin imports, host hooks,
general Web commands, and non-allowlisted CLI/GUI commands.

The lightweight ProcessContainer does not meet the Remote profile's VM
requirement. Remote Web and A2A tools remain denied, regardless of `--sandbox`.
The local Web opt-in does not enable this backend for remote Web or A2A.

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
