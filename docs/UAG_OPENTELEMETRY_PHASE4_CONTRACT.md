# OpenTelemetry Phase 4 Normative Contract

Status: Normative design contract  
Parent scope: `docs/UAG_OPENTELEMETRY_PHASE4_SCOPE.md`  
Prerequisite: OpenTelemetry Phase 3 complete

This is the **single normative source of truth** for OpenTelemetry Phase 4. Other Phase 4 documents may summarize intent but MUST NOT restate exact grammars, limits, processing orders, field schemas, or failure behavior. If a summary conflicts with this file, this file wins and the summary is a documentation defect.

## 1. Non-negotiable invariants

Phase 4 MUST preserve all Phase 1-3 guarantees:

- OpenTelemetry remains opt-in.
- UAG canonical Agent/LLM/Tool spans remain authoritative.
- One Web user turn remains one logical Agent trace.
- Browser trace context remains untrusted unless Phase 3 trusted-ingress policy accepts it.
- A2A/MCP trace context never supplies identity or authorization.
- OIDC/session and room/project/private-room authorization remain server-authoritative.
- Trace/span IDs, pseudonyms, baggage, resource attributes, backend records, provider metadata, and key-version labels never authenticate or authorize.
- Identity, secrets, captured content, and pseudonyms never become metric dimensions, baggage, or process resource attributes.
- Observability failure never changes Agent/model/tool execution.
- Uncertainty fails closed for telemetry; it never broadens capture, instrumentation, or access.

Phase 4 consists of four independent features, all OFF by default:

1. Phase 4A controlled content capture;
2. Phase 4B pseudonymous correlation;
3. Phase 4C optional provider SDK diagnostics;
4. Phase 4D authorization-aware trace query proxy.

## 2. Configuration contract

### 2.1 Precedence and complete shared-resolver surface

For every Phase 4 setting:

```text
explicit CLI/application value
    > UAGENT_* environment value
    > safe default
```

An invalid explicit higher-precedence value MUST NOT fall back to a lower-precedence source unless this contract explicitly says otherwise.

Effective core `--no-otel` is authoritative. When core OTel is OFF, every Phase 4 feature is inactive regardless of subordinate settings.

Browser/WebSocket/A2A/MCP/tool/provider/query/header/cookie/baggage/trace content MUST NOT alter process settings.

The shared observability settings resolver exposes **exactly** the following Phase 4 public settings. `None` in a programmatic field means "not explicitly supplied at this precedence level"; it does not itself override an environment value.

| Setting | CLI | Environment | Programmatic/application field | Effective safe default |
|---|---|---|---|---|
| controlled-content activation | `--otel-capture-content` / `--no-otel-capture-content` | `UAGENT_OTEL_CAPTURE_CONTENT` | `capture_content: bool | None` | `false` |
| controlled-content categories | `--otel-capture-categories <csv>` | `UAGENT_OTEL_CAPTURE_CATEGORIES` | `capture_categories: str | None` | empty set |
| per-field content bound | `--otel-capture-max-field-chars <n>` | `UAGENT_OTEL_CAPTURE_MAX_FIELD_CHARS` | `capture_max_field_chars: int | None` | `2048` |
| per-span content bound | `--otel-capture-max-span-chars <n>` | `UAGENT_OTEL_CAPTURE_MAX_SPAN_CHARS` | `capture_max_span_chars: int | None` | `8192` |
| pseudonymous-correlation activation | `--otel-pseudonymous-correlation` / `--no-otel-pseudonymous-correlation` | `UAGENT_OTEL_PSEUDONYMOUS_CORRELATION` | `pseudonymous_correlation: bool | None` | `false` |
| deployment scope | `--otel-deployment-scope <scope>` | `UAGENT_OTEL_DEPLOYMENT_SCOPE` | `deployment_scope: str | None` | absent; pseudonym emission disabled |
| correlation credential name | `--otel-correlation-key-name <name>` | `UAGENT_OTEL_CORRELATION_KEY_NAME` | `correlation_key_name: str | None` | `observability/correlation` |
| correlation key version | `--otel-correlation-key-version <version>` | `UAGENT_OTEL_CORRELATION_KEY_VERSION` | `correlation_key_version: str | None` | `v1` |
| provider SDK selector | `--otel-provider-instrumentation <csv>` | `UAGENT_OTEL_PROVIDER_INSTRUMENTATION` | `provider_instrumentation: str | None` | empty / OFF |
| ordinary-user trace-query activation | `--otel-trace-query` / `--no-otel-trace-query` | `UAGENT_OTEL_TRACE_QUERY_ENABLED` | `trace_query_enabled: bool | None` | `false` |

No alternate CLI spelling, environment alias, or second programmatic field is part of the initial contract. CLI/GUI/Web/A2A entry points that expose Phase 4 settings MUST feed these same resolver fields rather than implementing independent parsing or precedence.

Phase 4C is OFF unless the resolved provider selector contains at least one valid selected provider. There is no independent implicit enable.

### 2.2 Boolean parsing

Boolean CLI controls are presence-only flags and accept no string argument. When positive and negative forms both occur, the last explicit CLI flag wins.

Programmatic/application boolean inputs MUST satisfy `type(value) is bool` or be `None`. `int`, `str`, subclasses, and objects with truthiness hooks are invalid; implementations MUST NOT call `bool(value)` to coerce them.

Environment boolean values MUST be exact built-in strings. Before normalization, raw native length MUST be `<= 16`. Normalize by stripping surrounding ASCII space/tab only and ASCII-lowercasing. The accepted normalized values are exactly:

```text
true:  1, true, yes, on
false: 0, false, no, off
```

No other whitespace, Unicode case folding, numeric spelling, or token is accepted. An invalid explicit environment boolean disables the affected Phase 4 feature; it does not silently become a safe-default value while claiming the environment source was accepted.

### 2.3 Integer parsing

CLI/environment integer controls use the exact ASCII grammar:

```text
0 | [1-9][0-9]*
```

Rules:

- exact built-in string only;
- native length `1..5` before character scanning for current limits;
- ASCII digits only;
- no sign, surrounding/internal whitespace, Unicode digits, decimal point, exponent, plus sign, or leading zero except the single value `0`;
- parse only after the lexical checks pass.

Programmatic integer controls MUST satisfy `type(value) is int`, not `bool`, with no coercion.

Controlled-content limits are exactly:

```text
MAX_FIELD_CHARS default 2048, valid 64..16384
MAX_SPAN_CHARS  default 8192, valid 256..65536
MAX_SPAN_CHARS >= MAX_FIELD_CHARS
```

Missing values use the defaults. Any invalid bound disables controlled content capture for the process while metadata-only tracing continues.

### 2.4 CSV and string settings

CLI/environment CSV values MUST be exact built-in strings with native length `<= 256` before splitting. Programmatic CSV values MUST also be exact built-in `str` or `None`; list/set/tuple/custom iterable input is invalid and is never joined/coerced.

Split on ASCII comma and strip surrounding ASCII space/tab from each token only. Do not Unicode-normalize or case-fold.

Controlled-content categories form a closed set:

```text
user_input
assistant_output
tool_arguments
tool_result
```

Missing/empty -> empty set. Any empty or unknown token invalidates the category configuration and disables controlled content capture. Duplicate valid tokens deduplicate.

Provider instrumentation selectors form a closed set:

```text
openai
claude
```

`claude` selects the Anthropic SDK path; `anthropic` is not an alias. Missing/empty -> OFF. Unknown/empty token enables nothing for that token and emits only normalized content-free diagnostics; valid sibling tokens remain independently active.

All other programmatic string settings in this contract (deployment scope, credential name, key version) MUST be exact built-in `str` or `None`; no generic `str()` conversion is allowed. Their CLI/environment forms are also exact strings and are validated by the topic-specific bounds/grammars in section 4 before any normalization or use.

## 3. Phase 4A controlled content

### 3.1 Closed carrier and ownership

Controlled content is emitted only as the UAG-owned span event:

```text
event name: uag.content
attributes:
  uag.content.category
  uag.content.value
  uag.content.ordinal
```

No other initial attribute is allowed on this event.

Owner mapping is exact:

```text
user_input       -> local canonical invoke_agent span
assistant_output -> local canonical invoke_agent span
tool_arguments   -> matching local canonical execute_tool span
tool_result      -> matching local canonical execute_tool span
```

Canonical `chat`, provider SDK child, internal, and remote spans MUST NOT carry `uag.content` events.

`uag.content.ordinal` is a trusted integer `1..32` local to the owner span. The trusted candidate allocator MUST assign each admitted candidate on an owner span a unique ordinal; ordinals MUST NOT be reused on that span across categories. A duplicate/reused ordinal makes that later candidate ineligible and it is omitted before inspecting its value. At most 32 candidate records are admitted per owner span; candidate 33+ is omitted before inspecting its value. These unique ordinals make the category-plus-ordinal ordering in section 3.10 total and deterministic.

### 3.2 Provenance and exact source/category pairs

Closed provenance vocabulary:

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

The **only** allowed root provenance/category pairs are:

```text
user_message         -> user_input
assistant_message    -> assistant_output
tool_argument        -> tool_arguments
ordinary_tool_result -> tool_result
```

Every other root pairing fails closed before value traversal, even when the category itself is enabled. Payload data cannot choose or relabel either side of the pair.

Hard-denied provenance is exactly:

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

Hard denial overrides category selection recursively.

### 3.3 Trusted child-provenance representation

Plain `dict`/`list`/`tuple` payload values NEVER carry trusted provenance by themselves. Structured capture requires a separate UAG-owned metadata tree created by a reviewed source adapter before telemetry traversal.

The conceptual immutable metadata shape is:

```text
CaptureCandidateMeta
  category: one closed category
  root_provenance: one closed provenance
  owner_kind: invoke_agent | execute_tool
  source_adapter_id: trusted static adapter identifier
  root: ProvenanceNode

ProvenanceNode
  provenance: one closed provenance
  children:
    scalar -> none
    list/tuple -> ordered child nodes, exactly one per value element
    dict -> ordered entries, exactly one (key_node, value_node) pair per dict pair
```

Rules:

- metadata contains provenance/shape correspondence only, never copied body text;
- metadata is created from trusted UAG operation/tool schema state, never from payload-provided labels;
- list/tuple child metadata aligns by exact index;
- dict entry metadata aligns by built-in insertion-order pair index, key node first then value node;
- child-count/shape mismatch, missing node, extra node, unknown adapter, or adapter/schema revision mismatch omits the whole candidate before that unmatched child is inspected;
- child provenance is read from the metadata node; it is NEVER inherited implicitly from an allowed root;
- a structured candidate without a reviewed adapter is ineligible.

The initial reviewed adapter rules are:

```text
user_message adapter:
  textual user message body -> user_message
  attachment/data-url/base64/file/artifact body -> file or artifact (hard denied)
  unknown body-bearing part -> security_sensitive_unknown

assistant_message adapter:
  visible assistant output -> assistant_message
  reasoning/thinking/analysis -> reasoning (hard denied)
  unknown hidden/body-bearing part -> security_sensitive_unknown

tool_argument adapter:
  each tool/schema revision requires a static reviewed field map
  file-write body/content field -> file (hard denied)
  credential/auth/session field -> corresponding hard-denied provenance
  unknown body-bearing field -> security_sensitive_unknown

tool_result adapter:
  each tool/schema revision requires a static reviewed field map
  returned file/artifact body -> file/artifact (hard denied)
  Memory/retrieval query/body/result -> memory/retrieval (hard denied)
  auth/session/credential body -> corresponding hard-denied provenance
  unknown body-bearing field -> security_sensitive_unknown
```

There is no generic "ordinary tool field inherits tool_argument/tool_result" rule. A tool lacking a static reviewed adapter may still execute normally but its structured arguments/results are not captured.

### 3.4 Exact supported runtime values

Only exact built-in values are accepted:

```text
containers: dict, list, tuple
scalars:    str, int, float, bool, None
mapping keys: str only
```

