# UAG OpenTelemetry Integration Design

Status: Design only  
Target: post-v0.7.16  
Scope: observability architecture, OpenTelemetry integration boundary, automatic dependency installation, signal model, privacy, propagation, rollout  
Non-goal: this document does not implement OpenTelemetry.

## 1. Purpose

UAG already has provider-neutral runtime boundaries, structured event logging, lifecycle events, tool dispatch events, LLM round summaries, Context Runtime telemetry, Decision Log data, Sub-Agent execution, A2A, MCP, and Web/CLI/GUI entry points.

The purpose of this design is to add OpenTelemetry (OTel) without making OpenTelemetry the internal contract of UAG.

The central rule is:

> UAG owns the observability model. OpenTelemetry is one projection/export backend of that model.

A second product rule is:

> When the user enables OpenTelemetry, UAG installs the required OpenTelemetry packages automatically through the existing UAG auto-install mechanism unless the user's auto-install policy forbids it.

Users should not normally need to run a separate `pip install` command merely to turn tracing on.

## 2. Current UAG baseline

The current runtime already contains most information required for useful tracing.

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
  - retry/recovery summary fields
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
- `_pip_auto.py`
  - allowlisted first-use package installation
  - `UAGENT_AUTO_INSTALL=allow|prompt|off`
  - localized installation status
  - version checking and repair/reinstall support through `install_with_status()`

OpenTelemetry should therefore be added as an adapter around existing UAG boundaries and should reuse the existing auto-install policy instead of introducing a second dependency installer.

## 3. Goals

### 3.1 Primary goals

1. Trace one UAG task across Agent, LLM, Tool, Context Runtime, Memory, Sub-Agent, A2A, MCP, and external calls.
2. Preserve a provider-neutral trace model across OpenAI, Azure OpenAI, Anthropic, Gemini, xAI, OpenRouter, LM Studio, llama.cpp, and future providers.
3. Export traces and metrics through OTLP to an OpenTelemetry Collector or compatible backend.
4. Correlate existing UAG structured logs with OpenTelemetry `trace_id` / `span_id`.
5. Keep Decision Log as a UAG-owned diagnostic/audit artifact rather than flattening it into span attributes.
6. Keep telemetry opt-in and failure-isolated.
7. Avoid capturing prompt, response, tool argument, tool result, memory body, and artifact body content by default.
8. Follow OpenTelemetry GenAI semantic conventions where useful, while isolating semantic-convention mapping behind an adapter because the GenAI conventions are still evolving.
9. Automatically install required OTel Python packages when OTel is enabled and packages are missing, subject to the existing UAG auto-install policy.
10. Preserve normal UAG behavior if automatic installation is disabled or fails.

### 3.2 Non-goals

The first implementation must not:

- replace `log_event()`
- require an OpenTelemetry Collector for normal UAG operation
- force OTel packages into the minimal/base installation
- require ordinary users to manually install OTel packages before enabling the feature
- bypass `UAGENT_AUTO_INSTALL`
- alter LLM/provider behavior
- alter retry policy
- alter tool execution behavior
- alter Context Runtime decisions
- send raw conversation content by default
- use OpenTelemetry as persistent Agent state
- use spans as the canonical Decision Log store
- couple UAG internals directly to one observability vendor
- fail an Agent task merely because OTel packages cannot be installed or telemetry cannot be exported

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

Only the OTel adapter knows detailed OTel semantic-convention mapping.

### 4.2 Preserve existing correlation identity

`correlation_id` and OpenTelemetry `trace_id` are related but are not the same concept.

Do not replace `correlation_id` with `trace_id`.

Structured events may contain both when an active span exists:

```text
correlation_id
trace_id
span_id
```

`correlation_id` remains available when OTel is disabled.

### 4.3 Decision Log remains separate

Telemetry mainly answers:

> What happened, where, how long did it take, and how much resource was used?

Decision Log mainly answers:

> Why did UAG choose this context/action/plan?

Recommended linkage:

```text
trace_id
span_id
decision_id
plan_id
projection_id
```

Detailed decision reasoning remains in UAG storage.

### 4.4 Disabled means near-zero impact

