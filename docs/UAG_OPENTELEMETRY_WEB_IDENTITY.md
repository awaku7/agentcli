# UAG OpenTelemetry Web Multi-User / OIDC Design

Status: Design only  
Parent design: `docs/UAG_OPENTELEMETRY_DESIGN.md`  
Scope: Web multi-user execution, OIDC, room/project authorization, trace isolation, privacy, and observability access control  
Non-goal: this document does not implement authentication or OpenTelemetry.

## 1. Purpose

OpenTelemetry for UAG must work correctly in the Web deployment where multiple authenticated users can share one UAG process, rooms can be private or shared, rooms can be bound to projects, and browser identities can be established through OIDC.

The observability design must preserve the existing UAG trust model:

```text
Authentication
    -> IdentityContext
    -> Web connection authorization
    -> TurnContext
    -> Room / Project authorization
    -> Agent execution
    -> Observability
```

The ordering is intentional:

> OpenTelemetry observes an authorization decision; it never participates in authorization.

Trace context, span attributes, correlation IDs, exporter configuration, and observability backend data are never accepted as proof of identity, room membership, project membership, ownership, or role.

## 2. Existing identity and authorization model

UAG already separates identity from turn-local execution.

`IdentityContext` contains normalized authenticated-principal information such as:

```text
principal_id
authenticated
authn_kind
issuer
subject
display_name
groups
```

`TurnContext` contains the immutable actor/workspace/session boundary for one turn:

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

Web connections capture a trusted authenticated identity when the connection is accepted. Message payloads must not be allowed to replace that identity.

Room/project access is revalidated against server-side policy before protected operations and before delivery to room recipients. OpenTelemetry integration must preserve those boundaries rather than caching authorization state in trace metadata.

## 3. Multi-user observability principles

### 3.1 One user turn, one logical Agent trace

A long-lived Web process or shared room is not a single trace.

Recommended model:

```text
Web process
  |
  +-- user A / turn 1 -> trace A1
  +-- user B / turn 1 -> trace B1
  +-- user A / turn 2 -> trace A2
  +-- user C / turn 1 -> trace C1
```

A shared room may contain turns from many principals. Those turns remain separate traces.

Do not build this model:

```text
one room
  -> one trace lasting hours/days
      -> every user's turns
```

Reasons:

- it mixes security principals in one trace tree;
- it creates unbounded traces;
- it makes retention and sampling difficult;
- it creates accidental information disclosure between users;
- it makes authorization changes during a room lifetime difficult to represent correctly.

### 3.2 WebSocket handshake is not the Agent root

A WebSocket connection may outlive many user turns.

The initial handshake/server span may be useful for transport diagnostics, but Agent task spans must be created per turn/message after current authorization is established.

Conceptually:

```text
WebSocket connection
    |
    +-- turn 1 authorization -> invoke_agent trace 1
    +-- turn 2 authorization -> invoke_agent trace 2
    +-- turn 3 authorization -> invoke_agent trace 3
```

Do not keep one active OTel span in a ContextVar for the entire WebSocket lifetime and reuse it for every turn.

### 3.3 Authorization is server-controlled

The following are authoritative only when resolved by UAG's existing server-side identity/access components:

```text
principal
room membership
private-room ownership
project membership
project role
room role
room -> project binding
directory/group policy
server-bound project
```

An inbound `traceparent`, `tracestate`, baggage item, custom header, span attribute, browser field, or message JSON field must never grant or widen access.

## 4. OIDC authentication tracing

OIDC authentication is observability-relevant, but authentication telemetry must be deliberately minimal.

### 4.1 Suggested logical operations

Possible internal spans/events:

```text
uag.auth.oidc.login
uag.auth.oidc.callback
uag.auth.oidc.session.create
uag.auth.oidc.logout
```

Normal HTTP server spans may exist around these operations.

The authentication flow is separate from the later Agent task trace. An OIDC callback must not become the permanent parent of future user-turn traces.

### 4.2 Never export OIDC secrets or bearer material

The following must never be exported as span attributes, events, logs, metrics, baggage, or resource attributes:

```text
authorization code
access token
refresh token
ID token
session cookie
server-side session token
hash of the session token
client secret
PKCE verifier
state value
nonce value
raw Authorization header
raw Cookie header
raw token claims
```

The current server-side OIDC session token is deliberately opaque. Its value and storage key are not observability identifiers.

### 4.3 Identity fields

Default remote telemetry must not include raw:

```text
principal_id
OIDC subject
display_name
email-like identifiers
group names
group IDs
```

Safe low-cardinality identity metadata can include:

```text
uag.auth.authenticated = true|false
uag.auth.kind = oidc|local|oauth|trusted_proxy|windows_ad|token|external
uag.authz.outcome = allowed|denied
uag.authz.scope = room|project|private_room|global_admin|none
uag.authz.role = viewer|editor|admin|member
uag.room.private = true|false
uag.project.bound = true|false
```

Role values are emitted only after server-side policy resolution.

### 4.4 Optional pseudonymous identity correlation

If operators later require trace correlation by principal, use a server-controlled pseudonymous identifier rather than raw `principal_id` or OIDC `subject`.

Recommended properties:

- HMAC-based, not plain hash;
- keyed by a server/workspace observability key;
- stable only within the intended administrative domain;
- trace-only by default, never a metric dimension;
- rotatable;
- not reversible without the server key;
- disabled by default unless there is a demonstrated operational need.

Conceptual field:

```text
uag.identity.pseudonymous_id
```

Do not derive pseudonyms from the OIDC session token.

## 5. Room, project, owner, and role isolation

### 5.1 Ownership remains authorization data

Private-room owner and project/room membership are authorization state.

OpenTelemetry may record the result of authorization, but should not normally export the raw owner principal ID.

For example:

```text
uag.room.private = true
uag.authz.outcome = allowed
uag.authz.role = admin
```

is preferable to:

```text
uag.room.owner = alice@example.com
```

### 5.2 Room/project IDs are high-cardinality and potentially sensitive

`room_id` and `project_id` may reveal names or workspace structure. Therefore:

- never use them as metric dimensions;
- do not put them in OTel resource attributes for a process serving multiple users/projects;
- remote trace export should omit or pseudonymize them by default;
- local structured logs may retain existing IDs according to UAG's local logging/privacy policy;
- if a trace UI later needs room/project lookup, prefer a server-side mapping or pseudonymous scope ID.

Possible trace-only pseudonyms:

```text
uag.room.scope_id
uag.project.scope_id
```

### 5.3 Shared room does not imply shared trace visibility

A user who can read a shared room does not automatically receive permission to query the external OTel backend for all traces involving that room.

Observability authorization is a separate control plane.

Default recommendation:

> Direct Jaeger/Grafana/vendor trace access is an operator/admin capability, not an ordinary UAG room-member capability.

If UAG later exposes trace views to normal Web users, UAG must proxy/query the backend and enforce current room/project authorization before displaying any trace metadata.

Do not expose a trace URL containing a trace ID as an authorization mechanism.

## 6. Authentication and authorization revalidation

Web authorization can change while a connection is alive:

- OIDC session expires or is revoked;
- authentication configuration changes;
- room membership is revoked;
- project membership/role changes;
- directory group policy changes;
- room/project binding changes;
- a private room expires;
- global-admin configuration changes.

Therefore:

1. Observability context must not cache authorization as an authority.
2. Each turn uses the current trusted `TurnContext` created after current access checks.
3. Delivery/broadcast checks remain authoritative even if the producing span says `allowed`.
4. A previously valid trace or span never acts as a capability for later work.
5. Authorization revision/fingerprint data, if observed, is diagnostic only.

A denied operation may record:

```text
uag.authz.outcome = denied
error.type = authorization_denied
```

but should avoid including details that reveal membership structure to an unauthorized caller.

## 7. Trace Context trust policy for Web

### 7.1 Browser-supplied trace context is untrusted by default

A public browser can forge W3C `traceparent`/`tracestate` headers. Accepting those blindly can make one user appear as a child of another tenant's trace or poison operator diagnostics.

Default Web policy:

```text
untrusted browser request
    -> do not trust arbitrary inbound parent trace
    -> create new server/turn trace at UAG trust boundary
```

Trusted reverse proxies or controlled internal clients may be allowed to propagate inbound trace context through an explicit deployment policy.

### 7.2 OIDC provider trace context is not user-task identity

Even if an IdP or reverse proxy provides trace headers during OIDC redirects/callbacks, those headers are transport observability only.

They must not:

- identify the UAG user;
- bind a later Agent turn;
- select a room/project;
- grant permissions;
- be copied into the OIDC browser session as identity state.

### 7.3 Baggage restrictions

Do not propagate sensitive UAG identity or access state in OTel baggage.

Forbidden baggage examples:

```text
principal_id
subject
email
groups
session token
room membership
project role
OAuth/OIDC tokens
```

Baggage crosses process boundaries and is often forwarded farther than expected.

## 8. OIDC session-store considerations

The current OIDC session store is server-side and process-local. Observability must not depend on the implementation being process-local or durable.

Rules:

- `trace_id` is not an OIDC session key;
- OIDC session token is not a trace correlation ID;
- an OIDC session may create many independent Agent traces;
- telemetry export continues to work if session storage later becomes durable/shared;
- authentication configuration fingerprint/revision is not a user identity;
- session revocation invalidates access, not historical trace data.

