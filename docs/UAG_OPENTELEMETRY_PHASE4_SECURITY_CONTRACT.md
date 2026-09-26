# OpenTelemetry Phase 4 Security and Configuration Contract

Status: Normative Phase 4 companion  
Parent scope: `docs/UAG_OPENTELEMETRY_PHASE4_SCOPE.md`  
Traversal/rendering contract: `docs/UAG_OPENTELEMETRY_PHASE4_TRACE_NAME_AND_TRAVERSAL_CONTRACT.md`  
Scalar/timing contract: `docs/UAG_OPENTELEMETRY_PHASE4_SCALAR_AND_TIMING_CONTRACT.md`  
Pseudonym contract: `docs/UAG_OPENTELEMETRY_PHASE4_PSEUDONYM_OUTPUT_CONTRACT.md`  
Applies to: Phase 4A-4D security, configuration, provenance, ordinary-user trace schema, and query bounds

This document is the normative owner for Phase 4 configuration precedence/parsing, deployment-scope validation, field-level provenance, the ordinary-user `uag.trace_view.v1` field set and identifier/status semantics, and trace-query resource ceilings. It deliberately delegates content traversal/rendering, primitive scalar/timing normalization, and pseudonym representation/version association to the named topic contracts.

## 1. Configuration precedence and CLI surface

Phase 4 uses one precedence rule everywhere:

```text
explicit CLI/application setting
    > UAGENT_* environment setting
    > safe default
```

The core `--otel` / `--no-otel` result is authoritative. If effective core OTel is OFF, every Phase 4 feature is inactive regardless of subordinate settings.

The public Phase 4 CLI surface is:

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

Environment equivalents are:

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

- all entry points use the shared observability settings resolver;
- when both positive/negative forms of one boolean are supplied, the last explicit CLI flag wins, matching core OTel behavior;
- an invalid explicit higher-precedence value does not silently fall back to a lower-precedence valid value unless a topic contract explicitly says so;
- browser/WebSocket/A2A/MCP/tool/provider/trace/baggage/header/query/cookie data cannot alter effective Phase 4 settings;
- raw correlation key material is never accepted on CLI; only its credential-store name is configurable.

### 1.1 Controlled-content category parsing

The closed category vocabulary is:

```text
user_input
assistant_output
tool_arguments
tool_result
```

For `--otel-capture-categories` / `UAGENT_OTEL_CAPTURE_CATEGORIES`:

- missing or empty means the empty set and therefore no content capture even if the master gate is ON;
- a non-empty value is split on commas;
- ASCII space/tab surrounding each token is removed;
- tokens remain case-sensitive; no lowercasing or Unicode normalization occurs;
- every non-empty token must exactly equal one closed category above;
- duplicate valid tokens are deduplicated as a set;
- an empty token or unknown token makes the category configuration invalid and disables controlled content capture as a whole for that process;
- invalid categories never broaden capture and do not disable metadata-only tracing.

### 1.2 Controlled-content numeric bounds

Initial bounds are:

```text
MAX_FIELD_CHARS
  default: 2048
  valid:   64..16384

MAX_SPAN_CHARS
  default: 8192
  valid:   256..65536
```

The CLI and environment forms use the same values.

Validation:

- missing uses the default;
- non-integer, zero, negative, below-minimum, or above-maximum is invalid;
- effective `MAX_SPAN_CHARS` must be `>= MAX_FIELD_CHARS`;
- any invalid bound disables controlled content capture for that process while core metadata tracing continues;
- invalid values never become an unbounded fallback.

Runtime traversal, candidate count, canonical renderer, and cumulative span-ledger rules are owned by the traversal/rendering contract.

### 1.3 Provider selector parsing

Provider selectors are UAG logical provider IDs, not SDK package names. Initial examples use:

```text
openai,claude
```

`claude` selects the Anthropic SDK path. `anthropic` is not an initial alias.

Parsing uses comma separation plus ASCII space/tab trimming around tokens, with no case folding or Unicode normalization. Missing/empty means OFF. A valid known token can be enabled independently; an unknown/malformed token enables nothing for that token and produces only a normalized diagnostic. Unknown tokens do not cause a valid sibling selector to instrument an unselected provider.

## 2. Stable deployment scope for pseudonymous correlation

Pseudonymous correlation requires an explicit stable deployment scope resolved as:

```text
--otel-deployment-scope
    > UAGENT_OTEL_DEPLOYMENT_SCOPE
    > no value
```

There is no hostname, PID, random value, current directory, repository path, or machine-local fallback.

### 2.1 Exact validation and hashing semantics

The configured scope is validated **without trimming or canonical rewrite**.

