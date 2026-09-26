# OpenTelemetry Phase 4 Scope

Status: Design only  
Parent design: `docs/UAG_OPENTELEMETRY_DESIGN.md`  
Prerequisite: Phase 3 complete on `main`  
Scope: optional advanced diagnostics without weakening the Phase 1-3 privacy, identity, authorization, propagation, or canonical-span contracts.

## 1. Purpose

Phase 4 adds optional diagnostics for operators that need deeper correlation, controlled content visibility, provider-level detail, or mediated trace access.

The core rule remains unchanged:

> UAG owns the observability model. OpenTelemetry is an optional projection/export backend.

Telemetry is never a source of truth for identity, authorization, session validity, Memory policy, tool permission, Agent state, or scope selection.

Every Phase 4 capability is separately opt-in and disabled by default.

## 2. Phase 4 capabilities

Phase 4 contains four independent capabilities:

1. controlled content capture;
2. pseudonymous principal/room/project correlation;
3. optional provider SDK nested instrumentation;
4. an authorization-aware trace-query proxy.

These features do not need to ship together. Each must preserve normal UAG behavior when disabled or unavailable.

## 3. Non-negotiable Phase 1-3 invariants

Phase 4 must preserve all earlier contracts, including:

- OTel remains opt-in;
- UAG canonical Agent/LLM/Tool spans remain authoritative;
- browser-provided trace context remains untrusted unless an explicit trusted ingress policy applies;
- A2A/MCP propagation never supplies identity or authorization;
- one Web user turn remains one logical Agent trace;
- OIDC live-session and room/project/private-room authorization remain server-authoritative;
- trace IDs, pseudonyms, baggage, span attributes, and backend data never authorize access;
- content, identity, and secrets remain absent from metrics, baggage, and process resource attributes;
- observability failure never changes Agent/model/tool behavior;
- privacy or authorization uncertainty fails closed for telemetry rather than broadening capture or access.

## 4. Rollout order

Recommended implementation order:

### Phase 4A - privacy and policy foundation

- formalize content-capture policy as a master gate plus explicit semantic categories;
- introduce typed capture provenance and a forbidden-provenance denylist that overrides category selection;
- add fail-closed value-level secret redaction before exporter submission;
- add hard size/depth/item caps for captured structured values;
- keep reasoning, authentication/session material, credentials, Memory/retrieval bodies, files, and artifacts excluded;
- add regression tests proving that enabling one category cannot indirectly enable a forbidden source.

### Phase 4B - pseudonymous correlation

- add server-keyed HMAC pseudonyms for selected trace-only scope correlation;
- require a dedicated generated high-entropy correlation key;
- use canonical framed input encoding and domain separation;
- keep pseudonyms out of metrics, baggage, resource attributes, auth decisions, and storage keys;
- support key versioning/rotation;
- keep raw identifiers local to UAG.

### Phase 4C - provider SDK nested instrumentation

- add explicitly selected provider SDK instrumentation only as nested diagnostics;
- scope hooks to the selected UAG provider call, not merely to an SDK package;
- keep the UAG provider-neutral `chat` span canonical;
- prevent duplicate logical LLM spans;
- keep SDK prompt/response capture subordinate to UAG content policy;
- failure or version mismatch must fall back without changing model calls.

### Phase 4D - trace-query proxy

- add a server-side query abstraction for supported trace backends;
- authorize every returned local trace segment using current UAG identity and room/project policy;
- filter distributed traces to locally indexed, currently authorized segments for ordinary users;
- return only a versioned fail-closed response schema;
- treat possession of a trace ID or pseudonym as insufficient for access;
- expose operator/admin access first; ordinary-user access follows only after segment-authorization tests are complete.

Controlled content capture should be the last feature enabled in production deployments, even if its policy foundation is implemented first.

## 5. Configuration principles

All Phase 4 settings are process/server policy. Browser input, A2A payloads, tool arguments, prompt text, query parameters, cookies, or incoming trace metadata cannot enable them.

Existing product-level OTel activation remains authoritative:

```text
--otel / --no-otel
UAGENT_OTEL_ENABLED
```

Phase 4 options are subordinate to normal OTel activation.

### 5.1 Controlled content capture

`UAGENT_OTEL_CAPTURE_CONTENT` remains the master gate and defaults to OFF.

Phase 4 adds an explicit category allowlist, for example:

```text
UAGENT_OTEL_CAPTURE_CONTENT=1
UAGENT_OTEL_CAPTURE_CATEGORIES=user_input,assistant_output
```

