# UAG OpenTelemetry Integration Design

Status: Design only  
Target: post-v0.7.16  
Scope: observability architecture, OpenTelemetry integration boundary, automatic dependency installation, signal model, privacy, propagation, rollout  
Non-goal: this document does not implement OpenTelemetry.

Companion design for Web multi-user/OIDC security and trace isolation:

- `docs/UAG_OPENTELEMETRY_WEB_IDENTITY.md`

## 1. Purpose

UAG already has provider-neutral runtime boundaries, structured event logging, lifecycle events, tool dispatch events, LLM round summaries, Context Runtime telemetry, Decision Log data, Sub-Agent execution, A2A, MCP, and Web/CLI/GUI entry points.

The purpose of this design is to add OpenTelemetry (OTel) without making OpenTelemetry the internal contract of UAG.

The central rule is:

> UAG owns the observability model. OpenTelemetry is one projection/export backend of that model.

A second product rule is:

> When the user enables OpenTelemetry, UAG installs the required OpenTelemetry packages automatically through the existing UAG auto-install mechanism unless the user's auto-install policy forbids it.

Users should not normally need to run a separate `pip install` command merely to turn tracing on.

For Web deployments, authentication and authorization remain authoritative outside OpenTelemetry. Browser trace context, span attributes, baggage, trace IDs, and exporter data never grant identity, room, project, ownership, or role permissions. Each Web user turn gets its own logical Agent trace; a shared room or long-lived WebSocket never becomes one cross-user trace.

## 2. Current UAG baseline

The current runtime already contains most information required for useful tracing.

- `runtime/logging_setup.py`
  - stable `event_code`
  - `event_id`
  - `correlation_id`
  - `agent_id`, `session_id`, `task_id`, `tool_call_id`
  - `provider`, `duration_ms`, `status`, `error_type`
  - ContextVar-based event context propagation
  - secret-field masking
- `runtime/execution.py`
  - shared Agent lifecycle events
- `runtime/round_orchestrator.py`
  - provider-neutral LLM round boundary
  - duration
  - event/tool-call counts
  - estimated request tokens
  - provider usage deltas
  - projection/tool-schema sizes
  - retry/recovery summary fields
- `tools/__init__.py`
  - centralized tool execution boundary
  - tool completion/failure events
- Context Runtime
  - raw/active/saved context sizes
  - token estimates
  - per-section data
  - explicit Context Decision Log
- Web identity/runtime
  - `IdentityContext` / `TurnContext`
  - connection-bound authenticated identity
  - room/private-room authorization
  - project membership and role authorization
  - OIDC server-side session validation
- A2A/Sub-Agent/MCP
  - distributed or nested execution boundaries that benefit from trace propagation
- `_pip_auto.py`
  - allowlisted first-use package installation
  - `UAGENT_AUTO_INSTALL=allow|prompt|off`
  - localized installation status
  - version checking and repair/reinstall support through `install_with_status()`

OpenTelemetry should therefore be added as an adapter around existing UAG boundaries and should reuse the existing auto-install policy instead of introducing a second dependency installer.

## 3. Goals

### 3.1 Primary goals

1. Trace one UAG task across Agent, LLM, Tool, Context Runtime, Memory, Sub-Agent, A2A, MCP, and external calls.
2. Preserve a provider-neutral trace model across OpenAI, Azure OpenAI, Anthropic, Gemini, xAI, OpenRouter, LM Studio, llama.cpp, and future providers.
3. Export traces and metrics through OTLP to an OpenTelemetry Collector or compatible backend.
4. Correlate existing UAG structured logs with OpenTelemetry `trace_id` / `span_id`.
5. Keep Decision Log as a UAG-owned diagnostic/audit artifact rather than flattening it into span attributes.
6. Keep telemetry opt-in and failure-isolated.
7. Avoid capturing prompt, response, tool argument, tool result, memory body, and artifact body content by default.
8. Follow OpenTelemetry GenAI semantic conventions where useful, while isolating semantic-convention mapping behind an adapter because the GenAI conventions are still evolving.
9. Automatically install required OTel Python packages when OTel is enabled and packages are missing, subject to the existing UAG auto-install policy.
10. Preserve normal UAG behavior if automatic installation is disabled or fails.
11. Preserve Web multi-user identity, room/project authorization, private-room ownership, and OIDC session boundaries independently from telemetry.
12. Prevent trace context from becoming a cross-user or cross-project authorization channel.

### 3.2 Non-goals

The first implementation must not:

- replace `log_event()`
- require an OpenTelemetry Collector for normal UAG operation
- force OTel packages into the minimal/base installation
- require ordinary users to manually install OTel packages before enabling the feature
- bypass `UAGENT_AUTO_INSTALL`
- alter LLM/provider behavior
- alter retry policy
- alter tool execution behavior
- alter Context Runtime decisions
- alter authentication or authorization semantics
- use `trace_id`, `span_id`, baggage, or inbound `traceparent` as identity/authorization input
- merge multiple users in a shared room into one long-lived Agent trace
- send raw conversation content by default
- export OIDC tokens, session cookies, raw subjects, principal IDs, or group membership by default
- use OpenTelemetry as persistent Agent state
- use spans as the canonical Decision Log store
- couple UAG internals directly to one observability vendor
- fail an Agent task merely because OTel packages cannot be installed or telemetry cannot be exported

## 4. Design principles

### 4.1 UAG model first, OTel projection second

Application code should not spread direct calls such as:

```python
span.set_attribute("gen_ai.*", ...)
```

across the codebase.

Instead:

```text
UAG Runtime
   -> UAG Observability API
      -> Structured Log backend
      -> OpenTelemetry backend
      -> future backend(s)
```

Only the OTel adapter knows detailed OTel semantic-convention mapping.

### 4.2 Preserve existing correlation identity

`correlation_id` and OpenTelemetry `trace_id` are related but are not the same concept.

Do not replace `correlation_id` with `trace_id`.

Structured events may contain both when an active span exists:

```text
correlation_id
trace_id
span_id
```

`correlation_id` remains available when OTel is disabled.

### 4.3 Decision Log remains separate

Telemetry mainly answers:

> What happened, where, how long did it take, and how much resource was used?

Decision Log mainly answers:

> Why did UAG choose this context/action/plan?

Recommended linkage:

```text
trace_id
span_id
decision_id
plan_id
projection_id
```

Detailed decision reasoning remains in UAG storage.

### 4.4 Web identity and authorization are independent trust boundaries

For Web execution:

```text
OIDC/authentication
    -> IdentityContext
    -> room/project authorization
    -> TurnContext
    -> Agent execution
    -> OTel observation
```

OpenTelemetry observes the outcome only. It never creates or widens authorization.

Each user turn is an independent logical Agent trace. Shared rooms and WebSocket connections are correlation containers, not Agent trace roots.

Detailed requirements are normative in `docs/UAG_OPENTELEMETRY_WEB_IDENTITY.md`.

### 4.5 Disabled means near-zero impact

When OTel is disabled:

- no OTel package installation is attempted
- no network export is attempted
- no OTel package is required
- no trace-dependent logic changes execution
- existing `log_event()` behavior continues

### 4.6 Enabling OTel triggers dependency readiness

When OTel is enabled, UAG performs a lazy readiness check before creating the OTel backend.

Conceptually:

```text
UAGENT_OTEL_ENABLED=1
        |
        v
ensure_otel_dependencies()
        |
        +-- already installed -> continue
        |
        +-- missing -> existing UAG auto-install policy
                         |
                         +-- allow  -> install automatically
                         +-- prompt -> ask only when interactive
                         +-- off    -> do not install
        |
        v
initialize OTel backend or safely fall back to no-op
```

This check should run once per process, not once per user, room, span, or LLM call.

### 4.7 Telemetry must never break the Agent

Exporter failure, Collector failure, installation failure, queue overflow, invalid endpoint configuration, or serialization failure must not fail a user task.

Observability failures may generate a local diagnostic event, but Agent execution remains authoritative.

## 5. Architecture

```text
Authentication / Authorization
             |
             v
         TurnContext
             |
             v
                         UAG Runtime
                             |
                 +-----------+-----------+
                 |                       |
          Domain operations        Decision Log
                 |                       |
                 v                       v
          UAG Observability API      UAG storage
                 |
        +--------+---------+
        |                  |
        v                  v
 Structured Event      OTel Adapter
     backend                |
                            +--------------------+
                            |                    |
                            v                    v
                         Traces              Metrics
                            |                    |
                            +---------+----------+
                                      |
                                     OTLP
                                      |
                                      v
                           OpenTelemetry Collector
```

The Collector is recommended but not required by the internal design. UAG should use standard OTLP through the OTel SDK/exporter and avoid vendor-specific SDKs in core runtime code.

## 6. Proposed module boundary

A future implementation should introduce a small observability package, for example:

```text
src/uagent/runtime/observability/
    __init__.py
    api.py
    bootstrap.py
    dependencies.py
    noop.py
    logging_backend.py
    otel_backend.py
    semantic_mapping.py
    privacy.py
```

### `api.py`

Provider-neutral UAG observability contract.