Initial validation accepts exactly 1-128 Unicode scalar values and rejects:

- empty string;
- leading or trailing Unicode whitespace;
- any Unicode control character;
- any Unicode surrogate code point;
- more than 128 scalar values.

Internal non-control whitespace is permitted. No Unicode normalization, case folding, path normalization, delimiter rewrite, or other canonicalization occurs.

The exact validated string is the `deployment_scope` framed into the pseudonym HMAC input. Thus:

```text
prod    -> valid, hashes exactly as "prod"
" prod" -> invalid
"prod " -> invalid
```

Requirements:

- the value is stable across replicas intentionally in the same correlation domain;
- deployments that must not correlate use distinct scopes and/or keys;
- request/turn data cannot override it;
- it is never authorization, identity, routing, storage, Memory, or credential-selection state;
- raw deployment scope is not exported as a trace attribute by default;
- changing the scope intentionally breaks pseudonym correlation.

Missing/invalid scope while pseudonymous correlation is enabled disables pseudonym emission only; core tracing continues.

## 3. Correlation key configuration boundary

The correlation key is server-held observability secret material resolved by credential name. It must:

- be dedicated to observability pseudonymization;
- be generated from a cryptographically secure RNG with at least 256 bits of key material;
- be at least 32 bytes after trusted credential decoding;
- not be an arbitrary human passphrase;
- not equal/alias any known OIDC/OAuth/A2A/session/provider/MCP/token-signing/authentication key;
- never be logged/exported or accepted from browser/tool/provider/peer data.

Malformed, undersized, or known-reused key material disables pseudonym emission without disabling core tracing.

Exact HMAC framing, kind vocabulary, output representation, key-version grammar, and `uag.correlation.key_version` association are owned by the pseudonym contract.

## 4. Field-level provenance for controlled content

Operation-level provenance is insufficient. Body-capable composites require trusted field/node provenance before content eligibility.

### 4.1 Closed trusted provenance classes

Initial classes are:

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

The hard-denied classes are exactly:

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

Hard denial overrides semantic category selection recursively.

A tool/provider payload cannot self-assert provenance through its own keys/values. Only trusted UAG code assigns provenance.

### 4.2 Field-level body classification

Examples requiring explicit field/node classification include:

```text
create/write file tool:
  path                       -> ordinary safe metadata when separately captured
  content                    -> file (forbidden)

message attachment:
  filename/content-type      -> safe metadata only if explicitly reconstructed
  inline text/data/base64    -> file/artifact (forbidden)

artifact helper:
  id/name/type metadata      -> safe metadata only if explicitly reconstructed
  body/bytes/text            -> artifact (forbidden)

Memory/retrieval composite:
  safe count/type/status     -> safe derived metadata only if explicitly reconstructed
  record/query/body/result   -> memory/retrieval (forbidden)
```

An outer `tool_argument`, `ordinary_tool_result`, or `user_message` tag never makes forbidden descendants eligible.

### 4.3 Unannotated body-capable composites fail closed

Rules:

- known body-bearing fields require explicit trusted provenance;
- an unannotated child of a body-capable composite is omitted;
- unknown attachment/provider/tool composite shapes are omitted unless a reviewed adapter classifies fields individually;
- data URLs, base64 blobs, bytes/buffers, file-like values, attachment payloads, body wrappers, and opaque binary structures are forbidden unless a reviewed extractor creates new bounded safe metadata;
- safe metadata extraction constructs new scalars and never relabels an opaque body object as safe.

### 4.4 Source exclusion before redaction

The following are dropped before generic content secret handling:

- OIDC/OAuth/login/callback/session objects;
- credential-store/provider credential resolution outputs;
- Authorization/Cookie/header credential structures;
- A2A bearer structures;
- MCP OAuth/token structures;
- Memory/retrieval records or queries;
- file/artifact body-bearing representations;
- reasoning/thinking/analysis fields;
- system/developer instruction stores;
- security-sensitive structures that UAG cannot safely classify.

This typed-source exclusion is the primary guarantee for security material. Redaction is defense in depth for otherwise eligible bounded natural-language/tool values.

## 5. Secret handling requirements

Secret scanning occurs only after the traversal/rendering contract proves structural/scalar work is bounded.

At minimum the reviewed redactor must identify high-confidence forms including:

- `Bearer ...` / `Basic ...` Authorization-scheme values independent of containing key name;
- compact JWT-like forms;
- PEM private-key blocks/comparable private-key encodings;
- recognized credential-bearing URI userinfo;
- known UAG/provider secret wrapper types before string conversion;
- values tagged by trusted UAG code as credential-bearing.