The master gate alone must not mean "capture everything". If capture is enabled but no category is selected, no content is exported.

Initial semantic categories are:

```text
user_input
assistant_output
tool_arguments
tool_result
```

These categories express the logical role of a value. They do **not** override source/provenance restrictions.

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

A later design change is required before any excluded class can be captured.

Bounded controls are fixed by `docs/UAG_OPENTELEMETRY_PHASE4_SECURITY_CONTRACT.md`:

```text
UAGENT_OTEL_CAPTURE_MAX_FIELD_CHARS=2048   # valid 64..16384
UAGENT_OTEL_CAPTURE_MAX_SPAN_CHARS=8192    # valid 256..65536
```

Missing values use those defaults. Invalid/non-integer/zero/negative/out-of-range values, or a span limit smaller than the field limit, disable controlled content capture for that process while leaving core metadata tracing unchanged.

### 5.2 Pseudonymous correlation

Suggested controls:

```text
UAGENT_OTEL_PSEUDONYMOUS_CORRELATION=0
UAGENT_OTEL_CORRELATION_KEY_NAME=observability/correlation
UAGENT_OTEL_CORRELATION_KEY_VERSION=v1
```

The correlation key is a dedicated observability secret generated specifically for pseudonymization and stored through UAG's server-side credential mechanism.

The implementation contract is:

- key material is generated with a cryptographically secure RNG;
- the decoded key contains at least 256 bits of entropy and is at least 32 bytes;
- arbitrary human passphrases are not accepted as correlation keys;
- the correlation key has a dedicated credential namespace/purpose and must not reuse OIDC, OAuth, A2A, session-signing, API, provider, MCP, or other authentication/authorization secrets;
- startup validation rejects malformed, undersized, or known-reused key material and disables pseudonymous correlation without disabling core tracing;
- raw key material is never exported, logged, placed in environment-derived telemetry, or accepted from browser input.

The initial exported pseudonym representation is fixed by `docs/UAG_OPENTELEMETRY_PHASE4_PSEUDONYM_OUTPUT_CONTRACT.md`: exactly the first 128 bits of the HMAC-SHA-256 digest, encoded as exactly 32 lowercase hexadecimal characters. The truncation length and encoding are not configurable in the initial Phase 4 implementation.

### 5.3 Provider SDK diagnostics

Suggested control uses UAG logical provider IDs:

```text
UAGENT_OTEL_PROVIDER_INSTRUMENTATION=openai,claude
```

`claude` selects the Anthropic SDK path. `anthropic` is not an initial alias. Missing/empty means OFF. Unknown provider IDs are ignored with a normalized diagnostic event and do not fail startup.

SDK instrumentation is permitted only for explicitly supported/version-tested provider paths and only when it can be scoped to the selected UAG call.

### 5.4 Trace-query proxy

Trace-query support is server-controlled and disabled unless a supported backend adapter is configured.

Backend credentials remain server-side and are never sent to browser clients.

## 6. Controlled content capture model

### 6.1 Eligibility order

A value is eligible only if every gate succeeds in this order:

1. the source/provenance is not forbidden;
2. the content master gate is enabled;
3. the semantic category is explicitly allowlisted;
4. the typed source is permitted for that category;
5. value-level secret scanning/redaction succeeds;
6. size/depth/item bounds succeed;
7. the final attribute/event key passes the existing always-blocked privacy filter.

A category allowlist can never override forbidden provenance.

Conceptually:

```text
runtime value + semantic category + typed provenance
   -> forbidden provenance?
      -> yes: drop entire value
      -> no
         -> master gate enabled?
            -> no: drop
            -> yes
               -> category explicitly allowed?
                  -> no: drop
                  -> yes
                     -> source/category combination allowed?
                        -> no: drop
                        -> yes
                           -> value-level secret redaction
                              -> uncertain/failed: drop content
                              -> safe
                                 -> size/depth/item limits
                                 -> final key allow/block filter
                                 -> exporter
```

### 6.2 Mandatory provenance model

Every content-capture candidate must carry a UAG-owned typed provenance separate from arbitrary tool/provider payload fields.

Example internal categories:

```text
user_message
assistant_message
tool_argument
ordinary_tool_result
authentication
session
credential
memory
retrieval
file
artifact
reasoning
system_instruction
developer_instruction
security_sensitive_unknown
```