Conceptual operations:

```text
start_agent_span
start_llm_span
start_tool_span
start_context_span
start_retrieval_span
start_memory_span
start_sub_agent_span
record_event
record_metric
current_trace_ids
```

### `bootstrap.py`

Selects no-op vs OTel backend and initializes it once.

### `dependencies.py`

Owns OTel package readiness and delegates installation to the existing `_pip_auto.install_with_status()` mechanism.

It must not invoke pip directly.

### `noop.py`

No-op implementation used when disabled or unavailable.

### `logging_backend.py`

Bridge to existing structured events. The current `log_event()` API remains supported.

### `otel_backend.py`

OTel SDK integration, OTLP exporters, span creation, metrics, status/error recording, and context propagation.

### `semantic_mapping.py`

Single location that maps UAG domain concepts to OpenTelemetry GenAI semantic conventions and UAG custom attributes.

### `privacy.py`

Content-capture policy, identity/privacy redaction, cardinality policy, and safe attribute conversion.

## 7. Automatic dependency installation

### 7.1 Reuse UAG's existing installer

OTel installation must use the existing UAG mechanism:

```python
from uagent._pip_auto import install_with_status
```

No new subprocess/pip wrapper should be introduced in the observability package.

The OTel packages must be added to `_pip_auto.py`'s allowlist.

Initial package set:

```text
opentelemetry-api
opentelemetry-sdk
opentelemetry-exporter-otlp
```

Exact version constraints are selected at implementation time and should be validated as a compatible set.

### 7.2 Trigger

Automatic installation occurs only when all of the following are true:

1. `UAGENT_OTEL_ENABLED` is true.
2. The OTel backend is being initialized.
3. One or more required packages are missing or outside the supported version range.
4. Existing `UAGENT_AUTO_INSTALL` policy permits installation.

Merely importing UAG must not install OpenTelemetry.

Merely setting unrelated `OTEL_*` variables must not install OpenTelemetry unless UAG's product-level OTel switch is enabled.

### 7.3 Existing auto-install policy remains authoritative

| `UAGENT_AUTO_INSTALL` | OTel dependency behavior |
|---|---|
| `allow` (default) | install missing required packages automatically |
| `prompt` | ask before installation when interactive; non-interactive execution does not install |
| `off` | never install automatically |

UAG must not create an OTel-specific override that silently bypasses this policy.

### 7.4 Failure behavior

If dependencies remain unavailable:

```text
OTel requested
   -> dependency unavailable
   -> local diagnostic event/warning
   -> OTel backend disabled for this process
   -> no-op backend
   -> authentication/authorization/Agent execution continue normally
```

Do not repeatedly retry installation per user/room/round.

### 7.5 Preinstallation remains supported

An optional package extra may still be provided for offline/reproducible deployments, but automatic installation is normal UX.

## 8. Trace model

A typical non-Web/local task:

```text
invoke_agent uag
|
+-- uag.context.build
+-- chat <model>
+-- execute_tool <tool>
+-- chat <model>
```

A Web turn:

```text
web.message
   -> authorization checks
   -> invoke_agent uag
      +-- uag.context.build
      +-- chat <model>
      +-- execute_tool <tool>
```

A WebSocket or room itself is not the logical Agent root.

## 9. Mapping UAG operations to OpenTelemetry

Recommended mapping:

| UAG operation | OTel operation / span | Kind | Notes |
|---|---|---|---|
| Agent task | `invoke_agent` | INTERNAL | one logical task/turn |
| Web turn boundary | server/internal span | SERVER/INTERNAL | after trusted connection identity; never room-wide |
| OIDC login/callback | HTTP + UAG auth span/event | SERVER/INTERNAL | secrets excluded |
| Authorization check | UAG authz span/event | INTERNAL | result only; policy remains authoritative |
| Remote Agent call | `invoke_agent` | CLIENT | propagation required |
| Planner/decomposition | `plan` | INTERNAL | avoid trivial spans |
| LLM generation | `chat` or matching inference operation | CLIENT | logical call includes retries |
| Tool execution | `execute_tool` | INTERNAL | logical tool operation |
| Retrieval | `retrieval` | INTERNAL/CLIENT | local vs remote dependent |
| Memory search | `search_memory` | INTERNAL/CLIENT | content excluded by default |
| Context build | `uag.context.build` | INTERNAL | UAG custom span |
| A2A transport | Agent plus protocol spans | CLIENT/SERVER | W3C propagation |
| MCP | MCP conventions where applicable | CLIENT/SERVER | avoid duplicates |

## 10. LLM span semantics

Canonical tracing occurs at UAG's provider-neutral logical round boundary, not independently inside every provider SDK.