When OTel is disabled:

- no OTel package installation is attempted
- no network export is attempted
- no OTel package is required
- no trace-dependent logic changes execution
- existing `log_event()` behavior continues

### 4.5 Enabling OTel triggers dependency readiness

When OTel is enabled, UAG performs a lazy readiness check before creating the OTel backend.

Conceptually:

```text
UAGENT_OTEL_ENABLED=1
        |
        v
ensure_otel_dependencies()
        |
        +-- already installed -> continue
        |
        +-- missing -> existing UAG auto-install policy
                         |
                         +-- allow  -> install automatically
                         +-- prompt -> ask only when interactive
                         +-- off    -> do not install
        |
        v
initialize OTel backend or safely fall back to no-op
```

This check should run once per process, not once per span or LLM call.

### 4.6 Telemetry must never break the Agent

Exporter failure, Collector failure, installation failure, queue overflow, invalid endpoint configuration, or serialization failure must not fail a user task.

Observability failures may generate a local diagnostic event, but Agent execution remains authoritative.

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
                            +--------------------+
                            |                    |
                            v                    v
                         Traces              Metrics
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

The Collector is recommended but not required by the internal design. UAG should use standard OTLP through the OTel SDK/exporter and avoid vendor-specific SDKs in core runtime code.

## 6. Proposed module boundary

A future implementation should introduce a small observability package, for example:

```text
src/uagent/runtime/observability/
    __init__.py
    api.py
    bootstrap.py
    dependencies.py
    noop.py
    logging_backend.py
    otel_backend.py
    semantic_mapping.py
    privacy.py
```

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

### `bootstrap.py`

Selects no-op vs OTel backend and initializes it once.

### `dependencies.py`

Owns OTel package readiness and delegates installation to the existing `_pip_auto.install_with_status()` mechanism.

It must not invoke pip directly.

### `noop.py`

No-op implementation used when disabled or unavailable.

### `logging_backend.py`

Bridge to existing structured events. The current `log_event()` API remains supported.

### `otel_backend.py`

OTel SDK integration, OTLP exporters, span creation, metrics, status/error recording, and context propagation.

### `semantic_mapping.py`

Single location that maps UAG domain concepts to OpenTelemetry GenAI semantic conventions and UAG custom attributes.

### `privacy.py`

Content-capture policy, redaction, cardinality policy, and safe attribute conversion.

## 7. Automatic dependency installation

### 7.1 Reuse UAG's existing installer

OTel installation must use the existing UAG mechanism:

```python
from uagent._pip_auto import install_with_status
```

No new subprocess/pip wrapper should be introduced in the observability package.

The OTel packages must be added to `_pip_auto.py`'s allowlist.

Initial package set:

```text
opentelemetry-api
opentelemetry-sdk
opentelemetry-exporter-otlp
```

Exact version constraints are selected at implementation time and should be validated as a compatible set.

### 7.2 Trigger

Automatic installation occurs only when all of the following are true:

1. `UAGENT_OTEL_ENABLED` is true.
2. The OTel backend is being initialized.
3. One or more required packages are missing or outside the supported version range.
4. Existing `UAGENT_AUTO_INSTALL` policy permits installation.

Merely importing UAG must not install OpenTelemetry.

Merely setting unrelated `OTEL_*` variables must not install OpenTelemetry unless UAG's product-level OTel switch is enabled.

### 7.3 Existing auto-install policy remains authoritative

Behavior:

| `UAGENT_AUTO_INSTALL` | OTel dependency behavior |
|---|---|
| `allow` (default) | install missing required packages automatically |
| `prompt` | ask before installation when interactive; non-interactive execution does not install |
| `off` | never install automatically |

UAG must not create an OTel-specific override that silently bypasses this policy.

### 7.4 Failure behavior

If dependencies remain unavailable after readiness checking:

```text
OTel requested
   -> dependency unavailable
   -> local diagnostic event/warning
   -> OTel backend disabled for this process
   -> no-op backend
   -> Agent task continues
```

Suggested event codes:

```text
observability.otel.dependencies_missing
observability.otel.install_failed
observability.otel.disabled
```

