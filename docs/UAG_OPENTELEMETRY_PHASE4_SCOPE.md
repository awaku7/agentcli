# OpenTelemetry Phase 4 Scope

Status: Design only  
Parent design: `docs/UAG_OPENTELEMETRY_DESIGN.md`  
Prerequisite: Phase 3 complete on `main`  
Scope: optional advanced diagnostics without weakening Phase 1-3 privacy, identity, authorization, propagation, or canonical-span contracts.

## 1. Purpose

Phase 4 adds four independent, default-OFF capabilities:

1. controlled content capture;
2. pseudonymous principal/room/project correlation;
3. optional provider SDK nested diagnostics;
4. authorization-aware trace-query proxying.

The core rule remains:

> UAG owns the observability model. OpenTelemetry is an optional projection/export backend.

Telemetry is never a source of truth for identity, authorization, session validity, Memory policy, tool permission, Agent state, routing, credential selection, or scope selection.

## 2. Normative document ownership

Each exact Phase 4 rule has one normative owner:

| Topic | Normative owner |
| --- | --- |
| overall boundaries, rollout, provider SDK diagnostics, trace-authorization architecture | this scope |
| configuration parsing, correlation credential/deployment scope, field provenance, `uag.trace_view.v1`, trace-query limits | `docs/UAG_OPENTELEMETRY_PHASE4_SECURITY_CONTRACT.md` |
| safe span-name enum, content carrier/owner, traversal/privacy/redaction/renderer/span ledger | `docs/UAG_OPENTELEMETRY_PHASE4_TRACE_NAME_AND_TRAVERSAL_CONTRACT.md` |
| primitive content scalars and trace timing normalization | `docs/UAG_OPENTELEMETRY_PHASE4_SCALAR_AND_TIMING_CONTRACT.md` |
| pseudonym HMAC/kind/raw-ID/output/attachment/key-version | `docs/UAG_OPENTELEMETRY_PHASE4_PSEUDONYM_OUTPUT_CONTRACT.md` |

A parent summary must not redefine or weaken an exact grammar, limit, renderer, order, or field type owned by a companion. Any conflict is a documentation defect, not an implementation choice.

## 3. Phase 1-3 invariants

Phase 4 preserves all earlier contracts:

- OTel remains opt-in;
- UAG canonical Agent/LLM/Tool spans remain authoritative;
- one Web user turn remains one logical Agent trace;
- browser trace context remains untrusted unless Phase 3 trusted-ingress policy accepts it;
- A2A/MCP propagation never supplies identity or authorization;
- OIDC/session and room/project/private-room authorization remain server-authoritative;
- trace/span IDs, pseudonyms, key versions, baggage, and backend/span/resource data never authorize;
- content/identity/secrets remain absent from metrics, baggage, and process resource attributes;
- Phase 3 duplicate-span guarantees remain normative;
- observability failure never changes Agent/model/tool behavior;
- uncertainty fails closed for telemetry instead of broadening capture/access.

## 4. Rollout

### Phase 4A - privacy/content foundation

Implement first, keep capture OFF by default:

- shared configuration resolver;
- closed semantic categories;
- trusted typed provenance + hard-denied provenance;
- bounded candidate/structure/scalar processing;
- recursive privacy-key handling and deterministic secret redaction;
- one UAG-owned content carrier and canonical renderer;
- cumulative per-span content budget;
- regressions proving forbidden bodies cannot become eligible through composites.

### Phase 4B - pseudonymous correlation

Then add:

- dedicated server-held correlation key;
- stable validated deployment scope;
- canonical framed HMAC domains;
- fixed pseudonym representation/attachment scope;
- same-span key-version metadata;
- strict prohibition on auth/storage use.

### Phase 4C - provider SDK diagnostics

Then add only selected-call-scoped, metadata-only child diagnostics under canonical `chat`.

### Phase 4D - trace-query proxy

Finally add bounded backend querying, a local authorization index, current auth/authz revalidation, per-local-segment filtering, and the closed ordinary-user metadata-only schema.

Controlled content should be the last capability enabled in production even though its policy foundation is implemented first.

## 5. Configuration principles

