# Remote Web / A2A MXC default policy

- Decision: Remote Web and tool-enabled A2A use MXC ProcessContainer by default.
- Scope: current implementation baseline; this is **not** a claim that ProcessContainer is VM isolation or that Enterprise E0 acceptance is complete.
- Date: 2026-10-24

## Defaults

- `UAGENT_IDENTITY_MODE` defaults to `browser`: each browser profile receives
  an opaque HttpOnly guest cookie and a separate principal/private Project. This
  is not human authentication; see the guest-session warning below.
- `uagw` identifies the ingress from trusted startup configuration. An exact
  `127.0.0.1` bind with `browser` (default guest-cookie identity) or explicit
  `local` identity remains `local_trusted` and keeps Sandbox off by default.
  Other Web binds are Remote and default to `--sandbox auto` (or
  `UAGENT_SANDBOX_MODE=auto`). An explicit CLI or environment setting overrides
  the Sandbox default, never the trust profile. The browser cookie separates
  local browser histories, but is not human authentication or a multi-user
  authorization boundary.
- The A2A server is always Remote. With tool sending enabled (the default), it
  initializes the already-installed MXC backend at server startup. It does not
  interactively install dependencies. `--no-use-tool` / `UAGENT_USE_TOOL=off`
  disables model tool calls and therefore does not require a backend.
- If MXC, its runtime prerequisites, or the required capabilities are missing,
  startup or tool dispatch fails closed. There is no fallback to a Host tool
  runner. Local/remote ambiguity never opts into trusted-local behavior.
- Remote `--sandbox off` is not an escape hatch to Host execution: tools remain
  disabled or denied.

## Browser-cookie guest identity is not login

The default `browser` mode mints a random signed bearer cookie and uses its hash
as the browser's guest principal. It keeps separate sidebar histories/private
Memory per browser profile and survives refresh/restart until its signed expiry
or deletion. It does not identify a person; anyone who copies the cookie can
impersonate that guest until expiry. Losing the cookie means there is no
account-based recovery, and clearing it does not revoke copied tokens. Remote
public deployments that need identified users or confidential shared data must
configure OIDC or a properly secured `trusted_proxy`; do not treat guest cookies
as human authentication. Anonymous browser guests are restricted to their own
synthetic private Project and cannot receive administrator roles. The cookie
uses `HttpOnly`, `SameSite=Lax`, Secure on HTTPS, and a one-year default lifetime.
Its signing key is persisted under UAG's protected state directory; deployments
sharing browser sessions across processes must configure the same
`UAGENT_BROWSER_SESSION_SECRET` (at least 32 bytes).

## Deliberate baseline and deferred high assurance

The Windows MXC backend uses `base-container` / ProcessContainer. Linux x86_64
uses MXC Bubblewrap behind a host-enforced cgroup-v2 systemd scope. These provide
bounded process/container execution boundaries, not a Hyper-V, Windows Sandbox,
or Linux VM. This is the selected default baseline for Remote Web and A2A; the
user decision is to defer VM setup until a deployment explicitly requires it.
Windows 11 Home can use the ProcessContainer path when its runtime prerequisites
are installed; this does **not** mean Windows Sandbox VM is available on Home.
Linux must satisfy the Bubblewrap, cgroup-v2, and systemd-user prerequisites in
[MXC Sandbox platform notes](SANDBOX_MXC.md); the backend fails closed if
the host probe cannot verify isolation and resource limits.

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
separate, deferred gate. See [MXC Sandbox platform notes](SANDBOX_MXC.md)
for the recorded Windows Home ProcessContainer smoke test and its limits.
