# Remote Web / A2A MXC default policy

- Decision: Remote Web and tool-enabled A2A use MXC ProcessContainer by default.
- Scope: current implementation baseline; this is **not** a claim that ProcessContainer is VM isolation or that Enterprise E0 acceptance is complete.
- Date: 2026-10-24

## Defaults

- `uagw` identifies the ingress from trusted startup configuration. The exact
  `127.0.0.1` bind plus `UAGENT_IDENTITY_MODE=local` remains `local_trusted` and
  keeps its existing Sandbox-off default. Other Web deployments are Remote and
  default to `--sandbox auto` (or `UAGENT_SANDBOX_MODE=auto`). An explicit CLI
  or environment setting overrides that default.
- The A2A server is always Remote. With tool sending enabled (the default), it
  initializes the already-installed MXC backend at server startup. It does not
  interactively install dependencies. `--no-use-tool` / `UAGENT_USE_TOOL=off`
  disables model tool calls and therefore does not require a backend.
- If MXC, its runtime prerequisites, or the required capabilities are missing,
  startup or tool dispatch fails closed. There is no fallback to a Host tool
  runner. Local/remote ambiguity never opts into trusted-local behavior.
- Remote `--sandbox off` is not an escape hatch to Host execution: tools remain
  disabled or denied.

## Deliberate baseline and deferred high assurance

The currently integrated Windows MXC backend is `base-container` /
ProcessContainer. It provides a bounded process/container execution boundary,
not a Hyper-V/Windows Sandbox VM. This is the selected default baseline for
Remote Web and A2A; the user decision is to defer VM setup until a deployment
explicitly requires it. Windows 11 Home can use this ProcessContainer path when
its runtime prerequisites are installed; this does **not** mean Windows Sandbox
VM is available on Home.

Set `UAGENT_REMOTE_SANDBOX_MIN_ISOLATION=vm` to demand VM-level isolation. The
current ProcessContainer backend does not meet that setting and Remote tool
execution will fail closed until a VM backend and its host-specific acceptance
checks are implemented. The default is `container`. Other values are treated
as a request for the stricter VM tier and fail closed with the current backend.

ProcessContainer use does not, by itself, establish Enterprise E0, VM-grade
isolation, or a production multi-tenant security guarantee. Keep the high-
assurance acceptance gate in
[PR4 Windows Sandbox acceptance](plans/PR4_WINDOWS_SANDBOX_ACCEPTANCE.md)
separate from this baseline decision. In particular, no claim is made here that
all OS, identity-provider, network, credential, and resource-limit combinations
have passed real-host acceptance.

## What Remote tool calls can do

Remote turns expose only the static MXC tool catalog: `create_file`,
`file_exists`, `read_file`, and `python_exec`. The first three operate in a
per-scope MXC workspace; Python runs in the isolated session with bounded output
and execution time. A2A receives a server-created per-task scope and closes it
when the task ends. Web scopes are bound to the authenticated server-side Room
and are reauthorized at the parent-side RPC boundary. A fixed `get_current_time`
operation is handled by the narrow broker and does not invoke a generic Host
runner. Other tools, plugins, hooks, general Web commands, Computer Use, and
unapproved host operations are not implicitly enabled by turning Sandbox on.

The normal Web frontend continues to be served at `/`; `--no-frontend` removes
that UI route intentionally. `/docs` is the API documentation and `/api/*` are
service endpoints, not the main chat interface.

## Validation status

Unit tests cover the routing, scope binding, fail-closed paths, Web worker RPC,
and A2A lifecycle. Real MXC integration must be run on each supported host
before claiming that host's ProcessContainer behavior; VM acceptance is a
separate, deferred gate. See [Windows MXC Sandbox notes](SANDBOX_MXC_WINDOWS.md)
for the recorded Windows Home ProcessContainer smoke test and its limits.
