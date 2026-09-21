# Memory V2 Completion Decision

Status: **Complete**  
Decision date: 2026-09-22 (JST)  
Baseline after acceptance merge: `15affcedbc39f2ed34efda8ffd399fcbbbb8707d`

## 1. Completion decision

Memory V2 is complete as an implemented, tested, opt-in memory projection architecture.

The completion decision does **not** require Memory Projection or Strict Scope to become default-on. The V2 rollout defaults remain:

```text
UAGENT_MEMORY_PROJECTION=0
UAGENT_MEMORY_STRICT_SCOPE=0
```

Users and controlled deployments may explicitly enable either feature for evaluation or production use.

## 2. Why the defaults remain opt-in

The V2 implementation and deterministic acceptance contracts are in place, including:

- reliable Memory save/result handling;
- structured Memory records with stable IDs and revisions;
- SQLite/JSONL migration support;
- owner/project scope boundaries;
- read-only shadow retrieval;
- turn-local Memory Projection;
- Applicable User Guidance separated from retrieved evidence;
- contextual retrieval queries;
- frozen projection snapshots across retries/tool loops;
- forget-generation invalidation and stale-snapshot rejection;
- durable SessionStore/history boundaries for derived Memory context;
- deterministic retrieval/evaluation gates;
- baseline/shadow/projection/strict-scope comparison runner;
- host-routing acceptance contracts for CLI, GUI, Web, and A2A;
- Responses continuation invalidation/retry coverage.

However, deterministic/local acceptance is intentionally not treated as proof that default-on behavior is appropriate for every deployment. A default-on decision would additionally benefit from measured production data covering provider/model combinations, real workload latency, context growth, legacy-memory populations, and deployment-specific compatibility.

Keeping both features opt-in therefore preserves backward compatibility while leaving the completed V2 mechanisms available for controlled rollout.

## 3. Final V2 rollout contract

### Projection disabled

With no explicit setting:

```text
UAGENT_MEMORY_PROJECTION=0
```

UAG keeps the existing compatibility behavior and does not replace the broad startup Memory path with turn-local retrieval projection.

### Projection enabled, Strict Scope disabled

```text
UAGENT_MEMORY_PROJECTION=1
UAGENT_MEMORY_STRICT_SCOPE=0
```

Turn-local projection is enabled while legacy records with unknown owner/project metadata remain eligible under the compatibility policy.

### Projection enabled, Strict Scope enabled

```text
UAGENT_MEMORY_PROJECTION=1
UAGENT_MEMORY_STRICT_SCOPE=1
```

Turn-local projection is enabled and records without a verifiable owner/project boundary are rejected from the projection candidate set.

Strict Scope is intentionally not made the default while legacy records may still exist without complete scope metadata.

## 4. Acceptance evidence

The deterministic comparison path is implemented by:

```text
python -m uagent.runtime.memory_evaluation_runner \
  --fixture tests/fixtures/memory_evaluation_cases.json \
  --gate-mode strict_scope \
  --enforce
```

The focused V2 acceptance group is:

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

The repository does not currently expose a required GitHub Actions status check for this acceptance group. Therefore this document records the architectural/default decision and the executable acceptance contract; it does not claim that every external provider/model combination has been exercised in CI.

## 5. Conditions for revisiting default-on

Changing either V2 feature to default-on is a separate rollout decision, not unfinished V2 implementation work.

Before changing defaults, collect representative measurements for:

- recall and irrelevant-injection rate;
- scope violations;
- forgotten-memory reappearance;
- latency and context-size deltas;
- legacy-record exclusion impact;
- CLI/GUI/Web/A2A behavior in representative deployments;
- stateless providers and Responses-style continuation paths;
- provider cache/retry/recovery behavior where applicable.

Any scope leak, forgotten-memory reappearance, history contamination, or false save-success remains a stop condition.

## 6. What is outside V2

The following work belongs to V3 or later and is not required to reopen V2:

- stable multi-user `principal_id` identity;
- selectable authentication modes;
- OIDC / Entra ID / AD FS / Windows AD integration;
- per-principal Profile isolation;
- Personal / Room / Project / Global audience separation;
- shared-room Memory ACLs and management APIs;
- multi-user Web identity propagation;
- tenant-level isolation;
- Brain/Dream or semantic/embedding retrieval as a new default path.

These extend the completed V2 projection/retrieval contracts rather than replacing their source-of-truth, snapshot, scope, forget, and evaluation principles.

## 7. Final state

Memory V2 is closed with the following state:

```text
implementation        = complete
acceptance contract   = complete
evaluation runner     = complete
projection default    = OFF (opt-in)
strict scope default  = OFF (opt-in)
V3 identity work      = separate next phase
```
