# Observability development contract

This document records UAG's product-level OpenTelemetry configuration and runtime tracing contract. It applies to the CLI, desktop GUI, Web server, A2A server, and programmatic/library entry points.

## Activation

OpenTelemetry is opt-in. The default is OFF.

Supported process-level controls:

- `--otel`: explicitly enable observability for the current process.
- `--no-otel`: explicitly disable observability for the current process.
- `UAGENT_OTEL_ENABLED`: environment fallback when no explicit entry-point override is supplied.
- `UAGENT_OTEL_CAPTURE_CONTENT`: controls content capture policy. The default is OFF.

Activation precedence is:

```text
explicit entry-point setting
    > UAGENT_OTEL_ENABLED
    > default OFF
```

An explicit `--otel` / `--no-otel` decision must survive later environment loading and must not be overwritten by `.env` or `.env.sec`.

## Startup and dotenv ordering

The launcher must not fully resolve observability settings at import time, because the selected project working directory may contain the effective `.env` or `.env.sec`.

The required startup sequence is:

1. Collect any explicit launcher override (`--otel` / `--no-otel`) without resolving environment fallback yet.
2. Select/apply the effective working directory.
3. Load or reload `.env` and `.env.sec` for that directory.
4. Call `refresh_observability_settings()`.
5. Initialize observability with the resolved settings.
6. If enabled, ensure the supported OTel dependencies and construct the OTel backend; otherwise retain the no-op backend.

`runtime.runtime_init.reload_dotenv_custom()` performs the post-dotenv refresh and initialization, so entry points that use that startup path inherit the same contract.

A2A has two invocation forms and both are part of the supported surface:

- normal process launch through `uaga` / `sys.argv`;
- programmatic `uagent.a2a.server.main(argv=[...])`.

The explicit `argv` form accepts `--otel` / `--no-otel` directly and publishes the same entry-point override before dotenv refresh.

## Runtime architecture

The implementation lives under `uagent.runtime.observability`.

Important pieces are:

- `api.py`: UAG-owned provider-neutral span/backend Protocols;
- `settings.py`: activation and privacy policy resolution;
- `bootstrap.py`: process-level lazy initialization and safe no-op fallback;
- `dependencies.py`: `_pip_auto.install_with_status()` dependency readiness;
- `otel_backend.py`: OTel SDK/OTLP trace and metric projection backend;
- `semantic_mapping.py`: the only location that maps UAG operations to OTel/GenAI semantic names;
- `privacy.py`: remote attribute filtering;
- `runtime.py`: lifecycle/event bridge used by centralized runtime boundaries;
- `boundary_instrumentation.py`: best-effort wrappers around UAG-owned Memory and Decision Log persistence boundaries;
- `decision_log.py`: metadata-only trace/span correlation for persisted Context decision batches.

Runtime code must not depend directly on OTel SDK span or meter classes or scatter `gen_ai.*` attributes throughout the codebase.

## Canonical Phase-1 spans

UAG owns three canonical logical span families from Phase 1:

```text
invoke_agent uag
  +-- chat <model>
  +-- execute_tool <tool>
```

- Agent spans are created at `runtime.execution.lifecycle_execution()`.
- LLM spans stay at provider-neutral logical round boundaries, never inside provider SDK adapters. Registry-backed rounds use `runtime.round_orchestrator`; compatibility providers use the two centralized fallback outcome boundaries (`runtime.legacy_round_registry` and `runtime.legacy_openai_round`) through the shared observability helper.
- Tool spans use the centralized tool dispatch/lifecycle boundary. Confirmation-denied calls do not create execution spans.
- Existing structured events remain independent and receive the active `trace_id` / `span_id` when a span is active.

Estimated request tokens and provider-reported usage remain distinct on both registry and fallback LLM spans:

```text
uag.tokens.estimate.*
uag.tokens.reported.*
```

Never report estimates as provider-exact usage. Fallback providers attach reported deltas only when the provider has populated the existing authoritative legacy usage state; missing usage is omitted rather than invented.

## Phase-2 Context, Memory, and Retrieval spans

Phase 2 adds UAG-owned spans at existing centralized boundaries without changing selection, authorization, or provider behavior.

- `uag.context.build` covers provider-neutral message/candidate Context construction.
- `retrieval` with `uag.retrieval.kind=context` covers persisted Context retrieval.
- `retrieval` with `uag.retrieval.kind=memory` covers Memory retrieval used by projection.
- Decision Log persistence remains UAG-owned storage. After a batch is persisted, a metadata-only event records aggregate action counts and the active trace/span IDs when available.

These spans export aggregate counts and sizes only. They must not export prompts, memory/profile text, retrieval queries, decision reasons, item IDs, memory IDs, references, owners, principals, rooms, projects, sessions, or turns.

## Phase-2 metrics

`ObservabilityBackend` exposes provider-neutral counter and histogram operations. The no-op backend accepts those calls without work, and runtime code never imports OTel meter types.

Initial low-cardinality metrics include:

- `uag.context.raw.chars`, `uag.context.active.chars`, `uag.context.saved.chars`;
- `uag.context.raw.tokens`, `uag.context.active.tokens`, `uag.context.saved.tokens` when available;
- `uag.context.saved.ratio`;
- `uag.context.decisions` with only the bounded decision action dimension;
- `uag.retrieval.records`, `uag.retrieval.candidates`;
- `uag.memory.records`, `uag.memory.candidates`.

Metric dimensions use an explicit allowlist. Raw identity/scope IDs, trace/span IDs, item/memory IDs, references, arbitrary user strings, file paths, URLs, and query/content text are never metric dimensions.

## Phase-3 trusted propagation and local Sub-Agent spans

Authenticated A2A propagation, local Sub-Agent child spans, and the trusted MCP HTTP propagation primitive are Phase-3 runtime boundaries.

