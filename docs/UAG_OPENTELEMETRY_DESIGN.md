# UAG OpenTelemetry Integration Design

Status: Design only  
Target: post-v0.7.16  
Scope: observability architecture, activation, automatic dependency installation, privacy, Web/OIDC boundaries, propagation, rollout  
Non-goal: this document does not implement OpenTelemetry.

Companion Web/OIDC design:

- `docs/UAG_OPENTELEMETRY_WEB_IDENTITY.md`

## 1. Core rule

> UAG owns the observability model. OpenTelemetry is one projection/export backend of that model.

OpenTelemetry must not become UAG's internal runtime contract, identity system, authorization system, Decision Log store, or provider-specific coupling point.

When OpenTelemetry is enabled, missing OTel Python packages are installed automatically through UAG's existing auto-install mechanism unless `UAGENT_AUTO_INSTALL` forbids it.

## 2. Existing UAG boundaries to reuse

The implementation should instrument existing centralized boundaries rather than provider SDKs independently:

- Agent lifecycle in `runtime/execution.py`;
- provider-neutral LLM rounds in `runtime/round_orchestrator.py`;
- centralized tool execution;
- Context Runtime / Decision Log;
- `IdentityContext` / `TurnContext`;
- Web room/project authorization;
- Sub-Agent, A2A, and MCP boundaries;
- `_pip_auto.install_with_status()` for optional dependencies;
- existing structured `log_event()` events and `correlation_id`.

## 3. Architecture

```text
Authentication / Authorization
             |
             v
         TurnContext
             |
             v
         UAG Runtime
             |
             v
   UAG Observability API
      |              |
      v              v
structured events   OTel adapter
                       |
                 Traces / Metrics
                       |
                      OTLP
                       |
                    Collector
```

The Collector is recommended but is not required for normal UAG operation.

## 4. Internal module boundary

Future implementation should introduce a small runtime-neutral package such as:

```text
src/uagent/runtime/observability/
    __init__.py
    api.py
    settings.py
    bootstrap.py
    dependencies.py
    noop.py
    logging_backend.py
    otel_backend.py
    semantic_mapping.py
    privacy.py
```

Important rules:

- runtime code calls UAG observability functions, not raw `span.set_attribute("gen_ai.*", ...)` throughout the tree;
- semantic-convention-specific names stay in `semantic_mapping.py`;
- disabled or unavailable OTel resolves to a no-op backend;
- observability failure never changes Agent behavior.

## 5. Activation and configuration

### 5.1 Product-level activation

UAG must provide an explicit product-level switch.

For CLI, define:

```text
--otel
--no-otel
```

The CLI value is tri-state: explicitly enabled, explicitly disabled, or unspecified.

Resolution order:

```text
explicit entry-point setting
    > UAGENT_OTEL_ENABLED
    > default OFF
```

For CLI this means CLI flags override the environment variable, consistent with repository configuration conventions.

All entry points must use the same shared `ObservabilitySettings` resolver:

- CLI: `--otel` / `--no-otel` override env;
- GUI: explicit GUI/application setting, if exposed, overrides env;
- Web: server/operator configuration overrides env; browser input cannot enable OTel;
- A2A: server/process configuration overrides env; remote callers cannot enable OTel;
- library/internal entry points: explicit programmatic setting may override env.

Entry points must not independently invent different enablement semantics.

### 5.2 Standard OTel configuration

After UAG enables the OTel backend, prefer standard variables for exporter and sampler behavior:

```text
OTEL_SERVICE_NAME
OTEL_EXPORTER_OTLP_ENDPOINT
OTEL_EXPORTER_OTLP_PROTOCOL
OTEL_TRACES_EXPORTER
OTEL_METRICS_EXPORTER
OTEL_RESOURCE_ATTRIBUTES
```

UAG-specific policy remains limited to UAG-specific concerns, for example:

```text
UAGENT_OTEL_ENABLED=0
UAGENT_OTEL_CAPTURE_CONTENT=0
```

## 6. Automatic dependency installation

OpenTelemetry packages remain outside the minimal/base installation.

Initial package set:

```text
opentelemetry-api
opentelemetry-sdk
opentelemetry-exporter-otlp
```

Exact compatible versions are selected at implementation time.

When effective OTel activation is ON:

```text
initialize observability
      |
      v
ensure OTel dependencies once per process
      |
      +-- present -> continue
      |
      +-- missing -> _pip_auto.install_with_status()
                       |
                       +-- allow  -> install
                       +-- prompt -> ask only when interactive
                       +-- off    -> do not install
      |
      +-- ready -> OTel backend
      +-- unavailable -> warning/event + no-op backend
```

Rules:

- importing UAG alone never installs OTel;
- unrelated `OTEL_*` variables alone do not trigger installation;
- installation is process-level, never per user/room/turn/span;
- do not add a second pip wrapper;
- OTel packages must be added to `_pip_auto.py`'s allowlist;
- installation/exporter failures never fail the Agent task.