Subclasses and protocol-compatible custom Mapping/Sequence/iterator/generator/stream/file-like/numeric values are rejected without coercion. Bytes, bytearray, memoryview, data/body wrappers, Decimal, Fraction, numpy/custom numerics, and custom mapping keys are rejected.

### 3.5 Processing order

The exact order is:

```text
candidate record + trusted CaptureCandidateMeta
  -> candidate-count/unique-ordinal admission
  -> exact root provenance/category pair gate
  -> root forbidden-provenance gate
  -> master capture gate
  -> category allowlist gate
  -> source-adapter/metadata-shape gate
  -> canonical owner/carrier gate
  -> exact value type/shape gate
  -> node/depth/width/cycle checks
  -> primitive scalar preflight
  -> bounded child traversal with aligned child provenance metadata
  -> recursive blocked-key checks
  -> closed secret detector
  -> post-redaction scalar-token bound
  -> canonical rendering
  -> shared per-span character ledger
  -> emit whole event or omit whole candidate
```

No container enumeration, secret scan, generic conversion, serialization, or custom hook may run before the preceding gates prove the work bounded.

### 3.6 Structural limits

Initial hard limits are non-configurable:

```text
MAX_CAPTURE_DEPTH = 8
MAX_COLLECTION_ITEMS = 64
MAX_CAPTURE_NODES = 256
MAX_CAPTURE_CANDIDATES_PER_SPAN = 32
```

Root depth is 0; depth 9 fails the whole candidate. Lists/tuples permit at most 64 immediate elements; dict permits at most 64 pairs. The 65th immediate child/pair fails the whole candidate.

Node accounting is occurrence-based:

- root = 1;
- every list/tuple element occurrence = 1;
- every dict key occurrence = 1;
- every dict value occurrence = 1;
- aliases count again per occurrence;
- object identity never reduces the count.

Traversal order is list/tuple index order and dict insertion order, key then value. An active-ancestor container identity set detects cycles; encountering an active ancestor fails the whole candidate. The 257th occurrence fails the whole candidate.

The metadata tree is subject to the same depth/width/node ceilings and is validated incrementally; implementations MUST NOT materialize an unbounded provenance tree as part of telemetry capture.

### 3.7 Primitive preflight

Strings:

- exact built-in `str` only;
- native length MUST be `<= MAX_FIELD_CHARS` before regex/classification;
- surrogate code points `U+D800..U+DFFF` are forbidden;
- no UTF-8 encoding, JSON rendering, regex, or generic conversion before those checks.

Integers:

```text
-9223372036854775808 <= value <= 9223372036854775807
```

Range checking is conversion-free; arbitrary-precision integers outside the range are rejected before text/JSON formatting.

Floats MUST be exact built-in finite binary64 values. NaN/infinity/custom numerics are rejected. `bool` is classified before `int`.

### 3.8 Recursive always-blocked keys

For every bounded string mapping key, classification form is:

```text
normalized = key.strip().lower()
```

A key is always blocked when `normalized` contains any of:

```text
authorization
cookie
password
secret
client_secret
principal_id
subject
display_name
email
group
room_id
project_id
session_id
```

For token-style keys, replace `_`, `-`, `/` with `.`, split on `.`, and block an exact segment `token`. Plural usage names such as `input_tokens` are not blocked solely by the substring `token`.

Any blocked mapping key causes omission of the whole candidate; the raw key is never logged.

### 3.9 Closed secret detector and mandatory handling

The detector runs only on already-bounded exact strings. Its initial classes and actions are exact.

#### A. Authorization-scheme token

Scan left-to-right for ASCII-case-insensitive `bearer` or `basic` at a token boundary. A valid left boundary is start-of-string or one of:

```text
ASCII whitespace or  " ' = : ; , ( [ {
```

The scheme MUST be followed by one or more ASCII space/tab characters and then at least one credential character. Credential scanning stops at ASCII whitespace or one of:

```text
" ' < > [ ] { } ( ) , ;
```

A match replaces the entire scalar with `[REDACTED]`.

#### B. Compact JWT-like token

For this detector, the named `JWT_BOUNDARY` set is exactly:

```text
ASCII whitespace or  " ' = : ; , ( ) [ ] { } < > & ? #
```

A candidate JWT-like token is bounded on the left by start-of-string or one `JWT_BOUNDARY` character and on the right by end-of-string or one `JWT_BOUNDARY` character. No other previously defined delimiter set is used for JWT boundary decisions.

A right boundary MAY additionally be a single terminal period `.` immediately following the third segment **only** when that period is followed by end-of-string or one `JWT_BOUNDARY` character. That terminal period is sentence punctuation and is not part of the token. This exception MUST NOT make a fourth JWT-like segment valid: if the period after the third segment is followed by ASCII `[A-Za-z0-9_-]`, the three-segment prefix is not a match.

Within those boundaries, the token is JWT-like only if it consists of exactly three non-empty segments separated by two `.` characters and every segment contains only ASCII `[A-Za-z0-9_-]`. Each segment is limited by the already-established scalar bound. A match replaces the entire scalar with `[REDACTED]`.

Thus `access_token=aaa.bbb.ccc`, `jwt:aaa.bbb.ccc`, and `jwt=aaa.bbb.ccc.` are recognized when `aaa.bbb.ccc` otherwise satisfies the JWT-like grammar, while `aaa.bbb.ccc.ddd` is not accepted as a three-segment token by matching only its prefix.

#### C. PEM private key

Presence of any exact ASCII header below is a match:

```text
-----BEGIN PRIVATE KEY-----
-----BEGIN ENCRYPTED PRIVATE KEY-----
-----BEGIN RSA PRIVATE KEY-----
-----BEGIN DSA PRIVATE KEY-----
-----BEGIN EC PRIVATE KEY-----
-----BEGIN OPENSSH PRIVATE KEY-----
```

A match omits the whole candidate.

#### D. Credential-bearing URI userinfo

Recognize an ASCII URI scheme using:

```text
[A-Za-z][A-Za-z0-9+.-]{0,31}://
```

