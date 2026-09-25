# Observability development contract

This document records the product-level OpenTelemetry configuration contract introduced by the observability foundation work. It applies to the CLI, desktop GUI, Web server, A2A server, and programmatic/library entry points.

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
5. Resolve the final process settings using `explicit > environment > default OFF`.

`runtime.runtime_init.reload_dotenv_custom()` performs the post-dotenv observability refresh, so entry points that use that startup path inherit the same resolution contract.

A2A has two invocation forms and both are part of the supported surface:

- normal process launch through `uaga` / `sys.argv`;
- programmatic `uagent.a2a.server.main(argv=[...])`.

The explicit `argv` form must accept `--otel` / `--no-otel` directly and publish the same entry-point override before dotenv refresh.

## Shared runtime API

The implementation lives under `uagent.runtime.observability`.

Important pieces are:

- `ObservabilitySettings`: immutable resolved policy snapshot;
- `resolve_observability_settings()`: pure resolver for explicit values plus environment fallback;
- `set_observability_entrypoint_override()`: stores a launcher-level enable/disable decision until dotenv loading completes;
- `refresh_observability_settings()`: resolves and publishes the current process settings;
- `get_observability_settings()`: returns the latest process snapshot;
- the no-op backend and bootstrap/dependency helpers used by later instrumentation work.

Entry points should use the shared resolver rather than implementing their own precedence rules.

## Dependency installation

When a later runtime path actually needs the OpenTelemetry SDK/exporter, dependency readiness must use the existing `_pip_auto.install_with_status()` mechanism. `UAGENT_AUTO_INSTALL=allow|prompt|off` remains authoritative. Importing UAG by itself must not install OpenTelemetry packages.

The foundation pins the initial compatible auto-install set to the same OpenTelemetry Python release family used by the implementation. Recheck exact package versions before changing the adapter or semantic-convention mapping.

## Privacy and content capture

Observability configuration is server/process controlled. Browser payloads, A2A messages, tool arguments, prompts, responses, memory content, artifacts, and file contents must not enable tracing or content capture on their own.

`UAGENT_OTEL_CAPTURE_CONTENT` defaults to OFF. Later tracing code must use an allowlist-oriented attribute policy and keep raw prompt/response/tool/memory content out of exported telemetry unless an operator has explicitly enabled content capture.

## Current foundation scope

The foundation PR establishes configuration, bootstrap, dependency readiness, and the no-op API surface. It does not yet create real OpenTelemetry spans or exporters in normal runtime execution. Agent/LLM/Tool/Web/A2A instrumentation belongs to the subsequent adapter/instrumentation work.