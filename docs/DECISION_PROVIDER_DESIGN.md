# Decision Provider Architecture

## Status

Design and staged implementation for an opt-in decision-model layer in UAG.

PR 1 common infrastructure, PR 2 TypeSafe/Jev adapter, and PR 3 Laya adapter
are implemented: shared settings, provider-neutral request/result types, a lazy
registry/factory, common CLI/GUI/Web/A2A configuration, the TypeSafe System One
HTTP adapter, and the local Laya adapter. Runtime decision sites remain a
follow-up stage; no decision site is activated by the adapters alone.

The first supported provider keys are intended to be:

- `none`
- `typesafe`
- `laya`

`typesafe` represents the TypeSafe decision API. Jev is treated as a model selected
through the TypeSafe provider rather than as a provider key itself.

This layer is separate from the existing LLM provider layer. It is not an LLM
provider and must not be added to `provider_caps.ALL_PROVIDERS`.

## Goals

UAG currently lets the selected LLM make routing and orchestration decisions as
part of the normal agent flow. This design adds an optional dedicated decision
provider that can answer typed, non-generative decision questions before or
alongside the normal LLM flow.

The design must:

1. Preserve current UAG behavior by default.
2. Require explicit opt-in before TypeSafe or Laya is initialized or called.
3. Treat TypeSafe and Laya as interchangeable implementations behind a UAG-owned
   interface.
4. Keep provider-specific schemas out of the UAG core.
5. Avoid coupling the decision-provider layer to the LLM-provider registry.
6. Work consistently across CLI, GUI, Web, and A2A entry points.
7. Permit future shadow evaluation without making shadow results affect runtime
   behavior.
8. Keep `llmcapa` focused on model/provider capability metadata rather than
   decision execution.

## Non-goals

The first implementation does not:

- replace UAG's LLM provider selection,
- make TypeSafe or Laya mandatory dependencies,
- automatically initialize or call a decision provider when none is selected,
- automatically download or initialize a Laya model when Laya is not selected,
- automatically trust a provider's confidence value as a universal risk score,
- automatically route all UAG decisions through the selected decision provider,
- change existing behavior when the decision provider is `none`,
- make `llmcapa` responsible for decision-provider execution.

## Opt-in contract

The dedicated decision layer is disabled unless the user explicitly selects a
provider other than `none`.

The effective default is:

```text
Decision provider = none
```

`none` means **no dedicated decision provider**. It does not mean "make no
decisions". Existing UAG behavior remains authoritative and the current LLM/tool
flow runs unchanged.

When the effective provider is `none`, UAG must not:

- import or initialize TypeSafe-specific decision code,
- import or initialize Laya runtime packages/models,
- download decision-model assets,
- probe TypeSafe or Laya endpoints,
- add decision-model startup latency,
- validate provider-specific credentials that are not active,
- alter prompts, tool selection, routing, or agent behavior.

This is a strict backward-compatibility requirement.

## Configuration

Following the project convention, the CLI option is authoritative and the
environment variable is a fallback.

Proposed CLI option:

```bash
uag --decision-provider none
uag --decision-provider typesafe
uag --decision-provider laya
```

Proposed environment variable:

```text
UAGENT_DECISION_PROVIDER=none
UAGENT_DECISION_PROVIDER=typesafe
UAGENT_DECISION_PROVIDER=laya
```

Precedence:

```text
--decision-provider
    > UAGENT_DECISION_PROVIDER
    > none
```

The resolved value should be stored in shared runtime configuration so CLI, GUI,
Web, and A2A use the same semantics.

Provider-specific settings use the namespace:

```text
UAGENT_DECISION_<PROVIDER>_<SETTING>
```

### TypeSafe / Jev

Jev is a model selected through the TypeSafe provider. The provider key is
`typesafe`; the model is selected through `DEPNAME`.

```text
UAGENT_DECISION_PROVIDER=typesafe
UAGENT_DECISION_TYPESAFE_DEPNAME=jev-latest
UAGENT_DECISION_TYPESAFE_BASE_URL=...
UAGENT_DECISION_TYPESAFE_API_KEY=...
```

The adapter maps `UAGENT_DECISION_TYPESAFE_DEPNAME` to the model identifier sent
to TypeSafe.

### Laya

Laya is normally used as a local decision model/checkpoint.

```text
UAGENT_DECISION_PROVIDER=laya
UAGENT_DECISION_LAYA_DEPNAME=laya-multilingual
UAGENT_DECISION_LAYA_DEVICE=auto
```

Additional Laya-specific settings can follow the same namespace if required.

Secrets continue to follow the existing `.env.sec` handling.

