# UAG OpenTelemetry Phase 2 Implementation

Status: implementation plan for Phase 2  
Base: Phase 1 merged in PR #85  
Scope: Context / Memory / Retrieval tracing, low-cardinality metrics, and Decision Log trace linkage

## Goals

Phase 2 extends the provider-neutral observability layer introduced in Phase 1. OpenTelemetry remains an adapter/export backend; runtime code must not depend on OpenTelemetry SDK types.

Implement the following without changing authentication, authorization, Memory selection semantics, Context selection semantics, provider behavior, or tool behavior.

### 1. Context tracing

Instrument centralized Context Runtime boundaries with UAG-owned spans:

- `uag.context.build` for provider-neutral active-context/message-context construction.
- `retrieval` for bounded persisted-context retrieval.
- `uag.provider.project` only where there is already a centralized provider projection boundary and adding the span does not duplicate the canonical `chat` span.

Do not create per-candidate spans.

Context spans may export metadata such as:

- context kind (`messages`, `candidates`, or equivalent low-cardinality enum)
- input record/candidate count
- selected candidate count
- raw/active/saved char counts
- raw/active/saved estimated token counts
- saved ratio
- decision counts by action
- bounded retrieval round number/count where applicable

Never export context bodies, candidate content, item IDs, artifact references, query text, session IDs, room IDs, project IDs, principal IDs, or raw Decision Log reasons.

### 2. Memory tracing

Instrument the centralized Memory projection/retrieval boundary with a logical Memory/retrieval span. Prefer one span per logical projection/retrieval operation rather than one span per memory item.

Safe attributes include only low-cardinality or aggregate values, for example:

- projection enabled/disabled
- strict-scope boolean
- identity-bound boolean
- personal/shared retrieval enabled flags
- total/candidate/eligible/excluded counts
- evidence count
- profile/guidance present booleans
- memory/guidance budget sizes and used sizes

Do not export memory text, profile text, query text, memory IDs, revisions, owner/principal IDs, room/project IDs, session/turn IDs, grant IDs, projection fingerprints, or references.

Authorization and scope checks remain authoritative and unchanged. Observability failure must not change whether a memory item is readable.

### 3. Retrieval tracing

Instrument the provider-neutral `context_retrieval` path and Memory retrieval path with `retrieval` spans (or the adapter's matching GenAI retrieval operation). Use a low-cardinality attribute to distinguish retrieval kind such as `context` vs `memory`; do not put the query or record identifiers into attributes.

### 4. Aggregate metrics

Extend `ObservabilityBackend` with a small provider-neutral metric API. Runtime code must not import OTel meter classes.

The no-op backend must remain safe and zero-cost when OTel is disabled.

The OTel backend should export low-cardinality metrics through OTLP when metrics are enabled by standard `OTEL_*` settings. Support `OTEL_METRICS_EXPORTER=none` without disabling tracing. Metrics initialization/export failures must degrade metrics only; they must not disable tracing or fail Agent execution.

Recommended initial metrics:

- `uag.context.raw.chars` histogram
- `uag.context.active.chars` histogram
- `uag.context.saved.chars` histogram
- `uag.context.raw.tokens` histogram when available
- `uag.context.active.tokens` histogram when available
- `uag.context.saved.tokens` histogram when available
- `uag.context.saved.ratio` histogram
- `uag.context.decisions` counter, with only decision action as an attribute
- `uag.retrieval.records` histogram
- `uag.retrieval.candidates` histogram
- `uag.memory.records` histogram
- `uag.memory.candidates` histogram
- `uag.memory.evidence` histogram

Metric attributes must never contain principal/subject, room/project/session/turn IDs, trace/span IDs, group names, item IDs, memory IDs, references, provider request IDs, or arbitrary user strings.

### 5. Decision Log linkage

Decision Log remains independent from OpenTelemetry.

Add metadata-only linkage between a Context decision batch and the active trace/span using the existing structured-event/correlation mechanism and/or explicit safe trace identifiers. Do not copy decision reasons, content, references, or item IDs into telemetry.

The linkage must make it possible to correlate a persisted Context decision batch with the `uag.context.build` trace without turning OTel into the Decision Log store.

Prefer a single batch-level event with aggregate action counts rather than one event per decision.

### 6. Privacy / failure isolation

Phase 1 privacy filtering remains authoritative. Add regression coverage ensuring the new spans and metrics do not export:

- prompt/system/assistant/tool/memory/profile bodies
- retrieval query text
- decision reason text
- item/memory/reference IDs
- raw identity/scope values
- authorization/session material

All instrumentation is best-effort. Any tracing/metric exporter or instrumentation exception must leave runtime results unchanged.

## Implementation boundaries

Prefer the existing centralized modules:

- `src/uagent/runtime/observability/*`
- `src/uagent/runtime/context_manager.py`
- `src/uagent/runtime/context_retrieval.py`
- `src/uagent/runtime/memory_projection.py` / the centralized Memory retrieval boundary
- existing structured logging / correlation code for Decision Log linkage

Avoid broad provider-specific edits. Do not add provider SDK auto-instrumentation.

## Tests

Add focused tests covering at least:

1. Context build emits one logical context span with aggregate metadata only.
2. Context retrieval emits a retrieval span without query/content/IDs.
3. Memory projection/retrieval emits aggregate metadata only and preserves authorization behavior.
4. Decision Log linkage contains aggregate counts plus trace/span linkage but no decision bodies/reasons/IDs.
5. No-op backend accepts metric calls safely.
6. OTel metrics adapter records counters/histograms with sanitized low-cardinality attributes.
7. `OTEL_METRICS_EXPORTER=none` leaves tracing operational.
8. Metrics initialization/export failure does not disable tracing.
9. Existing Phase 1 privacy and Web/OIDC tests remain green.
10. Black, Ruff, i18n/tool-catalog checks, full pytest, and Python 3.11/3.13/3.14 compatibility remain green.

## Out of scope for this PR

- trusted distributed propagation for Sub-Agent / A2A / MCP (Phase 3)
- trusted reverse-proxy inbound trace policy (Phase 3)
- controlled content capture (Phase 4)
- user-visible trace query UI/proxy (Phase 4)
- provider SDK auto-instrumentation
- Decision Log schema redesign or migration unless strictly required for safe batch-level trace linkage
