# OpenTelemetry Phase 4 Pseudonym Output Contract

Status: Normative Phase 4 companion  
Parent scope: `docs/UAG_OPENTELEMETRY_PHASE4_SCOPE.md`  
Security/configuration contract: `docs/UAG_OPENTELEMETRY_PHASE4_SECURITY_CONTRACT.md`  
Applies to: Phase 4B pseudonym construction, output representation, attachment scope, kind domain, raw-identifier bounds, and correlation-key version association

This document is the sole normative owner for the initial pseudonym construction/output rules. The security contract owns deployment-scope and key-material validation; this contract consumes only already-validated values.

## 1. Canonical HMAC input is exact

Initial Phase 4 pseudonymization uses HMAC-SHA-256 over this exact framed message:

```text
magic = b"uag-otel-pseudo-v1"
frame(x) = uint32_be(len(utf8(x))) || utf8(x)
message = magic || frame(deployment_scope) || frame(kind) || frame(raw_identifier)
digest = HMAC-SHA-256(correlation_key, message)
```

Rules:

- `deployment_scope` is the exact validated value from the security contract;
- `kind` is exactly one of the ASCII strings `principal`, `room`, or `project`;
- `raw_identifier` is an authoritative UAG-local identifier string obtained from current trusted identity/scope state, never caller-supplied telemetry metadata;
- components are UTF-8 encoded independently and prefixed with unsigned 32-bit big-endian byte lengths;
- no delimiter-only concatenation is permitted;
- no Unicode normalization, case folding, trimming, path normalization, or other rewrite is applied to `raw_identifier` unless that transformation is already normative for the authoritative identifier before the pseudonym helper receives it;
- plain SHA hashes are not a substitute for HMAC;
- raw identifiers never leave the helper/export boundary in clear text.

### 1.1 Raw-identifier preflight is bounded

Before UTF-8 encoding/HMAC work, `raw_identifier` must be an exact built-in string with:

```text
1..256 Unicode scalar values
no surrogate code points U+D800..U+DFFF
```

After that bounded native-length check, UTF-8 encoding must be `1..1024` bytes. A value outside either bound emits no pseudonym for that identifier kind and produces only normalized content-free diagnostics.

No generic `str()`/`repr()` conversion of arbitrary identity objects is permitted in the pseudonym helper.

This bound is telemetry-only and never changes authoritative UAG identity or authorization.

## 2. Initial pseudonym representation is fixed

The exported pseudonym is exactly:

```text
pseudo128 = lowercase_hex(digest[0:16])
```

Therefore:

- exactly the first 128 digest bits are exported;
- output is exactly 32 lowercase hexadecimal ASCII characters;
- shorter/longer truncation is not configurable in the initial release;
- uppercase hex, base64, base64url, or implementation-specific encodings are not permitted;
- changing digest length or representation requires an explicitly reviewed schema/version change.

## 3. Exact trace attribute names and attachment scope

The only initial pseudonym attributes are:

```text
uag.correlation.principal
uag.correlation.room
uag.correlation.project
uag.correlation.key_version
```

Each principal/room/project value is exactly the 32-character `pseudo128` representation.

Initial attachment scope is also fixed:

- pseudonym attributes are emitted only on the locally owned canonical `invoke_agent` span that represents the local Agent-turn/segment root;
- applicable principal/room/project pseudonyms for that local authorization scope are attached to that one span;
- canonical `chat`, canonical `execute_tool`, provider-SDK child, and unrelated internal spans do not repeat pseudonym attributes in the initial release;
- each independent UAG service/instance participating in a distributed trace may attach its own local-scope pseudonyms to its own locally owned canonical `invoke_agent` segment root;
- remote spans never cause UAG to copy or trust their pseudonym attributes.

No raw identifier, deployment scope, correlation key, full HMAC digest, or caller-supplied label is exported by this contract.

## 4. Correlation-key version grammar is fixed

Public controls are:

```text
--otel-correlation-key-version <version>
UAGENT_OTEL_CORRELATION_KEY_VERSION=<version>
```

Precedence is inherited from the security contract:

```text
explicit CLI/application setting
    > environment setting
    > safe default
```

The safe default is exactly:

```text
v1
```

An explicit value is valid only when it matches exactly:

```text
^[a-z0-9][a-z0-9._-]{0,31}$
```

Thus the label is 1-32 lowercase ASCII characters, begins with letter/digit, and after the first character may contain only lowercase letters, digits, `.`, `_`, `-`.