An optional `uag[otel]` packaging extra may still exist for reproducible/offline deployment, but ordinary enabled use should not require a manual pip command.

## 7. Canonical trace model

A logical Agent task is the root application operation:

```text
invoke_agent uag
  +-- uag.context.build
  +-- chat <model>
  +-- execute_tool <tool>
  +-- chat <model>
  +-- invoke_agent <sub-agent>
```

For Web, each authorized user turn/task gets its own logical Agent trace. A room or long-lived WebSocket is never a cross-user Agent trace root.

## 8. Operation mapping

Recommended logical mapping:

| UAG operation | OTel operation/span | Notes |
|---|---|---|
| Agent task | `invoke_agent` | one logical task/turn |
| LLM round | `chat` / matching inference operation | provider-neutral UAG boundary |
| Tool execution | `execute_tool` | logical tool operation |
| Planner | `plan` | non-trivial planning only |
| Retrieval | `retrieval` | local/remote as appropriate |
| Memory search/create/update | matching GenAI memory operation | no memory body by default |
| Context build | `uag.context.build` | UAG custom span |
| Provider projection | `uag.provider.project` | internal span if useful |
| Sub-Agent | `invoke_agent` | child/sibling according to execution |
| A2A | agent + transport spans | W3C propagation only on trusted boundaries |
| MCP | logical tool + transport spans | avoid duplicates |

The canonical LLM trace is created at UAG's provider-neutral round boundary. Provider SDK auto-instrumentation may later be an optional nested diagnostic layer, not the canonical model.

## 9. Tokens and Decision Log

Keep estimated and provider-reported token data distinct:

```text
uag.tokens.estimate.*
uag.tokens.reported.*
```

Do not present estimates as exact provider usage.

Decision Log remains separate from OTel. It may store linkage such as:

```text
correlation_id
trace_id
span_id
decision_id
plan_id
projection_id
```

Detailed decision reasoning remains in UAG storage/debug artifacts.

## 10. Privacy and cardinality

Default is metadata only.

Do not export by default:

- system/user/assistant/reasoning bodies;
- tool arguments/results;
- memory/artifact/file bodies;
- OAuth/OIDC tokens and cookies;
- raw Authorization/Cookie headers;
- raw principal IDs, OIDC subjects, display names, or groups.

Never use the following as metric dimensions:

```text
principal_id
subject
room_id
project_id
session_id
trace_id
group name
```

`UAGENT_OTEL_CAPTURE_CONTENT` is operator/server policy, not browser/message input.

## 11. Web/OIDC security boundary

The companion document is normative.

Critical rules:

1. Authentication and authorization occur before Agent execution and remain authoritative outside OTel.
2. Trace IDs, baggage, `traceparent`, and span attributes are never authorization inputs.
3. Each user turn gets a separate logical Agent trace.
4. Shared rooms never merge principals into one trace tree.
5. OIDC session validity must be revalidated on every WebSocket turn before creating the turn's trusted execution context.
6. Room/project/private-room authorization must still be revalidated using server-side policy.
7. Browser-provided inbound trace context is rejected/detached by default from the first OTel-enabled Web release.
8. Trusted proxy/internal inbound context may be supported later through explicit deployment policy.
9. OIDC/session secrets and raw identity claims remain outside remote telemetry.
10. External trace backends are operator/admin surfaces by default.

## 12. Inbound trace policy

### 12.1 Phase-1 minimum requirement

Untrusted browser `traceparent` / `tracestate` must be rejected or detached **before** a UAG Web turn/server span is parented from it.

This requirement ships with initial Web tracing, not a later distributed-tracing phase.

This is important even if ASGI/HTTP auto-instrumentation is enabled: UAG must not let arbitrary browser context cause server spans or Agent traces to join an attacker-selected trace.

Default:

```text
browser request / WebSocket message
      -> discard untrusted inbound OTel parent
      -> perform authentication/session revalidation
      -> perform authorization
      -> create fresh trusted UAG turn/Agent trace
```

Later phases may add an explicit trusted-ingress policy for controlled reverse proxies or internal services.

## 13. OIDC live-session requirement

The current Web connection model may retain a resolved `IdentityContext` for a connection. That alone is not sufficient to guarantee that OIDC session expiry/revocation is observed on each later WebSocket turn.

Therefore the OTel/Web implementation must not describe live-session revocation as already guaranteed by current connection identity caching.

Implementation requirement:

- retain or derive a server-side OIDC session revalidation handle/reference at connection acceptance;
- never expose that handle to OTel;
- before every WebSocket turn, revalidate the handle against the authoritative OIDC session store/configuration;
- if expired/revoked/stale, deny the turn and do not create downstream Agent/LLM/Tool spans;
- only after successful revalidation create the trusted `TurnContext` and Agent trace;
- non-OIDC modes use their own appropriate revalidation semantics through the shared identity boundary.

This is an authentication hardening requirement discovered during design review, not an OTel authorization mechanism.

## 14. Signals

Priority:

1. traces;
2. low-cardinality metrics;
3. existing UAG structured logs with trace/span correlation;
4. OTel Logs only later if justified.

