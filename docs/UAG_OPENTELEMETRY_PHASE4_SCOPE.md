# OpenTelemetry Phase 4 Scope

Status: Design only  
Parent design: `docs/UAG_OPENTELEMETRY_DESIGN.md`  
Prerequisite: Phase 3 complete on `main`  
Scope: optional advanced diagnostics without weakening the Phase 1-3 privacy, identity, authorization, and canonical-span contracts.

## 1. Purpose

Phase 4 adds optional diagnostics for operators that need deeper correlation or provider-level detail.

The core rule remains unchanged:

> UAG owns the observability model. OpenTelemetry is an optional projection/export backend.

Phase 4 must not turn telemetry into a source of truth for identity, authorization, session validity, Memory policy, tool permission, or Agent state.

All Phase 4 features are separately opt-in and disabled by default.

## 2. Phase 4 capabilities

Phase 4 contains four independent capabilities:

1. controlled content capture;
2. pseudonymous principal/room/project correlation;
3. optional provider SDK nested instrumentation;
4. an authorization-aware trace-query proxy.

These features do not need to ship together. Each must preserve normal UAG behavior when disabled or unavailable.

## 3. Rollout order

Recommended implementation order:

### Phase 4A - privacy and policy foundation

- formalize content-capture policy as a master gate plus explicit capture categories;
- add value-level redaction/sanitization before exporter submission;
- add hard size/depth/item caps for captured structured values;
- keep reasoning, authentication/session material, credentials, Memory bodies, retrieval bodies, files, and artifacts excluded;
- add regression tests proving that enabling one category does not enable another.

### Phase 4B - pseudonymous correlation

- add server-keyed HMAC pseudonyms for selected trace-only scope correlation;
- keep pseudonyms out of metrics, baggage, resource attributes, auth decisions, and storage keys;
- support key versioning/rotation;
- keep the raw identifiers local to UAG.

### Phase 4C - provider SDK nested instrumentation

- add explicitly selected provider SDK instrumentation only as nested diagnostics;
- keep the UAG provider-neutral `chat` span canonical;
- do not enable generic HTTP auto-instrumentation as a replacement for UAG logical spans;
- keep SDK prompt/response capture disabled independently of UAG content-capture policy;
- failure or version mismatch must fall back without changing model calls.

### Phase 4D - trace-query proxy

- add a server-side query abstraction for supported trace backends;
- authorize every query using current UAG identity and room/project policy;
- use a local trace-authorization index rather than remote span attributes as proof of scope;
- treat possession of a trace ID as insufficient for access;
- expose operator/admin access first; ordinary-user access is a later sub-slice after authorization tests are complete.

Controlled content capture should be the last feature enabled in production deployments, even if its policy foundation is implemented first.

## 4. Configuration principles

All Phase 4 settings are process/server policy. Browser input, A2A payloads, tool arguments, prompt text, query parameters, cookies, or incoming trace metadata cannot enable them.

Existing product-level OTel activation remains authoritative:

```text
--otel / --no-otel
UAGENT_OTEL_ENABLED
```

Phase 4 options are subordinate to normal OTel activation.

### 4.1 Controlled content capture

`UAGENT_OTEL_CAPTURE_CONTENT` remains the master gate and defaults to OFF.

Phase 4 adds an explicit category allowlist, for example:

```text
UAGENT_OTEL_CAPTURE_CONTENT=1
UAGENT_OTEL_CAPTURE_CATEGORIES=user_input,assistant_output
```

The master gate alone must not mean "capture everything". If capture is enabled but no category is selected, no content is exported.

Initial allowed categories:

```text
user_input
assistant_output
tool_arguments
tool_result
```

Not allowed in the initial Phase 4 implementation, even when content capture is enabled:

```text
reasoning / chain-of-thought
system/developer instructions
OAuth/OIDC/session/authentication material
Authorization/Cookie headers
credentials or credential-store values
Memory bodies
retrieval bodies/queries
Decision Log reasoning
file bodies
artifact bodies
MCP OAuth material
A2A bearer tokens
```

A later design change is required before any of those excluded classes can be captured.

Suggested bounded controls:

```text
UAGENT_OTEL_CAPTURE_MAX_FIELD_CHARS=2048
UAGENT_OTEL_CAPTURE_MAX_SPAN_CHARS=8192
```

Invalid values fail closed to conservative defaults.

### 4.2 Pseudonymous correlation

Suggested controls:

```text
UAGENT_OTEL_PSEUDONYMOUS_CORRELATION=0
UAGENT_OTEL_CORRELATION_KEY_NAME=observability/correlation
UAGENT_OTEL_CORRELATION_KEY_VERSION=v1
```

