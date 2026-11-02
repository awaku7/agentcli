# MXC Sandbox Platform Notes

The MXC backend is the default baseline for Remote Web and tool-enabled A2A;
trusted local CLI/GUI and local-only Web remain opt-in or off as documented
below. Windows x64 uses MXC ProcessContainer; Linux x86_64 uses MXC's Bubblewrap
backend plus a host-enforced systemd/cgroup-v2 scope. macOS 15+ Apple Silicon
ARM64 uses MXC Seatbelt with a monitored POSIX process group. All four entry
points (CLI, GUI, Web, A2A) share the same tool execution manager. None of
these backends is VM isolation, and none establishes Enterprise E0 completion
or a production multi-tenant security guarantee. macOS resource monitoring
uses periodic host sampling rather than hard Job Object/cgroup limits. See [Remote Web / A2A MXC default policy](REMOTE_MXC_DEFAULT.md)
for the current decision and explicit limits.

## Usage

- Trusted local CLI/GUI and Web with exact `127.0.0.1` bind plus `browser`
  (default guest cookie) or explicit `local` identity retain Sandbox-off behavior
  unless explicitly enabled; when off, they do not probe MXC or install
  dependencies. The browser cookie separates history but is not authentication.
  Other Web binds use the Remote policy even with browser guest identity.
- Remote Web defaults to `--sandbox auto`; tool-enabled A2A initializes MXC at
  startup. Both use only an already-installed supported backend and fail closed
  if Node, the SDK, the host capability probe, or resource controls are
  unavailable. Remote startup never prompts to install dependencies and never
  falls back to Host tool execution. Remote Web is determined from trusted
  startup bind/identity configuration, not request headers or the client's IP.
- `uag --sandbox auto`, `uagg --sandbox auto`, and explicit trusted local Web
  `--sandbox auto` also use an already-installed supported backend. The
  `--sandbox mxc` option on CLI/GUI or trusted local Web opts into the native
  MXC backend for the supported host (Windows ProcessContainer, Linux
  Bubblewrap or macOS Apple Silicon Seatbelt). On first interactive local use,
  UAG asks before
  installing the pinned SDK in the current user's profile (about 105 MB). Web
  startup refuses to install in non-interactive mode. Installation uses the Node
  runtime already available to the user and does not request elevation. If
  a supported Node.js 24.21+ or 26.8+ runtime is unavailable, startup
  stops; UAG does not install Node at machine scope.
- `--sandbox off` on Remote Web does not enable Host tools. `--no-use-tool` /
  `UAGENT_USE_TOOL=off` is the explicit tool-less mode for A2A and avoids MXC
  initialization.
