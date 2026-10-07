# UAG Enterprise Platform Design

Status: Design only  
Target: post-v0.7.26 enterprise hardening and control-plane roadmap  
Scope: enterprise deployment, governance, identity lifecycle, audit, data governance, cost control, workload identity, and software supply-chain controls

## 1. Purpose

UAG already has substantial enterprise-oriented foundations:

- OIDC / Entra identity integration and server-side authorization boundaries;
- Project / Room / principal-scoped Memory and authenticated Web execution;
- Unified Policy for tools, providers, credentials, MCP servers, network destinations, skills, plugins, and roles;
- explicit dangerous-operation confirmation and side-effect policy;
- OpenTelemetry tracing, metrics, trusted propagation, privacy controls, and authorization-aware trace lookup;
- A2A / MCP / Sub-Agent execution boundaries;
- credential isolation and secret masking.

The next enterprise phase should therefore avoid adding isolated features without a common governance model. The goal is to turn the existing runtime into an enterprise-manageable Agent platform with a clear control plane, durable identity lifecycle, auditable decisions, controlled data egress, and predictable operational limits.

This document is a design and sequencing contract only. It does not imply that the listed features are implemented.

## 2. Design principles

The enterprise layer must preserve the following invariants.

1. Authentication, authorization, telemetry, and billing remain separate concerns.
2. A telemetry record, trace ID, session ID, room ID, project ID, or pseudonym never grants access.
3. Deny always wins over allow when policy sources conflict.
4. Missing or stale enterprise control-plane state fails closed for privileged or externally visible actions.
5. Existing local/single-user use remains possible without requiring enterprise infrastructure.
6. No enterprise feature may silently fall back from an explicitly selected identity or trust mode to local trust.
7. Secrets, raw tokens, private prompts, and credential material are excluded from audit and telemetry by default.
8. Multi-instance support must preserve revocation and authorization semantics rather than merely sharing state.
9. Enterprise controls apply consistently across CLI, GUI, Web, A2A, MCP, Sub-Agent, scheduled, and automated execution where the boundary is relevant.
10. New enterprise features should reuse existing UAG policy, identity, observability, and credential abstractions rather than creating parallel systems.

## 3. Target architecture

The target model separates the data plane from the enterprise control plane.

```text
                    Enterprise Control Plane
        +---------------------------------------------+
        | Identity lifecycle / SCIM                  |
        | Policy revisions / rollout / kill switch   |
        | Audit export / retention                   |
        | Data governance / DLP                      |
        | Quota / budget / cost policy               |
        | Agent & integration registry               |
        +---------------------+-----------------------+
                              |
                              v
+-----------------------------+------------------------------+
|                        UAG Data Plane                       |
|                                                            |
| Identity -> Authorization -> Policy -> Execution Broker    |
|      |             |           |             |             |
|      +-------------+-----------+-------------+             |
|                                      |                     |
|                              Sandboxed Tool Runtime         |
|                                      |                     |
|                         Controlled filesystem/egress        |
|                    Audit decision stream                    |
|                    OTel diagnostics                         |
+------------------------------------------------------------+
```

The control plane may initially be local-file / SQLite backed, but public interfaces must not assume one process or one host.

## 3.1. Enterprise Phase E0: external Web execution isolation

External Web access changes the tool-execution threat model. A successfully authenticated remote user, a compromised browser session, malicious prompt content, a vulnerable tool, or a compromised model/tool chain must not gain a direct host-OS execution path.

For an external or authenticated multi-user Web deployment, **no ordinary tool call may execute directly on the UAG host**.

Every Web-originated tool action must be classified into exactly one of these paths:

1. **sandbox execution**: normal data-plane tools run inside an isolated execution environment;
2. **brokered control-plane action**: credential, policy, identity, audit, or other privileged administration is handled by a narrow host-side service with explicit authorization;
3. **deny**: operations that cannot be safely sandboxed or brokered are unavailable.

There is no fourth "direct host execution because the user confirmed" path for external Web.

### 3.1.1 Execution Broker

Introduce an `ExecutionBroker` boundary between Agent/tool dispatch and the host.

The broker is responsible for:

- selecting the sandbox backend;
- binding execution to the current principal / Project / Room or session context;
- enforcing the effective Unified Policy before launch;
- creating a clean sandbox lease;
- projecting only approved workspace inputs;
- injecting only explicitly approved, short-lived credentials;
- applying CPU, memory, process, disk, wall-clock, and network limits;
- collecting bounded stdout/stderr/results/artifacts;
- terminating and cleaning the sandbox;
- emitting audit and OpenTelemetry linkage without exporting secret payloads.

The Web execution path must not expose a container daemon socket, hypervisor control socket, host shell, host home directory, host credential store, or unrestricted host filesystem to the sandbox.

### 3.1.2 Deployment profiles

The security profile must be explicit. Automatic network-interface detection may warn but must not be the authority that decides whether sandboxing is required.

