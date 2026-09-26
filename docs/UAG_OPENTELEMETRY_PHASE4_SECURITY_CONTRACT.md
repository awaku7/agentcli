# OpenTelemetry Phase 4 Security and Configuration Contract

Status: Normative Phase 4 companion  
Parent scope: `docs/UAG_OPENTELEMETRY_PHASE4_SCOPE.md`  
Applies to: Phase 4A-4D implementation and tests

This document closes implementation ambiguities found during Phase 4 design review. Where this contract is stricter than an example or suggested shape in the parent scope, this contract is normative for the initial Phase 4 implementation.

## 1. Configuration precedence and CLI surface

Phase 4 follows the same product rule as core OpenTelemetry configuration: explicit entry-point configuration overrides environment fallback, which overrides defaults.

```text
explicit CLI/application setting
    > UAGENT_* environment setting
    > safe default
```

The overall `--otel` / `--no-otel` switch remains authoritative. If effective core OTel activation is OFF, all Phase 4 features are inactive even when subordinate Phase 4 options are present.

The CLI must expose the public Phase 4 controls corresponding to the server/process environment settings:

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

- CLI parsing uses the shared observability settings resolver rather than entry-point-specific semantics.
- If both positive and negative boolean flags are present, the last explicit flag wins, matching existing `--otel` / `--no-otel` behavior.
- Invalid category names, numeric bounds, provider names, key versions, or deployment scopes fail closed for the affected Phase 4 feature.
- The correlation **key value** is never accepted as a CLI argument. Only the credential-store key name may be configured.
- Browser input, WebSocket messages, A2A payloads, tool calls, trace baggage, headers, or provider responses cannot alter effective Phase 4 configuration.

### 1.1 Concrete controlled-content bounds

The initial Phase 4 controlled-content limits are fixed as follows:

```text
UAGENT_OTEL_CAPTURE_MAX_FIELD_CHARS
  default: 2048
  minimum: 64
  maximum: 16384

UAGENT_OTEL_CAPTURE_MAX_SPAN_CHARS
  default: 8192
  minimum: 256
  maximum: 65536
```

The same ranges apply to the corresponding CLI options.

Validation rules:

- a missing value uses the documented default;
- a non-integer, zero, negative, below-minimum, or above-maximum value is invalid;
- the effective span limit must be greater than or equal to the effective field limit;
- any invalid bound disables controlled content capture as a whole for that process, even if the master gate and categories are otherwise enabled;
- invalid bounds never fall back silently to an effectively unbounded value;
- disabling capture because of invalid bounds emits only a normalized secret-free diagnostic and does not disable core metadata tracing.

These are safety ceilings, not targets. A later schema may lower them without weakening this contract; raising a ceiling requires explicit design review.

### 1.2 Provider selector vocabulary

Provider instrumentation selectors use UAG logical provider IDs, not SDK package names. The initial example is therefore:

```text
--otel-provider-instrumentation openai,claude
UAGENT_OTEL_PROVIDER_INSTRUMENTATION=openai,claude
```

`claude` is the logical UAG provider ID for the Anthropic SDK path. `anthropic` is not an alias in the initial Phase 4 contract. Unknown names fail closed to no instrumentation for that selector and produce only a normalized diagnostic.

## 2. Stable deployment scope for pseudonymous correlation

Pseudonymous correlation requires an explicit, stable deployment scope.

The scope is resolved from:

```text
--otel-deployment-scope
    > UAGENT_OTEL_DEPLOYMENT_SCOPE
    > no value
```

There is no hostname, PID, random process value, current working directory, repository path, or machine-local implicit fallback.

### 2.1 Exact validation and hashing semantics

The configured value is validated **without trimming or other canonical rewrite**. Initial validation accepts exactly 1-128 UTF-8 characters and rejects:

- an empty value;
- any leading or trailing Unicode whitespace;
- control characters;
- values longer than 128 characters.

Internal whitespace is permitted when it is not leading/trailing whitespace or a control character. No Unicode normalization, case folding, path normalization, delimiter rewriting, or other canonicalization is performed.

The exact validated configured string is the `deployment_scope` value framed into the HMAC input. Therefore:

```text
prod     -> valid, hashes as "prod"
" prod"  -> invalid
"prod "  -> invalid
```

This avoids two ambiguous outcomes: implementations must neither silently collapse distinct configured values by trimming nor hash surrounding whitespace that validation appeared to ignore.

Requirements:

- the value is stable across replicas that are intentionally part of the same correlation domain;
- production, staging, development, test, customer, or tenant deployments that must not correlate use distinct deployment-scope values and/or distinct correlation keys;
- callers cannot supply or override it per request/turn;
- it is not used as authorization, identity, storage, or routing state;
- it is not exported as a raw trace attribute by default;
- changing it intentionally breaks pseudonym correlation.