The key value is resolved from UAG's server-side credential mechanism. Raw HMAC keys are not accepted from browser input and are never exported.

### 4.3 Provider SDK diagnostics

Suggested control:

```text
UAGENT_OTEL_PROVIDER_INSTRUMENTATION=openai,anthropic
```

Missing/empty means OFF. Unknown providers are ignored with a normalized diagnostic event and do not fail startup.

SDK instrumentation is permitted only for explicitly supported/version-tested providers.

### 4.4 Trace-query proxy

Trace-query support is server-controlled and disabled unless a supported backend adapter is configured.

Backend credentials remain server-side and are never sent to browser clients.

## 5. Controlled content capture model

### 5.1 Two-key enablement

A content value is eligible only when both are true:

1. `capture_content` master policy is enabled;
2. the value's semantic category is explicitly allowlisted.

Runtime instrumentation must pass an explicit category. Attribute-name heuristics alone are not sufficient to decide eligibility.

Conceptually:

```text
runtime value
   -> classify semantic category
   -> category allowed?
      -> no: discard
      -> yes
         -> structured/value-level redaction
         -> size/depth/item limits
         -> final attribute/event serialization
         -> existing always-blocked key filter
         -> exporter
```

### 5.2 Attribute-name filtering is not enough

The existing `privacy.py` key-name filter remains a defense-in-depth layer, but Phase 4 must not rely on it as the only secret-control mechanism.

A permitted prompt can itself contain passwords, API keys, source code, personal data, or customer data. No generic redactor can guarantee removal of every secret from arbitrary natural-language text.

Therefore:

- content capture is explicitly documented as exporting potentially sensitive data;
- operator consent is required through process/server configuration;
- captured text is bounded;
- known structured secret fields are removed before serialization;
- always-blocked authentication/identity keys remain blocked after category selection;
- deployments must apply suitable trace-backend retention and access controls.

### 5.3 Structured tool values

For `tool_arguments` and `tool_result`, structured values are recursively sanitized before string serialization.

Rules:

- redact/drop known credential-style keys;
- cap recursion depth;
- cap collection item counts;
- cap each rendered field length;
- cap total captured characters per span;
- do not follow file references or artifact references to fetch bodies;
- do not automatically decode binary/base64 content for telemetry;
- malformed/unserializable values are omitted rather than causing tool failure.

### 5.4 Reasoning is excluded

Private reasoning / chain-of-thought is not a Phase 4 content category.

Provider-specific fields described as reasoning, thinking, analysis, hidden chain, or equivalent remain excluded from remote telemetry even when other content categories are enabled.

High-level outcome metadata may still be exported if it is already part of UAG's safe provider-neutral observability contract.

### 5.5 No content in metrics, baggage, or resources

Captured content may appear only on approved trace spans/events.

It must never become:

- a metric dimension;
- OTel baggage;
- a process resource attribute;
- an authorization input;
- a cache/storage key;
- a trace-routing key.

## 6. Pseudonymous correlation

### 6.1 Purpose

Operators may need to answer questions such as "are repeated failures affecting the same principal/project/room?" without exporting raw identifiers.

Phase 4 may expose trace-only pseudonyms such as:

```text
uag.correlation.principal
uag.correlation.room
uag.correlation.project
```

These are diagnostic labels only.

### 6.2 Construction

Use HMAC-SHA-256 with a server-held secret.

The input is domain-separated so the same raw identifier does not produce the same value across identifier classes:

```text
"uag-otel-pseudo-v1" || deployment_scope || kind || raw_identifier
```

The exported value may use a fixed truncated digest representation, for example 128 bits encoded as lowercase hex or base64url.

Requirements:

- raw identifier never leaves the pseudonymization helper;
- plain SHA hashes are not accepted as a substitute;
- principal/room/project use separate `kind` domains;
- deployment scope prevents accidental cross-deployment linkability;
- key version is low-cardinality metadata and contains no secret;
- changing the key intentionally breaks cross-version correlation unless an operator retains/query-maps both versions.

### 6.3 Rotation

Rotation must be supported without changing authentication or room/project identifiers.

Historical traces retain the old pseudonym. New traces use the new key version.

No migration of historical trace data is required by UAG.

### 6.4 Pseudonyms are not security identities

A pseudonym must never be used to:

- authenticate a user;
- select a `TurnContext`;
- authorize room/project access;
- lookup or mutate Memory;
- address a session;
- restore an Agent task;
- select a credential.

They are also forbidden as metric dimensions in the initial implementation because they are high-cardinality.

## 7. Provider SDK nested instrumentation

### 7.1 Canonical span ownership

UAG's provider-neutral `chat` span remains the canonical LLM operation.

Optional provider SDK instrumentation may create nested spans beneath that boundary:

```text
chat <model>                 # UAG canonical
  +-- provider-sdk ...       # optional diagnostic child
```

It must not replace, rename, suppress, or become the source of truth for the UAG `chat` span.

### 7.2 No duplicate logical spans

If an SDK instrumentor creates a span that semantically duplicates the UAG canonical LLM span, UAG must either:

- configure/suppress that duplicate; or
- reject that instrumentor/version as unsupported.

Phase 3's duplicate-span guarantee remains normative.

Generic HTTP client auto-instrumentation is not enabled globally merely to obtain provider spans.

### 7.3 Content policy separation

Provider SDK instrumentors often have their own content-capture environment variables or defaults.

UAG must not allow those provider/instrumentor settings to bypass UAG's content policy.

For supported instrumentors:

- SDK-level prompt/response capture stays disabled by default;
- UAG Phase 4 content capture remains the sole supported product-level content policy;
- if an instrumentor cannot prevent raw prompt/response export, it is unsupported for Phase 4.

### 7.4 Dependency and failure isolation

Provider instrumentors are optional dependencies.

Rules:

- do not install them merely because core OTel is enabled;
- install only when the corresponding Phase 4 provider is explicitly selected and normal auto-install policy permits;
- version compatibility is explicit and tested;
- import/install/setup failure produces a normalized diagnostic event and leaves the existing provider path operational;
- instrumentation failure never retries or alters the model request.

## 8. Authorization-aware trace-query proxy

### 8.1 Why a proxy is required

Raw access to Jaeger/Grafana/vendor trace backends is an operator/admin surface.

If UAG exposes traces to ordinary Web users, it must mediate the query and re-check current authorization.

A browser-provided trace ID is only a lookup hint, never proof of access.

### 8.2 Local trace-authorization index

UAG must not infer query authorization from exported span attributes or pseudonyms.

Instead, when an authorized Agent trace starts, UAG may record a local metadata-only authorization index such as:

```text
trace_id
created_at
entry_point
room_id        # local only
project_id     # local only
principal_id   # local only when needed for private scope
private_scope
```

This index is UAG-local state, not OTel data.

It contains only identifiers already required for UAG authorization and does not store prompts, responses, tool bodies, Memory bodies, or exporter credentials.

### 8.3 Query authorization flow

For a non-admin Web query:

```text
browser asks for trace_id
   -> authenticate/revalidate current session
   -> lookup local trace authorization record
   -> record missing/expired? deny
   -> re-run current room/project/private-room authorization
   -> denied? deny
   -> allowed
      -> server queries configured trace backend
      -> sanitize supported response fields
      -> return bounded trace view
```

Current policy wins. Historical membership or possession of the original trace is not sufficient if the user no longer has access.

### 8.4 Admin/operator queries

A separately authorized administrator/operator path may query traces outside room/project scope according to existing server-side admin policy.

This authority comes from UAG auth/authz, never OTel attributes or external backend roles supplied by the browser.

### 8.5 Missing local authorization record

For ordinary users, missing local authorization metadata fails closed.

UAG does not fall back to trusting pseudonymous labels, span names, baggage, remote resource attributes, or caller-supplied scope fields.

### 8.6 Backend abstraction

The query proxy should use a small provider-neutral interface such as:

```text
TraceQueryBackend
  get_trace(trace_id)
```

Backend-specific Jaeger/Grafana/vendor code stays behind adapters.

Backend credentials remain server-side. Query failure never changes normal Agent execution.

## 9. Retention and deletion

Phase 4 does not imply that deleting UAG data deletes already exported telemetry.

Operators must understand:

- deleting a room does not automatically erase external traces;
- deleting Memory does not automatically erase content already exported;
- rotating a pseudonym key does not rewrite historical traces;
- trace-query authorization index retention is separate from external trace retention;
- content-capture deployments need explicit backend retention policy.

For ordinary-user trace queries, expiration/removal of the local authorization index causes access to fail closed even if the external backend still retains the trace.

## 10. Multi-user and shared-room rules

Phase 1-3 isolation remains mandatory.

- one user turn remains one logical Agent trace;
- a WebSocket/room is not a long-lived trace root;
- a shared-room trace may contain context derived from multiple authorized sources, so content capture requires particular caution;
- content capture does not grant trace-query access;
- pseudonymous room/project labels do not grant trace-query access;
- trace-query authorization is evaluated independently on every request.

## 11. Failure behavior

Every Phase 4 feature is best-effort and isolated from UAG execution.

Examples:

```text
redactor fails
  -> omit content
  -> continue Agent/tool/model execution

correlation key missing
  -> omit pseudonyms
  -> continue tracing

SDK instrumentor import/version mismatch
  -> disable nested provider instrumentation
  -> continue canonical UAG chat tracing

trace backend unavailable
  -> trace query returns bounded server error
  -> Agent execution remains unaffected
```