All Phase 4 settings are process/server policy. Browser/WebSocket/A2A/MCP/tool/provider/query/cookie/header/trace/baggage data cannot enable or alter them.

Core activation remains authoritative:

```text
--otel / --no-otel
UAGENT_OTEL_ENABLED
```

Exact CLI/environment precedence, category/provider CSV parsing, capture bounds, correlation credential validation, and deployment-scope validation belong to the security contract.

Safe defaults:

- every Phase 4 feature OFF;
- master content ON with no categories still captures nothing;
- invalid content configuration disables content capture;
- invalid pseudonym configuration disables pseudonyms only;
- invalid provider selector never instruments an unselected provider.

## 6. Phase 4A controlled content

### 6.1 Categories

Initial categories are exactly:

```text
user_input
assistant_output
tool_arguments
tool_result
```

A category never overrides provenance restrictions.

### 6.2 Always excluded initially

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

### 6.3 Normative processing order

The parent order is intentionally identical to the topic contracts:

```text
trusted candidate
  -> candidate-count admission
  -> forbidden-provenance
  -> master gate
  -> category gate
  -> source/category gate
  -> approved canonical owner/content carrier
  -> exact supported type/shape
  -> bounded node/depth/width/cycle checks
  -> bounded primitive preflight
  -> bounded child traversal + child provenance
  -> recursive privacy-key / value-secret handling
  -> post-redaction field bound
  -> canonical rendering
  -> shared per-span content ledger
  -> emit whole content event or omit whole candidate
```

No value-level privacy/secret scan occurs before the work needed to prove that scanning is bounded. This supersedes older redaction-before-bounds wording.

### 6.4 Closed carrier and provenance

Content is exported only through the UAG-owned `uag.content` event on the exact canonical owner spans defined by the traversal contract. Arbitrary payload keys never become telemetry attribute/event names.

Body-capable composites require field/node provenance. File/artifact/Memory/retrieval/auth/session/credential/reasoning/system/developer bodies remain forbidden even inside otherwise eligible user/tool structures.

### 6.5 Non-trace channels

Controlled content never becomes metric dimensions, baggage, process resources, auth/identity state, routing/cache/storage keys, Memory identity, or credential-selection state.

## 7. Phase 4B pseudonymous correlation

Pseudonyms provide trace-only diagnostic correlation without exporting raw UAG authorization identifiers.

Required boundary:

- dedicated CSPRNG key isolated from auth/provider credentials;
- exact validated deployment scope;
- trusted authoritative raw identifiers only;
- closed `principal|room|project` kind domain;
- canonical length-prefixed HMAC framing;
- fixed 128-bit lowercase-hex output;
- fixed local canonical Agent-root attachment scope;
- bounded key-version label paired with emitted pseudonyms.

Exact rules belong to the security/pseudonym contracts.

Pseudonyms/key-version labels never authenticate, authorize, select rooms/projects/sessions/Memory/credentials, route requests, form storage keys, or grant trace-query access. They are absent from metrics, baggage, and resources.

## 8. Phase 4C provider SDK nested diagnostics

### 8.1 Canonical ownership

UAG's provider-neutral `chat` span remains the canonical LLM operation:

```text
chat <model>       # UAG canonical
  +-- provider_sdk # optional safe diagnostic child
```

SDK diagnostics never replace, rename, suppress, or become source of truth for canonical `chat`.

### 8.2 Selected-call scoping

Provider selection uses UAG logical provider IDs, not SDK package names. Shared SDK classes/clients do not imply instrumentation permission.

A supported integration uses either:

1. client/call-scoped instrumentation; or
2. a UAG-owned active-call guard checked by every SDK hook.

The guard proves all of:

- execution is inside active canonical `chat`;
- logical provider ID is explicitly selected;
- SDK call belongs to the guarded client/request for that canonical round;
- guard state is trusted process/context-local state, never endpoint/request payload data.

Global hooks are inert outside that guard. If an instrumentor cannot guarantee this, it is unsupported.

### 8.3 Initial raw exported provider-child shape is closed

Initial Phase 4C does **not** export arbitrary SDK-instrumentor span payloads. A supported selected call may produce one UAG-controlled child span with:

```text
span name: provider_sdk
parent:    active canonical chat span
attributes:
  uag.provider.id   # exact selected UAG logical provider ID
status:
  code only: UNSET | OK | ERROR
```

No other provider-child attribute/event/link/status description is permitted initially.

In particular the provider child must not export:

- SDK/instrumentor-generated arbitrary span names;
- model names or endpoint URLs;
- request/response IDs;
- prompts/responses/reasoning/tool bodies;
- HTTP headers/bodies;
- auth/provider credentials;
- exception messages/stacks;
- arbitrary resource/instrumentation attributes;
- SDK-native events or links;
- vendor request/response metadata.

`uag.provider.id` is assigned from trusted resolved configuration/selected-call state, not copied from remote/provider response data.

A provider SDK package may be used internally to detect lifecycle/timing/status, but if its instrumentor/version cannot suppress or normalize all non-allowlisted data before exporter submission, that instrumentor/version is unsupported and must remain disabled.

### 8.4 No duplicate logical span

Exactly one canonical UAG `chat` remains the LLM operation. If an SDK instrumentor would create a semantic duplicate, UAG suppresses it or rejects that instrumentor/version.

Generic global HTTP auto-instrumentation is not enabled merely to obtain provider diagnostics.

### 8.5 SDK-native content stays disabled

Provider/instrumentor-native prompt/response/header/body capture remains disabled regardless of its own environment variables/defaults. Product content capture occurs only through the Phase 4A UAG-owned content path.

### 8.6 Failure isolation

Import/install/version/setup/runtime/instrumentation failure:

- emits only normalized content-free diagnostics;
- disables optional provider child diagnostics;
- never retries or mutates the model request;
- leaves canonical provider behavior/tracing unchanged.

### 8.7 Required provider regressions

Tests must prove:

- OFF initializes no instrumentor;
- selected calls create at most the allowed child under canonical `chat`;
- unselected provider sharing SDK/client creates none;
- call outside active guard creates none;
- provider child span name is exactly `provider_sdk`;
- its only initial attribute is trusted `uag.provider.id`;
- status description/events/links/arbitrary attributes are absent;
- prompt/response/reasoning/header/URL/model/request-ID/exception/vendor text cannot appear in raw provider-child telemetry;
- no duplicate canonical LLM operation appears;
- unsupported/global-leaking instrumentors fail closed without changing model output.

## 9. Phase 4D authorization-aware trace queries

### 9.1 Raw backend boundary

Ordinary users never receive direct Jaeger/Grafana/vendor API credentials or raw backend responses. Initial ordinary-user lookup uses canonical trace ID only. Pseudonym-based ordinary-user discovery is deferred.

### 9.2 Local segment authorization

A distributed trace may span multiple UAG instances/services/scopes. A local record for one segment never authorizes the whole trace.

UAG records trusted local ownership/auth metadata and re-runs current auth/authz per local segment/span. Exported span/resource fields are never authorization truth.

Remote/unindexed spans and locally denied segments are omitted. Cross-instance authorization-index federation is deferred.

### 9.3 Query flow

```text
validate canonical trace_id
  -> authenticate/revalidate current user
  -> find local authorization records
  -> none? deny
  -> current authz per local segment
  -> bounded backend query
  -> validate/classify against trusted local membership
  -> drop non-local/unindexed/unauthorized
  -> project through closed uag.trace_view.v1
  -> no valid authorized spans? deny/not-found under API contract
  -> return bounded metadata-only response
```

Current policy wins over historical access or trace possession.

### 9.4 Ordinary-user schema

Exact top-level/span fields, canonical trace/span ID grammars, duplicate handling, parent semantics, `partial`, status vocabulary, and resource limits belong to the security contract. Safe name class belongs to traversal; timing to scalar/timing.

V1 never exposes content/events/general attributes/pseudonyms/key versions/status descriptions/resources/links/logs/baggage/HTTP or provider request data/raw identity/auth/exception/vendor text.

A future field requires a new reviewed schema version.

### 9.5 Bounded reads

Exact aggregate deadline/decoded-byte/page/span/output ceilings belong to the security contract. Adapters enforce them while reading; retries/pages share budgets; unsupported unbounded adapters fail closed.

