# OpenTelemetry Phase 4 Security and Configuration Contract

Status: Normative Phase 4 companion  
Parent scope: `docs/UAG_OPENTELEMETRY_PHASE4_SCOPE.md`  
Traversal/rendering contract: `docs/UAG_OPENTELEMETRY_PHASE4_TRACE_NAME_AND_TRAVERSAL_CONTRACT.md`  
Scalar/timing contract: `docs/UAG_OPENTELEMETRY_PHASE4_SCALAR_AND_TIMING_CONTRACT.md`  
Pseudonym contract: `docs/UAG_OPENTELEMETRY_PHASE4_PSEUDONYM_OUTPUT_CONTRACT.md`  
Applies to: Phase 4A-4D security, configuration, provenance, ordinary-user trace schema, and query bounds

This document is the normative owner for Phase 4 configuration precedence/parsing, correlation-key credential encoding, deployment-scope validation, field-level provenance, ordinary-user `uag.trace_view.v1` field/identifier/status semantics, and trace-query resource ceilings. Content traversal/rendering, primitive scalar/timing normalization, and pseudonym construction/output are delegated to their topic contracts.

## 1. Configuration precedence and CLI surface

Phase 4 uses one precedence rule:

```text
explicit CLI/application setting
    > UAGENT_* environment setting
    > safe default
```

Effective core `--otel` / `--no-otel` is authoritative. If core OTel is OFF, every Phase 4 capability is inactive.

Public Phase 4 CLI:

```text
--otel-capture-content
--no-otel-capture-content
--otel-capture-categories <csv>
--otel-capture-max-field-chars <n>
--otel-capture-max-span-chars <n>

--otel-pseudonymous-correlation
--no-otel-pseudonymous-correlation
--otel-correlation-key-name <credential-name>
--otel-correlation-key-version <version>
--otel-deployment-scope <deployment-id>

--otel-provider-instrumentation <csv>
```

Environment equivalents:

```text
UAGENT_OTEL_CAPTURE_CONTENT
UAGENT_OTEL_CAPTURE_CATEGORIES
UAGENT_OTEL_CAPTURE_MAX_FIELD_CHARS
UAGENT_OTEL_CAPTURE_MAX_SPAN_CHARS
UAGENT_OTEL_PSEUDONYMOUS_CORRELATION
UAGENT_OTEL_CORRELATION_KEY_NAME
UAGENT_OTEL_CORRELATION_KEY_VERSION
UAGENT_OTEL_DEPLOYMENT_SCOPE
UAGENT_OTEL_PROVIDER_INSTRUMENTATION
```

Rules:

- all entry points use the shared observability resolver;
- positive/negative duplicate booleans use the last explicit CLI flag;
- invalid explicit higher-precedence values do not silently fall back to lower-precedence values unless a topic contract explicitly says so;
- browser/WebSocket/A2A/MCP/tool/provider/trace/baggage/header/query/cookie data cannot alter settings;
- no CLI or environment variable accepts raw correlation key material.

### 1.1 Controlled-content categories

Closed vocabulary:

```text
user_input
assistant_output
tool_arguments
tool_result
```

Parsing:

- missing/empty -> empty set;
- non-empty -> split on comma;
- strip ASCII space/tab around each token only;
- no case folding/Unicode normalization;
- each non-empty token must exactly match the closed vocabulary;
- duplicates deduplicate as a set;
- empty or unknown token invalidates category configuration and disables controlled content capture for that process;
- invalid categories never disable metadata-only tracing.

### 1.2 Controlled-content numeric bounds

```text
MAX_FIELD_CHARS
  default 2048
  valid   64..16384

MAX_SPAN_CHARS
  default 8192
  valid   256..65536
```

Rules:

- missing -> default;
- non-integer/zero/negative/out-of-range -> invalid;
- `MAX_SPAN_CHARS >= MAX_FIELD_CHARS` required;
- any invalid bound disables controlled content capture for the process;
- never substitute an unbounded fallback.

Runtime candidate/structure/renderer/ledger limits are owned by the traversal contract.

### 1.3 Provider selectors

Provider selectors are UAG logical IDs. Initial example:

```text
openai,claude
```

`claude` is Anthropic SDK path; `anthropic` is not an alias.

Parsing uses comma separation plus surrounding ASCII space/tab trimming, no case folding/Unicode normalization. Missing/empty -> OFF. Unknown/malformed token enables nothing for that token and produces a normalized diagnostic; valid sibling selectors remain independently active.

