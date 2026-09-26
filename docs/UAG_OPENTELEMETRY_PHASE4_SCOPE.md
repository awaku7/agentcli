# OpenTelemetry Phase 4 Scope

Status: Design only  
Parent design: `docs/UAG_OPENTELEMETRY_DESIGN.md`  
Prerequisite: Phase 3 complete on `main`  
Scope: optional advanced diagnostics without weakening Phase 1-3 privacy, identity, authorization, propagation, or canonical-span contracts.

## 1. Purpose

Phase 4 adds four independent, default-OFF capabilities:

1. controlled content capture;
2. pseudonymous principal/room/project correlation;
3. optional provider SDK nested instrumentation;
4. authorization-aware trace-query proxying.

The core rule remains:

> UAG owns the observability model. OpenTelemetry is an optional projection/export backend.

Telemetry is never a source of truth for identity, authorization, session validity, Memory policy, tool permission, Agent state, routing, credential selection, or scope selection.

## 2. Normative document ownership

Phase 4 intentionally avoids defining the same exact contract in several places. Each topic below has one normative owner:

| Topic | Normative owner |
| --- | --- |
| overall capability boundaries, rollout, provider instrumentation, trace-authorization architecture | this scope document |
| configuration precedence/parsing, deployment-scope validation, field provenance, `uag.trace_view.v1` field set/ID/status rules, trace-query resource limits | `docs/UAG_OPENTELEMETRY_PHASE4_SECURITY_CONTRACT.md` |
| span-name enum, content carrier, candidate/structure limits, redaction marker behavior, canonical content renderer, per-span character ledger | `docs/UAG_OPENTELEMETRY_PHASE4_TRACE_NAME_AND_TRAVERSAL_CONTRACT.md` |
| primitive scalar admission and ordinary-user trace timing normalization | `docs/UAG_OPENTELEMETRY_PHASE4_SCALAR_AND_TIMING_CONTRACT.md` |
| pseudonym HMAC framing/kind/raw-ID bounds/output representation/key-version grammar and association | `docs/UAG_OPENTELEMETRY_PHASE4_PSEUDONYM_OUTPUT_CONTRACT.md` |

A summary in this parent must not redefine or weaken an exact grammar, limit, renderer, ordering rule, or field type owned by a companion. If text conflicts, the topic owner is normative and the conflict is a documentation defect to fix, not an implementation choice.

## 3. Non-negotiable Phase 1-3 invariants

Phase 4 preserves all earlier contracts:

- OTel remains opt-in;
- UAG canonical Agent/LLM/Tool spans remain authoritative;
- one Web user turn remains one logical Agent trace;
- browser trace context remains untrusted unless Phase 3 trusted-ingress policy explicitly accepts it;
- A2A/MCP trace propagation never supplies identity/authorization;
- OIDC live-session and room/project/private-room authorization remain server-authoritative;
- trace IDs, span IDs, pseudonyms, key versions, baggage, backend fields, and span/resource attributes never authorize access;
- content, identity, and secrets remain absent from metrics, baggage, and process resource attributes;
- observability failure never changes Agent/model/tool behavior;
- privacy/authorization uncertainty fails closed for telemetry rather than broadening capture/access;
- Phase 3 duplicate-span and canonical-span guarantees remain normative.

## 4. Rollout order

### Phase 4A - privacy and content-policy foundation

Implement first, but keep content capture OFF by default:

- shared settings/CLI resolution;
- closed semantic categories;
- trusted typed provenance and hard-denied provenance;
- bounded candidate/structure/scalar processing;
- deterministic secret handling;
- one canonical UAG-owned content carrier/renderer;
- cumulative per-span content budget;
- regression tests proving forbidden sources cannot become eligible through tool/user composites.

### Phase 4B - pseudonymous correlation

Then add:

- dedicated server-held correlation key;
- stable validated deployment scope;
- canonical HMAC domain framing;
- fixed pseudonym output representation;
- same-span key-version metadata;
- strict prohibition on security/storage use of pseudonyms.

### Phase 4C - provider SDK diagnostics

Then add selected provider SDK child instrumentation:

- explicitly selected UAG logical provider IDs only;
- selected-call/client scoping rather than SDK-package-wide trust;
- UAG canonical `chat` span remains source of truth;
- no duplicate logical LLM operation;
- provider-native prompt/response capture remains disabled in the initial release;
- unsupported/global-leaking instrumentors fail closed to disabled without changing model behavior.

### Phase 4D - trace-query proxy

Finally add:

- provider-neutral bounded backend adapter;
- local trace-authorization index;
- current auth/authz revalidation on every query;
- per-local-segment/span ownership filtering;
- closed ordinary-user metadata-only response schema;
- no ordinary-user raw-backend access.

Controlled content should be the last capability enabled in production even though its policy foundation is implemented first.

## 5. Configuration principles

All Phase 4 settings are process/server policy. Browser/WebSocket/A2A/MCP/tool/provider/query/cookie/header/trace/baggage data cannot enable or alter them.

Core activation remains authoritative:

```text
--otel / --no-otel
UAGENT_OTEL_ENABLED
```

Phase 4 configuration precedence, CLI forms, CSV parsing, capture bounds, provider selector parsing, deployment-scope validation, and failure semantics are owned by the security contract.

Important defaults:

- every Phase 4 capability is OFF by default;
- content master ON with an empty category set captures nothing;
- invalid controlled-content configuration disables controlled content rather than broadening it;
- invalid pseudonym configuration disables pseudonyms rather than core tracing;
- invalid/unknown provider instrumentation selectors never instrument unselected providers.

## 6. Phase 4A controlled content capture

### 6.1 Closed semantic categories

The initial categories are exactly:

```text
user_input
assistant_output
tool_arguments
tool_result
```

They express logical content role only; they never override provenance/security restrictions.

### 6.2 Always excluded in initial Phase 4

Even when content capture is enabled, the initial release does not capture:

```text
reasoning / chain-of-thought / thinking / hidden analysis
system/developer instructions
OAuth/OIDC/session/authentication material
Authorization/Cookie headers
credential-store/provider credentials
Memory bodies
retrieval bodies/queries
Decision Log reasoning
file bodies
artifact bodies
MCP OAuth/token material
A2A bearer tokens
opaque security-sensitive structures
```

A later reviewed design is required before any excluded class becomes eligible.

### 6.3 Exact processing order

The processing order must match the traversal/rendering and scalar contracts. The parent ordering is therefore:

```text
trusted candidate record
  -> per-span candidate-count admission
  -> root forbidden-provenance gate
  -> content master gate
  -> semantic-category gate
  -> root source/category gate
  -> approved canonical-span/content-carrier gate
  -> exact supported root type/shape gate
  -> bounded node/depth/width/cycle checks
  -> bounded primitive scalar preflight
  -> bounded deterministic child traversal with child-provenance checks
  -> value/key secret handling
  -> post-redaction field bound
  -> exact canonical content rendering
  -> shared per-span content ledger
  -> emit whole content event or omit whole candidate
```

This explicitly supersedes the older ambiguous sequence that placed redaction before structural bounds. **No value-level secret scan is allowed before the implementation has established that the relevant structure/scalar is bounded.**

### 6.4 Closed content carrier

Initial controlled content uses only the UAG-owned `uag.content` span event schema defined by the traversal/rendering contract. Arbitrary user/tool/provider keys do not become telemetry attribute/event names.

The event carries only:

- trusted semantic category;
- exact canonical rendered content string;
- trusted creation ordinal.

The exact renderer, fixed redaction marker, candidate cap, accepted container/key/scalar shapes, structural limits, and cumulative span ledger are defined only in the traversal/rendering and scalar contracts.

### 6.5 Provenance is stronger than category

Every content candidate has trusted UAG-owned provenance. Body-capable composites require field/node provenance. The security contract owns the closed provenance vocabulary and hard-denied classes.

Examples:

- a file-reading tool returning inline file text remains forbidden even under `tool_result`;
- file-writing `content` remains forbidden under `tool_arguments`;
- attachment data/base64/body values remain forbidden under `user_input`;
- artifact/Memory/retrieval/auth/session/credential bodies remain forbidden when nested in otherwise eligible structures;
- payload JSON cannot self-declare safer provenance.