No whitespace, control characters, slash/backslash, quotes, colon, uppercase, or non-ASCII text is accepted.

Validation rules:

- missing CLI/env value -> exact default `v1`;
- explicit empty/invalid value -> pseudonym emission disabled; do not fall back to env/default;
- label is process/server configuration only and cannot be supplied by browser/tool/provider/A2A/MCP/baggage/trace/request data;
- label is never derived from key bytes and never contains key material;
- key-version failure never disables core tracing or Agent/model/tool execution.

## 5. Every pseudonym is paired with its key version

Whenever a canonical local `invoke_agent` span emits one or more of:

```text
uag.correlation.principal
uag.correlation.room
uag.correlation.project
```

that same span MUST emit exactly one:

```text
uag.correlation.key_version
```

with the effective validated version label for the key generation that produced every pseudonym on the span.

Rules:

- all pseudonyms on one span use the same effective key material/version;
- mixing key generations on one span is forbidden;
- `uag.correlation.key_version` is not emitted alone on a span with no pseudonym;
- historical spans retain their historical pseudonym/version pair;
- version and pseudonyms are trace-only diagnostic metadata;
- they are forbidden from metrics, baggage, resource attributes, authorization, routing, storage keys, Memory identity, credential selection, and ordinary-user `uag.trace_view.v1`.

## 6. Rotation semantics

One version label identifies one intentionally selected correlation-key generation inside one deployment correlation domain.

When key material is intentionally rotated:

- the configured version label must also change before new pseudonyms are emitted;
- new spans use the new key/version;
- historical traces are not rewritten;
- reusing one version label with different key material is a configuration error and fails closed when detectable by UAG-managed metadata;
- when an external credential store cannot expose enough metadata to detect reuse, operators must rotate the label together with the key; UAG does not invent a replacement label.

The key-version label is intentionally **not** part of the HMAC message in the initial construction. Domain separation is supplied by the dedicated key plus `deployment_scope` and `kind`; version is diagnostic rotation metadata.

## 7. Pseudonyms are never security identities

A pseudonym or key-version label must never be used to:

- authenticate;
- authorize room/project/private scope;
- choose `TurnContext` or session;
- read/write Memory;
- restore Agent state;
- select credentials;
- route requests;
- build storage keys;
- authorize trace queries.

Collision cannot merge authorization because authorization uses only current UAG-owned identity/scope records.

## 8. Required regressions

Tests must prove that:

- `kind` accepts only exact `principal|room|project`;
- adversarial tuples that collide under naive concatenation differ under length-prefixed framing;
- raw identifier is exact built-in string, <=256 scalar values and <=1024 UTF-8 bytes, with no surrogates;
- oversized/custom raw identifiers are rejected before unbounded conversion/encoding work;
- equivalent key/scope/kind/raw-id inputs yield the same pseudonym across replicas;
- different kind or deployment scope domain-separates output;
- every exported pseudonym is exactly 32 lowercase hex and equals the first 128 digest bits;
- shorter/longer/base64/base64url/uppercase forms are rejected;
- pseudonyms appear only on local canonical `invoke_agent` segment roots and are not repeated on `chat`, `execute_tool`, provider-SDK, or remote spans;
- missing key version resolves to exact `v1`;
- valid version lengths 1 and 32 pass; invalid/uppercase/whitespace/non-ASCII/33-char versions fail closed;
- invalid explicit CLI version does not fall back to env or default;
- request/provider/tool/peer/trace data cannot override the version;
- every span with any pseudonym has exactly one matching `uag.correlation.key_version`;
- a span without pseudonyms has no standalone key-version attribute;
- one span cannot mix key versions;
- rotation changes key and label before new emission;
- no pseudonym/version attribute appears in metrics, baggage, resources, ordinary-user trace view, or authorization inputs;
- no pseudonym failure affects normal Agent execution.

## 9. Fixed Phase 4 decisions from this contract

- HMAC input framing, kind vocabulary, raw-identifier bounds, and attachment scope are exact and closed.
- Initial pseudonym output is exactly the first 128 HMAC-SHA-256 bits as 32 lowercase hex characters.
- Pseudonyms are attached only to each local canonical `invoke_agent` segment root.
- The only initial pseudonym attributes are principal/room/project plus same-span `uag.correlation.key_version`.
- Key-version default is `v1`; explicit labels match `^[a-z0-9][a-z0-9._-]{0,31}$`.
- Rotation changes key material and version label together.
- Pseudonyms and version labels are diagnostics only and never become security identities.