# OpenTelemetry Phase 4 Security and Configuration Contract

Status: Normative Phase 4 companion  
Parent scope: `docs/UAG_OPENTELEMETRY_PHASE4_SCOPE.md`  
Traversal/rendering contract: `docs/UAG_OPENTELEMETRY_PHASE4_TRACE_NAME_AND_TRAVERSAL_CONTRACT.md`  
Scalar/timing contract: `docs/UAG_OPENTELEMETRY_PHASE4_SCALAR_AND_TIMING_CONTRACT.md`  
Pseudonym contract: `docs/UAG_OPENTELEMETRY_PHASE4_PSEUDONYM_OUTPUT_CONTRACT.md`  
Applies to: Phase 4A-4D security, configuration, provenance, ordinary-user trace schema, and query bounds

This document owns Phase 4 configuration precedence/parsing, correlation-key credential encoding, deployment-scope validation, field-level provenance, ordinary-user `uag.trace_view.v1` field/identifier/status semantics, and trace-query resource ceilings. Content traversal/rendering, primitive scalar/timing normalization, provider SDK diagnostic projection, and pseudonym construction/output are owned by their topic contracts/parent scope.

## 1. Configuration precedence and CLI surface

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
- duplicate positive/negative booleans use the last explicit CLI flag;
- invalid explicit higher-precedence value never silently falls back unless its topic contract explicitly says so;
- browser/WebSocket/A2A/MCP/tool/provider/trace/baggage/header/query/cookie data cannot alter settings;
- no CLI/environment setting accepts raw correlation-key material.

### 1.1 Exact source-specific scalar parsers

Phase 4 settings are parsed before precedence fallback is considered. A higher-precedence value that is present but invalid fails closed for the affected feature and does not fall back to a lower-precedence source.

Boolean settings initially are exactly:

```text
capture content
pseudonymous correlation
```

Their source grammars are:

- CLI: presence-only flags `--otel-capture-content` / `--no-otel-capture-content` and `--otel-pseudonymous-correlation` / `--no-otel-pseudonymous-correlation`; no `=<value>` or following value token is accepted; last explicit positive/negative flag wins;
- environment: value must first be an exact built-in `str`; apply Python `str.strip()` followed by `str.lower()` and accept only `1`, `true`, `yes`, `on` as true or `0`, `false`, `no`, `off` as false; every other present value is invalid and resolves the affected feature to OFF without fallback;
- application/programmatic: value must be exact built-in `bool`; `int`/string/custom truthy objects are invalid; no `bool(value)` coercion is permitted.

Numeric Phase 4 settings initially are exactly the two controlled-content bounds. Source grammars are:

- CLI/environment raw value must be exact built-in `str` and match canonical ASCII decimal `0|[1-9][0-9]*`; no sign, whitespace, separator, exponent, leading zero on a multi-digit value, or Unicode digit is accepted;
- application/programmatic value must be exact built-in `int`, with `bool` explicitly rejected;
- parse only after the lexical/type gate, then apply the ranges in section 1.3;
- launcher/GUI/Web/A2A code must not use a more permissive parser and then pass a normalized value as if it were the original explicit setting.

String and CSV settings use exact built-in `str` values only. CLI arguments are passed as their raw token strings to the shared resolver; environment values must already be exact built-in strings; programmatic callers may not pass bytes/custom string-like objects. Topic sections below define each string/CSV grammar.

### 1.2 Controlled-content category parsing

Closed vocabulary:

```text
user_input
assistant_output
tool_arguments
tool_result
```

- missing/empty -> empty set;
- non-empty -> split on comma;
- strip only surrounding ASCII space/tab from each token;
- no case folding/Unicode normalization;
- every non-empty token must exactly match the closed vocabulary;
- duplicates deduplicate as a set;
- empty/unknown token invalidates the category configuration and disables controlled content capture for the process;
- metadata-only tracing continues.

### 1.3 Controlled-content numeric bounds

