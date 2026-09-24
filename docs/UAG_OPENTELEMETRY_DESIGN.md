# UAG OpenTelemetry Integration Design

Status: Design only  
Target: post-v0.7.16  
Scope: observability architecture, OpenTelemetry integration boundary, signal model, privacy, propagation, rollout  
Non-goal: this document does not implement OpenTelemetry.

## 1. Purpose

UAG already has provider-neutral runtime boundaries, structured event logging, lifecycle events, tool dispatch events, LLM round summaries, Context Runtime telemetry, Decision Log data, Sub-Agent execution, A2A, MCP, and Web/CLI/GUI entry points.

The purpose of this design is to add OpenTelemetry (OTel) without making OpenTelemetry the internal contract of UAG.

The central rule is:

> UAG owns the observability model. OpenTelemetry is one projection/export backend of that model.

This keeps UAG stable when OpenTelemetry GenAI semantic conventions evolve and preserves the existing local structured logging and debugging experience.

## 2. Current UAG baseline

The current runtime already contains most of the information required for useful tracing.

- `runtime/logging_setup.py`
  - stable `event_code`
  - `event_id`
  - `correlation_id`
  - `agent_id`, `session_id`, `task_id`, `tool_call_id`
  - `provider`, `duration_ms`, `status`, `error_type`
  - ContextVar-based event context propagation
  - secret-field masking
- `runtime/execution.py`
  - shared Agent lifecycle events
- `runtime/round_orchestrator.py`
  - provider-neutral LLM round boundary
  - duration
  - event/tool-call counts
  - estimated request tokens
  - provider usage deltas
  - projection/tool-schema sizes
  - retry/recovery related summary fields
- `tools/__init__.py`
  - centralized tool execution boundary
  - tool completion/failure events
- Context Runtime
  - raw/active/saved context sizes
  - token estimates
  - per-section data
  - explicit Context Decision Log
- A2A/Sub-Agent/MCP
  - distributed or nested execution boundaries that benefit from trace propagation

OpenTelemetry should therefore be added as an adapter around these boundaries rather than by instrumenting provider SDKs independently.

## 3. Goals

### 3.1 Primary goals

1. Trace one UAG task across Agent, LLM, Tool, Context Runtime, Memory, Sub-Agent, A2A, MCP, and external calls.
2. Preserve a provider-neutral trace model across OpenAI, Azure OpenAI, Anthropic, Gemini, xAI, OpenRouter, LM Studio, llama.cpp, and future providers.
3. Export traces and metrics through OTLP to an OpenTelemetry Collector or compatible backend.
4. Correlate existing UAG structured logs with OpenTelemetry `trace_id` / `span_id`.
5. Keep Decision Log as a UAG-owned diagnostic/audit artifact rather than flattening it into span attributes.
6. Keep telemetry optional and failure-isolated.
7. Avoid capturing prompt, response, tool argument, tool result, memory body, and artifact body content by default.
8. Follow OpenTelemetry GenAI semantic conventions where stable/useful, but isolate semantic-convention mapping behind an adapter because the GenAI conventions are still Development status.

### 3.2 Non-goals

The first implementation must not:

- replace `log_event()`
- require an OpenTelemetry Collector for normal UAG operation
- make OTel packages part of the minimal installation
- alter LLM/provider behavior
- alter retry policy
- alter tool execution behavior
- alter Context Runtime decisions
- send raw conversation content by default
- use OpenTelemetry as persistent Agent state
- use spans as the canonical Decision Log store
- couple UAG internals directly to one observability vendor

## 4. Design principles

### 4.1 UAG model first, OTel projection second

Application code should not spread direct calls such as:

```python
span.set_attribute("gen_ai.*", ...)
```

across the codebase.

Instead:

```text
UAG Runtime
   -> UAG Observability API
      -> Structured Log backend
      -> OpenTelemetry backend
      -> future backend(s)
```

The OTel adapter is the only layer that knows the detailed OTel semantic-convention mapping.

### 4.2 Preserve existing correlation identity

`correlation_id` and OpenTelemetry `trace_id` are related but not identical concepts.

Do not replace `correlation_id` with `trace_id`.

UAG structured events should eventually contain both when an active span exists:

```text
correlation_id
trace_id
span_id
```

`correlation_id` remains a UAG-level correlation key and can exist when OTel is disabled.

### 4.3 Decision Log is separate from telemetry

Telemetry answers mainly:

> What happened, where, how long did it take, and how much resource was used?

Decision Log answers mainly:

