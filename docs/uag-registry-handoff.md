# UAG Provider Runtime Registry — Handoff

Updated after commit `8fcaaab8` (`feat(registry): project generation options`).
This is the operational handoff for the next agent; the design authority
remains [UAG refactoring proposals](./uag-refactoring-proposals.md).

## Current status

The OpenAI and Azure registry route is **default enabled** and can be rolled
back without code changes. It covers both Chat Completions and Responses,
streaming and non-streaming responses, tool calls, structured output,
multimodal inputs, continuation state, local/remote overflow recovery, and
common generation options. The Inception event adapter is also enabled by
default for its own Chat Completions route and can be rolled back with
`UAGENT_PROVIDER_REGISTRY_INCEPTION`.

```text
ContextPlan → ProviderProjection → SerializedRequest
     ↓                 ↓                   ↓
RoundOrchestrator → OpenAICompatibleRuntime → StreamEvent → RoundResult
     ↓
ResponsesRuntime / ContextRecoveryManager
```

## Rollback switches

All three switches default to enabled for the migrated OpenAI/Azure routes.
Set any switch to `0` or `off` to use the established legacy path.

| Variable | Scope |
|---|---|
| `UAGENT_PROVIDER_REGISTRY` | Entire OpenAI/Azure registry route |
| `UAGENT_PROVIDER_REGISTRY_RESPONSES` | Responses route only |
| `UAGENT_PROVIDER_REGISTRY_TOOLS` | Tool-call route only |
| `UAGENT_PROVIDER_REGISTRY_INCEPTION` | Inception adapter route only |

Other providers are deliberately still legacy-only. Do not broaden the default
provider set without a dedicated adapter and parity tests.

For a failed or empty OpenAI/Azure Responses reply, set
`UAGENT_DEBUG_OPENAI_RUNTIME=1` to capture metadata-only stream diagnostics on
stderr. Prompt and response content are not logged.

## Completed implementation slices

| Area | Main files | Evidence |
|---|---|---|
| Contract, projection, registry | `runtime/round_contracts.py`, `runtime/round_orchestrator.py`, `providers/runtime_registry.py` | `tests/test_round_contracts.py`, `tests/test_round_orchestrator.py` |
| OpenAI/Azure event adapter | `providers/openai_compatible_runtime.py` | `tests/test_openai_compatible_runtime.py` |
| Inception event adapter | `providers/inception_runtime.py`, `llm_round_helpers.py` | `tests/test_inception_runtime.py`, `tests/test_round_integration_regressions.py` |
| Responses continuation and terminal state | `providers/responses_runtime.py`, `uagent_llm.py` | `tests/test_responses_runtime.py`, `tests/test_round_integration_regressions.py` |
| Recovery | `runtime/context_recovery.py`, `providers/responses_recovery_port.py` | `tests/test_context_recovery_integration.py` |
| Output parity | `llm_round_helpers.py`, `llm_flow_helpers.py`, `uagent_llm.py` | `tests/test_registry_output_parity.py` |
| Request options | `uagent_llm.py` | `tests/test_registry_generation_options.py` |
| I18N structural audit | `scripts/i18n_structure_audit.py` | `tests/test_i18n_structure_audit.py` |

Recent independent commits, newest first:

```text
8fcaaab8 feat(registry): project generation options
fb0951a4 feat(registry): migrate auto reasoning retry
bade7303 feat(registry): enable migrated routes by default
e1d81e1e fix(registry): preserve output post-processing
1ee2e738 feat(registry): support non-streaming OpenAI rounds
00e7787c fix(responses): synchronize registry terminal states
89faed19 fix(responses): preserve registry tool call identity
d3789f51 feat(registry): support multimodal round inputs
```

## Invariants to preserve

- `ContextPlan` is immutable input; recovery must not mutate persistent local
  history.
- Provider SDK / network I/O remains inside provider adapters or ports.
- `ResponsesRuntime` owns continuation invariants. A non-success terminal
  clears both runtime continuation and `responses_state` IDs.
- A tool may execute only after `ToolCallCompleted`; item IDs must be mapped to
  stable Responses `call_id` values before completion.
- Every retry is authorized by `RoundAttemptBudget`. The auto-reasoning quality
  retry is limited to one `feature_fallback` attempt.
- Registry adapters do not render host output. Pass
  `stream_output_rendered=False` to shared output/translation helpers when an
  adapter stream was collected but not rendered.
- I18N has two separate paths: host text uses gettext; tool text uses
  `*_tool.json`. Do not mix their key or placeholder rules.

## Remaining recommended work

1. Evaluate migrating an additional provider only behind a dedicated adapter
   and separate opt-out switch. Do not route other OpenAI-compatible gateways
   through the OpenAI/Azure default path.
1. Run the I18N audit in CI in non-strict reporting mode until the existing
   host/tool catalog coverage gaps are resolved. Keep structural validation and
   translation-quality review separate.
1. Before a release, run the full regression suite and manually verify an
   authenticated OpenAI and Azure Responses tool continuation. Unit tests do
   not exercise provider credentials or remote compaction behavior.

## Verification commands

On Windows, use a writable `--basetemp` because the default temporary location
may be restricted in some environments.

```powershell
$env:PYTHONPATH = 'src'
$temp = 'C:\Users\hirof\Documents\Codex\work\pytest-registry-handoff'
New-Item -ItemType Directory -Path $temp -Force | Out-Null
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q -p no:cacheprovider --basetemp $temp `
  tests/test_round_contracts.py `
  tests/test_round_orchestrator.py `
  tests/test_openai_compatible_runtime.py `
  tests/test_responses_runtime.py `
  tests/test_context_recovery_integration.py `
  tests/test_round_integration_regressions.py `
  tests/test_registry_output_parity.py `
  tests/test_registry_generation_options.py
python scripts/i18n_structure_audit.py --report docs/i18n-structure-report.json
```

Each work item should be committed independently with an English commit
message. Preserve unrelated worktree changes and do not use a broad formatter
or destructive Git operation to clean the tree.