### 6.6 Secret handling is defense in depth

After bounded traversal/scalar preflight, eligible natural-language/tool values pass the reviewed value-level secret handling rules.

High-confidence Authorization/JWT/private-key/credential-URI/secret-wrapper forms must not leave raw secrets in exported content. Redaction failure or ambiguity omits the candidate; it never fails the user operation.

Exact marker/key behavior belongs to the traversal/rendering contract.

### 6.7 No content in non-trace channels

Controlled content is forbidden from:

- metric dimensions;
- OTel baggage;
- process resource attributes;
- authorization/identity state;
- routing/cache/storage keys;
- Memory identity;
- credential selection.

## 7. Phase 4B pseudonymous correlation

### 7.1 Purpose

Pseudonyms let operators correlate repeated failures for the same principal/room/project without exporting raw UAG authorization identifiers.

Initial trace-only attributes are owned by the pseudonym contract and include principal/room/project pseudonyms plus same-span key-version metadata.

### 7.2 Security boundary

Pseudonymization requires:

- dedicated CSPRNG-generated correlation key separate from all auth/provider credentials;
- explicit stable deployment scope;
- trusted authoritative raw identifiers only;
- closed kind domain;
- canonical length-prefixed HMAC framing;
- fixed output representation;
- bounded key-version label and rotation discipline.

Exact grammar, raw-ID bounds, HMAC message, output encoding, and version association are defined only in the pseudonym/security contracts.

### 7.3 Pseudonyms never authorize

A pseudonym/key-version label must never authenticate, authorize, select a room/project/session/Memory record/credential, route a request, form a storage key, or grant trace-query access.

Pseudonyms are forbidden as metric dimensions, baggage, and resource attributes in the initial implementation.

## 8. Phase 4C provider SDK nested instrumentation

### 8.1 Canonical ownership

UAG's provider-neutral `chat` span remains canonical:

```text
chat <model>            # UAG canonical LLM operation
  +-- provider-sdk ...  # optional metadata-only diagnostic child
```

SDK instrumentation must not replace, rename, suppress, or become source of truth for the UAG `chat` span.

### 8.2 Selected-call scoping

Provider selection is by UAG logical provider ID, not SDK package. Shared SDK classes/clients do not imply shared instrumentation permission.

A supported integration must use either:

1. client-instance/call-scoped instrumentation; or
2. UAG-owned active-call guard checked by every SDK hook.

The guard must prove:

- currently inside active UAG canonical `chat`;
- current logical provider ID is explicitly selected;
- SDK call belongs to guarded client/request for that canonical round;
- guard is trusted process/context-local state, not endpoint/request payload data.

Global hooks are inert outside that guard. If an instrumentor cannot guarantee this, it is unsupported.

### 8.3 No duplicate logical spans

If an SDK instrumentor creates a semantic duplicate of the canonical UAG LLM span, UAG must suppress/configure that duplicate or declare that instrumentor/version unsupported.

Generic global HTTP auto-instrumentation is not enabled merely to obtain provider diagnostics.

### 8.4 Provider SDK content is disabled initially

In initial Phase 4C, provider SDK child spans are metadata-only diagnostics. Provider/instrumentor-native prompt/response/header/body capture stays disabled regardless of its own environment variables/defaults.

Product-level content capture occurs only through the UAG-owned Phase 4A canonical content surface. If an instrumentor cannot prevent raw content/headers from exporting directly, it is unsupported.

### 8.5 Failure isolation

Provider instrumentors are optional dependencies. Import/install/version/setup/runtime failure:

- yields only normalized diagnostics;
- disables that optional instrumentation;
- never retries or mutates the model request;
- leaves canonical UAG tracing/provider behavior unchanged.

## 9. Phase 4D authorization-aware trace queries

### 9.1 Raw backends are operator/admin surfaces

Ordinary users never receive direct Jaeger/Grafana/vendor API credentials or raw backend responses.

Initial ordinary-user lookup uses a canonical trace ID only. Pseudonym-based ordinary-user trace discovery is deferred; pseudonym possession is never proof of access.

### 9.2 Local segment authorization

