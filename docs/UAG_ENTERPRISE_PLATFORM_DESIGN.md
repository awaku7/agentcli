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
| Identity -> Authorization -> Policy -> Agent/Tool execution|
|      |             |           |             |             |
|      +-------------+-----------+-------------+             |
|                    Audit decision stream                    |
|                    OTel diagnostics                         |
+------------------------------------------------------------+
```

The control plane may initially be local-file / SQLite backed, but public interfaces must not assume one process or one host.

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

### Enterprise foundation: approximately 7 PRs

1. Durable OIDC session-store abstraction plus SQLite backend.
2. Shared/HA session backend and cross-node revocation semantics.
3. Directory freshness / session-time membership revocation.
4. SCIM Users lifecycle.
5. SCIM Groups / membership and authorization projection.
6. Central policy revisions, hierarchy, dry-run, rollout, and kill switch.
7. Foundation integration tests, deployment documentation, and enterprise rollout gate.

PRs 4 and 5 may be combined if review size remains reasonable. PRs 1 and 2 may also be combined if the storage abstraction stays small.

### Governance expansion: approximately 6-8 PRs

1. Dedicated audit schema and local durable sink.
2. SIEM/syslog/webhook audit exporters.
3. DLP / egress policy boundary.
4. Data classification and external DLP adapter contract.
5. Usage accounting and quota/budget enforcement.
6. Workload identity hardening.
7. SBOM / release provenance / security documentation.
8. Agent Registry and administration API.

Total expected implementation size is approximately 12-16 PRs, but the design favors coherent reviewable units over hitting a fixed number.

## 17. Recommended implementation order

Recommended order:

```text
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

E1-E4 form the minimum enterprise-control foundation. E5 should follow before broad deployment because administrator and policy activity must become reviewable. E6-E9 can then be prioritized according to customer/deployment needs.

## 18. Initial enterprise completion gate

The first enterprise milestone is complete when all of the following hold:

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