In a future multi-instance Web deployment, OTel naturally aggregates spans across instances using service/resource metadata while authentication-session replication remains a separate subsystem.

Useful resource metadata can include standard fields such as:

```text
service.name = uag
service.instance.id = <instance>
deployment.environment.name = <environment>
```

Do not encode a user/project/room as a service resource attribute when one UAG instance serves many users.

## 9. Multi-tenant / multi-project deployment

UAG currently has explicit principal, room, project, and authorization boundaries. A future tenant/organization abstraction may sit above them.

Observability must remain compatible with that extension.

If a `tenant_id` is introduced later:

- it must come from trusted server-side identity/project resolution;
- it must not be inferred from unverified JWT/browser fields;
- raw tenant IDs should not become metric dimensions by default;
- a multi-tenant UAG process must not set one tenant ID as a process-level resource attribute;
- per-tenant exporter routing, if added, must be selected by trusted server-side policy;
- failure to resolve tenant routing must fail closed for telemetry routing, not reroute data to another tenant.

The same principle applies today to project/room routing.

## 10. Trace export routing and data isolation

Three deployment models are possible.

### Model A: operator-wide backend

```text
all UAG Web users
      -> UAG
      -> one operator-controlled OTel backend
```

This is the simplest initial model. The backend is restricted to trusted operators/admins.

### Model B: project/tenant-separated exporters

```text
trusted project/tenant context
      -> exporter router
         -> backend A
         -> backend B
```

This may be useful for enterprise isolation but is not required for the first implementation.

If implemented, routing must use server-authoritative context only and must never use arbitrary client baggage/headers.

### Model C: user-visible observability through UAG

```text
browser
  -> UAG authorization
  -> UAG trace query proxy
  -> OTel backend
```

If users can inspect traces, this is preferred over exposing the raw backend. UAG must re-check current room/project rights on every trace query.

## 11. Content capture in multi-user Web

`UAGENT_OTEL_CAPTURE_CONTENT` is an operator/deployment policy, not a per-message browser request.

A normal Web user must not be able to enable content capture by sending a message/header/query parameter.

For multi-user servers, the recommended default remains:

```text
UAGENT_OTEL_CAPTURE_CONTENT=0
```

Even when content capture is enabled by an administrator, UAG should continue to redact secrets before the OTel SDK/exporter receives data.

Additional caution is required for shared rooms because one model call may contain context derived from multiple authorized sources.

## 12. Authentication telemetry metrics

Keep metrics low-cardinality.

Possible metrics:

```text
uag.auth.operation.duration
uag.auth.login.count
uag.auth.failure.count
uag.authz.decision.count
uag.authz.denied.count
```

Safe dimensions may include:

```text
authn_kind
operation
outcome
normalized error class
```

Do not use these metric dimensions:

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

## 13. Structured event correlation

Existing UAG structured security/auth events may be correlated to traces with:

```text
correlation_id
trace_id
span_id
```

when a span is active.

However, security events should remain useful even if tracing is disabled or sampled out. Audit/security logging must not depend on OTel sampling.

Suggested event families for future implementation:

```text
auth.oidc.started
auth.oidc.completed
auth.oidc.failed
auth.session.created
auth.session.revoked
authz.room.allowed
authz.room.denied
authz.project.allowed
authz.project.denied
```

Event payloads remain secret-minimized.

## 14. Web / OIDC trace hierarchy examples

### 14.1 Successful shared-room turn

```text
web.message
  -> uag.authz.room
  -> uag.authz.project
  -> invoke_agent uag
       -> uag.context.build
       -> chat <model>
       -> execute_tool <tool>
       -> chat <model>
```

The authorization spans may be omitted if overhead is not justified; in that case the Agent span can carry aggregate authorization outcome metadata derived from the already completed check.

### 14.2 Authorization denied

```text
web.message
  -> uag.authz.room [denied]
```

No Agent/LLM/Tool span is created if execution never starts.

### 14.3 OIDC login followed later by Agent work

```text
HTTP /auth/oidc/login
  -> uag.auth.oidc.login

HTTP /auth/oidc/callback
  -> uag.auth.oidc.callback
  -> uag.auth.oidc.session.create

# later, independent trace
web.message
  -> authorization
  -> invoke_agent uag
```

The login trace and later Agent trace are not parent/child solely because they belong to the same browser session.

### 14.4 Private-room turn

```text
web.message
  -> private-room owner/current-access check
  -> invoke_agent uag
       attributes:
         uag.room.private=true
         uag.authz.outcome=allowed
```