Conceptual profiles:

```text
local-trusted
    CLI / GUI or explicitly local-only Web
    -> host execution may remain available under Unified Policy

web-sandboxed
    externally reachable or authenticated multi-user Web
    -> sandbox or brokered-control-plane only

web-high-assurance
    hostile multi-tenant / regulated deployment
    -> hypervisor-backed isolation required
```

If a deployment selects an external Web profile and the required sandbox backend is unavailable or unhealthy, executable tools fail closed. UAG must not silently fall back to host execution.

### 3.1.3 What "all tools" means

All **data-plane tool execution** initiated through external Web is sandboxed. This includes, where applicable:

- shell / cmd / PowerShell / bash;
- Python and other interpreters;
- Git, compilers, package managers, and build/test tools;
- filesystem mutation;
- archive/media/document conversion and parsing;
- downloaded code, Skills, plugins, or helper binaries;
- browser automation;
- Computer Use;
- MCP/A2A helper processes and other local executable integrations.

Network-only operations may be implemented inside the sandbox or through a separately isolated egress service, but they must still pass the same destination and data-governance policy.

Control-plane capabilities such as policy administration, credential management, session revocation, directory/SCIM administration, or audit configuration are **not** moved into the untrusted sandbox. They remain narrow brokered services and are never reachable through a generic shell/file escape.

Hardware-facing tools such as Bluetooth, USB, camera, serial, local IoT, or GPU/device access are denied by default for external Web. Future device access requires an explicit device broker and per-device policy; generic device passthrough is not a baseline feature.

### 3.1.4 Sandbox lifetime and tenant binding

A sandbox must never carry mutable state from one principal or Project into another.

Recommended identity key for every reusable lease and workspace projection:

```text
deployment
  + principal_id
  + project_id
  + room_id
  + session_id (when the execution lifetime is session-specific)
```

`room_id` is mandatory and is never interchangeable with `session_id`. The same principal/project can participate in both private and shared rooms, so mutable sandbox state must not cross that room boundary. A session identifier may further narrow the execution scope, but it never replaces the room binding.

The default external-Web model should use a clean sandbox created from an immutable image or snapshot. Warm pools are allowed only when a sandbox is reset to a verified clean state before reassignment.

Mutable project files should live in a broker-managed workspace or volume. The sandbox receives only the specific workspace projection required for the task. Host root, arbitrary host paths, the UAG source/configuration tree, and user home directories are not mounted.

Prefer explicit copy-in/copy-out or broker-controlled workspace mounts. Host mounts are read-only by default; writable mappings require a reviewed Project boundary.

### 3.1.5 Network and metadata isolation

Sandbox networking is default-deny for destinations not required by the effective tool/policy.

The network boundary should support:

- destination allow/deny policy;
- DNS policy;
- outbound connection limits;
- blocking host-local control ports;
- blocking cloud instance metadata endpoints unless explicitly required;
- blocking private/link-local network ranges by default for Internet-facing deployments;
- DLP/egress inspection integration from E6;
- separate policy for provider, MCP, A2A, package registry, and arbitrary Web destinations.

A sandbox may not bypass the network policy by using a host network namespace.

### 3.1.6 Credential injection

The sandbox must not mount the UAG credential store or inherit the host process environment wholesale.

When a tool requires a secret:

1. Unified Policy authorizes the tool, destination, and credential reference;
2. the broker resolves the credential outside the sandbox;
3. prefer keeping the secret outside the sandbox entirely and perform the credential-bearing exchange through a narrowly scoped broker when the protocol/tool can support that model;
4. if plaintext secret injection into the sandbox is unavoidable, inject only the minimum required secret for the minimum required operation;
5. the broker revokes/removes the injection immediately when that credential-using operation completes, whether it succeeds, fails, or is cancelled;
6. a sandbox lease that received plaintext credential material is **tainted and non-reusable**: terminate the complete process tree and discard/reset all writable sandbox state before any later tool call;
7. warm-pool reuse is allowed only after returning to a verified clean image/snapshot that cannot retain files, processes, environment state, clipboard state, browser state, or other artifacts from the credential-bearing operation;
8. lease teardown performs an additional cleanup sweep but is never the primary secret-lifetime boundary;
9. stdout/stderr/tool results remain subject to secret masking;
10. raw secret material is excluded from audit and telemetry.

Long-lived static credentials should not be exposed to an untrusted sandbox where a brokered exchange, short-lived scoped credential, or workload identity from E8 can satisfy the operation.

### 3.1.7 Resource and denial-of-service controls

Each sandbox lease needs bounded resources:

- CPU shares/cores;
- memory;
- process count;
- disk and temporary-file usage;
- wall-clock timeout;
- stdout/stderr/result size;
- network bandwidth/connections where supported.

Limit violations terminate the sandboxed operation and must not destabilize the host Agent process.

