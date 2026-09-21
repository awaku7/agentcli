# Memory Evaluation Gates

This document describes the deterministic evaluation gate for the memory rollout.
The gate does not call an LLM, write a memory store, or judge provider output.

## Running the gate

```text
python -m pytest -q tests/test_memory_evaluation.py
```

The fixture is `tests/fixtures/memory_evaluation_cases.json` and is evaluated by
`uagent.runtime.memory_evaluation`.

## Metrics

Each case reports:

- `recall`: expected notes returned / expected notes
- `irrelevant_injection_rate`: returned notes not in the expected set / returned notes
- `scope_violation_count`: candidates marked with an invalid scope status
- `excluded_count`: records excluded before projection
- `failure_reasons`: deterministic failure categories

The aggregate report is suitable for comparing baseline, shadow, opt-in
projection, and strict-scope modes. It intentionally does not define a quality
threshold without a measured baseline.

## Required scenarios

The initial fixture covers:

- owner/project scoped retrieval
- owner and project mismatch exclusion
- strict-scope rejection of legacy records
- legacy compatibility mode
- Japanese query matching
- path and alphanumeric query matching

The production projection, forget propagation, history boundary, frozen
snapshot, and contextual-query contracts remain covered by their dedicated test
modules. They should be run together with this gate before changing defaults.

## Rollout rule

The order is:

```text
baseline -> shadow -> opt-in projection -> opt-in strict scope -> default decision
```

Do not enable projection or strict scope by default solely because this fixture
passes. Record recall, irrelevant injection, scope leakage, forget reappearance,
latency, and context size against the baseline first.