Do not repeatedly retry installation on every Agent round. Cache the failed readiness result for the process unless an explicit future reload/doctor operation is invoked.

### 7.5 Preinstallation remains supported

Automatic installation is the normal UX, but reproducible/offline/enterprise environments may preinstall dependencies.

An optional package extra may still be provided:

```toml
[project.optional-dependencies]
otel = [
    "opentelemetry-api...",
    "opentelemetry-sdk...",
    "opentelemetry-exporter-otlp...",
]
```

This is for packaging/deployment convenience, not a prerequisite for normal interactive use.

## 8. Trace model

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
|   +-- retry event(s)
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

The root span represents one logical Agent task/execution, not a long-lived CLI/Web process.

## 9. Mapping UAG operations to OpenTelemetry

Recommended mapping:

| UAG operation | OTel operation / span | Kind | Notes |
|---|---|---|---|
| Agent task | `invoke_agent` | INTERNAL | root logical task span |
| Remote Agent call | `invoke_agent` | CLIENT | propagation required |
| Workflow/Auto-Pilot group | `invoke_workflow` where appropriate | INTERNAL | true workflow boundaries only |
| Planner/decomposition | `plan` | INTERNAL | avoid trivial spans |
| LLM generation | `chat` or matching inference operation | CLIENT | logical call includes automatic retries |
| Tool execution | `execute_tool` | INTERNAL | logical tool operation |
| Retrieval | `retrieval` | INTERNAL/CLIENT | local vs remote dependent |
| Memory search | `search_memory` | INTERNAL/CLIENT | content excluded by default |
| Memory create/update | OTel memory operation | INTERNAL/CLIENT | operation-specific |
| Context build | `uag.context.build` | INTERNAL | UAG custom span |
| Context scoring | `uag.context.score` | INTERNAL | aggregated, not per candidate by default |
| Context decision | `uag.context.decide` | INTERNAL | aggregates only |
| Provider projection | `uag.provider.project` | INTERNAL | provider-neutral projection debugging |
| A2A transport | Agent plus protocol spans | CLIENT/SERVER | W3C propagation |
| MCP | MCP conventions where applicable | CLIENT/SERVER | avoid duplicate equivalent spans |

Logical operations and transport operations may nest:

```text
execute_tool remote_search
   -> MCP client request
      -> MCP server request
```

## 10. LLM span semantics

Canonical tracing occurs at UAG's provider-neutral logical round boundary, not independently inside every provider SDK.

A logical LLM span covers automatic retries that belong to the same UAG operation.

Recommended safe metadata:

```text
gen_ai.operation.name
gen_ai.provider.name
gen_ai.request.model
gen_ai.response.model
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

Preserve the distinction between estimated and provider-reported token counts:

```text
uag.tokens.estimate.*
uag.tokens.reported.*
```

Estimated values must never be presented as exact provider usage.

## 11. Tool tracing

The centralized UAG tool runner is the primary instrumentation point.

Recommended span:

```text
execute_tool <tool-name>
```

Recommended metadata:

```text
gen_ai.operation.name = execute_tool
gen_ai.tool.name
uag.tool.call_id
uag.tool.source
uag.tool.external_data
error.type
```

Raw tool arguments and results are not recorded by default.

Existing tool trace output and `tool.completed` / `tool.failed` structured events remain supported.

## 12. Context Runtime tracing

Recommended structure:

```text
uag.context.build
   +-- search_memory
   +-- retrieval
   +-- uag.context.score
   +-- uag.context.decide
   +-- uag.provider.project
```

Recommended aggregate metadata:

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

Do not attach every candidate, decision reason, raw memory value, or raw tool result to spans.

## 13. Decision Log correlation

Decision Log records may store:

```text
decision_id
correlation_id
trace_id
span_id
plan_id
projection_id
```

A context decision span may carry stable references such as:

```text
uag.decision.batch_id
uag.plan.id
uag.projection.id
```

The full decision body remains outside OTel by default.

## 14. Sub-Agent and multi-agent tracing

Local Sub-Agents are children of the invoking Agent span:

```text
invoke_agent uag
   -> invoke_agent reviewer
      -> chat ...
      -> execute_tool ...