Authority scanning starts **immediately after the matched `://`**. The authority remainder ends at the first `/`, `?`, `#`, or string end. Within that authority remainder, a credential-bearing userinfo match exists only when:

- an `@` occurs before the authority end;
- before that `@`, a `:` occurs;
- at least one character exists between `:` and `@`.

The username substring before `:` MAY be empty; the password substring between `:` and `@` MUST be non-empty. Thus both `https://user:password@example.com/path` and `https://:password@example.com/path` match. `https://user:@example.com/path` does not satisfy this detector by itself because its password substring is empty. The two slashes in `://` are not treated as authority/path delimiters. A match omits the whole candidate.

Known credential/secret wrapper objects never reach this detector; they are rejected earlier by exact type/provenance gates.

If multiple detector classes match, omission takes precedence over replacement. A recognized match MUST NEVER pass through unchanged. Mapping-key secret recognition, detector exception, classifier ambiguity, or security-sensitive uncertainty omits the whole candidate. Rejected content is never logged.

The replacement marker `[REDACTED]` is fixed and non-configurable.

### 3.10 Canonical rendering and budgets

Direct root string -> exact post-redaction string, unquoted.

All non-string primitives and structured values use compact JSON equivalent to:

```python
json.dumps(
    value,
    ensure_ascii=False,
    allow_nan=False,
    separators=(",", ":"),
    sort_keys=False,
)
```

No `default=` hook. Tuple -> JSON array. Dict keys are exact built-in strings and retain insertion order. No trailing newline/insignificant whitespace.

After privacy/redaction, every scalar MUST again fit `MAX_FIELD_CHARS` using the exact scalar token that appears in final output, including JSON quotes/escapes for structured strings/keys. No scalar is truncated.

Character count means Unicode code points in the exact final `uag.content.value` string.

Each owner span has one shared ledger, starting at zero. Candidate order is category order:

```text
user_input, assistant_output, tool_arguments, tool_result
```

then unique trusted ordinal ascending. Because section 3.1 requires ordinals to be unique across the owner span, no tie is possible. Candidate cost is exactly `len(uag.content.value)`. If it fits remaining `MAX_SPAN_CHARS`, emit it atomically and charge the ledger; otherwise omit the whole candidate with no ledger mutation. A later smaller candidate may still fit.

## 4. Phase 4B pseudonymous correlation

### 4.1 Deployment scope

`deployment_scope` is required for pseudonym emission. It MUST be exact built-in `str`, 1..128 Unicode scalar values, with no leading/trailing Unicode whitespace, control characters, or surrogates. No trimming, normalization, case-folding, or path rewriting occurs. Missing/invalid scope disables pseudonym emission only.

It is stable across intended replicas and distinct across deployments that must not correlate.

### 4.2 Correlation credential

The effective requested credential name is the resolved `correlation_key_name` setting. Its safe default is exactly:

```text
observability/correlation
```

An explicit credential name MUST be exact built-in `str`, 1..128 Unicode scalar values, with no leading/trailing Unicode whitespace, controls, or surrogates. Invalid explicit name disables pseudonym emission without fallback.

A custom `CredentialStore` result is accepted only when runtime shape validation passes **before** any field comparison, decoding, custom equality, or conversion:

```text
type(credential) is Credential
type(credential.kind) is CredentialKind
type(credential.name) is str
type(credential.secret) is str
type(credential.metadata) is dict
len(credential.metadata) <= 16
```

After those exact runtime-type gates, `credential.name` MUST itself satisfy the same bounded name validation as the effective requested credential name: native length `1..128`, no leading/trailing Unicode whitespace, controls, or surrogates, with no normalization. It MUST then equal the effective requested credential name exactly, code point for code point. Any mismatch rejects the credential. This returned-name validation/equality check occurs before metadata lookup, secret decoding, HMAC construction, or any use of the returned secret.

Before any metadata lookup/comparison, every existing metadata key/value pair MUST satisfy `type(x) is str`, key native length `<= 64`, value native length `<= 128`, and contain no surrogates. An invalid pair rejects the credential. Only after that bounded validation may the implementation read `purpose` and `key_version` from a safe copied built-in dict.

The credential kind MUST be exactly `CredentialKind.OTHER`.

Required metadata values are exact built-in strings:

```text
metadata["purpose"] = "observability_pseudonym_v1"
metadata["key_version"] = <effective validated key version>
```

Missing/wrong-type/mismatched purpose or version disables pseudonym emission.

`secret` is canonical unpadded base64url of exactly 32 raw bytes:

```text
native string length = 43
alphabet = [A-Za-z0-9_-]
no '='
decode -> exactly 32 bytes
canonical re-encode -> exact original string
```

Length/alphabet checks precede decode. Passphrases, padded/noncanonical values, decode failure, and wrong-length decoded values are rejected. UAG-provisioned keys use an OS CSPRNG. Raw key material is never accepted via CLI/environment.

Known reuse with authentication/token-signing/provider/A2A/MCP/OIDC/OAuth/session key material disables pseudonym emission.

### 4.3 Key version

Safe default is exactly `v1`.

Explicit key version MUST be exact built-in `str`; native length `1..32` is checked before character scanning. Grammar is exactly:

```text
^[a-z0-9][a-z0-9._-]{0,31}$
```

Invalid explicit value disables pseudonym emission without fallback. Rotation changes key material and version label together; one span may not mix generations.

### 4.4 HMAC construction

Kinds are exactly:

```text
principal
room
project
```

Raw identifier MUST be exact built-in `str`, 1..256 Unicode scalar values, no surrogates; native length check precedes scanning, then UTF-8 length MUST be `1..1024` bytes.

Construction is exactly:

```text
magic = b"uag-otel-pseudo-v1"
frame(x) = uint32_be(len(utf8(x))) || utf8(x)
message = magic || frame(deployment_scope) || frame(kind) || frame(raw_identifier)
digest = HMAC-SHA-256(correlation_key, message)
pseudonym = lowercase_hex(digest[0:16])
```

The pseudonym is exactly 32 lowercase hex ASCII characters (first 128 digest bits), non-configurable.