The provenance is assigned at trusted UAG boundaries. A tool result cannot self-declare a safer provenance through returned JSON.

The following provenance classes are hard-denied before semantic-category evaluation:

```text
authentication
session
credential
memory
retrieval
file
artifact
reasoning
system_instruction
developer_instruction
security_sensitive_unknown
```

This denylist applies recursively and overrides `tool_arguments` or `tool_result` eligibility.

Examples:

- a file-reading tool that returns file text inline remains `file` provenance and is dropped even if `tool_result` is enabled;
- an artifact helper that embeds artifact bytes/text inline remains `artifact` provenance and is dropped;
- a Memory or retrieval tool that returns records inline remains `memory`/`retrieval` provenance and is dropped;
- authentication/session/credential helpers are dropped wholesale, even if their returned object uses innocuous keys such as `value`;
- nested values inherit the strongest forbidden provenance unless a trusted UAG boundary explicitly creates a new safe derived metadata value.

References are not followed for telemetry, but "do not follow references" is only defense in depth; inline forbidden bodies are also blocked by provenance.

### 6.3 Typed-source exclusion before redaction

Certain source types are never passed to the generic content redactor in the initial Phase 4 implementation.

Drop the entire value before capture when it originates from:

- OIDC/OAuth/login/callback/session objects;
- credential-store reads or provider credential resolution;
- Authorization/Cookie/header credential containers;
- A2A bearer authentication structures;
- MCP OAuth/token structures;
- Memory/retrieval records or queries;
- file/artifact loaders or body-bearing representations;
- reasoning/thinking/analysis provider fields;
- system/developer instruction stores;
- an opaque security/authentication structure that UAG cannot classify safely.

This source-level exclusion is the primary guarantee that authentication/session/credential content is never captured. Key-name and value-pattern redaction are additional defenses.

### 6.4 Mandatory value-level secret redaction

Permitted natural-language/tool content can still contain secrets. Before export, Phase 4 requires a value-level sanitizer that operates on structured values before serialization and on bounded strings after normalization.

At minimum the sanitizer must detect and redact/drop high-confidence forms including:

- `Authorization`-scheme values such as `Bearer ...` and `Basic ...`, regardless of the containing key name;
- compact JWT-like token forms;
- PEM private-key blocks and comparable private-key encodings;
- credential-bearing URI userinfo where recognized;
- known UAG/provider secret wrapper types before they become strings;
- structured values tagged by trusted UAG code as secret/credential-bearing.

Rules:

- matches are replaced by a fixed marker such as `[REDACTED]`, never a reversible transform;
- secret classifiers run on values as well as keys;
- a structured authentication/security value that cannot be safely classified is dropped wholesale;
- redactor exceptions, parser ambiguity in a security-sensitive typed value, or resource-limit overflow cause that content item to be omitted;
- telemetry redaction failure never fails the user operation;
- logging of redactor failures contains only normalized error class/category, never the rejected value.

No generic redactor can guarantee removal of every secret from arbitrary natural-language text. Therefore content capture remains an explicit sensitive-data export feature requiring operator consent, backend access controls, and retention policy.

### 6.5 Structured tool values

For eligible `tool_arguments` and `tool_result` values:

- apply the trusted provenance denylist first;
- recursively preserve provenance for nested values;
- redact/drop known credential-style keys and value patterns;
- cap recursion depth;
- cap collection item counts;
- cap each rendered field length;
- cap total captured characters per span;
- do not follow file/artifact/Memory/retrieval references to fetch bodies;
- do not automatically decode binary/base64 content for telemetry;
- malformed/unserializable values are omitted rather than causing tool failure.

A tool category never grants permission to capture a forbidden body merely because that body is embedded inline in the tool result.

### 6.6 Reasoning is excluded

Private reasoning / chain-of-thought is not a Phase 4 content category.

Provider-specific fields described as reasoning, thinking, analysis, hidden chain, scratchpad, or equivalent remain excluded from remote telemetry even when other content categories are enabled.

High-level outcome metadata may still be exported if it is already part of UAG's safe provider-neutral observability contract.

### 6.7 No content in metrics, baggage, or resources

Captured content may appear only on approved trace spans/events.

It must never become:

- a metric dimension;
- OTel baggage;
- a process resource attribute;
- an authorization input;
- a cache/storage key;
- a trace-routing key.

## 7. Pseudonymous correlation

### 7.1 Purpose

Operators may need to answer questions such as "are repeated failures affecting the same principal/project/room?" without exporting raw identifiers.