```

Use context propagation so asynchronous/concurrent Sub-Agents retain correct parents.

Parallel Sub-Agents are sibling spans under the invoking operation.

Avoid user-entered arbitrary strings as metric labels.

## 15. A2A and distributed propagation

A2A should propagate W3C Trace Context (`traceparent` / `tracestate`) when OTel is enabled and transport allows it.

Rules:

1. Accept valid inbound trace context at the server boundary.
2. Create appropriate server/Agent spans.
3. Propagate context on outbound A2A calls.
4. Do not make trace headers part of business-level signed task identity unless required by the protocol.
5. Never use trace metadata for authorization.
6. Preserve `task_id` / `correlation_id` independently.

## 16. MCP propagation

Use standard MCP conventions for transport/client-server spans when available and retain the UAG logical tool span above them.

UAG should not require MCP servers to understand UAG-specific headers.

## 17. Signals

### 17.1 Traces

Highest-priority signal.

Initial boundaries:

- Agent task
- LLM logical round
- Tool execution
- Sub-Agent invocation
- Context build
- Retrieval/Memory

### 17.2 Metrics

Candidate low-cardinality metrics:

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

Use standard OTel GenAI metrics where definitions match UAG data.

Do not use `session_id`, `task_id`, `trace_id`, prompt text, arbitrary filenames, arbitrary URLs, or memory IDs as metric dimensions.

### 17.3 Logs

Existing UAG structured events remain the primary logging format.

When an active span exists, `log_event()` may enrich payloads with:

```text
trace_id
span_id
trace_flags
```

OTel Logs export is not required in the first phase.

## 18. Privacy and content capture

Default policy: metadata only.

Do not record by default:

- system prompts
- user prompts
- assistant response bodies
- reasoning bodies
- tool argument values
- tool result bodies
- Memory note bodies
- artifact/file bodies
- OAuth tokens
- API keys
- credentials
- raw authorization headers
- browser/session tokens

Content capture requires an explicit UAG-level opt-in:

```text
UAGENT_OTEL_CAPTURE_CONTENT=0
```

Existing secret masking/redaction remains authoritative and must run before exporters see data.

## 19. Cardinality policy

Trace-only/high-cardinality candidates may include:

```text
task_id
tool_call_id
plan_id
projection_id
decision_id
```

Metric-safe candidates include:

```text
normalized provider
normalized model family
operation name
stable registered tool name
terminal status/error class
```

Avoid arbitrary user text and arbitrary URLs as metric attributes.

## 20. Error semantics

UAG execution status remains authoritative.

The OTel adapter should:

- mark span status/error according to OTel guidance
- set `error.type` to a stable class when available
- represent cancellation and timeout distinctly
- avoid secret-bearing exception payloads
- keep dependency-install/export errors separate from task errors

An observability failure must not make a successful UAG task appear failed.

## 21. Sampling

Initial recommendation:

- respect standard OTel SDK sampler configuration
- do not create a UAG-specific sampling algorithm initially
- keep local structured events independent of remote sampling
- avoid per-candidate Context spans by default

## 22. Configuration

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

UAG-specific policy:

```text
UAGENT_OTEL_ENABLED=0
UAGENT_OTEL_CAPTURE_CONTENT=0
UAGENT_AUTO_INSTALL=allow
```

Important behavior:

```text
UAGENT_OTEL_ENABLED=0
    -> no OTel install, no export

UAGENT_OTEL_ENABLED=1
UAGENT_AUTO_INSTALL=allow
    -> install missing OTel dependencies automatically
    -> initialize backend

UAGENT_OTEL_ENABLED=1
UAGENT_AUTO_INSTALL=off
    -> do not install
    -> warn/diagnose locally
    -> use no-op backend
    -> continue Agent execution
```

The OTel SDK honors standard `OTEL_*` settings after UAG enables the backend.

Do not duplicate standard endpoint/protocol/header/sampler settings with UAG-specific alternatives unless required for compatibility.

## 23. Packaging

OpenTelemetry remains absent from the minimal installation, but dependency installation is automatic on first enabled use.

Normal UX:

```text
pip install uag
set UAGENT_OTEL_ENABLED=1
uag ...

