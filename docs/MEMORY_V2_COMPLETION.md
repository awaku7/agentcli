# Memory V2 Completion Decision

Status: **Complete after default-on rollout correction**  
Decision date: 2026-09-22 (JST)  
Baseline before default-on change: `e4b157ba143aa497eaf270473ce090f83bb545b2`

## 1. Final completion decision

Memory V2 is complete when its safer retrieval path is the normal runtime path, not only an opt-in experiment.

The final defaults are:

```text
UAGENT_MEMORY_PROJECTION=1
UAGENT_MEMORY_STRICT_SCOPE=1
```

Both remain explicitly reversible: setting either variable to `0` disables that layer for rollback or compatibility testing.

## 2. Default owner rule

`UAGENT_MEMORY_OWNER` remains the explicit override. When it is not configured, V2 resolves the owner from the current OS login.

Resolution order:

```text
explicit owner argument
-> UAGENT_MEMORY_OWNER
-> OS login ID
-> local-default (last-resort fallback)
```

On Windows, `USERDOMAIN\\username` is used when `USERDOMAIN` is available; otherwise the login username is used.

New Personal and Shared Memory records are therefore written with a non-empty owner by default.

For legacy records with no owner, projection treats the record as owned by the current OS login user for V2 single-user compatibility. This compatibility is read-only and does not rewrite the stored record.

Missing project metadata is **not** inferred. Under Strict Scope, a legacy record whose project cannot be verified remains excluded. This avoids silently assigning old data to whichever project happens to read it first.

## 3. Why both defaults are ON

The purpose of V2 is to improve normal Memory behavior. Leaving Projection and Strict Scope disabled would preserve most of the old broad-memory behavior and would not deliver the main retrieval improvement by default.

The measured deterministic comparison on 2026-09-22 produced:

| Mode | Recall | Irrelevant injection | Scope violations | Legacy unknown selected | Forget reappearance | Avg context chars | Mean latency ms | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| baseline | 1.000 | 0.654 | 4 | 4 | 0 | 166.8 | 1.733 | INFO |
| shadow | 1.000 | 0.333 | 0 | 3 | 0 | 0.0 | 0.026 | FAIL |
| projection | 1.000 | 0.333 | 0 | 3 | 0 | 237.6 | 0.055 | FAIL |
| strict_scope | 1.000 | 0.000 | 0 | 0 | 0 | 133.4 | 0.040 | PASS |

The non-strict projection result is intentionally not accepted as the production default because legacy-unknown compatibility still injected irrelevant records in the fixture. Strict Scope removed those records while retaining fixture recall.

These measurements are local deterministic retrieval/render measurements. They do not include LLM/provider network latency and must not be presented as an external-provider benchmark.

## 4. Final V2 runtime contract

### Normal operation

No Memory rollout environment variables are required:

```text
Projection   = ON
Strict Scope = ON
Owner        = explicit configured owner, otherwise OS login ID
Project      = UAGENT_MEMORY_PROJECT, otherwise workdir-derived project ID
```

The provider-facing request receives a frozen, turn-local Memory projection. Broad startup Memory blocks are removed from the provider call when the projection is applied, and derived projection text is not persisted as original conversation history.

### Compatibility rollback

Projection can be disabled explicitly:

```text
UAGENT_MEMORY_PROJECTION=0
```

Strict Scope can be disabled explicitly for legacy compatibility experiments:

```text
UAGENT_MEMORY_STRICT_SCOPE=0
```

Disabling Strict Scope allows owner/project-unknown legacy records to remain eligible. The evaluation runner demonstrates why that mode is not the default.

## 5. Acceptance commands

Run the focused V2 acceptance group:

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

Run the strict deterministic gate:

```text
python -m uagent.runtime.memory_evaluation_runner \
  --gate-mode strict_scope \
  --enforce
```

A scope leak, forgotten-memory reappearance, history contamination, or stale provider continuation surviving forget remains a stop condition.

## 6. Multi-user boundary

The OS-login fallback is deliberately a V2 local/single-user identity rule. It is not a substitute for authenticated multi-user identity.

For a Web or A2A service shared by multiple human users, the process OS account identifies the service process, not the remote human. V3 must replace this fallback with authenticated `principal_id` propagation before Personal Memory is considered multi-user isolated.

This does not block V2 default-on for the existing local/single-user model; it defines the boundary V3 must replace.

## 7. What remains outside V2

The following belongs to V3 or later:

- stable authenticated `principal_id`;
- OIDC / OAuth / trusted-proxy / Windows AD identity modes;
- per-principal Profile isolation;
- Personal / Room / Project / Global audience separation;
- shared-room Memory ACLs and management APIs;
- tenant-level isolation;
- Brain/Dream or embedding retrieval as a new source layer.

## 8. Final state

```text
implementation        = complete
acceptance contract   = complete
evaluation runner     = complete
projection default    = ON
strict scope default  = ON
default owner         = OS login ID (unless explicitly configured)
legacy owner fallback = current OS login ID
legacy project unknown= excluded under strict scope
V3 identity work      = separate next phase
```