## 2. Stable deployment scope

Resolution:

```text
--otel-deployment-scope
    > UAGENT_OTEL_DEPLOYMENT_SCOPE
    > no value
```

No hostname/PID/random/CWD/repository/machine-local fallback.

### 2.1 Exact validation and HMAC input semantics

Validate without trimming/canonical rewrite.

Accept exactly 1-128 Unicode scalar values and reject:

- empty;
- leading/trailing Unicode whitespace;
- any Unicode control;
- any surrogate `U+D800..U+DFFF`;
- >128 scalar values.

Internal non-control whitespace is permitted. No Unicode/case/path normalization occurs.

The exact validated string is framed into HMAC. Thus `prod` is valid; ` prod` and `prod ` are invalid.

The scope must be stable across intended replicas and distinct across deployments that must not correlate. It is never authorization/identity/routing/storage/Memory/credential state and is not exported raw by default.

Missing/invalid scope disables pseudonym emission only.

## 3. Correlation-key credential contract

### 3.1 Credential name

Effective credential name resolves by normal precedence, with safe default exactly:

```text
observability/correlation
```

An explicit credential name must be an exact string of 1-128 Unicode scalar values with:

- no leading/trailing Unicode whitespace;
- no control characters;
- no surrogates.

The exact validated name is passed to the existing credential store; it is not trimmed/canonicalized for lookup. Invalid explicit name disables pseudonym emission and does not fall back to the default.

### 3.2 Credential kind/purpose metadata

Initial correlation-key credential must be stored as:

```text
CredentialKind.OTHER
metadata["purpose"] = "observability_pseudonym_v1"
metadata["key_version"] = <effective validated correlation-key version>
```

The configured key version must exactly equal credential metadata `key_version`. Missing/mismatched purpose/version metadata disables pseudonym emission.

This purpose/version binding is server-side validation metadata only and is never exported as raw credential metadata.

### 3.3 Secret encoding

The credential `secret` is exactly the unpadded base64url encoding of 32 raw key bytes.

Canonical form:

```text
43 ASCII characters from [A-Za-z0-9_-]
no '=' padding
base64url-decode -> exactly 32 bytes
re-encode(decoded) -> exactly the original 43-character string
```

Any non-canonical, wrong-length, decode-failing, or non-32-byte secret disables pseudonym emission. Arbitrary passphrases are not accepted.

The raw 32-byte key must be generated with a cryptographically secure RNG. Entropy origin cannot be proven solely from the bytes, so CSPRNG generation is a provisioning requirement; UAG's own generator, if provided, must use an OS cryptographic RNG.

No raw key environment fallback is supported.

### 3.4 Purpose isolation/reuse

Correlation key material must not equal/alias any authentication/token-signing/provider/A2A/MCP/OIDC/OAuth/session key known to UAG. Where UAG can compare known material or managed metadata, detected reuse disables pseudonym emission. The dedicated purpose/key-version metadata never weakens this requirement.

Exact HMAC framing, kind vocabulary, raw-ID bounds, pseudonym output, and exported `uag.correlation.key_version` association are owned by the pseudonym contract.

## 4. Field-level provenance for controlled content

### 4.1 Closed provenance vocabulary

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

Hard-denied classes:

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

Hard denial overrides category selection recursively. Payload data cannot self-assert provenance; trusted UAG code assigns it.

### 4.2 Field-level body classification

Examples:

```text
file write:
  path -> separately constructed safe metadata if needed
  content -> file (forbidden)

attachment:
  filename/type -> safe only if explicitly reconstructed
  data/base64/body -> file/artifact (forbidden)

artifact:
  id/name/type -> safe only if explicitly reconstructed
  body/bytes/text -> artifact (forbidden)

Memory/retrieval:
  derived count/type/status -> safe only if explicitly reconstructed
  record/query/body/result -> memory/retrieval (forbidden)
```

Outer `tool_argument`, `ordinary_tool_result`, or `user_message` never makes forbidden descendants eligible.

### 4.3 Unannotated body-capable composites fail closed

- known body fields require trusted provenance;
- unannotated child of a body-capable composite is omitted;
- unknown attachment/provider/tool composite is omitted absent reviewed field adapter;
- data URLs/base64/bytes/buffers/file-like/body wrappers are forbidden absent safe metadata extractor;
- safe extractor creates new bounded scalar metadata, never relabels opaque bodies.

### 4.4 Source exclusion before content redaction

Drop before generic secret handling:

- OIDC/OAuth/login/callback/session structures;
- credential/provider secret resolution;
- Authorization/Cookie credential containers;
- A2A bearer/MCP token structures;
- Memory/retrieval records/queries;
- file/artifact bodies;
- reasoning/thinking/analysis fields;
- system/developer stores;
- unclassifiable security-sensitive structures.

## 5. Secret handling boundary

Secret scanning occurs only after the traversal/scalar contracts prove work is bounded.

Reviewed high-confidence classes include:

- `Bearer ...` / `Basic ...` values independent of key name;
- compact JWT-like forms;
- PEM private-key blocks/comparable key encodings;
- recognized credential-bearing URI userinfo;
- known secret wrapper types before conversion;
- trusted credential-bearing tags.

Recursive always-blocked mapping-key rules, exact replacement marker, mapping-key failure behavior, post-redaction field checks, renderer, and span ledger are owned by the traversal contract.

Redactor exception/security ambiguity omits the candidate and never fails user execution.

## 6. Ordinary-user `uag.trace_view.v1` is closed metadata-only

The proxy constructs v1 field-by-field and never forwards arbitrary backend JSON.

### 6.1 Exact top-level schema

```text
schema_version : exact "uag.trace_view.v1"
trace_id       : canonical W3C trace-id string
partial        : JSON boolean
spans          : JSON array, maximum 500 returned spans
```

No other top-level field exists.

`trace_id` grammar:

```text
^[0-9a-f]{32}$
not all zeros
```

Invalid ordinary-user input is rejected before local-index/backend lookup. No trim/case-fold/prefix stripping. Response trace ID comes from validated query/local state, never arbitrary backend text.

### 6.2 Exact span schema

Every returned span contains exactly:

```text
span_id
parent_span_id    # optional only when returned parent is present
parent_omitted
name
start_time
end_time
duration_ms
status_code
```

Types:

```text
span_id:
  ^[0-9a-f]{16}$ and not all zeros

parent_span_id when present:
  same grammar as span_id

parent_omitted:
  JSON boolean

name:
  AGENT | LLM | TOOL | PROVIDER_SDK | INTERNAL | UNKNOWN
  safe mapping owned by traversal contract

start_time/end_time/duration_ms:
  JSON integers under scalar/timing contract

status_code:
  UNSET | OK | ERROR
```

Invalid span ID/timing omits that span rather than echoing arbitrary text.

### 6.3 Duplicate/mismatched backend identity is fail closed

Within one bounded backend result:

- if a backend record explicitly carries a trace ID, it must exactly equal the canonical requested trace ID or that record is dropped;
- after span-ID validation, if the same `span_id` occurs in more than one fetched record, **all records with that duplicated ID are omitted** and `partial=true`;
- duplicate IDs are never resolved by trusting resource attributes, service names, arrival order, or remote metadata;
- returned `spans[]` therefore has unique span IDs.

This prevents ambiguous remote records from impersonating a locally indexed span ID.

### 6.4 Parent semantics

- no parent: omit `parent_span_id`, `parent_omitted=false`;
- returned authorized valid parent: include validated parent ID, `parent_omitted=false`;
- parent known to exist but filtered/invalid/truncated/not returned: omit ID, `parent_omitted=true`;
- malformed raw parent ID is never echoed; the child may be returned with `parent_omitted=true` if the child itself is otherwise valid/authorized.

### 6.5 Status mapping

Closed values:

```text
UNSET
OK
ERROR
```

Unknown/malformed backend status -> `UNSET`. Never copy status description/exception/URL/request text.

### 6.6 Explicitly absent

V1 contains no:

```text
status_description
attributes
events
links
resource/instrumentation attributes
logs
baggage
HTTP/provider request metadata
captured content
pseudonyms/key-version attributes
raw identity/auth fields
vendor extensions
exception messages/stacks
```

Unknown structures are dropped. Future fields require a reviewed new schema version.

### 6.7 `partial` semantics

`partial=true` when UAG knowingly omits safely relevant data because of:

- backend deadline/byte/page/span truncation;
- 500-span output limit;
- authorization/local-ownership filtering;
- duplicate/mismatched/invalid span projection;
- invalid timing/ID;
- omitted known parent;
- other supported fail-closed projection omission.

`partial=false` only when no known omission exists within bounded retrieved data.

## 7. Local trace authorization is independent of telemetry

Trace/span IDs, pseudonyms, key versions, baggage, backend/resource attributes, service names, links, and provider metadata never authorize.