> Why did UAG choose this context/action/plan?

Decision details may contain high-cardinality or sensitive diagnostic data, so OpenTelemetry should carry only stable references and aggregates.

Recommended linkage:

```text
trace_id
span_id
decision_id
plan_id
projection_id
```

Detailed decision reasoning remains in the UAG Decision Log.

### 4.4 Disabled means near-zero behavioral impact

When OTel is disabled or unavailable:

- no network connection is attempted
- no OTel package is required
- no trace-dependent logic changes execution
- the existing `log_event()` path continues to work

### 4.5 Telemetry must never break the Agent

Exporter failures, Collector failures, queue overflow, invalid endpoint configuration, or telemetry serialization errors must not fail a user task.

Observability failures may generate a local diagnostic event, but execution remains authoritative.

## 5. Architecture

```text
                         UAG Runtime
                             |
                 +-----------+-----------+
                 |                       |
          Domain operations        Decision Log
                 |                       |
                 v                       v
          UAG Observability API      UAG storage
                 |
        +--------+---------+
        |                  |
        v                  v
 Structured Event      OTel Adapter
     backend                |
        |                   +--------------------+
        |                   |                    |
        v                   v                    v
 local/debug logs        Traces              Metrics
                            |                    |
                            +---------+----------+
                                      |
                                     OTLP
                                      |
                                      v
                           OpenTelemetry Collector
                                      |
                      +---------------+---------------+
                      |               |               |
                    Jaeger          Grafana      Vendor backend
```

The Collector is recommended but not required by the internal design. UAG should speak standard OTLP through the OTel SDK/exporter and avoid vendor-specific SDKs in core runtime code.

## 6. Proposed module boundary

A future implementation should introduce a small runtime-neutral observability package, for example:

```text
src/uagent/runtime/observability/
    __init__.py
    api.py
    noop.py
    logging_backend.py
    otel_backend.py
    semantic_mapping.py
    privacy.py
```

Responsibilities:

### `api.py`

Provider-neutral UAG observability contract.

Conceptual operations:

```text
start_agent_span
start_llm_span
start_tool_span
start_context_span
start_retrieval_span
start_memory_span
start_sub_agent_span
record_event
record_metric
current_trace_ids
```

This is an internal interface, not a public compatibility guarantee in the first phase.

### `noop.py`

No-op implementation used when observability is disabled.

### `logging_backend.py`

Bridge to existing structured events. The current `log_event()` API remains supported.

### `otel_backend.py`

Optional OTel SDK integration, OTLP exporters, span creation, metrics, status/error recording, and context propagation.

### `semantic_mapping.py`

Single location that maps UAG domain concepts to OpenTelemetry GenAI semantic conventions and UAG custom attributes.

This file is intentionally isolated because OpenTelemetry GenAI semantic conventions are still Development status.

### `privacy.py`

Content-capture policy, redaction, cardinality policy, and safe attribute conversion.

## 7. Trace model

A typical UAG task should appear approximately as:

```text
invoke_agent uag
|
+-- uag.context.build
|   +-- search_memory
|   +-- retrieval
|   +-- uag.context.score
|   +-- uag.context.decide
|
+-- chat <model>
|   +-- retry event(s), when applicable
|
+-- execute_tool <tool>
|
+-- chat <model>
|
+-- invoke_agent <sub-agent>
|   +-- chat <model>
|   +-- execute_tool <tool>
|
+-- execute_tool <tool>
|
+-- chat <model>
```

The root span represents one logical Agent task/execution, not the whole long-lived CLI/Web process.

## 8. Mapping UAG operations to OpenTelemetry

OpenTelemetry GenAI semantic conventions currently define operations including `chat`, `generate_content`, `invoke_agent`, `invoke_workflow`, `plan`, `retrieval`, `execute_tool`, `search_memory`, `create_memory`, `update_memory`, and related memory operations.

Recommended mapping:

| UAG operation | OTel operation / span | Kind | Notes |
|---|---|---|---|
| Agent task | `invoke_agent` | INTERNAL for local execution | root logical task span |
| Remote Agent call | `invoke_agent` | CLIENT | propagation required |
| Workflow/Auto-Pilot step group | `invoke_workflow` where appropriate | INTERNAL | only when it is truly a workflow boundary |
| Planner/decomposition | `plan` | INTERNAL | avoid emitting for every trivial branch |
| LLM generation | `chat` or provider-appropriate inference operation | CLIENT | logical call includes automatic retries |
| Tool execution | `execute_tool` | INTERNAL | MCP transport may add nested client/server spans |
| Retrieval | `retrieval` | INTERNAL/CLIENT | based on local vs remote implementation |
| Memory search | `search_memory` | INTERNAL/CLIENT | do not emit memory body by default |
| Memory create/update | OTel memory operations | INTERNAL/CLIENT | operation-specific |
| Context build | `uag.context.build` | INTERNAL | UAG custom span |
| Context scoring | `uag.context.score` | INTERNAL | emit only when useful, possibly sampled |
| Context decision phase | `uag.context.decide` | INTERNAL | aggregate attributes only |
| Provider projection | `uag.provider.project` | INTERNAL | useful for projection debugging |
| A2A transport | protocol/client-server spans plus Agent span | CLIENT/SERVER | preserve W3C context |
| MCP | MCP conventions when applicable | CLIENT/SERVER | avoid duplicate tool spans |

### 8.1 Do not duplicate equivalent spans

If MCP instrumentation reliably creates the transport span, UAG should still keep the logical `execute_tool` span when it represents UAG's tool operation, but it must not create two equivalent `execute_tool` spans for the same boundary.

Logical operation and transport operation are different:

```text
execute_tool remote_search
   -> MCP client request
      -> MCP server request
```

## 9. LLM span semantics

The LLM boundary should be the provider-neutral `RoundOrchestrator`/equivalent logical round, not a provider SDK-specific request whenever possible.

Important rule:

> A logical LLM span covers automatic retries that are part of the same UAG operation.

Retries should normally be represented as span events/attributes/metrics inside the logical operation rather than unrelated top-level spans.

Provider SDK auto-instrumentation may later be supported as an optional nested diagnostic layer, but UAG must not depend on it for the canonical trace.

Recommended safe attributes include:

```text
gen_ai.operation.name
gen_ai.provider.name
gen_ai.request.model
gen_ai.response.model (when available)
error.type
uag.round.status
uag.round.event_count
uag.round.tool_call_count
uag.round.fallback_count
uag.round.duplicate_event_count
uag.round.out_of_order_event_count
uag.plan.id
uag.projection.id
```

Token usage should use standard OTel GenAI metrics/attributes when the mapping is applicable, while preserving UAG's distinction between estimated request tokens and provider-reported usage.

Do not silently present estimated values as provider-reported exact values.

Suggested distinction in UAG custom metadata:

```text
uag.tokens.estimate.*
uag.tokens.reported.*
```

The OTel adapter may map reported values to the standard GenAI token usage signal.

## 10. Tool tracing

The centralized UAG tool runner is the primary instrumentation point.

Recommended span:

```text
execute_tool <tool-name>
```

Recommended attributes:

```text
gen_ai.operation.name = execute_tool
gen_ai.tool.name
uag.tool.call_id
uag.tool.source        # builtin / plugin / skill / mcp / other
uag.tool.external_data
error.type
```

Raw tool arguments and results are not recorded by default.

Existing tool trace output and `tool.completed` / `tool.failed` structured events remain supported.

## 11. Context Runtime tracing

Context Runtime contains UAG-specific behavior not fully represented by standard GenAI conventions. It should therefore use a small UAG custom namespace rather than forcing every detail into `gen_ai.*`.

Recommended structure:

```text
uag.context.build
   +-- search_memory
   +-- retrieval
   +-- uag.context.score
   +-- uag.context.decide
   +-- uag.provider.project
```

Recommended aggregate attributes/metrics:

```text
uag.context.raw.chars
uag.context.active.chars
uag.context.saved.chars
uag.context.raw.tokens
uag.context.active.tokens
uag.context.saved.tokens
uag.context.saved.ratio
uag.context.candidate.count
uag.context.keep.count
uag.context.compact.count
uag.context.exclude.count
uag.context.retrieve_more.count
uag.context.section_count
uag.context.budget.mode
```

Do not attach every candidate, decision reason, raw memory value, or raw tool result to the span.

Detailed per-candidate information remains in the Decision Log/debug snapshot.

## 12. Decision Log correlation

Decision Log records should be able to store optional observability references:

```text
decision_id
correlation_id
trace_id
span_id
plan_id
projection_id
```

Conversely, a context decision span may carry:

```text
uag.decision.batch_id
uag.plan.id
uag.projection.id
```

but not the full decision body by default.

This provides bidirectional navigation without making one storage system depend on the other.

## 13. Sub-Agent and multi-agent tracing

Local Sub-Agents should normally be children of the invoking Agent span:

```text
invoke_agent uag
   -> invoke_agent reviewer
      -> chat ...
      -> execute_tool ...
```

Use ContextVar/context propagation so asynchronous/concurrent Sub-Agents retain the correct parent trace context.

Parallel Sub-Agents are sibling spans under the invoking operation, not a forced serial chain.

Agent identity must not be encoded only in the span name. Use stable attributes such as the UAG agent/sub-agent identifier where safe.

Avoid user-entered arbitrary strings as metric labels.

## 14. A2A and distributed propagation

A2A should propagate standard W3C Trace Context (`traceparent` / `tracestate`) when OTel is enabled and the transport allows headers/metadata.

Rules:

1. Accept valid inbound trace context at the A2A server boundary.
2. Create a server/Agent span as appropriate.
3. Propagate context on outbound A2A calls.
4. Do not make trace headers part of the business-level signed task identity unless the A2A security protocol explicitly requires it.
5. Never trust arbitrary trace metadata for authorization.
6. Preserve UAG `task_id` / `correlation_id` independently of trace IDs.

Cross-process trace propagation is observability metadata, not identity or access control.

## 15. MCP propagation

When MCP transport instrumentation is available, use standard MCP conventions for transport/client-server spans and maintain the UAG logical tool span above it.

UAG should not require an MCP server to understand UAG-specific headers.

If standard trace context can be propagated over the MCP transport, use it. Otherwise, the UAG-side trace remains valid up to the transport boundary.

## 16. Signals

### 16.1 Traces

Highest-priority signal.

Initial useful boundaries:

- Agent task
- LLM logical round
- Tool execution
- Sub-Agent invocation
- Context build
- Retrieval/Memory

### 16.2 Metrics

Metrics should be low-cardinality and operationally useful.

Candidate metrics:

```text
uag.agent.operation.duration
uag.llm.operation.duration
uag.tool.operation.duration
uag.context.build.duration
uag.context.raw.tokens
uag.context.active.tokens
uag.context.saved.tokens
uag.context.saved.ratio
uag.llm.retry.count
uag.llm.error.count
uag.tool.error.count
```

Use standard OTel GenAI metrics such as client operation duration and token usage where their definitions match UAG data.

Do not use `session_id`, `task_id`, `trace_id`, prompt text, arbitrary file names, URLs with user data, or memory IDs as metric dimensions.

### 16.3 Logs

Existing UAG structured events remain the primary UAG logging format.

When an active span exists, `log_event()` should be able to enrich the payload with:

```text
trace_id
span_id
trace_flags (optional)
```

This allows log-to-trace correlation without requiring OTel Logs in the first phase.

OTel Logs export may be added later after the trace model is stable.

## 17. Privacy and content capture

### 17.1 Default policy

Default: metadata only.

Do not record by default:

- system prompts
- user prompts
- assistant response bodies
- reasoning bodies
- tool argument values
- tool result bodies
- Memory note bodies
- artifact bodies
- file contents
- OAuth tokens
- API keys
- credentials
- raw authorization headers
- browser/session tokens

### 17.2 Content capture is explicit opt-in

If future diagnostics require content capture, it must be controlled by an explicit UAG-level opt-in policy separate from ordinary `OTEL_*` exporter configuration.

Proposed setting:

```text
UAGENT_OTEL_CAPTURE_CONTENT=0   # default
```

Possible future values can be designed later; the first implementation should prefer a simple disabled/enabled policy with strict redaction rather than many partial modes.

### 17.3 Existing secret masking remains authoritative

OTel export must reuse or share the same secret-redaction policy as structured event logging instead of implementing an unrelated secret list.

Redaction must occur before data reaches exporters.

## 18. Cardinality policy

High-cardinality data is acceptable on individual traces when justified, but dangerous on metrics.

### Trace-only candidates

- `task_id`
- `tool_call_id`
- `plan_id`
- `projection_id`
- `decision_id`/batch reference
- response IDs, when policy allows

### Metric-safe candidates

- normalized provider
- normalized model family when needed
- operation name
- stable tool name from registered specs
- terminal status/error class

Avoid arbitrary user text and arbitrary URLs as metric attributes.

## 19. Error semantics

UAG execution status remains authoritative.

The OTel adapter should:

- mark span status/error according to OTel guidance
- set `error.type` to a stable exception/error class when available
- record cancellation and timeout distinctly from successful completion
- avoid attaching secret-bearing exception payloads
- keep telemetry-export errors separate from task errors