### 3.1.8 Virtualization technology evaluation

A Python virtual environment is dependency isolation, not a security boundary. It is not acceptable for external-Web tool isolation.

Likewise, process users, job objects, namespaces, seccomp, AppArmor/SELinux, Landlock, or rootless containers are valuable defense-in-depth controls but do not by themselves define the high-assurance hostile multi-tenant boundary.

| Technology | Isolation | UAG fit | Design decision |
|---|---|---|---|
| Python `venv` | dependency only | development | never a security boundary |
| OS process/user + resource controls | process-level | supplemental | defense in depth only |
| rootless OCI/Docker container | shared host kernel | useful orchestration and local/single-tenant sandbox | not sufficient alone for hostile external multi-user |
| gVisor / `runsc` | userspace application kernel between workload and host Linux kernel | strong Linux default with OCI/Docker/containerd integration | preferred Linux baseline for general external-Web tools |
| Kata Containers | lightweight VM per sandbox/container boundary | strong Kubernetes/containerd enterprise option | preferred where VM isolation and container orchestration are both required |
| Firecracker microVM | KVM microVM, minimal device model | high-assurance Linux/serverless-style execution | optional high-assurance backend; higher orchestration cost |
| Windows process-isolated container | shared Windows kernel | compatibility | not an adequate hostile multi-tenant boundary |
| Windows Hyper-V isolated container | optimized VM with separate kernel | strong Windows Server backend | preferred Windows external-Web baseline |
| Windows Sandbox | hardware-isolated disposable desktop, but client-oriented and single-instance | local development/testing | not the production multi-user execution backend |
| full VM / VM pool | hardware VM boundary | broadest compatibility, GUI/Computer Use | fallback/high-assurance backend where containers are insufficient |

The sandbox abstraction must prevent application code from depending directly on Docker, gVisor, Kata, Firecracker, or Hyper-V APIs. Backends implement a common UAG execution contract.

### 3.1.9 Recommended platform profiles

#### Linux server

Recommended default:

```text
ExecutionBroker
  -> OCI/container orchestration
     -> gVisor runsc
        -> per-lease workspace + controlled network
```

Rootless container orchestration is desirable where compatible, because it reduces daemon/runtime privilege, but rootless mode is an additional mitigation rather than the only isolation boundary.

For regulated/high-assurance or strongly hostile multi-tenant workloads:

```text
ExecutionBroker
  -> Kata Containers
     or
  -> Firecracker microVM
```

gVisor is optimized to isolate untrusted Linux workloads while retaining container-style resource efficiency. Kata adds a lightweight VM layer and integrates with containerd/Kubernetes. Firecracker uses KVM microVMs and a deliberately small device model, making it attractive for high-density serverless-style isolation.

#### Windows server

Recommended default for external Web:

```text
ExecutionBroker
  -> Windows container
     -> Hyper-V isolation
```

Microsoft documents Hyper-V-isolated containers as using a separate optimized VM/kernel and recommends hypervisor isolation rather than process-isolated containers for hostile multi-tenant workloads.

Windows Sandbox is useful for developer/testing scenarios but is not the enterprise server backend: it is client-oriented, networking is enabled by default unless configured otherwise, and current Windows documentation states that multiple Windows Sandbox instances cannot run simultaneously.

For tools that require a real Windows desktop, GUI applications, or full Computer Use, use a dedicated Hyper-V VM/VM-pool backend rather than exposing the host desktop.

### 3.1.10 Browser and Computer Use isolation

External-Web Computer Use must never attach to the UAG host's visible desktop.

The execution backend must provide a dedicated browser/desktop surface inside the sandbox or VM:

```text
remote Web user
    -> UAG Web
       -> ExecutionBroker
          -> isolated browser/desktop
             -> screenshots/events
          <- bounded visual/tool result
```

The sandbox owns browser profile, downloads, clipboard, temporary files, and desktop session. Host clipboard, microphone, camera, printers, arbitrary mapped folders, and host browser profile remain unavailable unless a separately reviewed capability explicitly enables them.

Headless browser automation may use the normal Linux sandbox backend. Native desktop Computer Use should prefer a microVM/VM backend when the chosen container runtime cannot provide the required GUI isolation.

### 3.1.11 Failure and fallback rules

- Sandbox launch failure: fail the tool call; never run on host.
- Unsupported syscall/application under gVisor: deny or route to an explicitly configured stronger compatible backend; never host fallback.
- Missing virtualization support in an external profile: executable tools remain unavailable.
- Sandbox network policy failure: fail closed.
- Artifact export failure: leave data inside the sandbox until cleanup policy removes it; do not copy arbitrary paths to host.
- Broker crash/restart: orphaned leases are reclaimed/terminated according to bounded cleanup rules.
- Audit/telemetry failure must not weaken the sandbox boundary.

### 3.1.12 Virtualization references used by this design

