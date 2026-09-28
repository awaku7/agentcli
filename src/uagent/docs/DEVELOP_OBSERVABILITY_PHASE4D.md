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
materializing segments. `generation_is_live()` is the final liveness hook that a
later HTTP/query slice uses before returning a successful projection.

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
new index generation. Missing/mismatched child trace/span IDs fail closed and make
the current generation non-queryable on a best-effort basis; tracing and Agent
execution continue normally.

Regression coverage is split between
`tests/test_observability_phase4_trace_ownership_index.py` and
`tests/test_observability_phase4_trace_ownership_runtime.py`. The runtime tests
cover root scope capture, the closed semantic-kind mapping, nested local segments,
feature-disabled behavior, and rejection of late TurnContext backfill.

These slices still do **not** expose
`/api/observability/traces/{trace_id}`, perform backend retrieval/projection, or
alter current Web authentication/authorization behavior. The trace-query feature
therefore remains inaccessible to ordinary users until the later route/query
slices are merged.

## Planned later slices

- **4D-3**: add the exact authenticated GET route, request framing/body-presence
  checks, one shared five-second deadline, and per-query authorization revalidation.
- **4D-4**: add reviewed bounded backend adapters and the closed
  `uag.trace_view.v1` projection with byte/page/span/output ceilings and final
  generation recheck.