### 4.5 Attachment

Only these attributes exist initially:

```text
uag.correlation.principal
uag.correlation.room
uag.correlation.project
uag.correlation.key_version
```

They are emitted only on the locally owned canonical `invoke_agent` span representing the local segment root. Every span with one or more pseudonyms MUST have exactly one matching `uag.correlation.key_version`; the version is not emitted alone. `chat`, `execute_tool`, provider-SDK, internal, and remote spans do not repeat them.

Pseudonyms/version labels are diagnostics only: never auth, authorization, routing, storage keys, Memory identity, credential selection, metrics, baggage, resources, or ordinary-user trace-view fields.

## 5. Phase 4C provider SDK diagnostics

UAG canonical `chat` remains the one logical LLM operation. Optional SDK diagnostics may produce at most one UAG-controlled child under the active `chat`:

```text
span name: provider_sdk
parent: active canonical chat
attribute: uag.provider.id = exact selected logical provider id
status code only: UNSET | OK | ERROR
```

No other provider-child attribute, event, link, status description, model, URL, request/response ID, prompt/response/reasoning/tool body, header/body, credential, exception text/stack, resource/instrumentation attribute, or vendor metadata is initially permitted.

Instrumentation is allowed only when client/call-scoped or guarded by trusted UAG active-call state proving:

- active canonical `chat` exists;
- logical provider is selected (`openai` or `claude`);
- SDK call belongs to the guarded client/request for that canonical round.

Global hooks MUST be inert outside the guard. An instrumentor that cannot suppress/normalize non-allowlisted telemetry before export is unsupported and remains disabled. Provider-native content capture remains disabled. No duplicate logical LLM span is allowed. Generic global HTTP auto-instrumentation is not enabled merely for provider diagnostics.

Provider diagnostic failure disables the optional child only and never changes the model request/output.

## 6. Phase 4D ordinary-user trace query

Phase 4D is active only when core OTel is ON **and** the resolved `trace_query_enabled` setting is true. The default is false. Merely enabling OTel or another Phase 4 feature MUST NOT expose usable trace data through the ordinary-user trace-query route.

### 6.0 HTTP route and feature-disabled behavior

The initial ordinary-user trace-query API surface is exactly:

```text
method: GET
path:   /api/observability/traces/{trace_id}
input:  trace_id is one path parameter only
body:   no request body is accepted or interpreted
query:  no query parameter is part of v1
```

No POST/PUT/PATCH alias, alternate route, query-string trace identifier, or body-supplied trace identifier is part of the initial contract.

The feature gate is evaluated before trace-query authentication/trace-ID parsing/index/backend work. When effective core OTel is OFF or `trace_query_enabled` is not true, this route returns HTTP `404` with exactly `{"error":"not_found"}` and performs no trace-query auth lookup, trace-ID parsing, local-index lookup, or backend access.

When the feature is enabled, the existing product authentication gate runs next. After successful authentication and **before** trace-ID parsing, local-index lookup, or backend work, request shape is validated without parsing content:

- any request containing one or more body octets is rejected;
- any request with a non-empty raw query string is rejected;
- the body/query values are never parsed, interpreted, logged, normalized, or reflected.

Either request-shape violation returns HTTP `400` with exactly `{"error":"invalid_request"}`. Section 6.1.1 defines the remaining externally observable outcomes.

### 6.1 Authorization architecture and bounded local index

Ordinary users never receive raw backend API credentials/responses. Initial lookup accepts canonical trace ID only; pseudonym discovery is deferred.

UAG keeps a local authorization/ownership index independent from telemetry. It contains no prompt/response/tool/Memory bodies or backend credentials.

Initial local-index hard ceilings per trace are:

```text
MAX_LOCAL_SEGMENTS_PER_TRACE = 64
MAX_LOCAL_OWNED_SPAN_IDS_PER_TRACE = 2000
MAX_LOCAL_SCOPE_TEXT_CHARS = 256 per stored room/project/principal/service/entry-point text field
```

Every stored trace/span ID uses the canonical fixed-length ID grammar defined below. Every owned span-ID entry MUST atomically retain an immutable trusted semantic kind alongside that span ID. The stored kind vocabulary is exactly:

```text
invoke_agent
chat
execute_tool
provider_sdk
internal
unknown
```

The `(span_id, semantic_kind)` association is created from trusted UAG-local semantic ownership when the span ID is registered/completed and MUST NOT be derived later from backend `span.name`, provider/model/tool text, URLs, resource metadata, or other telemetry. Once stored, the semantic kind for that owned span ID is immutable. An explicit locally classified `unknown` is valid and later maps to output `UNKNOWN`; a missing, malformed, unsupported, or multiply-associated semantic kind makes the local index malformed/non-queryable for ordinary-user access and therefore uses the fixed pre-backend `404` behavior in section 6.1.1. Missing kind metadata MUST NOT silently become `UNKNOWN`.

The 2000 owned-span ceiling includes these `(span_id, semantic_kind)` entries; implementations MUST NOT maintain an additional unbounded semantic-kind map outside the same bounded index.

The index MUST enforce these ceilings when records are added; it MUST NOT accumulate an unbounded per-trace list and defer bounding until query time. If a trace would exceed any ceiling, mark its local authorization index non-queryable/overflowed for ordinary-user access; normal tracing/Agent execution continues.

The aggregate five-second trace-query deadline begins **before local-index lookup**. Query code MUST use a bounded index API such as:

```text
lookup_segments(trace_id, max_segments=64, deadline=shared_deadline)
```

and MUST NOT call an unbounded `get_all`/materialize-all path. Across all returned local segments, at most 2000 owned span IDs and their semantic-kind associations may be materialized/scanned. Authorization uncertainty is never converted into `partial` access.

Current auth/session and room/project/private-room authorization are revalidated per local segment/span on every query. A local segment never authorizes remote/unindexed segments in the same distributed trace. Cross-instance authorization-index federation is deferred.

#### 6.1.1 Externally observable ordinary-user API outcomes

