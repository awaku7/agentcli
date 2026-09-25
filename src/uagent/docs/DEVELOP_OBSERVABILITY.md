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
- `otel_backend.py`: OTel SDK/OTLP projection backend;
- `semantic_mapping.py`: the only location that maps UAG operations to OTel/GenAI semantic names;
- `privacy.py`: remote attribute filtering;
- `runtime.py`: lifecycle/event bridge used by centralized runtime boundaries.

Runtime code must not depend directly on OTel SDK span classes or scatter `gen_ai.*` attributes throughout the codebase.

## Canonical Phase-1 spans

UAG owns three canonical logical span families in this phase:

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

## OTLP and standard OTel configuration

After UAG product-level activation is enabled, exporter/sampler behavior uses standard OTel environment settings.

Supported trace exporter values in this phase:

- `OTEL_TRACES_EXPORTER=otlp` (default when UAG OTel is enabled)
- `OTEL_TRACES_EXPORTER=none`

Supported OTLP protocols:

- `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf` (default)
- `OTEL_EXPORTER_OTLP_PROTOCOL=grpc`
- signal-specific `OTEL_EXPORTER_OTLP_TRACES_PROTOCOL` overrides the generic protocol.

Normal OTel endpoint/header variables are passed through to the selected exporter, including `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`, and the corresponding header variables.

`OTEL_SERVICE_NAME` defaults to `uagent` when absent.

Phase-1 sampler handling supports the common standard values `always_on`, `always_off`, `traceidratio`, `parentbased_always_on`, `parentbased_always_off`, and `parentbased_traceidratio`, with `OTEL_TRACES_SAMPLER_ARG` used for ratio sampling.

## Dependency installation and failure isolation

OpenTelemetry stays outside the minimal install. When effective UAG OTel activation is ON, readiness uses the existing `_pip_auto.install_with_status()` mechanism. `UAGENT_AUTO_INSTALL=allow|prompt|off` remains authoritative.

Importing UAG by itself does not install OTel. Exporter/dependency/bootstrap failures fall back to the no-op backend and must never fail an Agent task.

## Privacy and content capture

Observability configuration is server/process controlled. Browser payloads, A2A messages, tool arguments, prompts, responses, memory content, artifacts, and file contents cannot enable tracing or content capture on their own.

`UAGENT_OTEL_CAPTURE_CONTENT` defaults to OFF. The OTel adapter applies a metadata allow/filter boundary before exporter submission. Authentication/session secrets and raw identity/scope fields remain excluded even when content capture is enabled.

Never export raw values such as:

- Authorization/Cookie values, access/refresh/ID/session tokens, client secrets;
- `principal_id`, OIDC subject/display name/groups;
- room/project/session identifiers by default;
- prompt/response/reasoning/tool-result/memory/artifact/file bodies by default.

## Web/OIDC Phase-1 boundary

OpenTelemetry observes authorized execution; it is not part of authentication or authorization.

For OIDC WebSocket connections:

1. Connection acceptance retains a non-exported server-side session revalidation handle.
2. Before every `make_turn()`, the authoritative OIDC session store is queried again.
3. Expired, revoked, missing, configuration-stale, or identity-changing sessions are denied before a trusted `TurnContext` is created.
4. Room/project/private-room access is rechecked with the live identity.
5. Only then may Agent execution begin.

Web Agent spans always start as fresh OTel roots. This intentionally detaches them from any browser-provided `traceparent` / `tracestate`, including if transport auto-instrumentation is introduced around the application later. Trace context is never an identity or authorization input.

## Later phases

Context/Memory/Retrieval spans, metrics, Decision Log linkage, and trusted Sub-Agent/A2A/MCP distributed propagation remain separate follow-up phases. Provider SDK auto-instrumentation, if added later, is diagnostic nesting only and never replaces UAG's canonical logical spans.