```text
MAX_FIELD_CHARS default 2048, valid 64..16384
MAX_SPAN_CHARS  default 8192, valid 256..65536
MAX_SPAN_CHARS >= MAX_FIELD_CHARS
```

Missing -> default. Present values must first satisfy section 1.1's exact source grammar. Zero/negative/out-of-range/inconsistent values disable controlled content capture; never substitute an unbounded fallback.

Runtime candidate/structure/renderer/ledger limits are owned by the traversal contract.

### 1.4 Provider selector parsing

Initial Phase 4C supported logical provider selector set is exactly:

```text
openai
claude
```

`claude` selects the Anthropic SDK path; `anthropic` is not an alias. Adding another selector requires a reviewed Phase 4C provider adapter plus an update to the parent provider-diagnostics contract.

Parsing:

- missing/empty -> OFF;
- value is exact built-in `str` under section 1.1;
- split on comma;
- strip only surrounding ASCII space/tab;
- no case folding/Unicode normalization;
- exact `openai`/`claude` tokens enable only their corresponding reviewed integration;
- unknown/empty/malformed token enables nothing for that token and emits only a normalized diagnostic;
- valid sibling token remains independently active;
- provider payload/endpoint response cannot alter the selected logical provider ID.

## 2. Stable deployment scope

Resolution:

```text
--otel-deployment-scope
    > UAGENT_OTEL_DEPLOYMENT_SCOPE
    > no value
```

No hostname/PID/random/CWD/repository/machine-local fallback.

Validation occurs without trimming/canonical rewrite. The effective value must be an exact built-in string containing 1-128 Unicode scalar values and no:

- leading/trailing Unicode whitespace;
- Unicode control character;
- surrogate `U+D800..U+DFFF`.

No generic `str()` conversion, Unicode normalization, case folding, or path normalization occurs. The exact validated string is framed into HMAC. `prod` is valid; ` prod` / `prod ` are invalid.

The scope is stable across intended replicas, distinct across deployments that must not correlate, never caller-controlled, never authorization/identity/routing/storage/Memory/credential state, and not exported raw by default.

Missing/invalid scope disables pseudonym emission only.

## 3. Correlation-key credential contract

### 3.1 Credential name

Safe default:

```text
observability/correlation
```

An explicit effective credential name must be an exact built-in string containing 1-128 Unicode scalar values with no leading/trailing Unicode whitespace, controls, or surrogates. No generic conversion or canonicalization occurs before lookup.

Invalid explicit name disables pseudonym emission and does not fall back to the default.

### 3.2 Credential runtime type and metadata contract

Before any equality, length, alphabet, decoding, or conversion operation:

- the resolved credential object must expose the reviewed `CredentialKind` value without invoking a custom conversion hook;
- `credential.secret` must satisfy `type(secret) is str`;
- `credential.metadata` must satisfy `type(metadata) is dict`;
- `metadata["purpose"]` and `metadata["key_version"]` must both exist and each satisfy `type(value) is str`;
- required metadata keys are looked up only by the literal built-in string keys `purpose` and `key_version`;
- bytes, string subclasses, custom mappings, proxy values, custom equality objects, or coercible wrappers fail closed before comparison/decoding.

Initial correlation credential must then satisfy:

```text
CredentialKind.OTHER
metadata["purpose"] = "observability_pseudonym_v1"
metadata["key_version"] = <effective validated key version>
```

Configured key version must exactly equal metadata `key_version`. Missing/mismatched purpose or version disables pseudonym emission. Raw credential metadata is not exported.

### 3.3 Secret encoding

Credential `secret` is exactly the canonical unpadded base64url encoding of 32 raw key bytes:

```text
native string length = 43
ASCII only [A-Za-z0-9_-]
no '=' padding
base64url decode -> exactly 32 bytes
canonical re-encode -> exact original 43-character string
```

The exact built-in-string gate from section 3.2 occurs first. Native length/alphabet are checked before decoding. Wrong length/alphabet/noncanonical/decode failure/non-32-byte secret disables pseudonym emission. Arbitrary passphrases are not accepted.

