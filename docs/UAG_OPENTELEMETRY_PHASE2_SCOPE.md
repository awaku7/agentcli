# UAG OpenTelemetry Phase 2 Scope

Status: implementation scope for the next OpenTelemetry PR after #85  
Base: `main` after `feat: add OpenTelemetry runtime tracing`

## Goal

Extend the existing provider-neutral UAG observability layer with Phase 2 instrumentation while keeping OpenTelemetry as a projection backend rather than a runtime contract.

This PR covers:

- Context build spans;
- Memory operation spans;
- Retrieval spans;
- low-cardinality aggregate metrics;
- Decision Log linkage to the active trace/span;
- regression tests and observability documentation updates.

Trusted distributed propagation for Sub-Agent/A2A/MCP is explicitly deferred to the following PR.

## Required boundaries

Instrumentation should attach to existing centralized UAG boundaries instead of being scattered through provider-specific or UI-specific code.

Use the existing runtime observability package under `src/uagent/runtime/observability/` and extend its provider-neutral API as needed. Runtime code must not import raw OpenTelemetry SDK classes.

### Context

Create one logical `uag.context.build` span for each active-context build/projection path that is already centralized by the Context Runtime.

Safe metadata may include aggregate counts and sizes such as:

- candidate/message count;
- decision count by action;
- raw/active/saved chars;
- raw/active/saved estimated tokens;
- saved ratio;
- whether the build was budgeted/compacted.

Do not export context bodies, message text, item IDs, references, file names, raw session/project/room/principal identifiers, or other high-cardinality scope values.

### Memory

Instrument the existing centralized Memory create/update/search/read/delete boundaries where they exist. Use logical operation names that remain provider-neutral and compatible with future GenAI semantic-convention mapping.

Export only safe aggregate metadata by default, for example operation type, result count, success/failure, and duration. Do not export memory bodies, user content, raw IDs, references, or identity/scope metadata.

### Retrieval

Instrument centralized retrieval/search boundaries rather than individual backends. Avoid duplicate spans when a Memory search already owns the logical operation.

Safe attributes may include retrieval kind/backend class when it is bounded and non-sensitive, result count, cache hit/miss if already available, and terminal status. Queries/results must remain excluded by default.

## Metrics

Add a provider-neutral metric API to the UAG observability contract and implement it in the no-op and OTel backends.

Phase 2 metrics should remain low-cardinality. At minimum cover useful aggregates already produced by runtime code, such as:

- operation duration/count/error count for Context/Memory/Retrieval;
- context raw/active/saved size;
- context compression/savings ratio;
- token estimates where already available.

Never use principal/session/room/project/trace/span IDs, memory IDs, item IDs, query text, tool names from unbounded user/plugin namespaces, file paths, URLs, group names, or arbitrary exception messages as metric dimensions.

Respect standard `OTEL_METRICS_EXPORTER` / OTLP configuration once UAG observability is enabled. Metrics/exporter failures must remain isolated and must never fail Agent execution.

## Decision Log linkage

The existing Decision Log remains UAG-owned storage and must not be replaced by OTel.

When a context decision log is persisted while a trace/span is active, store linkage fields when available:

- `correlation_id` (existing UAG correlation);
- `trace_id`;
- `span_id`;
- existing decision/projection identifiers if already present.

Do not copy detailed reasoning/content into telemetry merely to establish linkage. Missing or sampled-out trace IDs must remain valid and non-fatal.

## Privacy and failure isolation

All Phase 1 rules from `docs/UAG_OPENTELEMETRY_DESIGN.md` remain mandatory:

- metadata-only by default;
- no prompt/response/tool/memory/retrieval/context bodies;
- no OIDC/session secrets or raw identity claims;
- no raw principal/subject/group values;
- authorization never depends on telemetry;
- telemetry failure never changes Agent behavior;
- semantic-convention-specific naming stays isolated in the adapter.

## Tests

Add focused regressions for at least:

- OTel disabled remains behaviorally inert;
- Context span hierarchy under the Agent trace;
- Memory and Retrieval span hierarchy without duplicate logical spans;
- context aggregate metadata and token estimates are emitted without content;
- Decision Log stores trace/span linkage when available and works when unavailable;
- metric dimensions reject/omit high-cardinality identity/scope/content fields;
- metrics exporter initialization/failure falls back safely;
- Web/OIDC privacy guarantees from Phase 1 remain intact;
- Black, Ruff, compile checks, full pytest, and supported Python compatibility continue to pass.

## Out of scope

The following belong to the next PR or later phases:

- trusted W3C propagation across Sub-Agent/A2A/MCP;
- reverse-proxy trusted-ingress policy;
- multi-instance propagation validation;
- provider SDK auto-instrumentation;
- controlled content capture;
- pseudonymous identity/scope correlation;
- trace-query UI/proxy.