The technology selection should be revalidated at implementation time. Current primary references:

- gVisor security architecture and OCI runtime: https://gvisor.dev/docs/architecture_guide/intro/
- Kata Containers VM-based container runtime: https://katacontainers.io/
- Firecracker microVM architecture: https://firecracker-microvm.github.io/
- Docker rootless mode: https://docs.docker.com/engine/security/rootless/
- Windows container isolation modes: https://learn.microsoft.com/en-us/virtualization/windowscontainers/manage-containers/hyperv-container
- Microsoft Windows container security guidance: https://learn.microsoft.com/en-us/virtualization/windowscontainers/manage-containers/container-security
- Windows Sandbox overview: https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-overview

## 4. Enterprise Phase E1: durable identity and HA session model

### 4.1 Problem

OIDC browser sessions are currently process-local. A process restart signs users out, and multi-instance Web deployment requires a durable session model.

### 4.2 Design

Introduce an `EnterpriseSessionStore` contract that preserves:

- opaque browser session IDs;
- expiration;
- revocation;
- authentication configuration fingerprint invalidation;
- principal binding;
- optional project selection binding;
- safe concurrent refresh;
- multi-instance visibility.

Initial backends may include:

- SQLite for single-host durable deployments;
- Redis or another shared store for multi-instance deployments.

The session store must never persist raw authorization codes, PKCE verifiers, access tokens, refresh tokens, or ID tokens unless a later explicit design introduces a protected token vault.

### 4.3 Required behavior

- Restart must not weaken authorization.
- Revocation on one node must become effective on all nodes.
- Session expiration must be authoritative and server-side.
- Configuration changes that invalidate the current authentication setup must invalidate affected sessions.
- WebSocket turns must continue to re-resolve the current authoritative session before execution.
- Storage failure for authenticated enterprise Web execution fails closed.

## 5. Enterprise Phase E2: directory freshness and immediate revocation

### 5.1 Problem

Entra group resolution is performed at login. Long-lived sessions therefore need an explicit freshness and revocation model.

### 5.2 Design

Add a directory membership freshness contract with:

- configurable maximum membership age;
- per-turn or periodic refresh policy;
- explicit refresh failure behavior;
- immediate administrative revocation;
- group/role downgrade propagation;
- directory-independent adapter interface.

Entra is the first concrete directory implementation. The abstraction must also permit future Active Directory, LDAP-backed, Okta, Google Workspace, or deployment-specific directory adapters.

### 5.3 Invariants

- Stale membership must never silently retain higher privilege beyond the configured freshness window.
- A failed refresh does not invent membership.
- Manual membership and directory-derived membership remain distinguishable.
- Directory claims are authorization input, not Memory ownership identity.

## 6. Enterprise Phase E3: SCIM 2.0 lifecycle provisioning

SCIM should manage enterprise lifecycle, not replace authentication.

### 6.1 Scope

Support a bounded subset of SCIM 2.0 sufficient for enterprise provisioning:

- Users;
- Groups;
- activation / deactivation;
- group membership;
- stable external IDs;
- PATCH for lifecycle changes;
- pagination and bounded filtering required by supported IdPs.

### 6.2 Mapping

SCIM entities map into an enterprise directory projection, which then feeds existing UAG principal / Project / Room authorization policy.

SCIM deactivation must be able to trigger:

- session revocation;
- removal of directory-derived role grants;
- denial of future authenticated execution.

SCIM must not directly mutate Personal Memory ownership or rewrite historical audit records.

## 7. Enterprise Phase E4: central policy control plane

The existing Unified Policy remains the enforcement engine. The enterprise control plane adds lifecycle and distribution around it.

### 7.1 Policy model

Policies gain:

- immutable revision ID;
- author / issuer metadata;
- creation and activation timestamps;
- optional signature;
- parent revision;
- rollout state;
- reason / change note;
- validation status.

### 7.2 Hierarchy

The desired evaluation hierarchy is:

```text
organization
  -> deployment
     -> project
        -> role
           -> principal/service
```

A lower layer may restrict an inherited permission but must not relax an explicit higher-level deny.

### 7.3 Rollout

Support:

- validate-only;
- audit-only / dry-run;
- canary scope;
- active;
- rollback to known revision;
- emergency kill switch.

Policy activation and rollback are auditable security events.

## 8. Enterprise Phase E5: dedicated audit trail and SIEM export

OpenTelemetry remains diagnostics. Enterprise audit is a separate security record.

### 8.1 Audit events

At minimum record:

- authentication success/failure;
- session creation/revocation;
- identity and directory role changes;
- policy decision and policy revision;
- tool / MCP / A2A / provider authorization decisions;
- confirmation requested / approved / rejected;
- administrator configuration changes;
- credential reference changes without secret values;
- SCIM lifecycle actions;
- DLP allow/redact/deny decisions;
- quota / budget enforcement.

### 8.2 Audit properties