A failure must never broaden capture, correlation, or access.

## 12. Audit and diagnostics

Phase 4 configuration changes and query denials may generate existing structured UAG events using safe, low-cardinality metadata.

Useful event families may include:

```text
observability.capture.enabled
observability.capture.redaction_failed
observability.correlation.unavailable
observability.provider_instrumentation.unavailable
observability.trace_query.allowed
observability.trace_query.denied
observability.trace_query.backend_error
```

These events must not include captured content, secrets, raw correlation keys, raw authentication material, or unbounded backend responses.

## 13. Testing requirements

### 13.1 Content capture

Verify:

- OFF remains metadata-only;
- master gate ON with no categories captures nothing;
- each category is independent;
- selecting `user_input` does not capture assistant/tool/system/reasoning fields;
- selecting tool categories recursively removes known credential fields;
- always-blocked identity/auth/session keys remain blocked;
- reasoning remains excluded;
- length/depth/item caps are enforced;
- malformed/unserializable values do not fail runtime execution;
- content never becomes metric dimensions, baggage, or resource attributes.

### 13.2 Pseudonymous correlation

Verify:

- feature OFF emits no pseudonyms;
- identical raw identifier + same key/scope/kind is stable;
- different kinds produce different pseudonyms;
- different deployment scopes produce different pseudonyms;
- key rotation changes pseudonyms;
- raw identifier and key never appear in exported spans/events;
- pseudonyms are absent from metrics and baggage;
- pseudonyms cannot affect auth/authz/Memory behavior.

### 13.3 Provider SDK instrumentation

Verify:

- OFF installs/initializes no SDK instrumentor;
- selected provider instrumentation remains nested under canonical `chat`;
- no duplicate canonical LLM span is introduced;
- UAG content policy cannot be bypassed through SDK instrumentation;
- provider/instrumentor failure does not change model results;
- unsupported versions fail closed to canonical UAG tracing only.

### 13.4 Trace-query proxy

Verify:

- anonymous/expired/revoked sessions are denied;
- caller-supplied trace ID or pseudonym alone cannot authorize access;
- missing local authorization record fails closed for ordinary users;
- current room/project/private-room access is revalidated for every query;
- revoked membership denies historical trace access through UAG proxy;
- admin path requires existing UAG admin authorization;
- backend credentials never reach the client;
- backend outage does not affect Agent execution;
- response is bounded and sanitized.

### 13.5 Regression gates

Phase 1-3 tests remain green, including:

- default OTel OFF behavior;
- Web/OIDC session revalidation and authorization isolation;
- A2A/Sub-Agent/MCP trusted propagation;
- trusted reverse-proxy ingress;
- Phase 3 multi-instance parentage and duplicate-span checks;
- Python 3.11 / 3.13 / 3.14 compatibility;
- Ruff, Black, I18N, tool catalog validation, and full pytest.

## 14. Acceptance criteria

Phase 4 is complete only when all shipped capabilities satisfy these rules:

1. Every Phase 4 feature is disabled by default and independently opt-in.
2. Phase 1-3 canonical spans and trust boundaries remain authoritative.
3. Content capture requires both a master gate and explicit semantic categories.
4. Reasoning/authentication/session/credential content is not captured by the initial Phase 4 implementation.
5. Structured captured values pass through value-level redaction and hard bounds before export.
6. Pseudonymous correlation uses server-keyed HMAC with domain separation and key rotation.
7. Pseudonyms never become authentication, authorization, Memory, session, metric, baggage, or resource keys.
8. Provider SDK spans are optional nested diagnostics and never replace UAG canonical `chat` spans.
9. Provider instrumentation cannot bypass UAG content policy or introduce duplicate canonical logical spans.
10. User-visible trace queries are authorized by current UAG policy using local authorization metadata, not remote telemetry fields.
11. Possession of a trace ID or pseudonym never grants trace access.
12. Missing query authorization metadata fails closed for ordinary users.
13. Phase 4 failure never changes Agent, model, tool, Memory, authentication, or authorization behavior.
14. Phase 1-3 regression suites and normal CI remain green.

## 15. Out of scope

The initial Phase 4 implementation does not include:

- reasoning/chain-of-thought export;
- automatic capture of system/developer instructions;
- Memory/retrieval/file/artifact body export;
- using telemetry as an audit-log replacement;
- using pseudonyms as security identities;
- generic global HTTP auto-instrumentation;
- automatic per-tenant exporter routing;
- direct browser credentials for external trace backends;
- unrestricted end-user trace search across traces without a local authorization record.

Any of these requires a separate design review.
