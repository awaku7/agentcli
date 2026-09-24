# UAG OpenTelemetry Web Multi-User / OIDC Design

Status: Design only  
Parent design: `docs/UAG_OPENTELEMETRY_DESIGN.md`  
Scope: Web multi-user execution, OIDC, room/project authorization, live-session revalidation, trace isolation, privacy, observability access control  
Non-goal: this document does not implement authentication or OpenTelemetry.

## 1. Purpose

UAG Web can serve multiple authenticated users in one process. Rooms may be private or shared, rooms may be bound to projects, and browser identities may be established through OIDC.

OpenTelemetry must preserve the trust ordering:

```text
Authentication / session validation
        -> IdentityContext
        -> room/project authorization
        -> TurnContext
        -> Agent execution
        -> Observability
```

> OpenTelemetry observes trusted execution. It never participates in identity or authorization.

Trace context, baggage, span attributes, trace IDs, correlation IDs, exporter metadata, and trace-backend data are never proof of identity, room membership, project membership, ownership, or role.

## 2. Existing identity model and one important gap

UAG already separates identity from turn-local execution.

`IdentityContext` carries authenticated-principal metadata such as:

```text
principal_id
authenticated
authn_kind
issuer
subject
display_name
groups
```

`TurnContext` carries the immutable actor/workspace/session boundary for one turn:

```text
principal_id
room_id
project_id
session_id
entry_point
authenticated
authn_kind
groups
private_session
server_bound_project
```

Web connections bind an authenticated identity when the connection is accepted, and room/project policy is checked server-side.

However, a connection-bound `IdentityContext` alone is **not sufficient** to guarantee that an OIDC session that expires or is revoked after WebSocket acceptance is rejected on every later turn.

This design therefore adds a required implementation contract:

> OIDC live-session validity must be revalidated on every WebSocket turn before a trusted `TurnContext` or Agent trace is created.

This is an authentication requirement discovered during design review. It must not be described as behavior already guaranteed by the current connection identity cache.

## 3. Multi-user trace isolation

### 3.1 One user turn, one logical Agent trace

A long-lived process, room, or WebSocket is not one Agent trace.

```text
Web process
  +-- user A / turn 1 -> trace A1
  +-- user B / turn 1 -> trace B1
  +-- user A / turn 2 -> trace A2
```

Shared rooms may contain turns from many principals, but those turns remain separate logical Agent traces.

Do not build a room-wide trace lasting hours or days.

### 3.2 WebSocket handshake is not the Agent root

The transport connection may outlive many turns.

```text
WebSocket connection
  +-- turn 1: session revalidate -> authz -> Agent trace 1
  +-- turn 2: session revalidate -> authz -> Agent trace 2
  +-- turn 3: session revalidate -> authz -> Agent trace 3
```

Do not keep one active OTel span in a ContextVar for the entire connection and reuse it across turns.

## 4. Per-turn OIDC live-session revalidation

### 4.1 Required behavior

For OIDC WebSocket connections, connection acceptance must retain enough **server-side revalidation state** to verify that the browser session is still valid later.

The implementation may use an opaque session handle/reference or equivalent server-side binding. The exact representation is an implementation choice, but these semantics are mandatory:

1. The raw OIDC/session secret is never exposed to OTel.
2. Before every WebSocket turn, UAG revalidates the server-side session reference against the authoritative OIDC session store and current authentication configuration.
3. If the session is expired, revoked, missing, or configuration-stale, the turn is denied.
4. No trusted `TurnContext` is created from stale cached identity alone.
5. No downstream Agent/LLM/Tool span is created for a denied stale session.
6. Only after successful session revalidation does UAG continue with room/project/private-room authorization.
7. Authorization is then rechecked using existing server-side policy.
8. Only after both authentication/session and authorization checks succeed is the turn's Agent trace started.

Conceptually:

```text
WebSocket message
   -> revalidate OIDC server-side session
      -> invalid -> deny / security event / stop
      -> valid
          -> current room/project/private-room authorization
             -> denied -> stop
             -> allowed
                 -> create TurnContext
                 -> create fresh Agent trace
```

### 4.2 Connection state

A future implementation may extend `WebConnectionContext` or the Web auth binding with a non-exported server-side session-validation reference.

That reference:

- is authentication state, not observability state;
- must never become a span attribute, metric label, baggage value, resource attribute, or trace correlation key;
- must not be accepted from ordinary message JSON;
- must not be replaced by `trace_id` or `correlation_id`.

### 4.3 Other authentication modes

OIDC specifically requires server-side session revalidation. Other identity modes may have different liveness semantics.

A shared Web identity boundary should support authentication-mode-specific revalidation without teaching the OTel package how to authenticate users.

OTel observes the result only.

## 5. Authorization remains server-controlled

The following are authoritative only when resolved by UAG's server-side identity/access components:

```text
principal
private-room owner
room membership
room role
project membership
project role
room -> project binding
directory/group policy
server-bound project
global administrator state
```

An inbound `traceparent`, `tracestate`, baggage item, custom header, span field, browser field, or message JSON field must never grant or widen access.

Current delivery/broadcast authorization checks remain authoritative even if an earlier span recorded `allowed`.

## 6. Browser trace-context trust policy

### 6.1 Default policy: reject/detach

A browser can forge W3C `traceparent` and `tracestate`.

Therefore the first OTel-enabled Web release must enforce:

```text
untrusted browser request / connection
     -> reject or detach inbound OTel parent context
     -> perform session revalidation and authorization
     -> create a fresh trusted UAG turn/Agent trace
```

This is a **Phase-1 requirement**, not something deferred until later A2A/distributed tracing work.

If ASGI/HTTP auto-instrumentation is used, UAG must ensure untrusted browser context is detached before an application/Agent trace can inherit that parent.

### 6.2 Trusted ingress later

A later deployment may explicitly trust trace propagation from controlled reverse proxies or internal services.

Such trust must be opt-in and based on server/operator configuration, not arbitrary browser input.

Trusted trace propagation is still observability metadata; it never supplies identity or authorization.

### 6.3 Baggage restrictions

Do not propagate sensitive UAG identity/access data in OTel baggage.

Forbidden examples:

```text
principal_id
subject
email
groups
session token
room membership
project role
OAuth/OIDC token
```

## 7. OIDC authentication tracing

Possible internal spans/events:

```text
uag.auth.oidc.login
uag.auth.oidc.callback
uag.auth.oidc.session.create
uag.auth.oidc.session.revalidate
uag.auth.oidc.logout
```

The login/callback trace is separate from later Agent task traces. The fact that operations belong to the same browser session does not make them parent/child traces.

## 8. Secret and identity privacy

Never export as OTel span attributes, events, logs, metrics, baggage, or resource attributes:

```text
authorization code
access token
refresh token
ID token
session cookie
server-side session token
hash of session token
client secret
PKCE verifier
state
nonce
raw Authorization header
raw Cookie header
raw token claims
```

Default remote telemetry also excludes raw:

```text
principal_id
OIDC subject
display_name
email-like identifier
group name
group ID
```

Safe low-cardinality result metadata may include normalized values such as:

```text
uag.auth.authenticated = true|false
uag.auth.kind = oidc|local|oauth|trusted_proxy|windows_ad|token|external
uag.authz.outcome = allowed|denied
uag.authz.scope = room|project|private_room|global_admin|none
uag.authz.role = viewer|editor|admin|member
uag.room.private = true|false
uag.project.bound = true|false
```

Role values are emitted only after server-side resolution.

## 9. Room/project/owner isolation

Ownership and membership are authorization state.

Prefer result metadata such as:

```text
uag.room.private = true
uag.authz.outcome = allowed
uag.authz.role = admin
```

over exporting an owner's raw identifier.

`room_id` and `project_id`:

- are never metric dimensions;
- are not process-level resource attributes in a multi-user server;
- are omitted or pseudonymized in remote traces by default;
- may remain in existing local UAG logs according to local logging policy.

A shared-room member does not automatically gain access to the external trace backend.

Direct Jaeger/Grafana/vendor access is operator/admin capability by default. If UAG later exposes traces to ordinary Web users, UAG must proxy the query and re-check current room/project authorization on every query.

Possession of a trace ID is never authorization.

## 10. Optional pseudonymous correlation

If operators later need cross-trace principal/project/room correlation, use server-keyed HMAC pseudonyms rather than raw IDs or plain hashes.

Requirements:

- disabled by default;
- trace-only by default;
- never metric dimensions;
- key rotation supported;
- scoped to intended administrative domain;
- never derived from OIDC session tokens.

## 11. OIDC session-store evolution

Current OIDC sessions may be process-local, but observability must not depend on that storage choice.

Rules:

- `trace_id` is not an OIDC session key;
- `correlation_id` is not an OIDC session key;
- one OIDC session may produce many independent Agent traces;
- session storage may later become durable/shared without changing the trace model;
- session revocation invalidates future access, not historical trace records.

For multi-instance UAG, OTel may aggregate service instances while authentication session replication remains a separate subsystem.

## 12. Multi-tenant / multi-project evolution

If a tenant/organization abstraction is added later:

- trusted server-side policy determines tenant scope;
- unverified browser/JWT fields do not select telemetry routing;
- raw tenant IDs are not metric dimensions by default;
- a process serving multiple tenants does not set one tenant as a process-level resource;
- per-tenant exporter routing, if implemented, fails closed rather than falling into another tenant backend.

## 13. Content capture

`UAGENT_OTEL_CAPTURE_CONTENT` is operator/deployment policy, not a browser/header/query/message option.

Default remains OFF.

Even when enabled by an administrator, secret redaction occurs before OTel exporters receive data.

Shared rooms require extra caution because a model call may contain context derived from multiple authorized sources.

## 14. Metrics

Authentication/authorization metrics may include low-cardinality dimensions such as:

```text
authn_kind
operation
outcome
normalized error class
normalized role
```

Never use:

```text
principal_id
subject
issuer URL
room_id
project_id
session_id
group name
trace_id
```

as metric dimensions.

## 15. Structured events and audit

Existing UAG security/auth events remain useful independently from OTel and may be correlated with active:

```text
correlation_id
trace_id
span_id
```

Security/audit logging must not depend on OTel sampling.

Possible future event families:

```text
auth.oidc.started
auth.oidc.completed
auth.oidc.failed
auth.session.created
auth.session.revalidated
auth.session.revalidation_failed
auth.session.revoked
authz.room.allowed
authz.room.denied
authz.project.allowed
authz.project.denied
```

Payloads remain secret-minimized.

## 16. Trace hierarchy examples

### 16.1 Successful OIDC WebSocket turn

```text
web.message
  -> auth.session.revalidate [valid]
  -> authz.room [allowed]
  -> authz.project [allowed]
  -> invoke_agent uag
       -> uag.context.build
       -> chat <model>
       -> execute_tool <tool>
```

### 16.2 Session revoked after connection acceptance

```text
WebSocket connection accepted earlier

# later turn
web.message
  -> auth.session.revalidate [revoked]
  -> deny
```

No Agent/LLM/Tool span follows the denial.

### 16.3 Authorization denied

```text
web.message
  -> auth.session.revalidate [valid]
  -> authz.room [denied]
```

### 16.4 OIDC login followed later by Agent work

```text
HTTP /auth/oidc/login
  -> uag.auth.oidc.login

HTTP /auth/oidc/callback
  -> uag.auth.oidc.callback
  -> uag.auth.oidc.session.create

# later independent trace
web.message
  -> session revalidate
  -> authorization
  -> invoke_agent uag
```

## 17. Failure behavior

Observability failure never changes authentication/authorization results.

```text
Collector unavailable
    -> normal auth/session/authz still runs
    -> Agent continues if authorized

OTel auto-install fails
    -> OTel backend becomes no-op
    -> normal auth/session/authz still runs

Trace serialization fails
    -> do not weaken auth checks
    -> do not retry the user operation merely for telemetry
```

Conversely, telemetry unavailability never converts an authentication/authorization denial into success.

## 18. Retention

External trace retention is independent from UAG room/session/Memory retention.

Therefore:

- expiring a private room does not automatically delete exported traces;
- revoking an OIDC session does not automatically delete historical traces;
- deleting Memory does not automatically delete backend telemetry;
- minimized direct identifiers reduce privacy impact;
- enterprise deployments define backend retention separately.

## 19. Implementation boundaries

Relevant existing components include:

```text
runtime/identity_context.py
web_impl/connection_identity.py
auth/oidc_sessions.py
auth/oidc_verifier.py
auth/oidc_callback.py
runtime/room_access.py
runtime/project_access.py
```