The 32 raw bytes are provisioned from a cryptographic RNG. UAG's own generator, if provided, uses an OS CSPRNG. No raw key environment/CLI fallback exists.

### 3.4 Purpose isolation/reuse

Correlation key material must not equal/alias known authentication/token-signing/provider/A2A/MCP/OIDC/OAuth/session key material. Where UAG can compare known material/managed metadata, detected reuse disables pseudonym emission.

Exact HMAC/kind/raw-ID/output/version rules belong to the pseudonym contract.

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

Hard-denied:

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

Hard denial overrides category selection recursively. Payload data cannot self-assert provenance.

### 4.2 Body-capable field classification

Examples:

```text
file write:
  path -> separately reconstructed safe metadata if needed
  content -> file (forbidden)

attachment:
  filename/type -> safe only if separately reconstructed
  inline data/base64/body -> file/artifact (forbidden)

artifact:
  id/name/type -> safe only if separately reconstructed
  body/bytes/text -> artifact (forbidden)

Memory/retrieval:
  derived count/type/status -> safe only if separately reconstructed
  record/query/body/result -> memory/retrieval (forbidden)
```

Outer allowed provenance never makes forbidden descendants eligible.

### 4.3 Unannotated body-capable composites fail closed

Known body fields require trusted provenance. Unknown/unannotated body-capable children/composites are omitted. Data URLs/base64/bytes/buffers/file-like/body wrappers remain forbidden unless a reviewed extractor creates new bounded scalar metadata.

### 4.4 Typed-source exclusion before secret handling

Drop before generic content secret handling:

- OIDC/OAuth/login/callback/session;
- credential/provider secret resolution;
- Authorization/Cookie structures;
- A2A bearer/MCP token structures;
- Memory/retrieval records/queries;
- file/artifact bodies;
- reasoning/thinking/analysis;
- system/developer stores;
- unclassifiable security-sensitive structures.

## 5. Secret-handling boundary

Secret/privacy scanning occurs only after traversal/scalar contracts establish bounded work.

The initial textual high-confidence detection set is closed and is owned by section 5.2 of the traversal/rendering contract: Authorization-scheme credentials, compact JWT-like tokens, fixed PEM private-key begin markers, and credential-bearing URI userinfo. Trusted secret wrappers/tags are excluded by typed provenance before textual scanning.

For every recognized match the implementation must perform the exact traversal-contract action: redact every recognized Authorization/JWT match with `[REDACTED]`, or omit the whole candidate for PEM/credential-URI/key/security-ambiguity cases. A recognized secret is never exported unchanged. “Best effort,” “may redact,” or implementation-defined pass-through is non-conformant.

Recursive always-blocked mapping-key behavior, exact replacement marker, post-redaction field checks, renderer, and span ledger belong to the traversal contract.

Redactor exception/security ambiguity omits the candidate and never fails user execution.

## 6. Ordinary-user `uag.trace_view.v1` is closed metadata-only

The proxy constructs v1 field-by-field and never forwards arbitrary backend JSON.

### 6.1 Exact top-level schema and trace-id validation

```text
schema_version : exact "uag.trace_view.v1"
trace_id       : canonical W3C trace-id
partial        : JSON boolean
spans          : JSON array, max 500 returned
```

No other top-level field exists.

A query `trace_id` must be an exact built-in string. Validate in this order without conversion:

```text
native length == 32
all characters are lowercase ASCII [0-9a-f]
value is not 00000000000000000000000000000000
```

Anything else is rejected before local-index/backend lookup. No regex/classifier is run before the fixed native-length check; no trim/case-fold/prefix stripping occurs. Response trace ID comes from validated query/local state, never arbitrary backend text.

### 6.2 Exact span schema and span-id validation

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

Backend `span_id` must be an exact built-in string validated before local-membership lookup/projection:

```text
native length == 16
all characters lowercase ASCII [0-9a-f]
not 0000000000000000
```

No arbitrary conversion/trim/case fold. `parent_span_id`, when safely parsed, uses the same grammar.

