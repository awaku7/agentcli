# Architecture and operational invariants

This document records the durable implementation contracts for uagent. Temporary improvement plans and execution logs should not be used as the source of truth.

## Runtime boundaries

- A2A tasks use atomic state transitions: `IN_PROGRESS -> SUCCEEDED|FAILED` or `IN_PROGRESS -> CANCEL_REQUESTED -> CANCELLED`.
- Runtime task handles, cancel events, and locale are internal and are not exposed in API task records.
- Async locale propagation uses `contextvars`; thread-local language APIs remain compatibility APIs.
- `core.py` remains an API compatibility facade for runtime modules. New state, console, history, logging, prompt, and cancellation logic belongs under `src/uagent/runtime/`.

## I18N and TDD requirements

I18N is part of the Agent execution context, not only a presentation concern.

- Propagate locale through asynchronous execution with `contextvars`.
- Resolve locale at CLI, Web, GUI, and A2A entry points.
- Keep user-facing messages translatable; do not hard-code them in runtime paths.
- Keep logs, event codes, API status values, tool names, provider names, and field names stable and machine-readable.
- Test missing translations, placeholder mismatches, non-interactive execution, errors, and cancellation in each affected locale path.
- Keep localized README and design documentation synchronized when durable behavior changes.

New behavior is developed with TDD:

```text
Red → add a failing test
Green → implement the minimum behavior
Refactor → improve boundaries, types, duplication, and readability
```

A change is complete only when its tests cover success, failure, boundary values, cancellation, authorization, and locale behavior as applicable, followed by the full acceptance suite.

## Optional dependency installation

`UAGENT_AUTO_INSTALL` controls runtime installation:

- `allow` (default): install only registered optional packages.
- `prompt`: ask only from an interactive TTY.
- `off`: never invoke pip.

Non-interactive A2A, Web, and CI execution must not prompt. Unknown packages are rejected without invoking pip. See [README_AUTO.md](README_AUTO.md) for user-facing details.

## Tool safety

Tools are classified with `ToolPolicy` and `SideEffect`:

- `READ_ONLY`
- `IDEMPOTENT_WRITE`
- `EXTERNAL_SEND`
- `DESTRUCTIVE`

Only read-only tools are parallelized by default. External-send and destructive operations require the configured confirmation callback. Unknown tools are conservative: serial and confirmation-oriented.

## Provider capabilities

Provider capability checks go through `DEFAULT_PROVIDER_REGISTRY`. Capability values include `chat`, `streaming`, `responses`, `vision`, `tools`, `fim`, and `unknown`. Unknown capabilities must not be treated as supported for safety-sensitive decisions.

## OAuth trust boundary

OAuth metadata discovery is path-aware with origin fallback. Issuer, resource, authorization endpoint, token endpoint, registration endpoint, redirect URI, and transport must be validated. HTTPS is required except for explicitly permitted localhost development endpoints. Tokens, secrets, and authorization codes must be redacted from logs.

## Structured events and verification

Stable event codes are separate from localized messages. Current entry/task events include:

- `cli.start`
- `web.start`
- `gui.start`
- `a2a.task.created`
- `tool.dispatch`
- `web.room.task.started`
- `web.room.task.completed`

Run the complete local acceptance suite with:

```text
python scripts/acceptance_check.py
```

The suite checks import graph policy, all tests, ruff, required design artifacts, and required event codes. A change is acceptable only when it reports `acceptance: OK`.