Implementation rules:

- authentication/session revalidation stays in auth/Web identity layers;
- room/project authorization stays in access-policy layers;
- observability helpers receive only safe outcomes/metadata;
- OTel context is never passed into policy APIs as a decision input;
- authentication secrets never enter OTel helper payloads.

## 20. Rollout requirements

### Phase 1

Initial Web tracing must include:

- per-turn fresh Agent trace roots;
- server-side OIDC session revalidation on every WebSocket turn;
- rejection/detachment of untrusted browser inbound trace context;
- current room/project/private-room authorization before Agent execution;
- no raw identity/session/content export.

### Later phases

Later work may add:

- trusted reverse-proxy/internal trace propagation;
- multi-instance authentication-session storage;
- tenant-aware exporter routing;
- pseudonymous identity/scope correlation;
- user-visible trace proxy guarded by UAG authorization.

None of those later features may weaken Phase-1 isolation.

## 21. Testing requirements

### 21.1 Multi-user isolation

Verify:

- user A and B turns create separate root Agent traces;
- shared room does not produce a cross-user long-lived trace;
- WebSocket connection span is not reused as Agent root for all turns;
- authorization denial creates no downstream LLM/tool spans.

### 21.2 Live OIDC-session tests

Verify:

- accepted WebSocket + valid session -> turn allowed;
- session expires after connection acceptance -> next turn denied;
- session explicitly revoked after connection acceptance -> next turn denied;
- authentication configuration fingerprint changes -> stale session denied;
- cached `IdentityContext` alone cannot bypass revalidation;
- session revalidation reference/value is absent from telemetry.

### 21.3 Inbound trace spoofing

Verify that forged browser `traceparent` / `tracestate`:

- is detached/rejected in initial Web tracing;
- cannot cause one user's Agent trace to join another trace;
- cannot alter `correlation_id` semantics;
- cannot select room/project scope;
- cannot affect authorization.

### 21.4 Privacy

Verify absence of codes, state, nonce, PKCE verifier, ID/access/refresh tokens, session cookie/token, Authorization/Cookie headers, raw claims, principal/subject/group values from remote OTel output by default.

### 21.5 Revocation and policy

Verify room/project/private-room membership and role changes still take effect on established connections independently from trace state.

## 22. Acceptance criteria

Web/OIDC OTel integration is acceptable only when:

1. Each Web user turn has an isolated logical Agent trace.
2. Shared rooms/WebSockets do not merge principals into one Agent trace.
3. Authentication/authorization remain server-controlled and independent from trace context.
4. Every OIDC WebSocket turn revalidates the authoritative server-side session before trusted turn creation.
5. Session expiration/revocation/configuration change after connection acceptance denies the next turn.
6. Raw OIDC/session secrets and raw claims are never exported.
7. Raw principal IDs, subjects, display names, and groups are not exported by default.
8. Room/project/owner identifiers are not metric dimensions.
9. Browser-provided inbound trace context is rejected/detached by default in the initial OTel Web phase.
10. Current room/project/private-room authorization is revalidated after session validation.
11. Trace IDs/baggage/headers never grant access.
12. Normal users do not automatically gain direct trace-backend access.
13. OTel failure does not change authentication/authorization behavior.
14. OTel dependency installation remains process-level and not user/room-specific.
15. Future multi-instance/tenant features can be added without changing the per-turn trust model.

## 23. Fixed design decisions

- Agent traces are per turn/task, not per WebSocket or room.
- OIDC session liveness is revalidated per WebSocket turn.
- A cached `IdentityContext` is not sufficient evidence of live OIDC session validity.
- Authentication traces are separate from later Agent traces.
- OTel trace context is never an authorization credential.
- Browser-provided inbound trace context is rejected/detached by default from Phase 1.
- Trusted inbound propagation, if added, requires explicit operator configuration.
- OIDC/session secrets and raw identity claims are excluded from telemetry.
- Ownership is authorization state; raw owner IDs are not exported by default.
- Shared-room membership does not imply trace-backend access.
- `UAGENT_OTEL_CAPTURE_CONTENT` is operator policy, not user input.
- OTel auto-install is process-level and uses existing `UAGENT_AUTO_INSTALL` policy.