- `UAGENT_SANDBOX_MODE=off|auto|mxc` is the environment equivalent (including
  the selected workdir's dotenv files). CLI arguments take precedence and mode
  resolution occurs after the workdir environment is loaded.
- `UAGENT_MXC_NODE` and `UAGENT_MXC_RUNTIME_DIR`, when used, are trusted
  process-startup overrides only; values from a project's `.env`/`.env.sec` are
  ignored. Relative override paths are rejected. On Windows, Node may also be
  discovered from the process-startup PATH (never the selected project's dotenv
  PATH); Node/npm use only the selected Node directory and Windows System32.
  Linux uses the selected Node directory plus fixed system binary directories.
- `uag realtime` is not supported with `--sandbox auto|mxc` or an equivalent
  environment setting. Realtime dependencies may be installed/executed on the
  Host; Sandbox-enabled realtime startup is refused before the realtime runner.

The Windows acceptance target is Windows 11 x64 with MXC Node SDK `1.0.1`,
Node `24.22.0`, and the MXC `base-container` ProcessContainer tier. The adapter
rejects unsupported Windows builds, probe warnings, DACL-augmentation
requirements, and missing deny-path support. Linux x86_64 uses the pinned SDK's
Bubblewrap backend; the host probe also verifies a live cgroup-v2 systemd scope
with the required limits before enabling it. Both platforms fail closed, with
no fallback to Host execution.

## macOS Apple Silicon (ARM64) prerequisites and controls

macOS 15+ on Apple Silicon is a supported MXC Seatbelt target in the same
execution manager used by CLI, GUI, Web and A2A. Intel Mac is **not supported
for Seatbelt**. A trusted Node.js ARM64 24.21+ (or 26.8+) runtime and npm
are required. macOS discovers Node only from trusted process-startup override
`UAGENT_MXC_NODE`, the user-local UAG toolchain, or system paths
`/opt/homebrew/bin` and `/usr/local/bin`, and installs the pinned MXC SDK
under `~/Library/Application Support/uagent/mxc_runtime`. Untrusted
project dotenv overrides cannot choose the Node executable or helper.

`uag --sandbox mxc`, `uagg --sandbox mxc`, local Web with explicit
Sandbox opt-in, Remote Web, and tool-enabled A2A use the **same Seatbelt
runtime** on Apple Silicon. Remote startup never silently installs the SDK
and never falls back to Host execution; the prerequisite must be provisioned
before starting Remote services. No entry-point allowlist is artificially
limited just because it runs on macOS.

The runtime performs a real Seatbelt probe before enabling tools. It proves
workspace read/write, explicit host-canary denial, and explicit permission
denial of a loopback connection to a live test listener. Each tool worker and
one-shot Python execution uses SDK `containment.type=seatbelt` and the same
filesystem, network, and tool allowlist contracts. The trusted host runs the
adapter in a fresh private POSIX process group with a sampling watchdog
(default 1 GiB group RSS, 64 processes, four aggregate CPU hours) and verifies
group cleanup before releasing the per-session workspace lease. Individual
tool execution and workspace limits remain enforced by the existing adapter.

**Important security difference:** macOS process-group sampling is not a hard
kernel-enforced cgroup/Job Object quota. A burst may temporarily exceed
memory/process limits before the watchdog samples it. Seatbelt subprocess
reaping and process-group cleanup require real-host acceptance tests. Treat
the backend as the documented lightweight process isolation tier, not VM-grade
or Enterprise E0 isolation. As with Windows/Linux, use independent security
acceptance before claiming suitability for an adversarial multi-tenant
production environment. If a host probe, watchdog, process cleanup, or other
required capability fails, startup/execution is denied rather than using
unconfined Host tools.

The `macOS MXC Seatbelt smoke` GitHub Actions workflow now runs both the
standalone SDK host smoke and integrated CLI/GUI/Web/A2A tool-scope tests on
macOS ARM64. Those tests verify the registered tool catalog, denied host
file/network access and child process lifetime. A CI pass is evidence for its
particular macOS runner, not a guarantee for every Mac.

## Linux x86_64 prerequisites and controls

The Linux implementation targets Ubuntu 24.04 and 26.04 x86_64. The real-host
integration job runs on both versions, but passing on a GitHub-hosted runner
only validates that runner's configuration; it does not certify every
installation. The host requires Node.js `24.21.0+` (or `26.8.0+`), npm, the
pinned MXC SDK, and working MXC Bubblewrap support. Install the host tools with
the system package manager:

```bash
sudo apt-get install apparmor bubblewrap iptables iproute2 slirp4netns util-linux
```

The host must permit unprivileged Bubblewrap/user namespaces. On Ubuntu
24.04+ with `kernel.apparmor_restrict_unprivileged_userns=1`, AppArmor must
load a profile granting `userns` permission to the Bubblewrap executable. Do
not disable this host-wide restriction. For the standard `/usr/bin/bwrap` path,
a host administrator can install a scoped profile like this:

```bash
sudo tee /etc/apparmor.d/bwrap >/dev/null <<'EOF'
abi <abi/4.0>,
include <tunables/global>
profile bwrap /usr/bin/bwrap flags=(unconfined) {
  userns,
}
EOF
sudo apparmor_parser -r /etc/apparmor.d/bwrap
```

The profile must match the installed Bubblewrap path; have the host's security
administrator review local AppArmor policy before enabling MXC. The host must
also provide a unified cgroup-v2 hierarchy with the `cpu`, `memory`, and `pids`
controllers. A running systemd user manager and its D-Bus socket
(`/run/user/<uid>/bus`) are required; `systemd-run --user` and
`systemctl --user` must be able to create, inspect, stop, and kill transient
user scopes. The user manager must be delegated the cgroup controllers required
to apply the scope limits. MXC startup performs a real Bubblewrap probe and
verifies those resource controls; missing packages, permissions, controllers,
user bus, or properties disable MXC with no host or weaker-isolation fallback.
Containers/WSL environments that do not expose these facilities are unsupported.

The user-local runtime defaults to `~/.local/share/uagent/mxc_runtime`; Node and
npm are resolved only from the trusted startup override or explicit system
locations, not from the selected project's dotenv/PATH. Linux applies a
1 GiB aggregate cgroup memory cap, disables swap for the scope, sets `TasksMax`
to 64 (Linux tasks include threads, so this is stricter than Windows' process
count), and limits the scope to one CPU. A host watchdog stops the scope at four
hours of aggregate CPU time. Scope shutdown kills all remaining cgroup tasks and
checks cgroup emptiness before releasing the workspace lease. If the systemd
user manager cannot verify cleanup, the workspace remains leased and cannot be
reused. Bubblewrap denies filesystem access outside the explicit runtime and
workspace read roots. Outbound network access is allowed inside a private
network namespace (including external HTTP(S) and Git endpoints), while inbound
connections and host loopback remain denied. Enabling outbound access requires
the Bubblewrap network dependencies (`slirp4netns`, `iptables`, `iproute2`);
missing runtime support fails closed rather than running on the host network.

The `mxc-linux-integration` CI matrix runs real-host acceptance on both Ubuntu
versions. Unit tests and a successful build alone do
not prove that a particular host's user namespaces, Bubblewrap, cgroup
controllers, and systemd delegation are correctly configured; use the same
fail-closed probe on each deployment host.

This PoC assumes that UAG itself, the Host Python interpreter and dependencies,
and the Python startup/import path are trusted. Running `python -m uagent`
with an untrusted project on Python's import path can execute project-supplied
modules on the Host before MXC isolation begins (including shadowed `win32api`
or `win32job` modules). Do not treat Sandbox mode as protection against
untrusted Host startup/import code; launch UAG from a trusted environment.
Hardening that entire startup boundary is outside this local tool-execution PoC.

## Execution boundary

The LLM receives a fixed catalog of locally sandboxed tools, including
`create_file`, `file_exists`, `read_file`, `python_exec`, and local
`git_ops`. Workspace file tools use relative paths under a per-scope workspace
in the user's local application data directory; they do not read or publish
the host project tree. Absolute paths, traversal, symlinks,
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
Outbound network access is allowed (including public and private networks).
Windows ProcessContainer requires private-network ingress capability to reach
LAN addresses, so private-network inbound connections can also be possible;
host loopback remains denied. This is not a network-isolated deployment profile.
A Windows Job Object
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

### General command execution in Sandbox

The `command_exec` tool executes an installed program using an `argv` array,
with an optional workspace-relative `cwd`. For example:
`{"argv":["git","--version"]}` or
`{"argv":["python","-m","pip","--version"]}`. There is no implicit shell,
command-specific allowlist, extra startup option, or Host-side execution
fallback. Explicit shell invocations (for example `["sh","-c","..."]`) are
possible when a shell is available inside MXC.

Each command uses the existing **one-shot MXC** process, just like
`python_exec`, rather than running an unbounded subprocess in the persistent
worker. The 25-second command timeout, 30-second one-shot watchdog, bounded
stdout/stderr, workspace quota, and verified process-tree cleanup all remain
enforced. The command runs under the session's workspace/environment, not the
Host environment. It can connect outward over the already-enabled network,
but the Host loopback and inaccessible Host files stay isolated.

Commands depend on executables already visible inside the OS-specific MXC
filesystem policy; installing or provisioning Node/npm, Git, compilers, and
Python packages across all supported hosts is a separate step. The default
`git_ops` tool remains restricted to offline operations, while `command_exec`
may invoke the Git CLI directly where available. Host Git credentials, SSH
agents, system package-manager access, and arbitrary Host environment variables
are **not** automatically passed into a session. For Git pushes to private
remotes, session-scoped credential provisioning still needs its own design.
This feature does not change those identity or privilege boundaries.

Web and A2A use the same static MXC tool allowlist. Web Room scopes are bound
to authenticated server-created Room/Principal context. Spawned per-turn workers
send fixed-schema Sandbox tool requests over a size-bounded private JSON pipe;
the parent revalidates the active Room scope and authorization for each request
before dispatching to its MXC session. A2A receives a server-created per-task
scope and closes it at task completion. The MXC manager caps active sessions.
Sandbox mode also blocks Host plugin imports, Host hooks, tool-genre changes,
general Web commands, and non-allowlisted tools.

Remote Web and tool-enabled A2A now use the same supported MXC backend as
local opt-in sessions (Windows ProcessContainer, Linux Bubblewrap, or macOS
ARM64 Seatbelt). This is a process/container boundary, **not** VM isolation and not a claim of completed
Enterprise E0 acceptance. The high-assurance VM tier remains deferred; setting
`UAGENT_REMOTE_SANDBOX_MIN_ISOLATION=vm` requires a future VM-capable backend and
fails closed with the current ProcessContainer. The recorded Windows 11 Home
smoke test below exercised the local Web route, not a real Remote Web/A2A
production flow.

## Network and Git acceptance status (2026-11-02)

Outbound networking in MXC 1.0.1 is enabled; this does **not** mean that
authenticated remote Git operations are supported.

| Host | Verified in GitHub Actions | Still to validate |
| --- | --- | --- |
| Ubuntu 24.04 / 26.04 x86_64 | Real MXC Bubblewrap DNS + external TCP/443 egress, host loopback denial, host-file denial, child cleanup (PR #320) | Deployment-specific network, credentials and cleanup policy |
| macOS 15+ ARM64 | Real MXC Seatbelt host-file and loopback denial, child cleanup across entry-point scopes (PR #320) | External DNS/TCP egress inside the sandbox; authenticated Git |
| Windows x64 ProcessContainer | Earlier SDK 1.0.0 local smoke tested host-file and loopback denial | **MXC 1.0.1** DNS/TCP egress, host-loopback denial, cleanup and credential isolation on a supported real host |

The existing `git_ops` tool supports **local/offline** workspace Git
operations only. It explicitly rejects `clone`, `fetch`, `pull`, `push`,
remote URLs, and access to host Git metadata. `python_exec` can make outbound
network requests but does not inherit host Git credentials. Never claim that
network-enabled Python is equivalent to an authenticated Git transport.

### Next Git credential boundary (not implemented)

Keep local Git usable without adding mandatory user configuration. For
authenticated remote operations, require a narrow, host-side credential broker
that validates the authenticated execution scope (principal, session/room/task,
project), the selected remote and the approved operation. The broker must not
provide a general host shell or arbitrary Git commands. A missing authorization
fails closed; a Web room identifier or browser guest cookie alone is not a
credential identity.

Do not mount the host `.ssh`, Git credential store or global Git configuration
inside MXC, forward an unrestricted SSH agent, place tokens in clone URLs,
or copy long-lived credentials into the session workspace or logs. Prefer
short-lived, operation-scoped access without exposing secret values to the LLM
or sandbox. If a future backend must inject plaintext credentials, its lease
must be marked tainted immediately and destroyed after that single operation,
including on failure, cancellation and timeout.

Before enabling authenticated remote Git, add regression tests for cross-scope
credential denial, allowlisted remote and operation checks, unavailable-identity
failure, credential redaction, subprocess and hook escape attempts, and cleanup
on every exit path. Verify DNS/TCP egress and host-loopback denial on each
supported real-host backend independently. Those acceptance tests do not
establish VM-grade or multi-tenant isolation.

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
production multi-tenant security guarantee. Windows ARM64 and macOS remain
unsupported; Linux x86_64 requires the Linux host prerequisites and a successful
MXC probe described above.

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