The enabled initial ordinary-user endpoint has one fixed observable policy so trace existence is not exposed through differing authorization/index failures. Responses are JSON and MUST contain no raw backend/index/error payload, trace-specific reason text, scope text, or rejected identifier beyond the successful v1 response itself.

- **Unauthenticated request:** the existing UAG authentication layer rejects it before request-shape validation, trace-ID parsing, or local-index lookup using the product's standard authentication response. Phase 4 does not define a second authentication format.
- **Authenticated request with one or more body octets or a non-empty raw query string:** return HTTP `400` with exactly `{"error":"invalid_request"}` and perform no body/query parsing, trace-ID parsing, local-index lookup, or backend work.
- **Syntactically invalid `trace_id`:** return HTTP `400` with exactly `{"error":"invalid_trace_id"}` and perform no local-index/backend lookup.
- **Syntactically valid `trace_id`, but no complete authorized local view can be established before backend access:** return HTTP `404` with exactly `{"error":"trace_not_found"}` and perform no backend lookup. This single result covers nonexistent/local-index-missing traces, a complete lookup yielding zero currently authorized local segments, overflowed/non-queryable index state, malformed index state (including missing/malformed/unsupported semantic-kind association), local-index timeout/deadline expiry, incomplete index state, and equivalent authorization uncertainty. The endpoint MUST NOT use `403` or distinct bodies/statuses to distinguish those cases.
- **Complete bounded local authorization succeeds with at least one authorized local segment, but backend retrieval/projection later fails or cannot produce a safe bounded partial result:** return HTTP `503` with exactly `{"error":"trace_query_unavailable"}` and no backend payload/details.
- **Successful projection:** return HTTP `200` with exactly the `uag.trace_view.v1` schema in section 6.5.

When a complete bounded local lookup establishes at least one authorized local segment, other complete-but-unauthorized local/remote segments may be filtered during projection as specified below; that filtering may yield `partial=true`. Only uncertainty/incompleteness in the authorization index itself is collapsed to the fixed pre-backend `404` result.

### 6.2 Query trace ID

Query `trace_id` MUST be exact built-in `str`. Validate without conversion in this order:

```text
native length == 32
ASCII lowercase [0-9a-f] only
not 00000000000000000000000000000000
```

Invalid input is rejected before local-index/backend lookup. No trim/case-fold/prefix stripping.

### 6.3 Every backend record MUST be trace-bound

Every backend span record considered for projection MUST carry an explicit canonical trace ID. The record trace ID MUST be exact built-in `str`, length 32, lowercase hex, nonzero, and exactly equal the validated requested trace ID **before** span membership lookup.

A record with missing, malformed, mismatched, or non-string trace ID is omitted and sets `partial=true` when safely relevant bounded data remains. A 64-bit `span_id` match alone is never sufficient. Service/resource fields, arrival order, or the fact that a record arrived from a trace-specific backend endpoint never rescue a missing/mismatched record trace ID. An adapter that cannot provide the per-record canonical trace ID is unsupported for initial ordinary-user projection.

### 6.4 Span IDs and duplicates

Backend `span_id` MUST be exact built-in `str`:

```text
native length == 16
ASCII lowercase [0-9a-f] only
not 0000000000000000
```

Validate before local-membership lookup. Parent ID, when present, uses the same grammar. No conversion/trim/case fold.

If the same canonical span ID appears in multiple fetched records, omit all records with that duplicate and set `partial=true`; never choose by arrival order, resource/service/provider text, or metadata.

### 6.5 Closed response schema

Top level is exactly:

```text
schema_version = "uag.trace_view.v1"
trace_id       = validated query trace id
partial        = JSON boolean
spans          = JSON array (max 500)
```

Every returned span contains exactly:

```text
span_id
parent_span_id    # optional only if returned parent is present
parent_omitted
name
start_time
end_time
duration_ms
status_code
```

Closed `name` values:

```text
AGENT
LLM
TOOL
PROVIDER_SDK
INTERNAL
UNKNOWN
```

Query projection MUST obtain the semantic kind **only** from the bounded local index's immutable `(span_id, semantic_kind)` association after canonical span-ID membership succeeds. Backend `span.name`, provider/model/tool/agent names, URLs, request text, exception text, and vendor/resource/instrumentation fields never participate in this mapping.

The trusted indexed semantic-kind mapping is exhaustive and exact:

```text
invoke_agent -> AGENT
chat         -> LLM
execute_tool -> TOOL
provider_sdk -> PROVIDER_SDK
internal     -> INTERNAL
unknown      -> UNKNOWN
```

The `internal` and `unknown` input kinds are UAG-owned static classifications only; arbitrary backend/provider text cannot create them. A missing, malformed, unsupported, or conflicting indexed semantic kind is not projected as `UNKNOWN`: it makes the local authorization index malformed/non-queryable and therefore produces the fixed pre-backend `404` outcome from section 6.1.1. No adapter may remap one admitted trusted kind to another output class.

#### 6.5.1 Status normalization

The output `status_code` is exactly one of `UNSET | OK | ERROR`; arbitrary status description/exception/backend text is never copied.

For initial v1, the backend adapter may supply status only as a missing value/`None` or an exact built-in `str`. Before normalization, a string MUST have native length `<= 16`; overlength or non-string/non-`None` values map to `UNSET` without conversion and do not by themselves omit the span or set `partial=true`.

For an admitted exact string, normalize only by stripping surrounding ASCII space/tab and ASCII-lowercasing. Mapping is exactly:

```text
unset, unknown, ""          -> UNSET
ok, success, completed      -> OK
error, failed, failure      -> ERROR
all other bounded strings   -> UNSET
```

Missing/`None` status -> `UNSET`. No `str()` conversion, Unicode case-folding, numeric/enum coercion, vendor lookup table, status description, or exception text participates in normalization. A future additional raw status representation requires a reviewed contract revision.

V1 contains no generic attributes/events/links/resources/instrumentation attributes/logs/baggage/HTTP/provider metadata/captured content/pseudonyms/key versions/raw identity/auth/vendor extensions/exceptions.