If pseudonymous correlation is enabled but deployment scope is missing or invalid, pseudonym emission is disabled and a secret-free normalized diagnostic is produced. Core tracing continues unchanged.

## 3. Field-level provenance for content capture

Operation-level provenance alone is insufficient for composite messages and tool values. Every body-bearing field that can contain a forbidden source must be classified at the field/node level before content eligibility is evaluated.

### 3.1 Trusted field provenance

Trusted UAG code assigns provenance to individual structured nodes, not only to the outer operation.

Examples that require explicit field-level classification include:

```text
create/write file tools:
  path       -> ordinary tool metadata
  content    -> file_body (forbidden)

message attachments:
  filename/content-type metadata -> attachment_metadata
  inline text/data URL/base64 body -> file_body or artifact_body (forbidden)

artifact helpers:
  artifact id/name/type metadata -> artifact_metadata
  embedded body/bytes/text       -> artifact_body (forbidden)

Memory/retrieval composites:
  count/type/status metadata      -> safe derived metadata when explicitly constructed
  record/query/body/result text   -> memory_body/retrieval_body (forbidden)
```

The implementation must distinguish safe derived metadata from body data. A parent value tagged `tool_argument`, `ordinary_tool_result`, or `user_message` does not make all descendants eligible.

### 3.2 Unannotated composites fail closed

For a structured value that can contain heterogeneous provenance, an unannotated child is not assumed to inherit an allowed category.

Rules:

- known body-bearing fields must have an explicit trusted provenance tag;
- an unannotated child of a body-capable composite is omitted from content capture;
- unknown attachment/provider/tool composite shapes fail closed to omission unless a reviewed adapter maps individual fields;
- data URLs, base64 blobs, byte arrays, file-like objects, attachment payloads, and body wrapper objects are treated as forbidden body content unless a reviewed safe-metadata extractor is used;
- a tool/provider payload cannot self-assert a safe provenance through its own keys or values;
- safe metadata extractors create new bounded scalar values rather than relabeling an opaque body-bearing object.

### 3.3 Required regressions

Phase 4A tests must include at least:

- a file-writing tool with `content` in `tool_arguments` while `tool_arguments` capture is enabled;
- an attachment represented as a `data:` URL inside otherwise allowed `user_input`;
- base64/binary attachment bodies inside a structured user/tool value;
- inline file/artifact/Memory/retrieval bodies returned from a tool;
- an unknown composite with one unannotated body-bearing child.

All body content above must remain absent from exported telemetry.

## 4. Ordinary-user trace view v1 is metadata-only

The initial ordinary-user schema `uag.trace_view.v1` is metadata-only.

For v1, the proxy MUST NOT return general `attributes` or `events` containers. They are deferred until a separately reviewed schema enumerates every allowed nested key and event.

The complete ordinary-user v1 span schema is:

```text
schema_version = "uag.trace_view.v1"
trace_id
partial
spans[]:
  span_id
  parent_span_id        # only when parent is also authorized and returned
  parent_omitted        # boolean
  name                  # bounded canonical/supported span name
  start_time
  end_time
  duration_ms
  status_code           # closed UAG-owned normalized enum
```

No other span member is returned in v1.

`status_code` is mapped by UAG from backend/provider status into a closed product-owned vocabulary. The initial vocabulary is limited to:

```text
UNSET
OK
ERROR
```

Unknown or malformed backend status values map to `UNSET`. Arbitrary backend/provider status text, exception text, URLs, request details, or descriptions are never copied into the ordinary-user response.