Useful aggregate metrics include operation duration, token usage, retry/error counts, and Context Runtime compression/savings. Security/audit logs remain useful even when OTel is disabled or sampled out.

## 15. Rollout

### Phase 0 - design only

- finalize core design;
- finalize Web/OIDC companion design;
- no runtime behavior change.

### Phase 1 - safe core tracing

- shared `ObservabilitySettings` including CLI `--otel` / `--no-otel` precedence;
- automatic dependency readiness;
- no-op and OTel backends;
- Agent/LLM/Tool spans;
- trace/log correlation;
- Web per-turn root behavior;
- **reject/detach untrusted browser inbound trace context**;
- **OIDC live-session revalidation before every WebSocket turn**;
- content and raw identity capture OFF.

### Phase 2 - Context and metrics

- Context/Memory/Retrieval spans and aggregate metrics;
- Decision Log linking;
- auth/authz operational events/spans where useful.

### Phase 3 - trusted distributed propagation

- Sub-Agent/A2A/MCP propagation hardening;
- explicit trusted reverse-proxy/internal ingress policy;
- multi-instance validation;
- duplicate-span policy with transport instrumentation.

### Phase 4 - optional advanced diagnostics

- controlled content capture;
- optional pseudonymous scope correlation;
- optional SDK nested instrumentation;
- optional trace-query proxy with UAG authorization.

## 16. Testing requirements

Core tests:

- OTel disabled requires no OTel package;
- enabling OTel auto-installs when policy allows;
- `prompt`/`off` policy is honored;
- CLI flags override env and all entry points resolve through shared settings;
- exporter/install failure falls back safely;
- Agent/LLM/Tool hierarchy is coherent;
- estimated and reported tokens remain distinct;
- secrets/content are excluded;
- metrics avoid high-cardinality identity/scope fields.

Web/OIDC tests:

- user A and user B turns have separate root Agent traces;
- shared room/WebSocket does not create a long-lived cross-user trace;
- OIDC session expiry/revocation after connection acceptance denies the next turn;
- authentication configuration change denies stale sessions;
- room/project/private-room revocation still takes effect;
- authorization denial creates no downstream Agent/LLM/Tool spans;
- forged browser `traceparent` is detached/rejected in Phase 1;
- trace context never changes authorization outcome;
- no OIDC/session secrets or raw identity values are exported.

## 17. Acceptance criteria

The first implementation is acceptable only when all are true:

1. UAG behavior is unchanged with OTel disabled.
2. CLI supports explicit enable/disable and CLI overrides environment fallback.
3. CLI/GUI/Web/A2A share one activation resolver and equivalent semantics.
4. Missing OTel dependencies auto-install when enabled and policy permits.
5. `UAGENT_AUTO_INSTALL=prompt|off` is honored.
6. OTel/exporter/install failures do not fail Agent tasks.
7. Each Web user turn has an isolated logical Agent trace.
8. An OIDC session expired/revoked after WebSocket acceptance is rejected on the next turn through server-side revalidation.
9. Untrusted browser `traceparent` is rejected/detached from the initial Web tracing phase.
10. Existing room/project/private-room authorization remains server-authoritative and revalidated.
11. OTel trace context never acts as identity or authorization input.
12. OIDC/session secrets and raw identity claims are not exported by default.
13. Prompt/response/tool-result content is not exported by default.
14. Room/project/principal identifiers are not metric dimensions.
15. Existing structured events remain operational and trace-linkable.
16. Decision Log remains independent and trace-linkable.
17. Provider paths share the same logical trace model.
18. Semantic-convention-specific names remain isolated in the adapter.

## 18. Decisions fixed by this design

- OpenTelemetry is opt-in and disabled by default.
- CLI `--otel` / `--no-otel` overrides `UAGENT_OTEL_ENABLED`.
- All entry points use shared activation semantics.
- OTel dependencies auto-install through the existing UAG installer when enabled.
- OTel is a projection backend, not UAG's canonical observability contract.
- `correlation_id` remains distinct from `trace_id`.
- Decision Log remains separate.
- Canonical LLM tracing is provider-neutral.
- Web Agent traces are per turn/task, not per room/WebSocket.
- OIDC live sessions must be revalidated per WebSocket turn.
- Untrusted browser inbound trace context is detached/rejected in Phase 1.
- Authentication/authorization remain independent of telemetry.
- Raw OIDC/session secrets and identity claims are excluded by default.
- Standard `OTEL_*` exporter/sampler configuration is preferred after UAG activation.
- OTLP is the standard export path.

## 19. Remaining implementation-time choices

These do not change the architecture:

1. exact internal Python Protocol/context-manager API;
2. exact compatible OTel package versions;
3. exact validated GenAI semantic-convention revision;
4. concrete CLI parser placement for `--otel` / `--no-otel`;
5. concrete representation of the server-side OIDC session revalidation handle;
6. explicit trusted-ingress configuration shape for reverse proxies/internal clients;
7. whether metrics ship in the same release as initial traces.