Audit records should have:

- stable event schema;
- timestamp;
- event ID;
- principal/service identity when authorized to record;
- project / deployment scope where appropriate;
- policy revision;
- result;
- reason code;
- correlation ID and optional trace ID linkage.

The audit channel must avoid prompt bodies, tool payload bodies, raw claims, raw credentials, cookies, bearer tokens, and secret values by default.

### 8.3 Export

Planned sinks:

- JSONL;
- Syslog;
- CEF or equivalent SIEM-friendly projection;
- signed webhook / HTTPS batch exporter.

Tamper-evident chaining or signed batches should be considered for regulated deployments.

## 9. Enterprise Phase E6: DLP and data-governance egress gate

### 9.1 Goal

Create one common outbound governance boundary before data leaves the trusted UAG execution context.

### 9.2 Enforcement points

The gate should cover:

- model/provider requests;
- MCP calls;
- A2A calls;
- Web/fetch/search network tools where payloads are sent;
- external plugins;
- export / sharing operations.

### 9.3 Classification

Introduce a small initial classification model:

```text
public
internal
confidential
restricted
```

Policies may use classification plus project, principal role, provider, destination, tool, and content category.

Possible actions:

- allow;
- redact;
- confirm;
- deny.

Detection can later support PII, credential-like data, custom regex/rule packs, or external enterprise DLP integrations. The first implementation should keep the detector pluggable.

## 10. Enterprise Phase E7: usage, quota, and FinOps controls

Add a provider-neutral usage accounting model.

### 10.1 Accounting dimensions

Prefer low-cardinality enterprise dimensions:

- deployment;
- project;
- principal or service account where appropriate;
- provider;
- model family;
- operation type.

Do not use raw prompt content or arbitrary user-controlled strings as dimensions.

### 10.2 Counters

Possible counters:

- input/output tokens;
- reported cost when a provider supplies it;
- estimated cost when explicitly marked as estimated;
- tool calls;
- MCP/A2A calls;
- Web/search calls;
- Computer Use duration;
- media generation duration/count.

### 10.3 Enforcement

Support:

- soft warning thresholds;
- hard quotas;
- project budgets;
- model/provider allow/deny by cost tier;
- per-principal or per-service rate policy.

Quota enforcement belongs in policy/runtime boundaries, not in telemetry callbacks.

## 11. Enterprise Phase E8: workload identity for Agent-to-Agent boundaries

Human identity and workload identity must remain separate.

### 11.1 Initial support

Strengthen service-to-service identity using:

- mTLS;
- OAuth 2.0 client credentials;
- short-lived service credentials;
- explicit audience/resource binding.

### 11.2 Optional future support

Allow SPIFFE/SPIRE-style workload identities where deployments need a common identity layer across Kubernetes, VM, cloud, and on-prem environments.

The workload identity becomes an input to existing A2A/MCP trust and policy decisions. It never substitutes for end-user authorization when a user-scoped action is being performed.

## 12. Enterprise Phase E9: software supply chain and Agent Registry

### 12.1 Repository/release hardening

Add:

- `SECURITY.md`;
- SBOM generation;
- dependency vulnerability scanning;
- secret scanning;
- release artifact checksums/signatures;
- provenance / build attestation where practical.

### 12.2 Agent Registry

Create a registry for managed Agent/Sub-Agent definitions containing metadata such as:

- stable agent ID;
- owner/team;
- version;
- risk level;
- allowed providers;
- allowed tool genres / tools;
- MCP/A2A destinations;
- applicable policy revision;
- prompt/configuration hash;
- deployment state.

The registry is governance metadata. It must not become an authorization bypass around Unified Policy.

## 13. Administration surface

The enterprise design eventually needs an administrator surface, but the first implementation should expose stable backend contracts before building a large UI.

Required administrative capabilities include:

- identity/session status and revoke;
- directory sync status;
- SCIM status;
- active policy revision and rollout state;
- audit export health;
- DLP policy status;
- quota/budget status;
- registered agents and integrations;
- deployment health.

Every mutating administration operation requires explicit administrator authorization and audit logging.

## 14. Multi-instance requirements

Enterprise-ready multi-instance deployment requires more than shared sessions.

The architecture should eventually make these state classes explicit:

| State | Local allowed | Shared/HA requirement |
|---|---:|---|
| OIDC sessions | yes | required |
| revocation state | yes | required |
| policy revision | yes | required |
| SCIM directory projection | yes | required |
| audit queue | yes | durable export required |
| quota counters | yes | required for global limits |
| Agent Registry | yes | required |
| transient execution state | yes | optional depending on feature |

Cross-instance state must have deterministic ownership, TTL, conflict, and failure semantics.

## 15. Security and privacy constraints

Enterprise additions must continue to enforce:

- least privilege;
- fail-closed authorization;
- explicit trust boundaries;
- no raw secrets in logs, telemetry, audit, policy snapshots, or registry metadata;
- bounded external responses;
- bounded retries and queues;
- SSRF-safe enterprise integrations;
- tenant/project separation before retrieval;
- authorization revalidation before protected reads and writes;
- revocation affecting future use even when already-delivered data cannot be recovered.

## 16. Delivery plan

The implementation should be delivered in bounded PRs. Exact PR count may change after design review, but avoid one PR per tiny helper.

### Enterprise foundation: approximately 9-10 PRs

1. Execution Broker contract, external-Web fail-closed routing, and sandbox policy model.
2. Linux sandbox backend using OCI plus gVisor as the preferred baseline.
3. Windows Hyper-V isolation / VM backend and isolated Computer Use surface. This may be deferred to a platform-specific PR if Linux server deployment is the initial target.
4. Durable OIDC session-store abstraction plus SQLite backend.
5. Shared/HA session backend and cross-node revocation semantics.
6. Directory freshness / session-time membership revocation.
7. SCIM Users lifecycle.
8. SCIM Groups / membership and authorization projection.
9. Central policy revisions, hierarchy, dry-run, rollout, and kill switch.
10. Foundation integration tests, deployment documentation, and enterprise rollout gate.

Execution-isolation PRs should remain backend-oriented rather than splitting every tool into a separate sandbox PR. SCIM Users/Groups or durable/shared session work may be combined when review size remains reasonable.

### Governance expansion: approximately 6-8 PRs

1. Dedicated audit schema and local durable sink.
2. SIEM/syslog/webhook audit exporters.
3. DLP / egress policy boundary.
4. Data classification and external DLP adapter contract.
5. Usage accounting and quota/budget enforcement.
6. Workload identity hardening.
7. SBOM / release provenance / security documentation.
8. Agent Registry and administration API.

With E0 execution isolation and the OIDC hardening profile included, the full roadmap is expected to require approximately 16-20 PRs. This is not a target to maximize PR count: backend work should be combined into coherent reviewable units whenever possible.

## 17. Recommended implementation order

Recommended order:

```text
E0 External Web Execution Isolation
        |
        v
E1 Durable Identity / HA
        |
        v
E2 Directory Freshness / Revocation
        |
        v
E3 SCIM
        |
        v
E4 Central Policy Control Plane
        |
        v
E5 Audit / SIEM
        |
        +----------> E6 DLP
        |
        +----------> E7 FinOps / Quota
        |
        +----------> E8 Workload Identity
        |
        v
E9 Supply Chain / Agent Registry
```

E0 is the prerequisite for exposing executable tools through external Web. E1-E4 then form the minimum enterprise-control foundation. E5 should follow before broad deployment because administrator and policy activity must become reviewable. E6-E9 can then be prioritized according to customer/deployment needs.

## 18. Initial enterprise completion gate

The first enterprise milestone is complete when all of the following hold:

- external Web has no direct-host ordinary tool-execution path;
- executable external-Web tools fail closed when the required sandbox backend is unavailable;
- any sandbox that receives plaintext credential material is destroyed/reset to a verified clean state before reuse, or the credential-bearing operation is kept behind a narrow broker outside the sandbox;
- Computer Use/browser automation does not expose the host desktop or host browser profile;
- authenticated Web can run safely across process restart and multiple instances;
- administrator revocation takes effect across nodes;
- directory-derived privileges have a defined freshness bound;
- SCIM deactivation prevents future authenticated use;
- active policy revision is centrally identifiable and auditable;
- policy rollback and emergency deny are supported;
- enterprise audit records exist independently from OpenTelemetry;
- no enterprise control-plane failure silently grants privilege;
- regression tests cover isolation, revocation, downgrade, stale-directory, policy-conflict, and multi-instance cases;
- local/single-user mode remains usable without enterprise dependencies.

## 19. Explicit non-goals for the first enterprise milestone

The first milestone does not require:

- implementing every IdP or directory;
- a complete graphical admin console;
- replacing provider-native cost management;
- generic legal-hold/eDiscovery workflow;
- storing raw enterprise prompts for audit;
- using telemetry as an authorization database;
- federating every runtime data structure across nodes;
- introducing Kubernetes as a deployment requirement;
- requiring SPIFFE/SPIRE for all deployments.

These may be added only when there is a concrete deployment need and a reviewed security contract.

## 20. Relationship to existing documents

This design is an umbrella roadmap. Existing documents remain authoritative for their current areas:

- `docs/ENTERPRISE_POLICY.md`: current Unified Policy behavior;
- `docs/UAG_MEMORY_ARCHITECTURE_V3.md`: principal / Project / Room / Memory isolation;
- `docs/UAG_MEMORY_V3_SECURITY_HARDENING.md`: current Memory/Web security hardening and remaining identity rollout concerns;
- `docs/WEB_IDENTITY_MEMORY.md`: current Web identity and session behavior;
- `docs/UAG_OPENTELEMETRY_DESIGN.md`: observability architecture;
- `docs/UAG_OPENTELEMETRY_PHASE4_CONTRACT.md`: normative Phase 4 observability contract.