Other field types:

```text
parent_omitted: JSON boolean
name: AGENT | LLM | TOOL | PROVIDER_SDK | INTERNAL | UNKNOWN
start_time/end_time/duration_ms: JSON integers under scalar/timing contract
status_code: UNSET | OK | ERROR
```

Invalid span ID/timing omits that span rather than echoing raw text.

### 6.3 Every projected backend record is bound to the requested trace

For the initial ordinary-user v1 adapter, **every** fetched record considered for projection must explicitly carry a trace ID. Absence is not accepted as an implicit query binding.

For each fetched backend record, before span-ID membership lookup or timing/status projection:

- raw record trace ID must satisfy `type(value) is str`;
- native length must be exactly 32 before any regex/classifier work;
- characters must be lowercase ASCII `[0-9a-f]` and value must be nonzero;
- canonical record trace ID must exactly equal the requested canonical trace ID;
- missing, malformed, zero, or mismatched trace ID drops the record and sets `partial=true` when otherwise safely relevant data is returned;
- no record lacking this explicit matching trace ID may be rescued by span-ID collision, service/resource attributes, arrival order, or backend query context.

A future adapter that cannot expose a per-record trace ID is unsupported for ordinary-user v1 until a separately reviewed contract defines an equally trusted query-bound association. Initial v1 has no such exception.

After trace-ID validation, if one canonical `span_id` appears in more than one fetched record, omit **all** records with that duplicate ID and set `partial=true`; never resolve duplicates by resource attributes, service names, arrival order, provider metadata, or remote text. Returned spans therefore have unique canonical IDs.

### 6.4 Parent semantics

- no parent -> omit `parent_span_id`, `parent_omitted=false`;
- returned authorized valid parent -> include canonical parent ID, `parent_omitted=false`;
- known parent filtered/invalid/truncated/not returned -> omit ID, `parent_omitted=true`;
- malformed raw parent ID is never echoed; otherwise-valid child may be returned with `parent_omitted=true`.

### 6.5 Status mapping

Closed values:

```text
UNSET
OK
ERROR
```

Unknown/malformed backend status -> `UNSET`. Never copy description/exception/URL/request text.

### 6.6 Explicitly absent

V1 contains no status description, attributes, events, links, resource/instrumentation attributes, logs, baggage, HTTP/provider request metadata, captured content, pseudonyms/key versions, raw identity/auth fields, vendor extensions, or exception messages/stacks.

Unknown structures are dropped. Future fields require a reviewed new schema version.

### 6.7 `partial` semantics

`partial=true` whenever UAG knowingly omits safely relevant data because of backend limits, output limit, auth/local-ownership filtering, duplicate/mismatched/missing/invalid records, invalid timing/ID, omitted known parent, or another supported fail-closed projection omission.

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

The index is UAG-local state, not exported telemetry, and stores no prompt/response/tool/Memory bodies or backend credentials.

Provider-SDK children are eligible for ordinary-user v1 only if their span IDs are registered as locally owned under the active selected-call guard; otherwise they are unindexed and omitted.

Current authorization is evaluated per local segment/span. Cross-instance authorization-index federation is deferred.

## 8. Ordinary-user query flow

```text
fixed-length/canonical trace_id validation
  -> authenticate/revalidate session
  -> local authorization record lookup
  -> none? deny
  -> current authz per local segment
  -> bounded backend query
  -> require matching canonical trace ID on every record
  -> fixed-length/canonical span-ID + duplicate validation
  -> trusted local membership classification
  -> drop non-local/unindexed/unauthorized
  -> closed v1 projection
  -> no authorized valid spans? deny/not-found under API contract
  -> bounded response
```

Current policy wins; historical access/trace possession is insufficient.

## 9. Trace-query resource limits

Supported ordinary-user adapter enforces bounds without first materializing an unbounded response.

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