Phase 4 may expose trace-only pseudonyms such as:

```text
uag.correlation.principal
uag.correlation.room
uag.correlation.project
```

These are diagnostic labels only.

### 7.2 Dedicated key requirements

Pseudonymization uses HMAC-SHA-256 with a dedicated server-held correlation key.

The key must:

- be generated specifically for observability pseudonymization;
- contain at least 256 bits of CSPRNG-generated entropy;
- be stored under a reserved observability credential purpose/name;
- not be accepted as an arbitrary passphrase;
- not equal or alias any authentication, token-signing, provider API, A2A, MCP, OIDC/OAuth, session, or other security key known to UAG;
- fail closed by disabling pseudonym emission if validation fails.

Credential-store storage protects key handling but is not itself sufficient; entropy and purpose isolation are mandatory.

### 7.3 Canonical HMAC input framing

Variable-length components must never be concatenated ambiguously.

The canonical input is a version tag followed by length-prefixed UTF-8 byte strings:

```text
magic = b"uag-otel-pseudo-v1"
frame(x) = uint32_be(len(utf8(x))) || utf8(x)
message = magic || frame(deployment_scope) || frame(kind) || frame(raw_identifier)
digest = HMAC-SHA-256(correlation_key, message)
```

Requirements:

- encoding is UTF-8;
- framing uses the byte length after encoding;
- `kind` is selected from a closed enum such as `principal`, `room`, `project`;
- `deployment_scope` is server/operator controlled, not caller supplied;
- raw identifiers are not normalized in a way that could merge distinct authoritative identifiers unless that normalization is already normative for the identifier source;
- tests include adversarial tuples that would collide under simple concatenation but must differ under framing.

For the initial Phase 4 implementation, the exported pseudonym is exactly `lowercase_hex(digest[0:16])`: the first 128 digest bits encoded as exactly 32 lowercase hexadecimal characters. Shorter truncation, base64/base64url, uppercase hex, or operator-configurable representation is not permitted. The normative representation contract is `docs/UAG_OPENTELEMETRY_PHASE4_PSEUDONYM_OUTPUT_CONTRACT.md`; changing the representation later requires an explicitly reviewed schema/version change.

### 7.4 Domain separation and scope

Requirements:

- raw identifier never leaves the pseudonymization helper;
- plain SHA hashes are not accepted as a substitute;
- principal/room/project use separate `kind` domains;
- deployment scope prevents accidental cross-deployment linkability;
- key version is low-cardinality metadata and contains no secret;
- changing the key intentionally breaks cross-version correlation unless an operator retains/query-maps both versions.

### 7.5 Rotation

Rotation must be supported without changing authentication or room/project identifiers.

Historical traces retain the old pseudonym. New traces use the new key version.

No migration of historical trace data is required by UAG.

### 7.6 Pseudonyms are not security identities

A pseudonym must never be used to:

- authenticate a user;
- select a `TurnContext`;
- authorize room/project access;
- lookup or mutate Memory;
- address a session;
- restore an Agent task;
- select a credential;
- determine trace-query authorization.

They are also forbidden as metric dimensions in the initial implementation because they are high-cardinality.

## 8. Provider SDK nested instrumentation

### 8.1 Canonical span ownership

UAG's provider-neutral `chat` span remains the canonical LLM operation.

Optional provider SDK instrumentation may create nested spans beneath that boundary:

```text
chat <model>                 # UAG canonical
  +-- provider-sdk ...       # optional diagnostic child
```

It must not replace, rename, suppress, or become the source of truth for the UAG `chat` span.

### 8.2 Selected-call scoping

Provider selection is not equivalent to SDK-package selection.

UAG may use the same SDK class for multiple logical providers or OpenAI-compatible endpoints. Therefore an instrumentor that globally monkeypatches an SDK is acceptable only if UAG can guarantee that it emits provider diagnostic spans **only** for the selected canonical provider call.

A supported implementation must use one of these forms:

1. client-instance/call-scoped instrumentation; or
2. a UAG-owned active-call guard checked by every SDK hook.

The guard must prove all of the following before an SDK span is emitted:

- execution is currently inside an active UAG canonical `chat` span;
- the logical UAG provider ID matches an explicitly selected Phase 4 provider;
- the model call belongs to the guarded client/request instance for that canonical round;
- the guard is process-local/context-local trusted state, not request payload or environment data supplied by the model endpoint.