- A2A propagates only W3C `traceparent` / `tracestate` across authenticated UAG-controlled hops. Baggage is not propagated, and trace metadata never affects authentication, authorization, identity, scope, or session validity.
- Local Sub-Agent execution opens one canonical `invoke_agent <sub-agent>` child span at the existing `tools.context.set_active_sub_agent()` / `reset_active_sub_agent()` boundary.
- Sub-Agent spans always inherit the current process-local context and never force a new root. `run_sub_agent_chain` therefore produces one logical Agent span per step, while parallel tool execution inherits ContextVars through the existing `submit_with_current_context()` path.
- The Sub-Agent span exports only bounded agent metadata such as `uag.agent.name`. Task text, ContextPack bodies, run/task IDs, file scope, shared-store values, tool payloads, provider credentials, and model output are not span attributes.
- Exceptions are forwarded to the active Agent span without replacing or swallowing the original exception. Observability creation/close failures remain best-effort and must not alter Sub-Agent results.
- Active Sub-Agent tokens remain reset-compatible across hot reloads and with the older plain ContextVar-token form.
- MCP HTTP trace propagation is OFF by default and requires the explicit `trusted_trace_propagation=True` transport flag. Only UAG-created HTTP clients install the request hook; caller-supplied `http_client` instances are not mutated.
- Trusted MCP propagation removes any pre-existing `traceparent`, `tracestate`, and `baggage` request headers, then injects only the current UAG-owned W3C `traceparent` / `tracestate`. Authorization/OAuth headers are preserved and propagation failures are ignored.
- MCP stdio does not serialize W3C trace headers; it remains related to the current execution only through process-local context and the existing outer `execute_tool` span.

Regression coverage for this slice is in `tests/test_observability_phase3_subagent.py`, `tests/test_observability_phase3_a2a.py`, and `tests/test_observability_phase3_mcp.py`.

## OTLP and standard OTel configuration

After UAG product-level activation is enabled, exporter/sampler behavior uses standard OTel environment settings.

Supported trace exporter values:

- `OTEL_TRACES_EXPORTER=otlp` (default when UAG OTel is enabled)
- `OTEL_TRACES_EXPORTER=none`

Supported metric exporter values:

- `OTEL_METRICS_EXPORTER=otlp` (default when UAG OTel is enabled)
- `OTEL_METRICS_EXPORTER=none`

Trace and metric initialization are failure-isolated. In particular, `OTEL_METRICS_EXPORTER=none` leaves tracing operational, and a metrics exporter initialization/recording failure must not disable tracing or fail Agent execution.

Supported OTLP protocols:

- `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf` (default)
- `OTEL_EXPORTER_OTLP_PROTOCOL=grpc`
- signal-specific `OTEL_EXPORTER_OTLP_TRACES_PROTOCOL` and `OTEL_EXPORTER_OTLP_METRICS_PROTOCOL` override the generic protocol.

Normal OTel endpoint/header variables are passed through to the selected exporter, including `OTEL_EXPORTER_OTLP_ENDPOINT`, signal-specific endpoint variables, and the corresponding header variables.

`OTEL_SERVICE_NAME` defaults to `uagent` when absent.

Sampler handling supports the common standard values `always_on`, `always_off`, `traceidratio`, `parentbased_always_on`, `parentbased_always_off`, and `parentbased_traceidratio`, with `OTEL_TRACES_SAMPLER_ARG` used for ratio sampling.

## Dependency installation and failure isolation

OpenTelemetry stays outside the minimal install. When effective UAG OTel activation is ON, readiness uses the existing `_pip_auto.install_with_status()` mechanism. `UAGENT_AUTO_INSTALL=allow|prompt|off` remains authoritative.

Importing UAG by itself does not install OTel. Exporter/dependency/bootstrap failures fall back to the no-op backend and must never fail an Agent task. Metrics failures are isolated from the already-initialized trace provider.

## Privacy and content capture

Observability configuration is server/process controlled. Browser payloads, A2A messages, tool arguments, prompts, responses, memory content, artifacts, and file contents cannot enable tracing or content capture on their own.

`UAGENT_OTEL_CAPTURE_CONTENT` defaults to OFF. The OTel adapter applies a metadata allow/filter boundary before exporter submission. Authentication/session secrets and raw identity/scope fields remain excluded even when content capture is enabled.

Never export raw values such as:

- Authorization/Cookie values, access/refresh/ID/session tokens, client secrets;
- `principal_id`, OIDC subject/display name/groups;
- room/project/session identifiers by default;
- prompt/response/reasoning/tool-result/memory/artifact/file bodies by default;
- Memory/retrieval queries, Decision Log reasons, item IDs, memory IDs, or references.

## Web/OIDC boundary

OpenTelemetry observes authorized execution; it is not part of authentication or authorization.

For OIDC WebSocket connections:

1. Connection acceptance retains a non-exported server-side session revalidation handle.
2. Before every `make_turn()`, the authoritative OIDC session store is queried again.
3. Expired, revoked, missing, configuration-stale, or identity-changing sessions are denied before a trusted `TurnContext` is created.
4. Room/project/private-room access is rechecked with the live identity.
5. Only then may Agent execution begin.

Web Agent spans always start as fresh OTel roots. This intentionally detaches them from any browser-provided `traceparent` / `tracestate`, including if transport auto-instrumentation is introduced around the application later. Trace context is never an identity or authorization input.

## Later phases

Wiring trusted MCP propagation into server-managed `mcp_servers.json` configuration and explicit trusted reverse-proxy ingress remain Phase-3 follow-up work. Provider SDK auto-instrumentation, controlled content capture, pseudonymous identity correlation, and user-visible trace query UI/proxy remain later work.