Do not export the owner's raw principal ID by default.

## 15. Failure and privacy behavior

Observability failure must not change authentication or authorization results.

Examples:

```text
Collector unavailable
    -> user remains authenticated/authorized normally
    -> Agent continues

OTel package auto-install fails
    -> OTel backend becomes no-op
    -> OIDC login/room checks continue normally

Trace serialization fails
    -> do not weaken auth checks
    -> do not retry user operation merely to obtain telemetry
```

Conversely, authentication/authorization failure must not be converted into success because telemetry is unavailable.

## 16. Retention and deletion

External trace retention is independent from UAG room/session/Memory retention.

Therefore:

- expiring a private room does not automatically delete already exported traces;
- revoking an OIDC session does not delete historical traces;
- deleting Memory does not automatically delete backend telemetry;
- exported data should minimize direct personal identifiers so retention has lower privacy impact;
- enterprise deployments should set backend retention according to organizational policy.

If UAG later supports user-visible trace export/delete operations, those require an explicit backend lifecycle design and authorization checks.

## 17. Implementation boundary additions

The parent OpenTelemetry design should treat these as required implementation boundaries:

```text
runtime/identity_context.py
web_impl/connection_identity.py
auth/oidc_sessions.py
auth/oidc_verifier.py
auth/oidc_callback.py
runtime/room_access.py
runtime/project_access.py
```

Instrumentation should be shallow and non-invasive:

- observe completed identity resolution;
- observe auth/authz outcomes;
- never move authorization logic into the observability package;
- never pass OTel context into policy APIs as a decision input;
- never expose authentication secrets to OTel helpers.

## 18. Testing additions

### 18.1 Multi-user isolation tests

Verify:

- user A and user B turns create separate root Agent traces;
- a shared room does not create one long-lived cross-user trace;
- private-room owner ID is not exported;
- raw principal/subject/group values are absent by default;
- room/project IDs are absent from metrics;
- authorization denial creates no downstream LLM/tool spans;
- role changes/revocation take effect despite an existing WebSocket connection;
- trace context cannot override room/project authorization.

### 18.2 OIDC privacy tests

Verify absence of:

```text
code
state
nonce
PKCE verifier
ID/access/refresh token
session cookie/session token
Authorization header
Cookie header
raw claims
```

from spans, events, metrics, baggage, and structured OTel export.

### 18.3 Inbound trace spoofing tests

Verify that an untrusted browser-provided `traceparent` cannot:

- become an authorization identity;
- choose project/room scope;
- cause a trace to be joined to another user's trusted trace by default;
- alter UAG `correlation_id` semantics.

### 18.4 Observability access tests

If user-visible trace querying is added later, verify every query against current room/project authorization and verify that possession of a trace ID alone grants no access.

## 19. Acceptance criteria

Web/OIDC OpenTelemetry integration is acceptable when:

1. Each Web user turn has an isolated logical Agent trace.
2. Shared rooms do not merge multiple principals into one long-lived trace.
3. Authentication and authorization remain server-controlled and independent from trace context.
4. Raw OIDC tokens/session tokens/cookies/claims are never exported.
5. Raw principal IDs, OIDC subjects, display names, and groups are not exported by default.
6. Room/project/owner identifiers are not metric dimensions.
7. Authorization is revalidated according to current UAG policy even when a connection already has trace context.
8. OIDC session revocation/configuration changes are not bypassed by existing traces.
9. Browser-supplied trace context is untrusted by default.
10. Normal users do not automatically gain direct access to an operator-wide trace backend.
11. Observability failure cannot change authentication or authorization behavior.
12. OTel dependency auto-install remains process-level and does not vary by user/room.
13. Multi-instance telemetry does not depend on the current process-local OIDC session-store implementation.
14. Future tenant-level routing can be added using trusted server-side scope without changing the core trace model.

## 20. Design decisions

The following are explicit decisions:

- Agent traces are per turn/task, not per WebSocket connection or room.
- Authentication traces are separate from later Agent traces.
- OTel trace context is never an authorization credential.
- Browser-provided trace context is untrusted by default.
- OIDC/session secrets and raw identity claims are excluded from telemetry.
- Ownership is authorization state; owner identifiers are not exported by default.
- Shared-room membership does not imply trace-backend access.
- External observability backends are operator/admin surfaces by default.
- If user-visible trace access is added, UAG must enforce current room/project authorization on every query.
- `UAGENT_OTEL_CAPTURE_CONTENT` is server/operator policy, not user-controlled input.
- OTel auto-install is process-level and uses the existing `UAGENT_AUTO_INSTALL` policy.
- The design remains compatible with future durable OIDC sessions and tenant-aware deployments.