For global instrumentors, hooks must be inert outside this guard.

If the instrumentor cannot prevent spans/content for unselected calls sharing the same SDK package, that instrumentor/version is unsupported.

### 8.3 No duplicate logical spans

If an SDK instrumentor creates a span that semantically duplicates the UAG canonical LLM span, UAG must either:

- configure/suppress that duplicate while retaining useful nested diagnostics; or
- reject that instrumentor/version as unsupported.

Phase 3's duplicate-span guarantee remains normative.

Generic HTTP client auto-instrumentation is not enabled globally merely to obtain provider spans.

### 8.4 Content policy separation

Provider SDK instrumentors often have their own content-capture environment variables or defaults.

UAG must not allow those provider/instrumentor settings to bypass UAG's content policy.

For supported instrumentors:

- SDK-level prompt/response capture stays disabled by default;
- UAG Phase 4 content capture remains the sole supported product-level content policy;
- content emitted by SDK instrumentation must pass the same provenance/category/redaction gates before export, or be suppressed entirely;
- if an instrumentor cannot prevent raw prompt/response/headers from being exported directly, it is unsupported for Phase 4.

### 8.5 Dependency and failure isolation

Provider instrumentors are optional dependencies.

Rules:

- do not install them merely because core OTel is enabled;
- install only when the corresponding Phase 4 provider is explicitly selected and normal auto-install policy permits;
- version compatibility is explicit and tested;
- import/install/setup failure produces a normalized diagnostic event and leaves the existing provider path operational;
- instrumentation failure never retries or alters the model request.

## 9. Authorization-aware trace-query proxy

### 9.1 Why a proxy is required

Raw access to Jaeger/Grafana/vendor trace backends is an operator/admin surface.

If UAG exposes traces to ordinary Web users, it must mediate the query and re-check current authorization.

A browser-provided trace ID or pseudonym is only a lookup hint, never proof of access.

### 9.2 Distributed traces require segment authorization

Phase 3 can preserve one W3C trace ID across trusted ingress, A2A, MCP HTTP, and multiple UAG instances/services.

Therefore a local authorization record for one Web turn does **not** authorize every span sharing that trace ID.

For ordinary users, Phase 4D uses local segment ownership/authorization, not trace-wide authorization.

A segment is a set of spans produced by one UAG authorization scope and service-instance execution boundary. The local index must be able to bind returned spans to that segment without trusting remote attributes.

A practical local record may contain:

```text
trace_id
local_segment_id
local_root_span_id
owned_span_ids or an implementation-safe local span membership mapping
service_instance_id   # local trusted value
created_at
entry_point
room_id               # local only
project_id             # local only
principal_id           # local only when needed for private scope
private_scope
```

The exact storage representation is an implementation choice, but the security property is mandatory: ordinary-user authorization is evaluated per locally owned segment/span, never once for the whole distributed trace.

### 9.3 Local trace-authorization index

UAG must not infer query authorization from exported span attributes, resource attributes, service names, links, baggage, or pseudonyms.

When an authorized Agent trace/segment starts, UAG records local metadata sufficient to identify locally owned spans/segments and re-run current authorization later.

The index is UAG-local state, not OTel data.

It contains only identifiers already required for UAG authorization and does not store prompts, responses, tool bodies, Memory bodies, or exporter credentials.

### 9.4 Query authorization and filtering flow

For a non-admin Web query:

```text
browser asks for trace_id
   -> authenticate/revalidate current session
   -> find local authorization records for that trace
   -> no current local records? deny
   -> re-run current room/project/private-room authorization for each local segment
   -> server queries configured trace backend under the Phase 4D bounded-read contract
   -> classify each returned span against trusted local segment membership
   -> unindexed/non-local/unauthorized span? drop
   -> authorized local span
      -> project through versioned response allowlist
   -> no authorized spans remain? deny/not-found according to API contract
   -> return bounded partial trace view
```

Current policy wins. Historical membership or possession of the original trace is not sufficient if the user no longer has access.

For ordinary users, spans from another service/instance that are not represented in the local trusted authorization index are omitted even if they share the same trace ID.

Cross-instance federation of authorization metadata is **not** part of the first Phase 4D implementation. Adding it later requires a separate trusted-service authorization design.

If an omitted parent/linked span would otherwise reveal an unreturned span identifier, the response must not expose that identifier. The projected view may use a boolean such as `parent_omitted=true` rather than leaking an unauthorized span ID.

### 9.5 Cross-scope distributed traces