When an authorized local Agent segment starts, UAG records local trusted state sufficient to bind local spans to current scope, for example:

```text
trace_id
local_segment_id
local_root_span_id
owned_span_ids / safe local membership map
service_instance_id
created_at
entry_point
room_id
project_id
principal_id when private scope requires it
private_scope
```

The index is local UAG state, not exported telemetry, and stores no prompts/responses/tool/Memory bodies or backend credentials.

Provider-SDK child spans are eligible for ordinary-user v1 only if their IDs are registered as locally owned under the active selected-call guard; otherwise they are unindexed and omitted.

Current authorization is evaluated per local segment/span. Cross-instance authorization-index federation is deferred.

## 8. Ordinary-user query flow

```text
validate canonical trace_id
  -> authenticate/revalidate session
  -> find local authorization records
  -> none? deny
  -> re-run current authz per local segment
  -> bounded backend query
  -> validate IDs / duplicate conditions
  -> classify against trusted local membership
  -> drop non-local/unindexed/unauthorized
  -> closed v1 projection
  -> no authorized valid spans remain? deny/not-found under API contract
  -> return bounded response
```

Historical access/trace possession is insufficient; current policy wins.

## 9. Trace-query resource limits

Supported ordinary-user adapter must enforce bounds without first materializing an unbounded response.

Exact aggregate per-query limits:

```text
monotonic elapsed deadline:        5 seconds
maximum decoded backend bytes:     8 MiB
maximum backend spans fetched:     2000
maximum spans per backend page:    500
maximum backend pages:             4
maximum authorized spans returned: 500
```

Rules:

- one monotonic five-second budget starts at query start and is not reset by retry/page;
- retries/pages share all ceilings;
- use backend pagination/limits where available;
- enforce decoded byte count while application bytes become available after content decoding, not after full-body load;
- additionally bound compressed/wire reads where possible; wire cap never substitutes for decoded cap;
- stop when any bound is reached;
- authorize/filter only bounded fetched data;
- order returned spans by normalized `(start_time, span_id)` before output cap;
- safe truncation -> `partial=true`;
- inability to establish safe bounded partial result -> bounded server error, no backend payload;
- truncation never relaxes auth or exposes omitted IDs;
- backend failure never changes Agent execution.

## 10. Required regressions

### Configuration/credentials

- CLI overrides env and `--no-otel` suppresses all Phase 4;
- capture bound/category invalidity fails closed exactly as specified;
- provider selector behavior isolates valid/unknown tokens;
- default correlation credential name is exactly `observability/correlation`;
- leading/trailing whitespace/control/surrogate/oversize credential names fail closed;
- correlation credential must be `CredentialKind.OTHER` with exact purpose and matching key-version metadata;
- canonical 43-char unpadded base64url decodes to exactly 32 key bytes;
- padded/noncanonical/wrong-length/passphrase secrets fail closed;
- no raw key env/CLI input exists.

### Deployment/provenance

- exact deployment-scope validation/hashing behavior is consistent across replicas;
- forbidden body/auth/Memory/retrieval/file/artifact/reasoning sources never become eligible through nesting;
- unannotated body-capable children fail closed.

### Trace schema/identity

- invalid/uppercase/zero/overlong trace ID rejected before lookup;
- invalid/uppercase/zero span ID omitted;
- explicit backend trace-ID mismatch record omitted;
- duplicate span IDs omit all duplicates and set partial;
- returned IDs are unique and canonical;
- name/timing/status remain closed typed fields;
- unauthorized/missing/malformed parent ID never leaks;
- undeclared backend fields/content/pseudonyms/events/attrs never appear;
- known filtering/truncation/projection omissions set partial.

### Query bounds

- decoded byte/page/span/deadline/output ceilings are enforced across retries;
- output ordering is deterministic after normalization;
- unsupported unbounded adapter returns no raw payload.

## 11. Fixed Phase 4 decisions

- Configuration and correlation credential parsing are explicit/fail-closed.
- Correlation key secret is canonical unpadded base64url of exactly 32 bytes with dedicated purpose/version metadata.
- Deployment scope is exact, untrimmed, and bounded.
- Field/node provenance hard denial overrides content categories.
- Privacy/secret scanning runs only after bounded traversal/scalar preflight.
- Ordinary-user v1 has canonical trace/span IDs, unique returned span IDs, closed name/status/timing types, and no arbitrary nested backend data.
- Authorization derives only from current UAG-local state.
- Backend retrieval uses one aggregate bounded query budget.