Provider-specific settings are ignored when their provider is not selected. For
example, `UAGENT_DECISION_TYPESAFE_API_KEY` must not be required or validated
when `UAGENT_DECISION_PROVIDER=none` or `laya`.

## Architecture

The decision-provider layer is parallel to, not nested inside, the LLM provider
layer.

```text
                         UAG Core
                            |
              +-------------+-------------+
              |                           |
        LLM Provider                Decision Provider
              |                           |
    OpenAI / Claude / ...       none / typesafe / laya
                                          |
                                 UAG Decision API
```

The UAG core must depend on UAG-owned request/result types. Provider adapters are
responsible for translating those types to TypeSafe- or Laya-specific APIs.

Suggested package layout:

```text
src/uagent/decision/
    __init__.py
    base.py
    models.py
    registry.py
    settings.py
    typesafe.py   # added with the TypeSafe adapter stage
    laya.py       # added with the Laya adapter stage
```

This deliberately does not use `src/uagent/providers/`, which is the LLM provider
namespace today.

## Common UAG decision model

Provider-specific concepts must not become the UAG public abstraction.

A UAG-owned request model should describe generic decision questions, for example:

```python
DecisionQuestion(
    id="needs_tools",
    kind="boolean",
    instruction="Does this request require tools?",
)

DecisionQuestion(
    id="difficulty",
    kind="choice",
    choices=["easy", "medium", "hard"],
)

DecisionQuestion(
    id="risk",
    kind="score",
    choices=["low", "medium", "high"],
)
```

Initial generic kinds:

- `boolean`
- `choice`
- `score`

Adapters map those kinds to provider-specific representations.

The state/input should remain generic and serializable:

```python
DecisionRequest(
    state=<str | dict | list>,
    questions=[...],
    metadata={...},
)
```

The common result should retain enough provenance for logging and evaluation:

```python
DecisionResult(
    provider="laya",
    model="laya-multilingual",
    answers={
        "needs_tools": DecisionAnswer(
            value=True,
            confidence=0.91,
        ),
    },
    latency_ms=34.2,
    skipped=False,
    raw=None,
)
```

For TypeSafe the same result shape is used, with `provider="typesafe"` and the
selected Jev model recorded in `model`.

## Provider interface

The first implementation should keep the interface intentionally small.

Conceptually:

```python
class DecisionProvider(Protocol):
    @property
    def name(self) -> str:
        ...

    def decide(self, request: DecisionRequest) -> DecisionResult:
        ...

    def close(self) -> None:
        ...
```

An asynchronous variant can be added if required by an adapter, but UAG should
avoid forcing every provider into a network-oriented design because Laya can be
a local in-process model.

## `none` provider

`none` is the default behavior and has special semantics.

It should preferably be represented by the absence of an active decision
provider in the hot path, or by a zero-cost `NoneDecisionProvider` where a common
object simplifies wiring.

If represented as an object, a result can be explicit:

```python
DecisionResult(
    provider="none",
    model=None,
    answers={},
    latency_ms=0.0,
    skipped=True,
)
```

However, the implementation must not insert a new decision stage into every
request merely to produce that object. The default path should remain as close
as possible to the current code path.

## TypeSafe adapter

The TypeSafe adapter owns all TypeSafe-specific details:

- API/client initialization,
- base URL handling,
- API-key handling,
- `DEPNAME` to model-id mapping,
- request translation,
- response translation,
- provider-specific errors,
- provider-specific raw metadata.

Jev is not exposed as a provider key. It is a model selected through
`UAGENT_DECISION_TYPESAFE_DEPNAME`.

The core must not depend on TypeSafe response schemas.

TypeSafe must only be initialized or contacted after the resolved provider is
`typesafe`.

The implemented adapter uses the existing `httpx` dependency and calls
`POST /v1/systemone` directly. It defaults to:

```text
UAGENT_DECISION_TYPESAFE_DEPNAME=jev-latest
UAGENT_DECISION_TYPESAFE_BASE_URL=https://api.typesafe.ai
```

`UAGENT_DECISION_TYPESAFE_API_KEY` is required only when the TypeSafe adapter
is actually created. The common question mapping is:

```text
boolean -> noul
choice  -> choice
score   -> score
```

TypeSafe response schemas are validated at the adapter boundary and translated
back into UAG-owned `DecisionAnswer` values. Provider-specific probabilities,
score legends, and the Noul true-probability are retained as answer metadata.
The raw provider response remains excluded from normal `DecisionResult.to_dict()`
serialization unless explicitly requested.

## Laya adapter

The Laya adapter owns all Laya-specific details:

- lazy package import,
- checkpoint/model selection through `UAGENT_DECISION_LAYA_DEPNAME`,
- device selection through `UAGENT_DECISION_LAYA_DEVICE`,
- mapping UAG `boolean` / `choice` / `score` questions to Laya-native typed
  decisions,
- result conversion,
- provider-specific confidence/calibration metadata,
- resource cleanup where required.

Laya should only be imported, initialized, and allowed to load/download a model
after the resolved provider is `laya`.

The implemented adapter goes further and defers importing the optional `laya`
runtime and constructing `laya.Router` until the first actual `decide()` call.
Router construction uses `preload=False` and `max_loaded=1`; therefore no
checkpoint is loaded or downloaded merely because UAG starts or because the Laya
provider object is created.

The defaults are:

```text
UAGENT_DECISION_LAYA_DEPNAME=laya-multilingual
UAGENT_DECISION_LAYA_DEVICE=auto
```

`auto` is translated to Laya's native automatic device selection by leaving the
Router device unset. Explicit values such as `cpu`, `cuda`, `mps`, or `xpu`
are forwarded as configured.

Install the optional runtime with:

```bash
pip install "uag[decision-laya]"
```

The adapter maps UAG `boolean / choice / score` to Laya
`noul / choice / score`. It uses Laya's `answer_confidence` as diagnostic
confidence metadata but records `calibrated=False` in the common result. UAG
does not use that value as a universal execution threshold. The entropy-style
Laya `confidence`, probabilities, action probability, score legend, and Noul
true-probability are retained as provider metadata where present.

The adapter must not expose Laya-specific question types as the UAG core API.

## Dependency policy

Decision providers must remain optional.

Provider-specific packages must not be imported by module import side effects on
the default path and must not become unconditional core dependencies.

If UAG's existing optional-dependency auto-install mechanism is reused for Laya,
the installer may run only after the user explicitly selected `laya`.

The important behavior is:

```text
provider=none      -> no TypeSafe/Laya decision-provider work
provider=typesafe  -> TypeSafe configuration/client path may run
provider=laya      -> Laya dependency/model path may run
```

A failed optional-provider initialization must produce a clear startup/runtime
error identifying the selected decision provider. It must not silently switch
the user to another dedicated decision provider.

## Runtime placement

The initial integration should introduce the capability without immediately
changing agent policy.

Recommended first runtime use is an explicit decision service callable from the
orchestration layer. Candidate decisions include:

- `difficulty`
- `needs_tools`
- `domain`
- `sensitive`
- `needs_subagent`
- `needs_human`

Those names are policy-level concepts, not provider capabilities. They should be
added incrementally and only after each one has a defined fallback behavior.

The first implementation should not replace the existing provider router or tool
flow wholesale.

## Fallback behavior

Fallback policy must be explicit per decision site.

A provider failure must not be interpreted as a negative decision. For example,
failure to evaluate `needs_tools` must not become `needs_tools=False`.

Safe patterns are:

1. Preserve the current UAG/LLM decision path on provider failure.
2. Mark the dedicated result unavailable and let the existing policy decide.
3. For a future decision site with no legacy equivalent, fail closed according
   to that site's documented policy.

The generic decision-provider layer should not hard-code one global fallback
answer.

## Confidence semantics

`confidence` is provider-reported or provider-derived metadata. It is not a
universal probability scale across TypeSafe/Jev and Laya.

Therefore UAG must not initially implement logic such as:

```python
if result.confidence > 0.8:
    auto_execute()
```

without decision-specific validation and calibration.

The result model should permit additional metadata, for example:

```python
DecisionAnswer(
    value="hard",
    confidence=0.84,
    calibrated=False,
    metadata={...},
)
```

Cross-provider comparisons should use observed task accuracy/calibration from
UAG evaluation data rather than raw confidence values.

## Shadow evaluation

Shadow mode is useful but should be a later, explicitly configured feature.

A future configuration could look like:

```text
UAGENT_DECISION_PROVIDER=laya
UAGENT_DECISION_SHADOW_PROVIDER=typesafe
```

Semantics:

- primary provider result may be consumed by the configured decision site,
- shadow provider result is recorded only,
- shadow result must never alter runtime behavior,
- failures in the shadow provider must not fail the request.

This allows UAG to collect agreement, latency, accuracy, and calibration data
before changing policy.

The first implementation can omit shadow execution while keeping the result and
registry design compatible with adding it later.

## Relationship to `llmcapa`

`llmcapa` remains the capability-information source for LLM/provider features.
The decision-provider layer performs runtime decisions.

These concerns should remain separate:

```text
llmcapa
    -> What can this LLM/provider/model do?

Decision provider (TypeSafe/Laya)
    -> What decision should UAG make for this input/question?
```