## 10. Retention/deletion

Phase 4 does not imply external telemetry deletion propagation.

- deleting UAG room/Memory data does not automatically erase exported traces;
- rotating pseudonym key does not rewrite history;
- local authorization-index retention is independent of backend retention;
- content-capture deployments require explicit backend retention/access policy;
- removal/expiry of local authorization metadata makes ordinary-user query fail closed even if backend trace remains.

## 11. Multi-user/shared-room rules

- one turn remains one logical Agent trace;
- WebSocket/room is not a long-lived trace root;
- content capture never grants trace-query access;
- pseudonyms never grant trace-query access;
- current auth/authz is re-run for every query;
- one distributed segment never authorizes another.

## 12. Failure behavior

```text
content provenance/privacy/bound/render failure
  -> omit content, continue runtime

correlation key/scope/version/raw-id failure
  -> omit affected pseudonym(s), continue tracing

provider SDK diagnostic failure
  -> disable optional child diagnostic, continue canonical chat/model call

trace backend/bounded-query failure
  -> bounded query error/no raw payload, Agent unaffected
```

Failure never broadens capture, instrumentation, identity correlation, or access.

## 13. Diagnostics

Safe normalized low-cardinality diagnostics may report feature/category/error-class outcomes but never rejected content, secrets, raw correlation key/identifier, raw auth identifiers, arbitrary provider/backend text, or unbounded values.

## 14. Cross-feature tests

Implementation is incomplete until topic-contract tests and these integration properties pass:

- Phase 4A OFF remains metadata-only; forbidden provenance wins; bounds precede scanning; only closed content events carry content; no content reaches metrics/baggage/resources/auth/storage.
- Phase 4B failure modes omit pseudonyms without affecting tracing; exact construction/attachment/version rules hold; pseudonyms never affect auth/query behavior.
- Phase 4C obeys the closed provider-child projection above and never leaks provider/request/content/exception text or duplicate the canonical LLM operation.
- Phase 4D rejects invalid trace IDs before lookup, revalidates current auth/authz, omits unindexed/unauthorized spans, returns exact v1 types only, hides unauthorized parent IDs, and enforces bounded backend reads.

Every implementation slice retains repository gates: Python 3.11/3.13/3.14, Ruff, Black, applicable I18N/tool-catalog checks, full pytest, and unchanged OTel-disabled behavior.

## 15. Acceptance criteria

Phase 4 is acceptable only when:

1. all four capabilities are OFF by default;
2. content requires master + explicit category + trusted allowed provenance;
3. structural/scalar bounds precede content privacy/secret scanning;
4. content uses one closed UAG carrier/renderer with finite candidate/field/span budgets;
5. forbidden provenance/reasoning/system/developer/auth/Memory/retrieval/file/artifact content remains excluded;
6. pseudonymization uses dedicated canonical key/scope/construction/output/version rules and never becomes security/storage identity;
7. provider SDK diagnostics are selected-call scoped, closed metadata-only, nested, and non-duplicative;
8. ordinary-user trace queries revalidate current UAG auth/authz per returned local segment/span;
9. unindexed/remote/unauthorized spans fail closed to omission;
10. ordinary-user response is closed metadata-only `uag.trace_view.v1` with no arbitrary backend text/structures;
11. backend retrieval is bounded before output projection;
12. all Phase 4 failures are isolated from normal Agent/model/tool behavior;
13. Phase 1-3 privacy/trust/propagation/authorization/canonical-span behavior is unchanged.

## 16. Explicitly deferred

Requires later review:

- reasoning/chain-of-thought capture;
- system/developer instruction capture;
- Memory/retrieval/file/artifact/auth/session/credential body capture;
- provider-SDK-native prompt/response export;
- richer provider SDK attributes/events/links;
- ordinary-user viewing of captured content;
- ordinary-user pseudonym-based trace discovery;
- cross-instance trace-authorization federation;
- pseudonyms as security/storage identity;
- generic global provider/HTTP auto-instrumentation;
- direct ordinary-user raw trace-backend access;
- telemetry-driven authorization decisions.