# first OTel-enabled use:
# UAG verifies/imports OTel packages
# -> missing packages are automatically installed when policy=allow
# -> tracing starts
```

Users do not normally need:

```text
pip install "uag[otel]"
```

An optional extra may still exist for prebuilt images, offline deployment, locked environments, CI, or users who intentionally set `UAGENT_AUTO_INSTALL=off`:

```toml
[project.optional-dependencies]
otel = [
    "opentelemetry-api<validated-range>",
    "opentelemetry-sdk<validated-range>",
    "opentelemetry-exporter-otlp<validated-range>",
]
```

The same validated constraints should be used by both the optional extra and `_pip_auto.install_with_status()` calls so manual/preinstalled and automatic paths do not drift.

## 24. GenAI semantic-convention compatibility

OpenTelemetry GenAI semantic conventions are still evolving.

Therefore:

1. UAG domain objects must not expose OTel attribute names as their internal API.
2. `semantic_mapping.py` is the compatibility boundary.
3. UAG custom attributes use the `uag.*` namespace.
4. Standard `gen_ai.*` attributes are emitted by the adapter only when mapping is clear.
5. Convention changes require adapter/test changes, not widespread runtime refactoring.
6. Releases should document the validated convention generation/revision after implementation begins.

## 25. Provider-neutral instrumentation vs SDK auto-instrumentation

Canonical UAG traces are created at UAG provider-neutral boundaries.

Provider SDK auto-instrumentation may later be an optional nested diagnostic layer, but it must not be required for canonical traces and duplicate spans must be avoided.

## 26. Integration with existing `log_event()`

Migration is incremental:

```text
existing caller
    -> log_event(...)
        -> structured log (unchanged)
        -> optional active trace correlation
```

New logical operation boundaries use the Observability API while current event codes remain compatible.

Do not rewrite all event call sites solely for OTel adoption.

## 27. Rollout phases

### Phase 0: design and contracts

- finalize this document
- define Observability API
- define privacy/cardinality policy
- define semantic mapping table
- define automatic dependency readiness contract
- no runtime behavior change

### Phase 1: dependency/bootstrap + core tracing

- add OTel packages to `_pip_auto.py` allowlist
- implement `dependencies.py` using `install_with_status()`
- one-time lazy installation/readiness check when OTel is enabled
- preserve `UAGENT_AUTO_INSTALL` behavior
- optional `otel` package extra for preinstallation
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
- standard GenAI duration/token metrics where applicable
- Decision Log references

### Phase 3: distributed tracing

- Sub-Agent context propagation hardening
- A2A W3C Trace Context propagation
- MCP integration/duplicate-span policy

### Phase 4: advanced diagnostics

- controlled content capture
- provider SDK nested auto-instrumentation if useful
- OTel Logs export if justified
- dashboards/examples
- optional `uag telemetry doctor`

## 28. Suggested implementation PR decomposition

### PR 1: Observability abstraction

- internal API
- no-op backend
- tests
- no runtime OTel use yet

### PR 2: automatic dependencies + OTel trace backend

- `_pip_auto.py` allowlist entries
- dependency readiness helper
- automatic first-use installation
- optional package extra
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

## 29. Testing strategy

### 29.1 Dependency readiness tests

Verify:

- OTel disabled -> no install attempt
- packages already installed -> no pip attempt
- OTel enabled + policy `allow` -> missing packages are auto-installed
- OTel enabled + policy `prompt` -> existing prompt behavior is honored
- `prompt` in non-interactive mode -> no install and safe no-op fallback
- OTel enabled + policy `off` -> no install and safe no-op fallback
- install failure -> Agent execution continues
- failed readiness is not retried for every span/round
- version mismatch uses the validated install constraint
- OTel package names are explicitly allowlisted

Mock installation calls in unit tests; do not mutate the test runner's environment unnecessarily.

### 29.2 Observability unit tests

Verify:

- no-op behavior when disabled/unavailable
- trace IDs appear only with active spans
- secret/content redaction
- semantic mapping
- error/cancel/timeout mapping
- estimated vs reported token distinction
- high-cardinality fields are not metric dimensions

### 29.3 In-memory OTel tests

Verify span hierarchy:

```text
Agent
  -> LLM
  -> Tool
  -> LLM
