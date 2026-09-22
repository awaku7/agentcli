# Memory V2 Acceptance

This document defines the final Memory V2 acceptance contract for the default-on
strict projection path.

The acceptance step does not add a new Memory architecture. It verifies that
the implemented V2 contracts remain valid across the supported host entry
points and the provider continuation paths that can retain derived context.

## 1. Host boundary

Memory V2 projection is owned by the shared `uagent_llm.run_llm_rounds()` turn
boundary. Host adapters must route user turns through that common path rather
than introducing host-specific Memory retrieval or projection logic.

The acceptance contract covers:

- CLI: `src/uagent/cli_impl/main.py`
- GUI: `src/uagent/scheckgui_impl/worker.py`
- Web: `src/uagent/web_impl/agent_worker.py`
- A2A: `src/uagent/a2a/engine.py`

`tests/test_memory_v2_acceptance.py` fails if one of these hosts no longer
routes through the shared LLM round path without an explicit review of the
Memory integration.

## 2. Deterministic acceptance gate

The production acceptance gate is `strict_scope`.

Required strict-scope conditions:

- recall = 1.0 for the deterministic fixture after strict-scope expectation
  adjustment;
- irrelevant injection rate = 0;
- scope violation count = 0;
- legacy/unknown scope selected count = 0;
- forget reappearance count = 0;
- provider continuation state is cleared after forget.

The legacy baseline is informational. Non-strict `projection` is also retained
as a comparison/rollback mode, but it is expected to fail the quality gate while
legacy-unknown records can still be selected. That failure is evidence for why
Strict Scope is part of the default-on V2 path rather than a reason to disable
Projection altogether.

## 3. Required test command

Run the following group together:

```text
python -m pytest -q \
  tests/test_memory_evaluation.py \
  tests/test_memory_evaluation_runner.py \
  tests/test_memory_v2_acceptance.py \
  tests/test_memory_projection.py \
  tests/test_memory_query.py \
  tests/test_memory_forget_propagation.py \
  tests/test_memory_history_boundary.py \
  tests/test_previous_response_id_compat.py
```

These tests cover separate responsibilities and should not be replaced by a
single large end-to-end test.

## 4. Evaluation report

Generate the comparison report with:

```text
python -m uagent.runtime.memory_evaluation_runner \
  --fixture tests/fixtures/memory_evaluation_cases.json \
  --iterations 25 \
  --json-out reports/memory_v2_evaluation.json \
  --markdown-out reports/memory_v2_evaluation.md
```

For a release/acceptance run, also execute:

```text
python -m uagent.runtime.memory_evaluation_runner \
  --fixture tests/fixtures/memory_evaluation_cases.json \
  --iterations 25 \
  --gate-mode strict_scope \
  --enforce
```

A measured 2026-09-22 run produced strict-scope Recall 1.000, irrelevant
injection 0.000, zero scope violations, zero legacy-unknown selections, zero
forget reappearance, and an overall PASS. See `MEMORY_EVALUATION.md` for the
full comparison table.

The generated report should be retained when practical, but raw Memory note
bodies must not be committed merely to support telemetry. The runner omits note
bodies by default.

## 5. Default runtime contract

Memory V2 is now default-on:

```text
UAGENT_MEMORY_PROJECTION=1
UAGENT_MEMORY_STRICT_SCOPE=1
```

When `UAGENT_MEMORY_OWNER` is unset, the current OS login ID is the V2 local
owner. Owner-less legacy records are treated as belonging to that owner at
projection time without rewriting storage. Missing project metadata is not
inferred and is rejected by Strict Scope.

Explicit rollback remains supported by setting either rollout flag to `0`.

## 6. Provider and recovery boundary

Memory V2 must remain safe when provider state can retain prior context.
Acceptance therefore includes the existing contracts for:

- Responses API continuation state;
- retry after stale/invalid `previous_response_id`;
- explicit forget invalidation;
- stale frozen snapshot rejection;
- Gemini/Vertex cache refresh marker;
- durable history boundary preventing derived Memory/Profile projection from
  becoming source conversation history.

The provider tests are compatibility contracts, not a requirement to make live
provider calls during the deterministic acceptance run.

## 7. Stop conditions

Do not ship or keep the default-on path if any of the following occurs:

- scope violation;
- forgotten Memory reappears;
- Personal/Shared scope is crossed;
- derived Memory/Profile text is persisted as original conversation history;
- projection mutates the original user message;
- provider continuation survives a forget when it can retain stale Memory;
- a supported host bypasses the shared Memory turn boundary.

## 8. V3 boundary

Embedding, Brain/Dream integration, authenticated multi-user identity,
authentication modes, and shared-room ownership belong to later work.

The OS-login owner fallback is intentionally a V2 local/single-user rule. V3
must replace it with authenticated `principal_id` propagation for shared Web or
A2A deployments serving multiple human users.
