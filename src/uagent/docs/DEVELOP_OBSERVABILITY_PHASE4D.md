# OpenTelemetry Phase 4D ordinary-user trace query

Phase 4D adds an authorization-aware ordinary-user trace-query path. The normative
contract is `docs/UAG_OPENTELEMETRY_PHASE4_CONTRACT.md`; this file records the
implementation slices and developer-facing boundaries only.

## Slice 4D-1: bounded local ownership index

The first implementation slice adds
`runtime/observability/trace_ownership_index.py`. It is process-local and
independent from the telemetry backend. Backend records can never create, repair,
or repopulate ownership records.

The index stores only bounded authorization metadata for local trace segments:

- canonical 32-character lowercase non-zero trace ID;
- canonical 16-character lowercase non-zero local segment root span ID;
- bounded principal, room, project, service, and entry-point text;
- private-session and server-bound-project flags;
- canonical owned span IDs paired atomically with one immutable trusted semantic
  kind from `invoke_agent`, `chat`, `execute_tool`, `provider_sdk`, `internal`, or
  `unknown`.

A segment admission atomically registers its root span as `invoke_agent` and
returns a generation-bound `TraceAdmissionHandle`. Later owned-span registration
requires the still-live handle. Conflicting semantic ownership or a per-trace
ceiling violation marks the generation non-queryable instead of guessing.

The hard per-trace ceilings are the Phase 4 contract values:

```text
segments per trace        64
owned spans per trace     2000
scope text per field      256 characters
```

The aggregate process-lifetime ceilings are also fixed:

```text
traces                    4096
segments                  16384
owned spans               65536
accounted retained bytes  64 MiB
TTL                        24 hours from first admission
```

Retained storage is charged conservatively before allocation. Capacity pressure
evicts whole traces in ascending `(first_admitted_monotonic_time, trace_id)` order.
Expiry, capacity eviction, or explicit deletion invalidates the old generation;
a stale handle cannot recreate it. Reads and updates never extend the original
24-hour TTL.

`lookup_segments()` returns only a bounded immutable snapshot and requires the
caller's existing shared monotonic deadline. It rechecks the deadline while
materializing segments. `generation_is_live()` is the final liveness hook used by
the route/projection slices before returning data.

## Slice 4D-2: trusted runtime ownership binding

The second slice adds `runtime/observability/trace_ownership_runtime.py` and binds
the local index to canonical runtime span creation without changing Agent/model/tool
behavior.

A canonical `lifecycle_execution()` masks any parent ownership binding before its
`invoke_agent` span is created. Immediately after that root span exists, 4D-2 may
admit it using only the already-resolved `TurnContext`, the active canonical
trace/span IDs, and the local OTel `service.name`. The resulting generation handle
is bound only for that Agent-span lifetime. A `TurnContext` supplied later through
`apply_turn_context_to_current_agent_span()` never backfills ownership.

The UAG-owned OTel span factory is wrapped once during observability bootstrap.
While a live admitted generation is bound, each new local child is registered from
the trusted UAG operation passed at creation time:

```text
invoke_agent  -> invoke_agent
chat          -> chat
execute_tool  -> execute_tool
provider_sdk  -> provider_sdk
other UAG-owned operations -> internal
```

The classifier uses the local operation before OTel semantic mapping. It never
reconstructs semantic kind from exported `span.name`, attributes, resource data,
provider/model/tool text, URLs, or backend query results. Nested canonical Agent
executions mask the parent binding, admit a second local segment, and restore the
parent binding when they exit.

Runtime binding is active only when both core observability and
`trace_query_enabled` are true. Replacing the active backend or resolved settings
starts a new process-local ownership epoch, so stale bindings cannot write into a
new index generation. Backend authority is rechecked while serializing an epoch
replacement so a retired backend cannot race a newer authoritative backend and
replace its ownership index. Missing/mismatched child trace/span IDs fail closed
and make the current generation non-queryable on a best-effort basis; tracing and
Agent execution continue normally.

Regression coverage is split between
`tests/test_observability_phase4_trace_ownership_index.py` and
`tests/test_observability_phase4_trace_ownership_runtime.py`. The runtime tests
cover root scope capture, the closed semantic-kind mapping, nested local segments,
feature-disabled behavior, rejection of late TurnContext backfill, exact-local
span proof, and backend-replacement races.

## Slice 4D-3: authenticated bounded Web route

The third slice adds exactly:

```text
GET /api/observability/traces/{trace_id}
```

The route preserves the normative processing order. The Phase 4D feature gate is
checked before authentication. After successful existing product authentication,
one five-second monotonic deadline is created and reused by request-shape checks,
local-index lookup, authorization revalidation, backend work, projection, and the
final generation check.