When implementation starts, each feature should update its authoritative subsystem document rather than turning this roadmap into a second normative source for low-level grammars, exact numeric limits, or protocol schemas.

## 21. OIDC enterprise hardening profile

The existing OIDC implementation already provides Authorization Code + PKCE (S256), browser-bound state / nonce handling, verified discovery and JWKS, signed ID-token validation, opaque server-side sessions, safe authentication status, local UAG logout, Entra group claims, and bounded Entra group-overage resolution.

Enterprise deployments still need additional OIDC lifecycle and assurance controls. These are part of the enterprise identity program and should build on E1/E2 rather than create a parallel authentication stack.

### 21.1 Priority 1: RP-Initiated Logout

Current `POST /auth/logout` revokes the UAG server-side session and clears UAG cookies. Enterprise OIDC should additionally support standards-based RP-Initiated Logout when the configured provider advertises a reviewed `end_session_endpoint`.

Required properties:

- revoke the local UAG session before redirecting to the IdP logout endpoint;
- support an explicitly configured and allowlisted post-logout return URI;
- never accept an arbitrary browser-supplied logout destination;
- preserve safe behavior when the IdP does not support RP-Initiated Logout;
- avoid exposing ID tokens or provider session material to logs, telemetry, or audit records.

Local logout must remain available even when IdP logout is unavailable.

### 21.2 Priority 2: Back-Channel Logout and remote revocation

Enterprise deployments need a server-to-server way for the IdP to invalidate UAG sessions after administrator revocation or upstream session termination.

The preferred design is OIDC Back-Channel Logout where supported.

The back-channel endpoint must:

- enforce a bounded HTTP form/body size and bounded `logout_token` length **before** JWT decoding, JOSE header parsing, JWKS lookup, or signature verification; oversized requests fail closed without attempting cryptographic validation;
- verify the Logout Token signature against the configured issuer JWKS;
- validate the JWT `alg` through the same provider/UAG/deployment algorithm intersection used for ID Tokens, and always reject `alg=none`;
- require and validate `iss`, `aud`, `iat`, `exp`, `jti`, and the back-channel logout `events` member;
- require `sub`, `sid`, or both;
- reject every Logout Token containing a `nonce` claim;
- validate `iat` and `exp` with bounded clock skew and reject expired tokens;
- maintain a bounded `jti` replay cache as an additional replay defense;
- bind the logout request only to sessions created by the same verified issuer/client;
- when `sid` is present, revoke the matching verified issuer/client/session binding;
- when `sid` is absent and `sub` is present, revoke all UAG sessions matching that verified issuer/client/subject, as required by the Back-Channel Logout semantics;
- make revocation visible across all UAG nodes once E1 shared sessions are enabled;
- return bounded, non-secret diagnostics.

Front-Channel Logout is lower priority because it depends on browser behavior. It may be added for provider compatibility but must not be the authoritative enterprise revocation path.

### 21.3 Priority 3: authentication assurance and step-up MFA

UAG should understand verified authentication-assurance claims without turning them into identity by themselves.

Candidate verified claims include:

- `acr`;
- `amr`;
- `auth_time`.

The login flow may additionally support reviewed request parameters such as:

- `max_age`;
- `acr_values`;
- `prompt=login` where a deployment explicitly requires reauthentication.

These claims should feed a normalized authentication-assurance context that Unified Policy can use.

Example policy intent:

```text
ordinary chat / read-only tools
    -> normal authenticated session

credential administration / process-wide admin changes
    -> recent authentication required

shell, destructive write, external secret-bearing action
    -> deployment policy may require MFA/strong ACR
```

Important invariants:

- an unrecognized `acr` or `amr` value never grants additional privilege;
- assurance policy is based only on verified ID-token/session state;
- MFA state does not replace Project/Room/tool authorization;
- every step-up transaction is bound to the originating UAG session;
- the verified step-up result must have the exact same issuer and subject as the session that initiated step-up; account switching or a changed provider subject aborts the upgrade and must use a separate sign-in flow;
- assurance metadata is merged into an existing session only after that same-principal check succeeds;
- step-up failure leaves the existing lower-assurance session bounded by its original permissions rather than silently upgrading it.

### 21.4 Priority 4: durable session and directory revocation integration

OIDC hardening depends on E1 and E2.

The durable session model must preserve:

- verified issuer/client binding;
- verified subject identity;
- the verified OIDC `sid` when the provider supplies it;
- authentication time and assurance metadata needed for policy;
- revocation state;
- configuration-fingerprint invalidation;
- cross-node visibility.