### 6.6 Parent semantics

- no parent -> omit `parent_span_id`, `parent_omitted=false`;
- returned authorized valid parent -> include parent ID, `parent_omitted=false`;
- known parent filtered/invalid/truncated/not returned -> omit ID, `parent_omitted=true`;
- malformed raw parent ID is never echoed; otherwise-valid child may still return with `parent_omitted=true`.

### 6.7 Timing

Canonical output:

```text
start_time  : JSON integer Unix epoch milliseconds
end_time    : JSON integer Unix epoch milliseconds
duration_ms : JSON integer = end_time - start_time
```

Canonical start/end range:

```text
0..9007199254740991
```

The initial ordinary-user v1 supports **only** exact built-in integer backend timestamps whose reviewed adapter supplies one of the closed unit tags `ms`, `us`, or `ns`. Textual timestamp input of every form is unsupported in the initial contract; there is no ISO-8601/RFC-3339/general date parser and no adapter-specific textual exception. A backend record exposing only textual timestamps cannot project that span into v1; the span is omitted under the normal bounded `partial=true` rules. Adding any textual timestamp grammar requires a later reviewed contract revision.

Supported exact built-in integer raw units and preflight maxima:

```text
ms: 0..9007199254740991
us: 0..9007199254740991999
ns: 0..9007199254740991999999
```

Booleans are not timestamps. Raw range/type validation occurs before division, multiplication, text conversion, serialization, or logging.

Chronology MUST be validated at original precision before discarding sub-millisecond precision. For two integer timestamps, after both raw-unit preflights pass, compare them in a common exact nanosecond domain using fixed factors:

```text
ms factor = 1_000_000
us factor = 1_000
ns factor = 1
```

The products are bounded (< 2^74) by the preceding maxima. Require:

```text
end_raw * end_factor >= start_raw * start_factor
```

before `//` conversion to milliseconds. Thus reversed values that collapse to the same millisecond are rejected.

Only after chronology passes are endpoints converted:

```text
ms -> raw
us -> raw // 1000
ns -> raw // 1000000
```

and `duration_ms` is derived from canonical endpoints. Backend duration is never copied.

Invalid or textual timing omits the span; raw timing text is never parsed, logged, or echoed.

### 6.8 Partial semantics

`partial=true` whenever UAG knowingly omits safely relevant backend data due to backend/query limits, authorization/local ownership filtering after a complete bounded authorization lookup, trace-ID mismatch/missing record binding, invalid/duplicate IDs, invalid/unsupported timing, parent omission, output truncation, or another supported fail-closed projection omission.

`partial=false` only when no known omission exists within bounded retrieved data. Local authorization-index uncertainty/overflow/malformed state is the fixed pre-backend `404` result from section 6.1.1, not a partial authorization result.

### 6.9 Aggregate query resource ceilings

The one monotonic query budget starts before local-index lookup and continues through backend retrieval/projection. It is never reset by local lookup, retry, or page.

Exact backend/output ceilings are:

```text
monotonic elapsed deadline:        5 seconds total, including local index work
maximum local segments read:       64
maximum local owned span IDs read: 2000
maximum decoded backend bytes:     8 MiB
maximum backend spans fetched:     2000
maximum spans per backend page:    500
maximum backend pages:             4
maximum authorized spans returned: 500
```

Adapters enforce decoded bytes while reading, not after an unbounded full-body materialization. Backend limits/pagination are used where available. Stop on any ceiling. Order authorized valid spans by `(start_time, span_id)` before the output cap. Safe backend/output truncation sets `partial=true`; if a safe bounded partial cannot be established after authorization succeeds, return the fixed HTTP `503` response from section 6.1.1 with no backend payload.

## 7. Failure and diagnostics

All failures emit only normalized low-cardinality content-free diagnostics. Diagnostics MUST NOT contain rejected content, keys, secrets, raw correlation identifiers/key material, raw identity/auth values, arbitrary provider/backend text, malformed unbounded values, or exception payloads derived from them.

Feature failure behavior:

```text
content policy/bound/redaction/render failure -> omit content; runtime continues
pseudonym configuration/construction failure  -> omit pseudonym; tracing continues
provider SDK diagnostic failure               -> disable optional child; model call continues
trace query config/auth/index/backend failure  -> fixed bounded response per 6.0/6.1.1; no raw payload; Agent continues
```

## 8. Required conformance tests

Implementation is incomplete until tests prove at least:

### Configuration

- CLI > env > default precedence;
- the complete section 2.1 resolver matrix has one and only one CLI/environment/programmatic name and the documented default for every Phase 4 setting;
- all Phase 4A/4B/4D booleans default OFF;
- Phase 4D route is exactly `GET /api/observability/traces/{trace_id}` and returns the exact disabled `404 {"error":"not_found"}` response before trace-query work when core OTel/trace query is OFF;
- last positive/negative CLI boolean wins;
- exact programmatic bool/int/string type gates reject subclasses/coercion;
- env booleans accept only the defined normalized tokens and reject other whitespace/tokens;
- numeric CLI/env grammar rejects signs, whitespace, Unicode digits, leading zeros, overlength, and out-of-range values;
- category/provider CSV parsing follows exact ASCII trim/no-normalization rules;
- each deployment-scope/correlation-key/provider selector CLI/environment control resolves into the exact shared field named in section 2.1;
- `--no-otel` suppresses all Phase 4 behavior.

### Content