An exporter failure must not make a successful UAG task appear failed at the UAG lifecycle layer.

## 20. Sampling

Initial recommendation:

- respect standard OTel SDK sampler configuration
- do not create a UAG-specific sampling algorithm in the first phase
- keep local structured events independent from remote trace sampling

This allows operators to configure parent-based/ratio sampling through standard OTel settings.

For expensive fine-grained spans such as per-candidate scoring, UAG may later add internal controls, but the initial design should avoid generating a span per Context candidate.

## 21. Configuration

Prefer standard OpenTelemetry environment variables wherever possible.

Examples:

```text
OTEL_SERVICE_NAME=uag
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
OTEL_TRACES_EXPORTER=otlp
OTEL_METRICS_EXPORTER=otlp
OTEL_RESOURCE_ATTRIBUTES=deployment.environment.name=dev
```

UAG-specific settings should exist only for UAG-specific policy.

Proposed settings:

```text
UAGENT_OTEL_ENABLED=0
UAGENT_OTEL_CAPTURE_CONTENT=0
```

`UAGENT_OTEL_ENABLED` is an explicit product-level switch so installing OTel dependencies alone does not silently enable network export.

The OTel SDK may still honor standard `OTEL_*` variables after UAG enables the backend.

Do not duplicate standard OTel endpoint/protocol/header/sampler variables with UAG-specific alternatives unless a concrete compatibility requirement appears.

## 22. Packaging

OpenTelemetry remains optional.

Future `pyproject.toml` shape:

```toml
[project.optional-dependencies]
otel = [
    "opentelemetry-api",
    "opentelemetry-sdk",
    "opentelemetry-exporter-otlp",
]
```

Expected installation:

```text
pip install uag
```

continues to work without OTel.

Users who want OTel can install:

```text
pip install "uag[otel]"
```

Exact version constraints should be chosen at implementation time after compatibility testing with the then-current OTel Python packages.

## 23. OpenTelemetry GenAI semantic-convention compatibility

As of this design, OpenTelemetry GenAI semantic conventions are still marked Development.

Therefore:

1. UAG domain objects must not expose OTel attribute names as their internal API.
2. `semantic_mapping.py` is the compatibility boundary.
3. UAG custom attributes use the `uag.*` namespace.
4. Standard `gen_ai.*` attributes are emitted only by the adapter when the mapping is sufficiently clear.
5. Semantic-convention version changes should require adapter/test changes, not widespread runtime refactoring.
6. UAG documentation should state which semantic-convention generation/version was validated by each release once implementation begins.

Reference:

- https://github.com/open-telemetry/semantic-conventions-genai
- https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-spans.md
- https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md

## 24. Provider-neutral instrumentation vs SDK auto-instrumentation

Canonical UAG traces should be created at UAG provider-neutral boundaries.

Why:

```text
OpenAI SDK auto instrumentation     -> provider-specific
Anthropic instrumentation           -> provider-specific
Gemini instrumentation              -> provider-specific
LM Studio/local provider             -> may differ or be absent
```

UAG already has a shared logical round contract, so tracing there provides consistent semantics.

Provider SDK auto-instrumentation may be enabled as an optional nested diagnostic feature in the future. It must not be required for standard UAG traces and duplicate spans must be avoided.

## 25. Integration with existing `log_event()`

Migration should be incremental.

Initial direction:

```text
existing caller
    -> log_event(...)
        -> structured log (unchanged)
        -> optional active trace correlation
```

New logical operation boundaries can use the Observability API to create spans while continuing to emit current event codes.

Long term, event emission may route through the shared observability layer internally, but public/runtime behavior of existing event codes should remain compatible.

Do not perform a large rewrite of all event call sites solely for OTel adoption.

## 26. Proposed rollout phases

### Phase 0: design and contracts

- finalize this document
- define internal Observability API
- define privacy/cardinality policy
- define semantic mapping table
- no runtime behavior change

### Phase 1: optional core tracing

- optional `otel` dependency group
- no-op backend
- OTel backend/bootstrap
- Agent root span
- LLM round span
- Tool execution span
- trace/log correlation
- content capture OFF

### Phase 2: Context Runtime and metrics

- context build span
- retrieval/memory spans
- context aggregate metrics
- standard GenAI client duration/token metrics where applicable
- Decision Log references

### Phase 3: distributed tracing

- Sub-Agent context propagation hardening
- A2A W3C Trace Context propagation
- MCP integration/duplicate-span policy

### Phase 4: optional advanced diagnostics