One distributed trace ID may span multiple UAG instances/services/scopes. A local authorization record for one segment never authorizes the whole trace.

UAG records local trusted ownership/auth metadata sufficient to bind local spans to room/project/private scope and re-run current authorization later. Exported span/resource fields are never used as authorization truth.

For ordinary users:

- current session/auth is revalidated per query;
- current room/project/private-room authorization is re-run per local segment;
- remote/unindexed spans are omitted;
- local spans belonging to denied segments are omitted;
- cross-instance authorization-index federation is not part of initial Phase 4D.

### 9.3 Query flow

```text
validate canonical trace_id
  -> authenticate/revalidate current user
  -> find local authorization records
  -> none? deny
  -> re-run current authz per local segment
  -> perform bounded backend query
  -> classify fetched spans using trusted local membership only
  -> drop non-local/unindexed/unauthorized spans
  -> project authorized spans through closed uag.trace_view.v1
  -> no valid authorized spans remain? deny/not-found under API contract
  -> return bounded metadata-only response
```

Current policy wins; historical membership or trace possession is insufficient.

### 9.4 Ordinary-user response schema

`uag.trace_view.v1` is strictly metadata-only. Its exact top-level/span field set, canonical trace/span ID grammars, parent semantics, status enum, `partial` rules, and resource limits are defined by the security contract. Safe span-name mapping is defined by the traversal contract; timing normalization by the scalar/timing contract.

V1 never exposes:

- captured content/events;
- general attributes;
- pseudonyms/key-version attributes;
- status descriptions;
- resource/instrumentation metadata;
- links/logs/baggage;
- request/response bodies/headers;
- raw identity/auth fields;
- exception text;
- vendor extensions.

A future field requires a new reviewed schema version; v1 does not grow implicitly.

### 9.5 Bounded backend reads

The exact aggregate deadline/decoded-byte/page/span/output ceilings and deterministic truncation rules are owned by the security contract.

Adapters must enforce bounds while reading rather than materializing an unbounded response. Retries/pages share the same aggregate budgets. Unsupported adapters fail closed for ordinary-user queries.

### 9.6 Parent omission

If a parent exists but is not authorized/valid/returned, ordinary-user response omits its ID and may expose only the safe `parent_omitted` boolean defined by the security contract.

## 10. Retention and deletion

Phase 4 does not imply deletion propagation into external telemetry.

Operators must understand:

- deleting a room/Memory record does not automatically erase exported traces;
- rotating a pseudonym key does not rewrite history;
- local trace-authorization index retention is independent of external trace retention;
- content-capture deployments require explicit backend retention/access policy.

If local authorization metadata expires/is removed, ordinary-user query fails closed even while backend data still exists.

## 11. Multi-user/shared-room rules

Phase 1-3 isolation remains mandatory:

- one turn = one logical Agent trace;
- WebSocket/room is not a long-lived trace root;
- shared-room content capture remains server-policy controlled and does not grant trace viewing;
- room/project pseudonyms do not grant trace viewing;
- every trace query re-runs current auth/authz;
- authorization for one distributed segment never authorizes another.

## 12. Failure behavior

Every Phase 4 feature is best effort and isolated from normal execution:

```text
provenance/redaction/bound/render failure
  -> omit content
  -> continue Agent/model/tool execution

correlation key/scope/version/raw-id failure
  -> omit affected pseudonym(s)
  -> continue tracing

provider SDK instrumentation failure
  -> disable optional child diagnostics
  -> continue canonical chat tracing

trace backend/bounded-query failure
  -> bounded trace-query error/no raw payload
  -> Agent execution unaffected
```

Failure must never broaden capture, instrumentation scope, identity correlation, or trace access.

## 13. Audit diagnostics

Safe, low-cardinality normalized event families may include:

```text
observability.capture.enabled
observability.capture.source_blocked
observability.capture.redaction_failed
observability.capture.limit_exceeded
observability.correlation.unavailable
observability.provider_instrumentation.unavailable
observability.trace_query.allowed
observability.trace_query.partial
observability.trace_query.denied
observability.trace_query.backend_error
```

Diagnostics never include rejected content, secrets, raw correlation keys/identifiers, raw auth identifiers, arbitrary backend text, or unbounded values.