Preserve the distinction between estimated and provider-reported tokens:

```text
uag.tokens.estimate.*
uag.tokens.reported.*
```

Estimated values must never be presented as exact provider usage.

## 11. Tool tracing

The centralized UAG tool runner is the primary instrumentation point.

Raw tool arguments/results are not recorded by default.

Existing tool trace output and structured events remain supported.

## 12. Context Runtime tracing

Recommended aggregate metadata:

```text
uag.context.raw.chars
uag.context.active.chars
uag.context.saved.chars
uag.context.raw.tokens
uag.context.active.tokens
uag.context.saved.tokens
uag.context.saved.ratio
uag.context.candidate.count
uag.context.keep.count
uag.context.compact.count
uag.context.exclude.count
uag.context.retrieve_more.count
uag.context.budget.mode
```

Detailed decisions remain in Decision Log/debug data.

## 13. Decision Log correlation

Decision Log records may store:

```text
decision_id
correlation_id
trace_id
span_id
plan_id
projection_id
```

The full decision body remains outside OTel by default.

## 14. Web multi-user and OIDC rules

The companion design `UAG_OPENTELEMETRY_WEB_IDENTITY.md` is normative for Web deployments.

Key rules:

1. One Web user turn -> one logical Agent trace.
2. Shared room != shared trace.
3. Long-lived WebSocket != Agent trace root.
4. Browser-supplied `traceparent` is untrusted by default.
5. Trace context is never identity or authorization input.
6. OIDC code/token/session cookie/session token and raw claims are never exported.
7. Raw `principal_id`, OIDC subject, display name, and groups are not exported by default.
8. Room/project/owner identifiers are never metric dimensions.
9. Private-room ownership and room/project roles remain server-side authorization data.
10. Authorization is revalidated according to existing UAG policy even when trace context already exists.
11. OTel auto-install is process-level and never per user/room.
12. External trace backends are operator/admin surfaces by default; user-visible trace access requires UAG authorization mediation.

## 15. Sub-Agent and multi-agent tracing

Local Sub-Agents are children of the invoking Agent span. Parallel Sub-Agents are siblings under the invoking operation.

Identity/Turn Context and OTel Context must both propagate correctly, but neither substitutes for the other.

## 16. A2A and distributed propagation

A2A may propagate W3C Trace Context when enabled, but trace headers are observability metadata only and never authorization.

## 17. MCP propagation

Use standard MCP conventions where available and retain the logical UAG tool span above transport spans.

## 18. Signals

### 18.1 Traces

Initial boundaries:

- Web turn / Agent task
- LLM logical round
- Tool execution
- Sub-Agent invocation
- Context build
- Retrieval/Memory
- OIDC/authz operations where operationally useful

### 18.2 Metrics

Keep metrics low-cardinality.

Safe auth-related dimensions may include:

```text
authn_kind
operation
outcome
normalized role
normalized error class
```

Never use:

```text
principal_id
subject
room_id
project_id
session_id
group name
trace_id
```

as metric dimensions.

### 18.3 Logs

Existing UAG structured events remain the primary logging/audit format and may be enriched with active `trace_id` / `span_id`. Security/audit logging must remain useful even when OTel is disabled or sampled out.

## 19. Privacy and content capture

Default: metadata only.

In addition to prompt/tool/memory content, Web deployments must exclude by default:

```text
OIDC authorization code
access/refresh/ID tokens
session cookie/token
PKCE verifier
state
nonce
raw claims
Authorization/Cookie headers
principal_id
subject
display_name
groups
```

`UAGENT_OTEL_CAPTURE_CONTENT` is operator/server policy, not browser/user input.

## 20. Cardinality and identity policy

Raw room/project/principal identifiers are trace-only at most and omitted from remote telemetry by default.

If cross-trace identity/scope correlation becomes operationally necessary, use server-keyed HMAC pseudonyms, disabled by default, never plain hashes and never metric labels.

## 21. Error semantics

Authentication denial, authorization denial, cancellation, timeout, LLM/tool errors, exporter errors, and dependency-install errors remain distinct.

Observability failure cannot change authentication or authorization outcomes.

## 22. Sampling

Standard OTel sampling applies to telemetry only. It does not affect security/audit checks or authorization decisions.

## 23. Configuration

```text
UAGENT_OTEL_ENABLED=0
UAGENT_OTEL_CAPTURE_CONTENT=0
UAGENT_AUTO_INSTALL=allow
```

Standard `OTEL_*` variables configure exporters/sampling after the UAG OTel backend is enabled.

A multi-user process must not set one user/project/room as a process-level OTel Resource identity.

