# Windows MXC Sandbox PoC (PR 2)

This is a local, opt-in proof of concept. It is **not** the production remote
isolation boundary and does not claim Windows Sandbox/Hyper-V VM isolation,
E0 completion, or cross-platform support.

## Usage

- Sandbox is off by default. `uag` and `uagg` do not probe MXC, install Node/npm
  packages, or change the environment when Sandbox is off.
- `uag --sandbox auto` / `uagg --sandbox auto` use an already-installed supported
  backend. They fail closed if Node, the SDK, the host capability probe, or the
  resource-control prerequisites are missing.
- `uag --sandbox mxc` / `uagg --sandbox mxc` opt into Windows MXC ProcessContainer.
  On first use, the CLI asks before installing the pinned SDK in the current
  user's profile (about 105 MB). The GUI uses a Yes/No prompt. Installation uses
  the Node runtime already available to the user and does not request elevation.
  If Node.js 24.21+ x64 or 26.8+ x64 is not available, startup stops with an instruction; UAG
  does not install Node at machine scope.
- `UAGENT_SANDBOX_MODE=off|auto|mxc` is the environment equivalent. The command
  line option takes precedence.

The verified PoC target is Windows 11 x64 with MXC Node SDK `1.0.0`, Node
`24.22.0`, and the MXC `base-container` ProcessContainer tier. The adapter rejects
other operating systems/architectures, unsupported Windows builds, probe
warnings, DACL-augmentation requirements, and missing deny-path support. There
is no fallback to Host execution.

## Execution boundary

The LLM receives only four locally sandboxed tools: `create_file`, `file_exists`,
`read_file`, and `python_exec`. The first three use relative paths under a
per-session workspace in the user's local application data directory; they do
not read or publish the host project tree. Absolute paths, traversal, symlinks,
and oversized files/results are rejected. `python_exec` runs in its own
short-lived ProcessContainer using the same session workspace, so files created
by one tool remain visible to later tools. Its stdout/stderr are capped at 64 KiB
per stream and execution is forcibly stopped after 30 seconds. A ProcessContainer
is terminated after every Python execution to collect any child processes the
code may have started.

The worker receives a minimal environment, not the Host's `os.environ`. Its
filesystem policy grants write access only to the session workspace and read
access only to the Python runtime, adapter files, and Windows system runtime.
Network egress, ingress, and host loopback are denied. A Windows Job Object
around the adapter enforces a 1 GiB aggregate memory cap, a 64-process limit, a
four-hour aggregate user-CPU limit, and kill-on-close cleanup. A 256 MiB / 5,000
entry workspace watchdog stops the Python execution and tears down the session
when it detects an over-limit workspace. That workspace guard is an application
watchdog, not an NTFS hard quota; a short write burst can temporarily exceed the
threshold. At most four CLI/GUI scope workers may be active in one UAG process;
a fifth distinct scope is denied instead of creating more host resource usage.
Failure to create or assign the Job Object rejects the operation.

The lightweight ProcessContainer does not meet the Remote profile's VM
requirement. Remote Web and A2A tools remain denied; PR 2 does not attach this
backend to Web Rooms. Local Web Room ownership/recovery is a later integration
stage, and neither Web nor A2A should be enabled with this backend.

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