## 14. Test requirements

Implementation is not complete until the companion-contract conformance suites and these cross-feature cases pass.

### 14.1 Phase 4A integration

Verify:

- OFF remains metadata-only;
- master ON with no category captures nothing;
- category selection is independent;
- forbidden provenance overrides categories at root and nested fields;
- file/artifact/Memory/retrieval/auth/session/credential/reasoning/system/developer bodies remain absent;
- structural/scalar bounds execute before secret scanning;
- only exact closed `uag.content` events carry captured content;
- candidate/field/span limits are cumulative and deterministic;
- malformed/custom/overflow/redaction failures never alter runtime behavior;
- no content reaches metrics/baggage/resources/auth/storage.

### 14.2 Phase 4B integration

Verify:

- feature OFF emits no pseudonyms;
- weak/reused/missing key or invalid scope/version/raw-ID emits no affected pseudonym;
- pseudonym construction/output/version follows its normative contract exactly;
- raw IDs/key/scope are not exported by default;
- pseudonym/version cannot affect auth/authz/Memory/query behavior.

### 14.3 Phase 4C integration

Verify:

- OFF initializes no SDK instrumentor;
- selected provider child spans remain nested under canonical `chat`;
- unselected providers sharing SDK/client emit no child diagnostics;
- calls outside guarded canonical chat emit none;
- no duplicate logical LLM operation;
- provider SDK native content capture stays disabled;
- instrumentor failure does not alter model results.

### 14.4 Phase 4D integration

Verify:

- invalid trace ID rejected before lookup;
- unauthenticated/unauthorized/missing-local-record queries fail closed;
- current revocation takes effect;
- one local segment does not authorize another;
- remote/unindexed spans are omitted;
- cross-instance trace with different scopes returns only currently authorized local spans;
- ordinary-user response matches exact closed v1 schema/types;
- unauthorized parent IDs are never exposed;
- filtered/truncated/projection-incomplete views set `partial` according to security contract;
- backend resource ceilings are enforced before unbounded materialization;
- backend failures do not affect Agent execution.

### 14.5 Repository gates

Every implementation slice retains normal repository checks:

- Python 3.11 / 3.13 / 3.14;
- Ruff;
- Black;
- I18N/tool-catalog checks where applicable;
- full pytest;
- OTel-disabled behavior unchanged.

## 15. Acceptance criteria

Phase 4 is acceptable only when:

1. all four capabilities are OFF by default;
2. content requires master gate + explicit category + trusted allowed provenance;
3. structural/scalar bounds precede content secret scanning;
4. content uses only the closed canonical UAG content carrier/renderer and finite cumulative budgets;
5. forbidden provenance/reasoning/system/developer/auth/Memory/retrieval/file/artifact content remains excluded;
6. pseudonymization uses dedicated key + stable scope + closed construction/output/version rules;
7. pseudonyms/version labels remain diagnostic-only and never security/storage identities;
8. provider SDK instrumentation is selected-call scoped, metadata-only, nested, and non-duplicative;
9. ordinary-user trace queries revalidate current UAG auth/authz per returned local segment/span;
10. unindexed/remote/unauthorized spans fail closed to omission;
11. ordinary-user response is closed metadata-only `uag.trace_view.v1` with no arbitrary backend text/structures;
12. trace backend retrieval is bounded before authorization filtering/output projection;
13. all Phase 4 failures are isolated from Agent/model/tool behavior;
14. Phase 1-3 privacy, trust, propagation, authorization, and canonical-span behavior remain unchanged.

## 16. Explicitly deferred work

Requires later design review:

- reasoning/chain-of-thought capture;
- system/developer instruction capture;
- Memory/retrieval/file/artifact/auth/session/credential body capture;
- provider-SDK-native prompt/response content export;
- ordinary-user viewing of captured content;
- ordinary-user pseudonym-based trace discovery;
- cross-instance federation of trace authorization indexes;
- pseudonyms as security/storage identities;
- generic global provider/HTTP auto-instrumentation;
- direct ordinary-user access to raw Jaeger/Grafana/vendor APIs;
- telemetry-driven authorization decisions.