## 24. Packaging

OTel remains absent from minimal installation but is automatically installed on first enabled use when policy allows.

Auto-install state is process-level; it must not depend on the authenticated Web user.

## 25. GenAI semantic-convention compatibility

Semantic-convention-specific names remain isolated in `semantic_mapping.py`.

## 26. Provider-neutral instrumentation

Canonical UAG traces are created at UAG provider-neutral boundaries.

## 27. Integration with `log_event()`

Existing event codes remain compatible. Active trace correlation may be added without making logs dependent on OTel.

## 28. Rollout phases

### Phase 0

- finalize core design
- finalize Web/OIDC companion design
- no runtime behavior change

### Phase 1

- automatic dependencies
- Observability API/no-op/OTel backend
- Agent/LLM/Tool spans
- Web per-turn root behavior
- trace/log correlation
- content/identity capture OFF

### Phase 2

- Context/Memory/Retrieval metrics
- Decision Log linkage
- auth/authz operational spans/events where justified

### Phase 3

- Sub-Agent/A2A/MCP distributed propagation
- inbound trace trust policy hardening
- multi-instance validation

### Phase 4

- advanced diagnostics
- optional pseudonymous identity/scope correlation
- optional user-visible trace proxy only with authorization design

## 29. Testing strategy

In addition to core OTel tests, Web tests must verify:

- separate root Agent traces for different users/turns;
- no room-wide long-lived trace;
- no OIDC/session secrets in telemetry;
- raw principal/subject/groups excluded by default;
- room/project IDs absent from metric dimensions;
- trace context cannot override access policy;
- membership/role/session revocation still takes effect on existing WebSocket connections;
- authorization denial produces no downstream LLM/tool spans;
- untrusted browser `traceparent` does not join another user's trusted trace by default;
- exporter/install failures do not change authentication/authorization behavior.

## 30. Acceptance criteria

The initial implementation is acceptable when:

1. UAG runs unchanged with OTel disabled.
2. Missing OTel packages auto-install when enabled and policy permits.
3. `UAGENT_AUTO_INSTALL=prompt|off` is honored.
4. OTel failures degrade to no-op without Agent failure.
5. Each Web user turn has an isolated logical Agent trace.
6. Shared rooms and WebSocket connections do not merge user traces.
7. OTel trace context never acts as identity/authorization input.
8. OIDC/session secrets are never exported.
9. Raw principal IDs/subjects/groups are not exported by default.
10. Room/project/owner identifiers are not metric dimensions.
11. Existing room/project/private-room authorization remains authoritative and revalidated.
12. External trace-backend access is not implicitly granted to room members.
13. Provider paths share the same logical trace model.
14. Existing structured events still work.
15. Prompt/response/tool-result content is not exported by default.
16. Decision Log remains independent and trace-linkable.
17. Sub-Agent parentage is correct.
18. Semantic-convention names are isolated in the adapter.

## 31. Decisions made by this design

- OpenTelemetry is opt-in.
- Dependencies auto-install on first enabled use through existing UAG policy.
- OTel is not UAG's canonical telemetry contract.
- `correlation_id` remains distinct from `trace_id`.
- Decision Log remains separate.
- Canonical LLM tracing is provider-neutral.
- Web traces are per turn/task, not per room/WebSocket.
- Browser trace context is untrusted by default.
- Authentication/authorization remain independent from telemetry.
- Raw OIDC/session secrets and identity claims are excluded.
- Shared-room access does not imply observability-backend access.
- OTel auto-install is process-level, not user-level.
- Standard `OTEL_*` configuration is preferred.
- OTLP is the standard export path.

## 32. Remaining design questions before implementation

1. Exact internal Observability API shape.
2. Exact compatible OTel package versions.
3. Exact validated GenAI semantic-convention revision.
4. Whether metrics ship with initial traces.
5. Exact trusted-ingress configuration for accepting browser/reverse-proxy inbound trace context.
6. Whether pseudonymous principal/project/room correlation is needed in the first production deployment or remains off.
7. Whether a later UAG trace-query proxy is needed for non-admin Web users.

## 33. Summary

```text
Web/OIDC authentication
        |
        v
server-authoritative authorization
        |
        v
TurnContext
        |
        v
Agent task
        |
        v
UAG Observability API
        |
        +-- structured events
        +-- OTel adapter -> OTLP
```

OpenTelemetry observes the trusted UAG execution boundary. It does not define identity, ownership, room/project membership, or access. In multi-user Web mode, every turn remains isolated as its own logical trace, while OIDC/session secrets and raw identity information remain outside remote telemetry by default.