A future policy may use both inputs, for example using a decision model to select
an execution tier and `llmcapa` to filter that tier to models that actually
support the required tools or modalities. That does not require coupling their
registries.

## Startup and banner behavior

When disabled, no additional startup noise is necessary beyond an optional
concise line if the banner already shows feature state.

When enabled, startup diagnostics should clearly separate LLM and decision
providers, for example:

```text
[INFO] LLM provider      = openai
[INFO] LLM model         = ...
[INFO] Decision provider = typesafe
[INFO] Decision model    = jev-latest
```

or:

```text
[INFO] Decision provider = laya
[INFO] Decision model    = laya-multilingual
```

Secrets and endpoint credentials must never be printed.

## Observability

Decision-provider calls should eventually emit structured telemetry compatible
with the existing UAG observability direction.

Useful fields include:

- provider,
- model/checkpoint,
- decision/question id,
- answer,
- latency,
- success/failure,
- fallback used,
- confidence when present,
- calibrated flag when known,
- shadow/primary role when shadow mode exists.

Raw user input should not be duplicated into telemetry by default.

## Security and privacy

A decision provider may be local or remote. The adapter must make that boundary
clear.

For TypeSafe, UAG must treat the state sent for decision as externally
transmitted data and apply the same secret and privacy discipline used for other
remote services.

For local Laya execution, UAG should not imply that data leaves the machine
unless the selected adapter/checkpoint source actually causes a network action.
Model download behavior should be documented separately from inference behavior.

## Implementation sequence

### PR 1: common opt-in infrastructure — implemented

- Add shared decision-provider configuration.
- Default to `none`.
- Add UAG-owned request/result types.
- Add registry/factory and `none` behavior.
- Add tests proving the default path remains unchanged.
- Do not add TypeSafe or Laya dependencies yet.

### PR 2: TypeSafe adapter — implemented

- Add TypeSafe configuration handling.
- Use `UAGENT_DECISION_TYPESAFE_DEPNAME` for Jev model selection.
- Use `UAGENT_DECISION_TYPESAFE_BASE_URL` and
  `UAGENT_DECISION_TYPESAFE_API_KEY` for connection/authentication.
- Implement request/result translation.
- Add adapter unit tests with mocked TypeSafe boundaries.
- Document TypeSafe/Jev-specific configuration.

### PR 3: Laya adapter — implemented

- Add Laya optional dependency handling.
- Use `UAGENT_DECISION_LAYA_DEPNAME` for checkpoint/model selection.
- Use `UAGENT_DECISION_LAYA_DEVICE` for device selection.
- Implement typed-question mapping.
- Add adapter unit tests without requiring model download in the normal test
  suite.
- Document model/device/checkpoint behavior.

### PR 4: first decision site and evaluation logging — implemented

- Use auto-pilot completion review as the first policy decision.
- Preserve the existing UAG decision as fallback.
- Record provider result, latency, confidence diagnostics, and fallback behavior.
- Do not use raw confidence as an automatic execution threshold.
- Agreement measurement against the legacy LLM reviewer is deferred to an
  explicit shadow/evaluation mode so the normal Decision Provider path does not
  pay for the reviewer call it is intended to replace.

### Later PRs

- Add additional decision sites based on measured value.
- Add shadow providers if needed.
- Add calibrated thresholds only where UAG-specific evaluation supports them.

## Tests required for implementation

At minimum, implementation should verify:

1. No option and no environment variable resolve to `none`.
2. `--decision-provider` overrides the environment variable.
3. `none` does not initialize TypeSafe or import Laya.
4. `none` does not validate inactive provider-specific credentials.
5. `none` does not change existing LLM/tool behavior.
6. Selecting `typesafe` initializes only the TypeSafe decision path.
7. Selecting `laya` initializes only the Laya decision path.
8. TypeSafe model selection uses `UAGENT_DECISION_TYPESAFE_DEPNAME`.
9. Laya model selection uses `UAGENT_DECISION_LAYA_DEPNAME`.
10. Missing credentials/dependencies produce an actionable error only when their
    provider is selected.
11. Provider failures never become implicit negative decisions.
12. Common result serialization does not leak provider-specific objects.
13. CLI, GUI, Web, and A2A resolve the same shared setting.
14. Startup output never exposes credentials.
15. Adapter tests do not require network/model downloads in the normal CI path.

## Acceptance criteria

The architecture is considered correctly integrated when a stock UAG invocation
without new configuration behaves exactly as before, while an explicitly
selected `typesafe` or `laya` provider can be initialized through the common
decision API without altering the existing LLM-provider registry.

For TypeSafe, Jev remains a model selected by `DEPNAME`, not a provider key.