```

and correct parallel Sub-Agent parentage.

### 29.4 Integration tests

Optional CI profile:

```text
UAG -> OTLP -> Collector
```

Validate export without requiring a production backend.

### 29.5 Failure isolation tests

Simulate:

- pip/install failure
- OTel import failure after installation
- unreachable Collector
- exporter exception
- queue overflow
- malformed endpoint
- shutdown during pending export

UAG task behavior must remain correct.

## 30. Acceptance criteria for the first implementation

The initial implementation is acceptable when all are true:

1. UAG runs unchanged with OTel disabled and without OTel packages installed.
2. Enabling OTel with default auto-install policy installs missing required OTel packages automatically.
3. Users are not required to run `pip install "uag[otel]"` for normal OTel use.
4. `UAGENT_AUTO_INSTALL=prompt|off` is honored exactly as for other UAG optional dependencies.
5. Missing/failed OTel dependencies cause safe no-op fallback, not Agent failure.
6. Dependency readiness is evaluated once per process rather than per span.
7. Enabling OTel produces one coherent Agent trace containing LLM and Tool spans when dependencies/export are available.
8. Provider paths share the same UAG logical span model.
9. Existing structured events still work.
10. Structured events can include trace/span IDs when tracing is active.
11. Prompt/response/tool-result content is not exported by default.
12. Exporter failure cannot fail the Agent task.
13. Token metrics do not confuse estimates with provider-reported usage.
14. Metrics avoid high-cardinality identifiers.
15. Decision Log remains independent and can reference trace/span IDs.
16. Sub-Agent traces preserve correct parentage.
17. Semantic-convention-specific names are isolated in the mapping adapter.

## 31. Decisions made by this design

The following are design decisions, not open questions:

- OpenTelemetry is opt-in at the product level.
- OTel packages are not required in the minimal UAG installation.
- When OTel is enabled and dependencies are missing, UAG automatically installs them using the existing `_pip_auto.install_with_status()` mechanism.
- `UAGENT_AUTO_INSTALL` remains authoritative; OTel does not bypass `allow|prompt|off` policy.
- Auto-install is lazy and runs only when the OTel backend is actually requested.
- Installation/readiness failure degrades to the no-op backend and never fails the Agent task.
- An `otel` optional dependency extra may remain available for offline/reproducible/preinstalled deployments, but it is not the normal prerequisite.
- OTel is not the canonical UAG internal telemetry contract.
- Existing `log_event()` is preserved.
- `correlation_id` remains independent from `trace_id`.
- Decision Log remains separate from OTel trace storage.
- Canonical LLM tracing occurs at UAG's provider-neutral logical round boundary.
- Raw content capture is OFF by default.
- Standard `OTEL_*` configuration is preferred.
- OTLP is the standard export path.
- Collector-based deployment is recommended but not required.
- GenAI semantic-convention usage is isolated behind an adapter.
- A2A propagation uses trace context for observability only, never authorization.

## 32. Remaining design questions before implementation

These can be resolved immediately before implementation without changing the architecture:

1. Exact internal Python Protocol/context-manager API shape.
2. Exact mutually compatible OTel Python version constraints.
3. Exact validated GenAI semantic-convention revision for the target release.
4. Whether metrics ship in the same implementation release as traces or one release later.
5. Whether `UAGENT_OTEL_ENABLED` also permits console/in-memory exporters for developer diagnostics.
6. Whether `uag telemetry doctor` should explicitly clear/retry cached dependency readiness in a running diagnostic process.

## 33. Summary

UAG is already structurally ready for OpenTelemetry because its important logical boundaries are centralized.

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
                  dependency readiness
                         |
             existing UAG auto-installer
                         |
                    OTLP / Collector
```

Keep UAG's event model, lifecycle, Context telemetry, and Decision Log authoritative. Use OpenTelemetry as a standard projection/export layer. When users explicitly enable the feature, make dependency setup automatic through the same controlled mechanism UAG already uses for optional capabilities.