- exact root pair table permits only the four documented provenance/category combinations;
- mismatched pair is rejected before value inspection;
- feature OFF remains metadata-only;
- candidate 33 is omitted before value traversal;
- candidate ordinals are unique across an owner span and a duplicate/reused ordinal is omitted before value traversal;
- structured candidate without a reviewed provenance adapter fails closed;
- provenance metadata/value shape mismatch fails before unmatched child body inspection;
- file-write `content`, attachments, file/artifact reader bodies, Memory/retrieval bodies, reasoning, auth/session/credential bodies receive hard-denied provenance through reviewed adapters;
- tools without a reviewed adapter execute but do not export structured content;
- exact runtime types only; custom containers/numerics/keys fail closed;
- depth 8/9, width 64/65, node 256/257 boundaries apply to value and metadata traversal;
- alias/cycle accounting is deterministic;
- forbidden provenance wins through nested composites;
- oversized/surrogate strings and huge integers fail before scanner/rendering;
- every always-blocked key causes whole-candidate omission;
- Authorization/Basic, compact JWT-like, PEM private key, and URI-userinfo detector boundaries/actions are exact;
- `-----BEGIN ENCRYPTED PRIVATE KEY-----` and `-----BEGIN DSA PRIVATE KEY-----` each trigger mandatory whole-candidate omission;
- `access_token=aaa.bbb.ccc`, `jwt:aaa.bbb.ccc`, and `jwt=aaa.bbb.ccc.` are recognized when the token body otherwise satisfies the JWT-like grammar;
- `aaa.bbb.ccc.ddd` is not accepted by matching only its first three segments under the terminal-period rule;
- `https://user:password@example.com/path` and `https://:password@example.com/path` are detected, while empty-password `https://user:@example.com/path` does not satisfy the URI-userinfo detector by itself;
- every recognized value secret is redacted/omitted according to section 3.9 and never passes unchanged;
- mapping-key secret match omits candidate;
- canonical rendering is stable across supported Python 3.11/3.13/3.14 conformance corpus;
- exact field/span budgets and shared ledger behavior;
- no content in metrics/baggage/resources/auth/storage.

### Pseudonyms

- custom credential store output is rejected unless `type(credential) is Credential` and every required nested runtime type/size gate passes;
- returned `credential.name` is bounded/validated and must exactly equal the effective requested credential name before metadata lookup or secret decode;
- oversized/malformed metadata is rejected before unbounded iteration/custom comparison;
- canonical 43-char base64url secret decodes to 32 bytes; malformed/passphrase values fail closed;
- key version grammar/default/rotation behavior;
- deployment/raw-ID bounds and framing are exact;
- adversarial concatenation tuples remain separated by framing;
- output is exactly first 128 HMAC bits as 32 lowercase hex;
- only local canonical `invoke_agent` root carries pseudonyms/version;
- pseudonyms/version never affect auth/query behavior or non-trace channels.

### Provider diagnostics

- OFF initializes no instrumentation;
- only selected guarded calls may produce the one closed child;
- unselected shared-SDK call and call outside guard produce none;
- no duplicate canonical LLM operation;
- no arbitrary provider/request/content/exception telemetry is exported;
- unsupported/leaking instrumentors fail closed without model impact.

### Trace query

- feature is independently default-OFF and requires its explicit activation control;
- initial API is only `GET /api/observability/traces/{trace_id}` with no body/query trace identifier or method alias;
- disabled/core-OTel-OFF requests return exact `404 {"error":"not_found"}` before trace-query auth, parsing, index, or backend work;
- after successful product authentication, any body octet or non-empty raw query string returns exact `400 {"error":"invalid_request"}` before trace-ID parsing/index/backend work and the values are never parsed;
- invalid query trace ID returns the exact section 6.1.1 `400` response before local-index lookup;
- nonexistent, zero-authorized, overflowed, malformed, timed-out, and incomplete local-index cases all collapse to the exact same pre-backend `404 {"error":"trace_not_found"}` response and never use a trace-specific `403`/detail;
- backend/projection failure after successful complete authorization returns the exact fixed `503 {"error":"trace_query_unavailable"}` response with no backend payload;
- local index write/read ceilings prevent unbounded segment/span-ID materialization;
- every owned span ID has exactly one immutable indexed semantic kind from the closed local vocabulary; the association is created atomically from trusted UAG-local ownership and counts under the same 2000-span ceiling;
- missing/malformed/unsupported/conflicting indexed semantic kind makes the trace index non-queryable and uses the fixed pre-backend `404`; it is never silently mapped to UNKNOWN;
- query projection obtains semantic kind only from the indexed span-ID association; backend span names/metadata cannot influence it;
- the five-second budget starts before local-index lookup and is shared through backend work;
- every projected backend record requires an explicit matching canonical trace ID;
- missing/mismatched record trace ID cannot be rescued by span-ID membership;
- invalid/duplicate span IDs fail closed;
- current auth/authz is revalidated per local segment/span;
- remote/unindexed/unauthorized spans are omitted after a complete bounded authorization lookup;
- trusted indexed semantic-kind mapping is exact: `invoke_agent -> AGENT`, `chat -> LLM`, `execute_tool -> TOOL`, `provider_sdk -> PROVIDER_SDK`, `internal -> INTERNAL`, `unknown -> UNKNOWN`;
- raw status normalization accepts only missing/`None` or bounded exact built-in strings and maps the closed token sets exactly; malformed/unsupported status maps to `UNSET` without pass-through;
- textual timestamps are rejected in initial v1 without generic or adapter-specific parsing;
- reversed timestamps are rejected at raw precision even when millisecond flooring would make them equal;
- mixed ms/us/ns ordering uses the bounded exact common-domain comparison;
- v1 exposes only the closed fields/vocabularies;
- backend byte/page/span/deadline/output ceilings hold across retries;
- unauthorized/malformed parent IDs never leak.

Every implementation slice retains repository gates: Python 3.11/3.13/3.14, Ruff, Black, applicable I18N/tool-catalog checks, full pytest, and unchanged OTel-disabled behavior.

## 9. Explicitly deferred

The following require a later reviewed contract revision:

- reasoning/chain-of-thought/system/developer instruction capture;
- Memory/retrieval/file/artifact/auth/session/credential body capture;
- generic structured capture for tools without a reviewed provenance adapter;
- provider-native prompt/response export or richer SDK events/attributes/links;
- ordinary-user captured-content viewing;
- ordinary-user pseudonym-based trace discovery;
- cross-instance authorization-index federation;
- pseudonyms as security/storage identity;
- generic global HTTP/provider auto-instrumentation;
- textual timestamp parsing/projection;
- direct ordinary-user raw trace-backend access;
- telemetry-driven authorization decisions.