When `sid` is present, the shared session store must index it together with the verified issuer/client binding so a standards-compliant Logout Token containing `sid` without `sub` can locate and revoke the affected UAG session(s). A `sid` from one issuer/client must never revoke another issuer/client's sessions.

Directory freshness and OIDC session revocation are related but separate:

- OIDC logout/revocation invalidates the authenticated session;
- directory refresh may downgrade or remove authorization while the authenticated identity remains valid.

Both must be revalidated before privileged execution.

### 21.5 Priority 5: stronger client authentication

The initial OIDC implementation supports public-client/PKCE behavior and client-secret deployments. Enterprise deployments should add an explicit token-endpoint client-authentication abstraction.

Preferred additions:

- `private_key_jwt`;
- reviewed `client_secret_basic` / `client_secret_post` interoperability where required by the provider;
- optional mTLS client authentication only when a concrete deployment requires it.

Private-key material must use the existing credential/secret boundary and must never be embedded in ordinary policy, Memory, logs, telemetry, or exported session data.

Client-authentication method selection must be explicit and validated against provider metadata plus the local UAG allowlist. Discovery metadata alone must never enable a weaker method automatically.

### 21.6 Priority 6: ID-token signing algorithm agility

The current verifier deliberately restricts ID-token signatures to RS256. Enterprise interoperability may require additional algorithms, but broad algorithm acceptance is unsafe.

The target design is:

```text
provider-advertised algorithms
        intersect
UAG security allowlist
        intersect
deployment-selected algorithms
```

Only the resulting set may be accepted.

Possible future algorithms include PS256 and ES256 when supported by the verification stack and covered by regression tests.

Explicitly forbidden behavior:

- accepting `none`;
- trusting arbitrary algorithms solely because discovery advertises them;
- algorithm fallback after verification failure;
- mixing symmetric client-secret material with ID-token verification unless a separate reviewed contract explicitly requires it.

### 21.7 Optional: multiple issuers and tenant routing

The first enterprise milestone may remain one configured OIDC issuer per UAG deployment.

A later multi-tenant deployment may add multiple explicitly configured issuers. If implemented, routing must be configuration-driven and fail closed.

Requirements include:

- issuer allowlist;
- per-issuer client ID, redirect URI, client-authentication method, and policy binding;
- no issuer selection from an untrusted ID-token body before signature verification;
- principal IDs remain namespaced by verified issuer + subject;
- no cross-tenant session, Project, Room, Memory, or directory-policy leakage;
- operator-visible issuer/tenant health without exposing raw subject claims.

Dynamic arbitrary-issuer discovery is not a goal.

### 21.8 Refresh Token and UserInfo are not initial requirements

UAG currently avoids retaining provider access/refresh tokens after login except for bounded transient Entra group-overage resolution. This reduces credential lifetime and storage risk.

The initial enterprise OIDC milestone therefore does **not** require:

- refresh-token persistence;
- background access-token refresh;
- continuous UserInfo polling.

Add these only if a concrete integration requires them and only after defining:

- encrypted token storage;
- rotation/revocation semantics;
- multi-instance ownership;
- scope minimization;
- audit/telemetry exclusion;
- provider-specific failure handling.

Directory freshness should prefer a dedicated reviewed directory adapter rather than introducing persistent refresh tokens merely to keep authorization current.

### 21.9 OIDC hardening delivery order

Recommended order:

```text
RP-Initiated Logout
        |
        v
Back-Channel Logout
        |
        v
Step-up / assurance context
        |
        +----> E1 Durable shared sessions
        |
        +----> E2 Directory freshness / revocation
        |
        v
private_key_jwt / client-auth abstraction
        |
        v
Signing algorithm agility
        |
        v
Optional multi-issuer routing
```

The first three items provide the highest enterprise security value relative to implementation size. Durable sessions and directory freshness remain the broader E1/E2 foundation and should be implemented before claiming multi-instance enterprise OIDC readiness.

### 21.10 Completion gate for enterprise OIDC

Enterprise OIDC hardening is complete for a deployment profile when:

- local logout and IdP logout behavior are defined and tested;
- remote IdP revocation can invalidate UAG sessions without relying on a browser, including `sid`-only Logout Tokens when supported;
- Back-Channel Logout validation enforces the local algorithm allowlist, required `iat`/`exp`/event/session claims, `nonce` prohibition, and replay controls;
- privileged policy can require reviewed authentication assurance without permitting a different principal's step-up result to upgrade the current session;
- multi-instance sessions preserve issuer binding, expiry, and revocation;
- directory-role downgrade/revocation has a bounded freshness policy;
- token-endpoint client authentication is explicit and uses protected credential material;
- accepted ID-token signing algorithms are locally allowlisted;
- all authentication failures remain fail-closed;
- raw OIDC credentials and claims remain excluded from normal logs, telemetry, Memory, and audit payload bodies.

This profile does not change the earlier requirement that authentication, authorization, telemetry, and enterprise policy remain separate concerns.