Initial and final local authorization, including their synchronous policy-store
access, run in worker threads alongside backend projection/paging. Each await is
bounded on the event loop by the remaining original five-second budget, including
executor queue time. Timeout discards the worker result and returns fixed 503,
unless ownership epoch/generation invalidation requires fixed 404 first. Python
cannot interrupt an already-running synchronous adapter or policy query; that
worker may finish later, but its result is never published. Queued work checks the
deadline before starting, and backend work rechecks ownership after queueing and
before calling the adapter.

The v1 route accepts no query string or request body. It examines raw ASGI framing
metadata without decoding query/body content. `Transfer-Encoding`, multiple or
malformed `Content-Length` values, and any positive content length fail with the
fixed `invalid_request` result before trace-ID/index work. `Content-Length: 0` is
accepted. For HTTP/1.0 and HTTP/1.1, absence of both framing headers proves an empty
request body. ASGI provides no receive API that can cap an HTTP/2/3 presence probe
to one decoded octet, so an unframed HTTP/2/3 request fails closed unless
`Content-Length: 0` already proves emptiness; route logic never drains or
materializes a request body.

After canonical trace-ID validation, the route consumes only the bounded local
ownership snapshot. It validates the closed semantic-kind/index shape and
revalidates current product identity, project membership, room membership,
private-room ownership, and room-to-project binding for every local segment and
again for every indexed owned span. Every authorized segment must still belong to
the authenticated principal recorded at admission; membership in the same shared
room or project never grants access to another principal's turn trace. Current
session or authorization revocation during a query fails closed instead of
returning a mixed-time authorization view.

A missing, expired, malformed, incomplete, timed-out, or zero-authorized local view
returns the single fixed `trace_not_found` result and never accesses a telemetry
backend. Before leaving the authorization slice, the route also verifies that the
same ownership epoch is still authoritative and that the snapshot generation is
still live.

## Slice 4D-4: bounded backend adapter and closed projection

The fourth slice adds
`runtime/observability/trace_query_projection.py`. The module defines the only
trusted application-integration surface for backend reads and performs all
ordinary-user projection independently from backend/vendor metadata.

Phase 4's public configuration contract intentionally contains no backend query
URL, backend query credential, vendor selector, or alternate trace-query setting.
Therefore UAG does not reinterpret an OTLP export endpoint as a query API and does
not accept request-controlled backend configuration. A trusted application
integration may bind one reviewed adapter to the exact active observability
backend instance with `install_trace_query_backend_adapter()`. Replacing the
observability backend makes the previous binding unusable by identity. With no
adapter bound, a fully authorized trace continues to return the fixed
`503 {"error":"trace_query_unavailable"}` result.

A reviewed adapter receives only the validated trace ID, an opaque bounded cursor,
remaining page/span/decoded-byte ceilings, and the already-started monotonic
query deadline. It must enforce decoded-byte limits while reading rather than
materializing an unbounded raw response. Adapter output is the closed
`TraceBackendPage` / `TraceBackendSpanRecord` representation; raw backend payload,
attributes, events, links, resource data, provider metadata, exception text, and
credentials are never passed to the Web response layer.

The retrieval loop enforces the contract ceilings:

```text
decoded backend bytes     8 MiB
backend spans             2000
spans per page            500
backend pages             4
authorized spans returned 500
```

Projection requires every considered record to carry the exact requested canonical
trace ID before span-ID membership lookup. Canonical duplicate span IDs are all
omitted. Only span IDs present in the currently authorized local view can project,
and their output names come exclusively from the immutable local semantic-kind
association:

```text
invoke_agent  -> AGENT
chat          -> LLM
execute_tool  -> TOOL
provider_sdk  -> PROVIDER_SDK
internal      -> INTERNAL
unknown       -> UNKNOWN
```

Status normalization accepts only the contract's bounded exact built-in strings.
Timing accepts only exact integer `ms`, `us`, or `ns` values, validates chronology
at original precision, converts to integer epoch milliseconds, and derives
`duration_ms`; textual timestamps are never parsed. Parent IDs are emitted only
when the canonical parent also survives authorization, validation, and output
truncation. Otherwise the ID is omitted and `parent_omitted=true`.

The route returns only the closed `uag.trace_view.v1` schema. Known safe omissions
set `partial=true`, including backend truncation, unauthorized/unindexed records,
trace-ID mismatch, invalid or duplicate span IDs, invalid timing, missing expected
owned records, parent omission, and the 500-span output cap. Adapter/projection
failure after successful authorization returns the fixed 503 with no backend
payload. Ownership epoch/generation replacement still overrides a backend result
with the fixed 404 before a successful response is returned.

Regression coverage is in
`tests/test_observability_phase4_trace_query_projection.py` in addition to the
4D-1/4D-2/4D-3 suites. Coverage includes closed schema/semantic mapping,
duplicate handling, trace binding, exact timing/status rules, byte/page/output
ceilings, adapter/backend identity binding, and a successful Web-route projection.