A distributed trace can legally contain segments associated with different rooms, projects, principals, or internal services.

The proxy must support partial views:

```text
trace T
  segment A -> room A -> user authorized -> include allowed local spans
  segment B -> room B -> user denied     -> omit
  segment C -> remote service, unindexed -> omit
```

Authorization for segment A never implies authorization for B or C.

Tests must cover a multi-instance trace in which different segments have different authorization scopes.

### 9.6 Versioned fail-closed response schema

The proxy must never pass through arbitrary backend trace JSON.

Ordinary-user responses use the complete `uag.trace_view.v1` metadata-only schema below; no draft extensions are implied:

```text
schema_version = "uag.trace_view.v1"
trace_id
partial
spans[]:
  span_id                   # only for an authorized local span
  parent_span_id            # only when the parent is also authorized and returned
  parent_omitted            # boolean when parent exists but is not returned
  name                      # bounded canonical/supported span name
  start_time
  end_time
  duration_ms
  status_code               # closed UAG-owned enum: UNSET | OK | ERROR
```

No `status_description`, `attributes`, or `events` container exists in v1. Unknown or malformed backend status maps to `UNSET`; arbitrary backend/provider status text is never copied.

The following backend structures are dropped in v1:

```text
status descriptions
all span attributes
raw resource attributes
raw instrumentation-scope attributes
all events
links
logs
backend/vendor extension fields
HTTP headers
request/response bodies
identity attributes
security/authentication attributes
exception messages/stacks
```

Unknown fields and unknown nested structures are dropped, not recursively returned. If safe attributes/events/descriptive status are needed later, they require an explicitly versioned schema revision with closed reviewed allowlists.

### 9.7 Content in trace-query responses

The initial ordinary-user `uag.trace_view.v1` response is metadata-only even if the external backend contains content captured under operator policy.

Content capture and trace-query authorization are separate capabilities. Enabling capture does not automatically grant ordinary users access to captured prompts/responses/tool data.

A later design may add a separate `trace_content_view` permission and content response schema, but that is out of scope for initial Phase 4D.

This separation prevents provider instrumentation, backend enrichment, or another service from smuggling content through an otherwise allowed trace query.

### 9.8 Admin/operator queries

A separately authorized administrator/operator path may query broader traces according to existing server-side admin policy.

This authority comes from UAG auth/authz, never OTel attributes or external backend roles supplied by the browser.

Even admin-facing UAG proxy responses should use an explicit schema or an explicitly documented operator-only raw-backend mode; ordinary-user response rules never downgrade automatically.

### 9.9 Missing local authorization record

For ordinary users, missing local authorization metadata fails closed.

UAG does not fall back to trusting pseudonymous labels, span names, baggage, remote resource attributes, remote service names, trace links, or caller-supplied scope fields.

### 9.10 Backend abstraction and bounded reads

The query proxy uses a provider-neutral adapter such as:

```text
TraceQueryBackend
  get_trace(trace_id, limits)
```

Backend-specific Jaeger/Grafana/vendor code stays behind adapters. Backend credentials remain server-side. Query failure never changes normal Agent execution.

The initial ordinary-user bounded-read contract is normative:

```text
backend deadline:               5 seconds
maximum decoded backend bytes:  8 MiB
maximum backend spans fetched:   2000
maximum spans per backend page:   500
maximum backend pages:               4
maximum authorized spans returned:  500
```

Adapters must enforce byte/deadline/page/span ceilings while retrieving data rather than first materializing an unbounded response. Reaching a safe truncation boundary produces `partial=true`; if a safe bounded partial result cannot be established, the query fails closed with no backend payload. Retries and pagination share the same aggregate per-query ceilings. Returned authorized spans are deterministically ordered by `(start_time, span_id)` before applying the output limit.

## 10. Retention and deletion

Phase 4 does not imply that deleting UAG data deletes already exported telemetry.

Operators must understand:

- deleting a room does not automatically erase external traces;
- deleting Memory does not automatically erase content already exported;
- rotating a pseudonym key does not rewrite historical traces;
- trace-query authorization index retention is separate from external trace retention;
- content-capture deployments need explicit backend retention policy.

For ordinary-user trace queries, expiration/removal of the local authorization index causes access to fail closed even if the external backend still retains the trace.

## 11. Multi-user and shared-room rules

Phase 1-3 isolation remains mandatory.