- one monotonic five-second budget starts at query start and is never reset by retry/page;
- retries/pages share every ceiling;
- use backend pagination/limits where available;
- enforce decoded bytes while application bytes become available after content decoding, not after full-body load;
- additionally bound compressed/wire reads where possible; wire cap never substitutes for decoded cap;
- stop on any ceiling;
- authorize/filter only bounded fetched data;
- order returned spans by normalized `(start_time, span_id)` before output cap;
- safe truncation -> `partial=true`;
- if safe bounded partial cannot be established -> bounded server error, no backend payload;
- truncation never relaxes auth/exposes omitted IDs;
- backend failure never changes Agent execution.

## 10. Required regressions

### Configuration/credentials

- CLI overrides env; `--no-otel` suppresses all Phase 4;
- environment booleans accept exactly the documented normalized token set and reject every other present value without fallback;
- programmatic booleans require exact built-in `bool`; `0/1`, strings, and custom truthy objects fail closed;
- CLI/environment numeric strings accept only canonical ASCII decimal grammar; signs, surrounding whitespace, leading-zero multi-digit forms, Unicode digits, decimal/exponent forms fail closed;
- programmatic numeric values require exact built-in `int`; `bool`/float/string/custom numeric wrappers fail closed;
- category/bound invalidity fails closed;
- initial provider selector set is exactly `openai|claude`; `anthropic`/unknown values never instrument an unselected path;
- default correlation credential name exactly `observability/correlation`;
- invalid credential names fail closed;
- credential secret, metadata mapping, purpose, and key-version values pass exact runtime type gates before comparison/length/decode;
- bytes/string subclasses/custom mappings/custom equality wrappers fail closed before credential comparison/decoding;
- credential kind/purpose/version metadata is exact;
- canonical 43-char unpadded base64url decodes to exactly 32 bytes;
- padded/noncanonical/wrong-length/passphrase secrets fail closed before expensive decode work;
- no raw key env/CLI input.

### Deployment/provenance/secrets

- deployment-scope exact validation/hashing is replica-stable;
- forbidden body/auth/Memory/retrieval/file/artifact/reasoning sources remain excluded through nesting;
- unannotated body-capable children fail closed;
- each initial recognized secret class follows the mandatory redact-or-omit action and no recognized secret passes unchanged.

### Trace schema/identity

- giant/non-string/31/33-char/uppercase/zero trace IDs reject before lookup and without conversion;
- giant/non-string/15/17-char/uppercase/zero span IDs omit before membership lookup/projection;
- every projected backend record requires an explicit canonical trace ID matching the requested trace;
- missing/malformed/explicit backend trace-ID mismatch records are omitted before span membership lookup;
- duplicate span IDs omit all duplicates and set partial;
- returned IDs are unique/canonical;
- name/timing/status remain closed typed fields;
- unauthorized/missing/malformed parent ID never leaks;
- undeclared backend content/fields never appear;
- known omission sets partial.

### Query bounds

- decoded byte/page/span/deadline/output ceilings hold across retries;
- output ordering deterministic after normalization;
- unsupported unbounded adapter returns no raw payload.

## 11. Fixed Phase 4 decisions

- Configuration parsing has source-specific exact runtime types and lexical grammars; invalid explicit higher-precedence settings fail closed without fallback.
- Initial provider diagnostics are selectable only for `openai` and `claude`.
- Correlation credential secret/metadata values require exact built-in runtime types before comparison or decoding.
- Correlation key is canonical unpadded base64url of exactly 32 bytes with dedicated purpose/version metadata.
- Deployment scope is exact/untrimmed/bounded.
- Field/node provenance hard denial overrides content categories.
- Privacy/secret scanning runs only after bounded traversal/scalar preflight, and recognized initial secret forms must redact or omit.
- Ordinary-user v1 requires a matching canonical trace ID on every projected backend record before span membership lookup, performs fixed-length canonical trace/span-ID validation, has unique returned span IDs, closed name/status/timing types, and no arbitrary backend structures.
- Authorization derives only from current UAG-local state.
- Backend retrieval uses one aggregate bounded query budget.
