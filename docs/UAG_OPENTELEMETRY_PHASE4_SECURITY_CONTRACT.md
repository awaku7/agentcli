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

## 2. Stable deployment scope for pseudonymous correlation

Pseudonymous correlation requires an explicit, stable deployment scope.

The scope is resolved from:

```text
--otel-deployment-scope
    > UAGENT_OTEL_DEPLOYMENT_SCOPE
    > no value
```

There is no hostname, PID, random process value, current working directory, repository path, or machine-local implicit fallback.

Requirements:

- the value is non-empty after trimming;
- the value is stable across replicas that are intentionally part of the same correlation domain;
- production, staging, development, test, customer, or tenant deployments that must not correlate use distinct deployment-scope values and/or distinct correlation keys;
- callers cannot supply or override it per request/turn;
- it is not used as authorization, identity, storage, or routing state;
- it is not exported as a raw trace attribute by default;
- changing it intentionally breaks pseudonym correlation.

Initial validation accepts 1-128 UTF-8 characters after trimming and rejects control characters. Implementations may later narrow the syntax, but must not silently rewrite two distinct configured values into one scope.

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

The initial ordinary-user schema `uag.trace_view.v1` is intentionally narrower than the draft example in the parent scope.

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

## 5. Additional acceptance tests

The implementation is not complete until these cases are covered:

### Configuration

- each new CLI Phase 4 option overrides its environment fallback;
- effective `--no-otel` suppresses all Phase 4 behavior regardless of subordinate flags;
- invalid Phase 4 CLI/env values fail closed for only the affected feature;
- no CLI option accepts raw correlation key material.

### Deployment scope

- missing scope while pseudonymization is requested emits no pseudonym;
- empty/invalid scope emits no pseudonym;
- the same key + same stable deployment scope across replicas produces stable pseudonyms;
- different deployment scopes produce different pseudonyms;
- no process-random/hostname fallback silently substitutes for a missing scope.

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

## 6. Fixed Phase 4 decisions from this contract

- Phase 4 has a CLI surface with explicit-setting > environment > default precedence.
- Raw correlation keys are credential-store values, never CLI values.
- Pseudonymization requires a non-empty stable deployment scope; absence disables pseudonym emission.
- Content provenance is field/node-level for body-capable composites.
- Unannotated body-capable composite fields fail closed.
- File/artifact/Memory/retrieval/authentication bodies cannot become eligible merely by being nested inside allowed `user_input`, `tool_arguments`, or `tool_result` values.
- Ordinary-user `uag.trace_view.v1` is strictly metadata-only and has no generic `attributes`, `events`, or free-form status-description fields.
- Ordinary-user v1 `status_code` is a closed UAG-owned enum and never includes copied backend/provider text.