- one user turn remains one logical Agent trace;
- a WebSocket/room is not a long-lived trace root;
- a shared-room trace may contain context derived from multiple authorized sources, so content capture requires particular caution;
- content capture does not grant trace-query access;
- pseudonymous room/project labels do not grant trace-query access;
- trace-query authorization is evaluated independently for every query and every returned local segment;
- an authorization decision for one distributed-trace segment never authorizes another segment.

## 12. Failure behavior

Every Phase 4 feature is best-effort and isolated from UAG execution.

Examples:

```text
redactor fails or provenance is uncertain
  -> omit content
  -> continue Agent/tool/model execution

correlation key missing/weak/reused
  -> omit pseudonyms
  -> continue tracing

SDK instrumentor import/version/scoping mismatch
  -> disable nested provider instrumentation
  -> continue canonical UAG chat tracing

trace backend unavailable or bounded-read contract cannot be satisfied
  -> trace query returns bounded server error
  -> Agent execution remains unaffected
```

A failure must never broaden capture, correlation, instrumentation scope, or access.

## 13. Audit and diagnostics

Phase 4 configuration changes and query denials may generate existing structured UAG events using safe, low-cardinality metadata.

Useful event families may include:

```text
observability.capture.enabled
observability.capture.source_blocked
observability.capture.redaction_failed
observability.correlation.unavailable
observability.provider_instrumentation.unavailable
observability.trace_query.allowed
observability.trace_query.partial
observability.trace_query.denied
observability.trace_query.backend_error
```

These events must not include captured content, secrets, raw correlation keys, raw authentication material, raw UAG authorization identifiers, or unbounded backend responses.

## 14. Testing requirements

### 14.1 Content capture

Verify:

- OFF remains metadata-only;
- master gate ON with no categories captures nothing;
- each semantic category is independent;
- selecting `user_input` does not capture assistant/tool/system/reasoning fields;
- forbidden provenance overrides an allowed category;
- an inline file body inside `tool_result` is omitted;
- an inline artifact body inside `tool_result` is omitted;
- inline Memory/retrieval data inside `tool_result` is omitted;
- authentication/session/credential outputs are omitted even under innocuous keys such as `value`;
- nested values inherit forbidden provenance;
- `Bearer ...` and `Basic ...` values are redacted independent of key name;
- JWT-like compact tokens and PEM private-key blocks are redacted/dropped;
- opaque security-sensitive structures fail closed;
- always-blocked identity/auth/session keys remain blocked;
- reasoning remains excluded;
- exact capture-bound defaults/ranges and invalid-bound disablement are enforced;
- malformed/unserializable/redactor-failure values do not fail runtime execution;
- content never becomes metric dimensions, baggage, resources, auth inputs, or storage keys.

### 14.2 Pseudonymous correlation

Verify:

- feature OFF emits no pseudonyms;
- weak/short/passphrase correlation keys are rejected;
- correlation key reuse with a known auth/token/provider credential is rejected where detectable;
- a generated 256-bit dedicated key is accepted;
- identical raw identifier + same key/scope/kind is stable;
- different kinds produce different pseudonyms;
- different deployment scopes produce different pseudonyms;
- adversarial component tuples that collide under naive concatenation differ under length-prefixed framing;
- exported pseudonyms equal the first 128 digest bits and are exactly 32 lowercase hexadecimal characters;
- shorter truncation, uppercase hex, base64, or base64url output is rejected by conformance tests;
- key rotation changes pseudonyms;
- raw identifier and key never appear in exported spans/events;
- pseudonyms are absent from metrics, baggage, and resource attributes;
- pseudonyms cannot affect auth/authz/Memory/trace-query behavior.

### 14.3 Provider SDK instrumentation

Verify:

- OFF installs/initializes no SDK instrumentor;
- selected provider instrumentation remains nested under canonical `chat`;
- an unselected provider that shares the same SDK/client class emits no SDK diagnostic span;
- calls outside an active canonical UAG `chat` guard emit no SDK diagnostic span;
- selected and unselected OpenAI-compatible providers remain isolated;
- logical selector `claude` selects the Anthropic SDK path and unknown `anthropic` does not silently alias it;
- no duplicate canonical LLM span appears;
- SDK content capture cannot bypass UAG provenance/category/redaction policy;
- unsupported globally emitting instrumentors fail closed to disabled;
- instrumentor import/setup/runtime failure does not alter model results.

### 14.4 Trace-query authorization

Verify:

- unauthenticated query is denied;
- trace ID possession alone grants nothing;
- missing local authorization record fails closed;
- current room/project/private-room revocation denies subsequent query;
- one authorized local segment does not authorize another local segment with a different scope;
- remote/unindexed spans sharing the same trace ID are omitted;
- a cross-instance trace with different room/project authorization returns only authorized local segments;
- an omitted parent/linked span does not leak its span ID;
- pseudonyms and remote span/resource attributes cannot grant access;
- backend credentials never reach the client;
- backend failure does not affect Agent execution;
- oversized traces respect byte/span/page/deadline/output ceilings and deterministic partial behavior.

### 14.5 Trace response schema

Verify:

- ordinary-user responses declare `uag.trace_view.v1`;
- the complete span shape contains only the explicitly listed metadata fields;
- `status_description`, `attributes`, and `events` are absent;
- status is restricted to `UNSET`, `OK`, or `ERROR`, with malformed/unknown backend values mapping to `UNSET`;
- unknown backend fields and nested structures are dropped;
- resource attributes, links, arbitrary events, logs, headers, identities, exception text, and vendor extensions are absent;
- filtered or safely truncated distributed traces are marked partial;
- parent identifiers are included only when the parent is authorized and returned;
- captured prompt/response/tool content is absent from the initial ordinary-user schema even when capture exists in the backend.

### 14.6 Compatibility

All Phase 4 slices retain the normal repository gates:

- Python 3.11 / 3.13 / 3.14 compatibility;
- Ruff;
- Black;
- I18N/tool-catalog checks where applicable;
- full pytest;
- OTel disabled behavior unchanged.

## 15. Acceptance criteria

Phase 4 implementation is acceptable only when all applicable conditions are true:

1. Every Phase 4 capability is OFF by default.
2. The content master flag alone captures nothing.
3. Content requires an explicit semantic category and permitted trusted provenance.
4. Forbidden provenance overrides allowed categories, including inline tool-returned file/artifact/Memory/retrieval/authentication bodies.
5. Authentication/session/credential/security-opaque typed values are excluded before generic content redaction.
6. Mandatory value-level secret redaction operates on values as well as keys and fails closed for uncertain security-sensitive structures.
7. Reasoning/system/developer content remains excluded.
8. Content is bounded by finite validated defaults/ranges and never enters metrics, baggage, resources, auth decisions, or storage/routing keys.
9. Pseudonymous correlation requires a dedicated CSPRNG-generated key with at least 256 bits of entropy and purpose isolation from security credentials.
10. Pseudonym HMAC input uses canonical unambiguous length-prefixed framing, and the initial exported representation is fixed to the first 128 digest bits as exactly 32 lowercase hexadecimal characters.
11. Pseudonyms are trace-only diagnostics and never security identities or query authorization inputs.
12. Provider SDK instrumentation is selected-call scoped and uses UAG logical provider IDs.
13. Provider SDK diagnostics remain nested beneath UAG canonical spans and introduce no duplicate logical LLM spans.
14. Provider instrumentors cannot bypass UAG content policy.
15. Ordinary-user trace queries revalidate current UAG auth/authz and authorize/filter every returned local segment/span.
16. Authorization for one distributed-trace segment never authorizes another segment solely because it shares a trace ID.
17. Unindexed/remote spans fail closed to omission for ordinary users.
18. Ordinary-user trace responses use the closed metadata-only `uag.trace_view.v1` field set and drop unknown backend structures.
19. Initial ordinary-user trace responses are metadata-only even if captured content exists in the backend.
20. Ordinary-user backend retrieval is bounded before authorization filtering by explicit deadline/byte/span/page limits and output truncation is deterministic.
21. Missing/failed privacy, correlation, instrumentation, query, or backend components never broaden access and never fail Agent execution.
22. Existing Phase 1-3 privacy, trust, propagation, authorization, and canonical-span behavior remains unchanged.

## 16. Explicitly deferred work

The following require later design review and are not implicitly enabled by Phase 4:

- capture of reasoning/chain-of-thought;
- capture of system/developer instructions;
- capture of Memory/retrieval/file/artifact bodies;
- capture of authentication/session/credential material;
- ordinary-user viewing of captured prompt/response/tool content;
- cross-instance federation of trace authorization indexes;
- using pseudonyms for security or storage identity;
- generic global provider/HTTP auto-instrumentation;
- direct ordinary-user access to raw Jaeger/Grafana/vendor trace APIs;
- telemetry-driven authorization decisions.