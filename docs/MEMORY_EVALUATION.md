# Memory Evaluation Gates

This document describes the deterministic evaluation gate and comparison runner
for the Memory V2 rollout. Neither path calls an LLM or writes a persistent
memory store.

## Deterministic retrieval gate

Run the focused fixture gate with:

```text
python -m pytest -q tests/test_memory_evaluation.py
```

The fixture is `tests/fixtures/memory_evaluation_cases.json` and is evaluated by
`uagent.runtime.memory_evaluation`.

Each case reports:

- `recall`: expected notes returned / expected notes
- `irrelevant_injection_rate`: returned notes not in the expected set / returned notes
- `scope_violation_count`: candidates marked with an invalid scope status
- `excluded_count`: records excluded before projection
- `failure_reasons`: deterministic failure categories

## V2 comparison runner

The comparison runner evaluates the same fixture through four rollout modes:

```text
baseline -> shadow -> projection -> strict_scope
```

Run it from the repository root:

```text
python -m uagent.runtime.memory_evaluation_runner \
  --fixture tests/fixtures/memory_evaluation_cases.json \
  --iterations 25 \
  --json-out reports/memory_v2_evaluation.json \
  --markdown-out reports/memory_v2_evaluation.md
```

To make the selected acceptance gate fail the command with exit code 2:

```text
python -m uagent.runtime.memory_evaluation_runner \
  --fixture tests/fixtures/memory_evaluation_cases.json \
  --gate-mode strict_scope \
  --enforce
```

`strict_scope` is the default gate mode. `shadow` and `projection` can also be
selected explicitly.

### Mode definitions

- `baseline`: uses the production broad startup formatter
  `build_long_memory_system_message()`. It intentionally represents the current
  broad prompt baseline and does not add V2 owner/project retrieval filtering.
- `shadow`: uses `shadow_retrieve_memories()` with legacy-unknown compatibility,
  but injects no provider context.
- `projection`: uses the same non-strict retrieval and then the production
  Memory Evidence whole-item budget behavior.
- `strict_scope`: uses projection rendering while rejecting records whose
  owner/project boundary cannot be verified.

Strict-scope expectations are adjusted only when an expected fixture note is a
legacy-unknown record that strict scope is intentionally required to reject.
This prevents deliberate legacy rejection from being counted as recall loss.

## Runner metrics

The runner records, per mode and per case:

- recall
- irrelevant injection rate
- explicit scope violations
- selected legacy-unknown records
- candidate count and candidate characters
- provider memory-context characters
- budget-dropped item count
- local retrieval/render latency
- forget reappearance count
- whether Responses-style continuation IDs are cleared by forget invalidation

The report also includes deltas against the broad baseline for recall,
irrelevant injection, context characters, and local CPU latency.

### Forget probe

The runner uses the production forget-generation and projection application
helpers. For baseline/shadow it verifies that an invalidated startup Personal
Memory system block is stripped. For projection/strict-scope it verifies that a
snapshot captured before the generation change cannot be re-applied. It also
checks that provider continuation IDs are cleared.

A forget reappearance count greater than zero is a stop condition.

## Report privacy

Memory note bodies are omitted from JSON and Markdown reports by default. Case
results contain short SHA-256-derived note fingerprints instead. Raw note text
is included only when `--include-notes` is explicitly supplied.

Do not publish reports created with `--include-notes` unless their contents have
been reviewed for sensitive information.

## Measurement boundaries

The runner is intentionally local and deterministic:

- it does not call an LLM or provider;
- latency is retrieval/render CPU time, not end-to-end model latency;
- shadow mode contributes zero provider context by design;
- `context_chars` covers broad Memory text or projected Memory Evidence only;
- Profile/Applicable User Guidance budget behavior remains covered by dedicated
  projection tests;
- full CLI/GUI/Web/A2A and provider continuation acceptance remains a separate
  V2 acceptance step.

The CPU timings are useful for relative comparison on the same machine and run.
They are not a cross-machine performance benchmark.

## Required scenarios

The fixture covers:

- owner/project scoped retrieval
- owner and project mismatch exclusion
- strict-scope rejection of legacy records
- legacy compatibility mode
- Japanese query matching
- path and alphanumeric query matching
- duplicate and unrelated-record suppression

The production projection, forget propagation, history boundary, frozen
snapshot, applicable-guidance, and contextual-query contracts remain covered by
their dedicated test modules. Run those together with the comparison runner
before changing defaults.

## Rollout rule

The V2 rollout order remains:

```text
baseline -> shadow -> opt-in projection -> opt-in strict scope -> default decision
```

Passing the deterministic runner is necessary but not sufficient to change a
default. Before the default decision, record the comparison report and complete
host/provider acceptance for:

- CLI / GUI / Web / A2A
- stateless chat and Responses continuation
- retry/recovery and available provider-cache paths
- forget/restart behavior

Any scope leakage, forgotten-memory reappearance, source-history contamination,
or save-success false positive blocks rollout. Recall, irrelevant injection,
latency, and context size should be recorded against the baseline before the V2
default decision is documented.