In particular, v1 excludes:

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
prompt/response/tool content
identity/scope pseudonyms
raw identity/authorization fields
backend/vendor extensions
exception messages/stacks
```

Unknown top-level, span-level, or nested backend structures are dropped. The proxy constructs the response object field-by-field and never forwards or recursively serializes backend JSON.

If later requirements need descriptive status text, safe attributes, or events, introduce `uag.trace_view.v2` (or an explicitly versioned extension) with a closed UAG-owned message table and/or enumerated permitted attribute keys, event names, and event-attribute keys plus privacy tests. `v1` does not grow implicitly.

## 5. Trace-query resource limits

Ordinary-user trace queries are bounded before and after authorization filtering. A backend adapter is supported only if it can enforce these limits without first materializing an unbounded response.

Initial Phase 4D limits are:

```text
backend deadline:             5 seconds
maximum decoded backend bytes: 8 MiB
maximum backend spans fetched: 2000
maximum spans per backend page: 500
maximum backend pages:           4
maximum authorized spans returned: 500
```

Requirements:

- adapters use backend-side pagination/limits where available;
- HTTP/stream readers enforce the decoded byte ceiling while reading, not after loading the entire body;
- reaching the byte, span, page, or deadline limit stops further backend retrieval;
- a backend integration that cannot enforce a bounded read is unsupported for ordinary-user Phase 4D queries;
- authorization/filtering is applied only to bounded fetched data;
- returned authorized spans are deterministically ordered by `(start_time, span_id)` before the output-span ceiling is applied;
- when a safe prefix/subset can be returned after any fetch/output ceiling is reached, `partial=true` is mandatory;
- if an adapter cannot determine a safe bounded partial result after a limit is hit, the query fails with a bounded server error and returns no backend payload;
- truncation never relaxes segment authorization and never exposes omitted parent/span identifiers;
- backend limit failures do not affect Agent execution.

The proxy must not retry in a way that can exceed the same per-query aggregate ceilings.

## 6. Additional acceptance tests

The implementation is not complete until these cases are covered:

### Configuration

- each new CLI Phase 4 option overrides its environment fallback;
- effective `--no-otel` suppresses all Phase 4 behavior regardless of subordinate flags;
- absent capture bounds use exactly 2048 field chars and 8192 span chars;
- `0`, negative, non-integer, below-minimum, above-maximum, or span-smaller-than-field bounds disable controlled content capture without affecting core tracing;
- no CLI option accepts raw correlation key material;
- provider selectors use logical IDs and `claude` selects the Anthropic SDK path while `anthropic` remains unknown unless a future reviewed alias is added.

### Deployment scope

- missing scope while pseudonymization is requested emits no pseudonym;
- empty/invalid scope emits no pseudonym;
- exact `prod` is valid and is framed exactly as configured;
- ` prod `, leading-whitespace, or trailing-whitespace variants are invalid rather than trimmed or hashed with whitespace;
- the same key + same stable deployment scope across replicas produces stable pseudonyms;
- different deployment scopes produce different pseudonyms;
- no process-random/hostname fallback silently substitutes for a missing scope;
- no Unicode/case/path normalization silently rewrites a valid scope before hashing.

### Field provenance

- file-writing `content` arguments remain excluded with `tool_arguments` enabled;
- attachment data URLs and base64/binary bodies remain excluded with `user_input` enabled;
- unannotated body-capable composite children are omitted;
- safe derived metadata can be captured only when explicitly constructed and tagged by trusted UAG code.

### Trace view

- `uag.trace_view.v1` contains no `attributes`, `events`, or `status_description` keys;
- `status_code` is one of the closed UAG-owned values `UNSET`, `OK`, or `ERROR`;
- unknown/malformed backend status values map to `UNSET` without copying backend text;
- backend status descriptions, exception text, attributes/events/resources/links/vendor extensions are not copied even when present;
- schema output is identical in shape across supported backends for equivalent safe metadata;
- unknown backend fields do not appear in the response.

### Trace-query bounds

- an oversized backend response is stopped before exceeding the 8 MiB decoded-byte ceiling;
- more than 2000 backend spans or four pages are not fetched;
- a backend call cannot run beyond the five-second adapter deadline;
- at most 500 authorized spans are returned;
- deterministic truncation sets `partial=true`;
- an adapter unable to produce a safe bounded partial result returns no raw/backend payload;
- pagination/retry behavior cannot exceed aggregate per-query limits.

## 7. Fixed Phase 4 decisions from this contract

- Phase 4 has a CLI surface with explicit-setting > environment > default precedence.
- Raw correlation keys are credential-store values, never CLI values.
- Controlled content capture uses explicit finite ranges and invalid bounds disable capture rather than broadening it.
- Provider instrumentation selectors use UAG logical provider IDs; the Anthropic path is selected as `claude`.
- Pseudonymization requires a non-empty stable deployment scope; surrounding whitespace is rejected and the exact validated value is framed into the HMAC.
- Content provenance is field/node-level for body-capable composites.
- Unannotated body-capable composite fields fail closed.
- File/artifact/Memory/retrieval/authentication bodies cannot become eligible merely by being nested inside allowed `user_input`, `tool_arguments`, or `tool_result` values.
- Ordinary-user `uag.trace_view.v1` is strictly metadata-only and has no generic `attributes`, `events`, or free-form status-description fields.
- Ordinary-user v1 `status_code` is a closed UAG-owned enum and never includes copied backend/provider text.
- Ordinary-user trace-backend retrieval is bounded before authorization filtering and cannot materialize an unbounded backend response.