The exact replacement marker, mapping-key behavior, post-redaction bounds, canonical renderer, and shared span ledger are owned by the traversal/rendering contract.

Redactor exceptions or security ambiguity omit the whole candidate, emit only normalized content-free diagnostics, and never fail the user operation.

## 6. Ordinary-user `uag.trace_view.v1` is a closed metadata-only schema

The proxy constructs v1 field-by-field and never forwards arbitrary backend JSON.

### 6.1 Exact top-level schema

```text
schema_version : exact string "uag.trace_view.v1"
trace_id       : exact canonical W3C trace-id string
partial        : JSON boolean
spans          : JSON array, at most 500 returned spans
```

No other top-level field exists in v1.

`trace_id` must match:

```text
^[0-9a-f]{32}$
```

and must not be all zeros. Ordinary-user query input that fails this grammar is rejected before local-index/backend lookup. No trimming, case folding, prefix stripping, or arbitrary string conversion occurs. The response `trace_id` comes from the validated query/local authorization record; arbitrary backend trace-id text is never echoed.

### 6.2 Exact span schema

Every returned span contains exactly:

```text
span_id
parent_span_id    # optional; only when returned parent is also authorized and present
parent_omitted
name
start_time
end_time
duration_ms
status_code
```

Types/grammars:

```text
span_id:
  exact lowercase hex string matching ^[0-9a-f]{16}$, not all zeros

parent_span_id:
  when present, same grammar as span_id

parent_omitted:
  JSON boolean

name:
  one of AGENT | LLM | TOOL | PROVIDER_SDK | INTERNAL | UNKNOWN
  mapping owned by the traversal/rendering contract

start_time, end_time, duration_ms:
  JSON integers with exact normalization/bounds owned by the scalar/timing contract

status_code:
  one of UNSET | OK | ERROR
```

Backend span IDs are validated by exact bounded grammar before inclusion. Invalid span ID or invalid timing omits that span rather than copying arbitrary text.

### 6.3 Parent semantics

For a returned span:

- no parent exists: omit `parent_span_id`, set `parent_omitted=false`;
- parent exists and is authorized/valid/returned: include validated `parent_span_id`, set `parent_omitted=false`;
- parent is known to exist but is not returned because of authorization filtering, local-index filtering, invalid projection, or bounded truncation: omit `parent_span_id`, set `parent_omitted=true`.

An unauthorized/unreturned parent ID is never exposed.

### 6.4 Status mapping

`status_code` is mapped into exactly:

```text
UNSET
OK
ERROR
```

Unknown/malformed backend status -> `UNSET`. Backend/provider status descriptions, exception text, URLs, request details, or free-form status text are never copied.

### 6.5 Fields explicitly absent from v1

V1 contains no:

```text
status_description
attributes
events
links
resource attributes
instrumentation scope
logs
baggage
HTTP metadata/headers
provider request/response metadata
captured content
pseudonyms/key-version attributes
raw identity/authorization fields
backend/vendor extensions
exception messages/stacks
```

Unknown top-level/span/nested backend structures are dropped. A future field requires an explicitly reviewed new schema version; v1 does not grow implicitly.

### 6.6 `partial` semantics

`partial=true` whenever UAG knowingly returns less than the safely available trace view because of one or more of:

- backend byte/page/span/deadline truncation;
- 500-span output ceiling;
- authorization or local-ownership filtering;
- invalid span identifier/timing/name ownership projection;
- an omitted known parent;
- another supported fail-closed projection omission.

`partial=false` only when UAG has no known omission within the bounded data it was able to retrieve/project. The boolean does not expose omitted IDs or content.

## 7. Local trace authorization remains independent of telemetry

Possession of trace ID, span ID, pseudonym, key version, baggage, backend attributes, resource attributes, service names, links, or provider metadata never authorizes access.

When an authorized local Agent trace/segment starts, UAG records local state sufficient to bind local spans/segments to current UAG authorization scope. A practical record may contain:

```text
trace_id
local_segment_id
local_root_span_id
owned_span_ids / safe local membership mapping
service_instance_id
created_at
entry_point
room_id
project_id
principal_id when required for private scope
private_scope
```

This index is UAG-local state, not exported OTel state. It contains no prompt/response/tool/Memory bodies or backend credentials.

Ordinary-user authorization is evaluated per local segment/span using current UAG auth/authz. Cross-instance authorization-index federation is deferred.

## 8. Trace-query authorization flow

For a non-admin query:

```text
validate canonical trace_id
  -> authenticate/revalidate current session
  -> find local authorization records
  -> none? deny
  -> re-run current authorization for each local segment
  -> bounded backend query
  -> validate/classify each fetched span against trusted local membership
  -> drop non-local/unindexed/unauthorized spans
  -> project each authorized span through closed v1 schema
  -> no authorized valid spans remain? deny/not-found under API contract
  -> return bounded v1 response
```

Current policy wins over historical access. Authorization for one segment never authorizes another segment sharing the trace ID.

## 9. Trace-query resource limits

A backend adapter is supported for ordinary-user Phase 4D only if it can enforce bounded retrieval without first materializing an unbounded response.

Initial aggregate per-query limits are exactly:

```text
elapsed deadline:                 5 seconds
maximum decoded backend bytes:    8 MiB
maximum backend spans fetched:    2000
maximum spans per backend page:   500
maximum backend pages:            4
maximum authorized spans returned: 500
```

Rules:

- the five-second deadline is one monotonic elapsed budget from query start and is not reset by retries/pages;
- retries and pagination share every aggregate ceiling;
- backend-side pagination/limits are used where available;
- decoded-byte accounting is enforced while application response bytes are made available after transport/content decoding, not after full-body materialization;
- adapters should additionally bound compressed/wire reads where the client permits, but a wire-byte cap never substitutes for the decoded 8 MiB cap;
- stop retrieval when any deadline/byte/span/page ceiling is reached;
- authorization/filtering operates only on already-bounded fetched data;
- returned spans are ordered by normalized `(start_time, span_id)` before the 500-output ceiling;
- safe truncation yields `partial=true`;
- if a safe bounded partial result cannot be established, fail closed with a bounded server error and no backend payload;
- truncation never relaxes authorization or exposes omitted parent IDs;
- backend failure never changes Agent execution.

## 10. Required regressions

### Configuration

- every new CLI option overrides its environment fallback;
- `--no-otel` suppresses all Phase 4 behavior;
- missing capture bounds resolve to 2048/8192;
- invalid/inconsistent bounds disable controlled content capture only;
- missing/empty categories capture nothing;
- category tokens trim only surrounding ASCII space/tab and otherwise require exact closed names;
- unknown/empty category token disables capture rather than being ignored;
- provider `claude` selects Anthropic path, `anthropic` is not an alias, and unknown provider tokens do not activate unselected calls;
- raw correlation key material has no CLI option.

### Deployment scope

- `prod` is valid and framed exactly as configured;
- leading/trailing whitespace, controls, surrogates, empty, or >128-scalar scopes are invalid rather than normalized;
- same key/scope across intended replicas is stable;
- different scopes domain-separate pseudonyms;
- no hostname/PID/random fallback exists.

### Provenance

- file-writing `content`, attachment data/base64, artifact body, Memory/retrieval body, auth/session/credential structures remain excluded under otherwise allowed categories;
- unannotated body-capable children fail closed;
- safe derived metadata requires trusted reconstruction.

### Trace view

- invalid/uppercase/zero/overlong trace IDs are rejected before lookup;
- invalid/uppercase/zero span IDs are omitted rather than echoed;
- top-level and span schema contain no undeclared fields;
- name is only the closed span-class enum;
- timing is only normalized integer milliseconds/duration;
- status is only `UNSET|OK|ERROR`;
- parent ID is present only for a returned authorized parent;
- omitted parents expose only `parent_omitted=true`;
- content/pseudonyms/events/attributes/resources/links/logs/exception text never appear;
- every known filtering/truncation/projection omission sets `partial=true`.

### Query bounds

- more than 8 MiB decoded content is stopped during reading;
- no more than 2000 spans/four pages/500 per page are fetched;
- one monotonic five-second budget covers retries/pages;
- at most 500 authorized spans are returned;
- output ordering is deterministic after ID/timing normalization;
- unsupported unbounded adapters return no raw payload.

## 11. Fixed Phase 4 decisions from this contract

- Phase 4 uses explicit CLI/application > environment > safe-default precedence.
- Controlled-content categories and numeric bounds have deterministic fail-closed parsing.
- Deployment scope is not trimmed/normalized; surrounding whitespace is invalid.
- Body-capable content uses trusted field/node provenance and hard-denied provenance overrides categories.
- Secret scanning happens only after bounded traversal/scalar preflight as defined by the traversal contract.
- Ordinary-user `uag.trace_view.v1` is a closed metadata-only schema with canonical trace/span ID grammars, closed name/status vocabularies, canonical timing types, and no generic nested backend containers.
- Ordinary-user trace authorization comes only from current UAG-local auth/authz records, never telemetry.
- Trace backend retrieval is bounded by one aggregate deadline/byte/span/page budget before output.