- controlled content capture
- provider SDK nested auto-instrumentation if useful
- OTel Logs export if justified
- dashboards/examples

## 27. Suggested PR decomposition

When implementation begins, keep changes reviewable.

### PR 1: Observability abstraction

- internal API
- no-op backend
- tests
- no OTel dependency required yet

### PR 2: OTel trace backend

- optional dependencies
- bootstrap/configuration
- Agent/LLM/Tool spans
- log correlation

### PR 3: Context/Memory/Retrieval + metrics

- Context Runtime instrumentation
- Memory/Retrieval mapping
- Decision Log linking
- low-cardinality metrics

### PR 4: distributed propagation

- Sub-Agent concurrency validation
- A2A trace context
- MCP propagation/integration

No implementation PR should combine OTel adoption with unrelated runtime refactoring.

## 28. Testing strategy

### 28.1 Unit tests

Verify:

- no-op behavior when disabled
- missing OTel packages do not break startup
- IDs are added only when a span is active
- secret/content redaction
- semantic mapping
- error/cancel/timeout status mapping
- estimated vs reported token distinction
- high-cardinality fields are not metric dimensions

### 28.2 In-memory OTel tests

Use OTel in-memory exporters/readers in tests where possible.

Verify span hierarchy:

```text
Agent
  -> LLM
  -> Tool
  -> LLM
```

and parallel Sub-Agent parentage.

### 28.3 Integration tests

Optional CI/integration profile:

```text
UAG -> OTLP -> Collector
```

Validate export without requiring a production backend.

### 28.4 Failure isolation tests

Simulate:

- unreachable Collector
- exporter exception
- queue overflow
- malformed endpoint
- shutdown during pending export

UAG task behavior must remain correct.

## 29. Acceptance criteria for the first implementation

The initial OTel implementation is acceptable when all of the following are true:

1. UAG runs unchanged with OTel disabled and without OTel packages installed.
2. Enabling OTel produces one coherent Agent trace containing LLM and Tool spans.
3. OpenAI/Anthropic/Gemini/xAI/local-provider paths share the same UAG logical span model.
4. Existing structured events still work.
5. Structured events can include trace/span IDs when tracing is active.
6. Prompt/response/tool-result content is not exported by default.
7. Exporter failure cannot fail the Agent task.
8. Token metrics do not confuse estimates with provider-reported usage.
9. Metrics avoid high-cardinality identifiers.
10. Decision Log remains independent and can reference a trace/span.
11. Sub-Agent traces preserve correct parentage.
12. Semantic-convention-specific names are isolated in the mapping adapter.

## 30. Decisions made by this design

The following are design decisions, not open questions:

- OpenTelemetry is optional.
- OTel is not the canonical UAG internal telemetry contract.
- Existing `log_event()` is preserved.
- `correlation_id` is preserved independently from `trace_id`.
- Decision Log remains separate from OTel trace storage.
- Canonical LLM tracing occurs at UAG's provider-neutral logical round boundary.
- Raw content capture is OFF by default.
- Standard `OTEL_*` configuration is preferred over duplicating settings.
- OTLP is the standard export path.
- Collector-based deployment is recommended but not required.
- GenAI semantic-convention usage is isolated behind an adapter because the specification is still Development.
- A2A propagation uses standard trace context for observability only, never authorization.

## 31. Remaining design questions before implementation

These items can be resolved immediately before implementation without changing the architecture:

1. Exact internal Python Protocol/context-manager API shape.
2. Exact OTel Python package version constraints.
3. Exact validated OpenTelemetry GenAI semantic-convention revision for the target UAG release.
4. Whether metrics ship in the same implementation release as traces or one release later.
5. Whether `UAGENT_OTEL_ENABLED` also permits console/in-memory exporters for developer diagnostics, or only activates configured SDK exporters.
6. Whether a small `uag telemetry doctor` command is useful later for endpoint/configuration validation.

None of these questions require changing the main architectural decisions above.

## 32. Summary

UAG is already structurally ready for OpenTelemetry because the important logical boundaries are centralized.

The recommended design is:

```text
UAG domain runtime
        |
        v
UAG Observability API
        |
   +----+----------------+
   |                     |
structured events    OpenTelemetry adapter
                         |
                    OTLP / Collector
```

Keep UAG's event model, lifecycle, Context telemetry, and Decision Log authoritative. Use OpenTelemetry to project operational traces and metrics into standard tooling. This provides portable observability without coupling UAG's runtime design to a still-evolving GenAI telemetry specification.
