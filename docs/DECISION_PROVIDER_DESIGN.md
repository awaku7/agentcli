# Decision Provider Architecture

## Status

Design proposal for an opt-in decision-model layer in UAG.

The first supported provider keys are intended to be:

- `none`
- `jev`
- `laya`

This layer is separate from the existing LLM provider layer. It is not an LLM
provider and must not be added to `provider_caps.ALL_PROVIDERS`.

## Goals

UAG currently lets the selected LLM make routing and orchestration decisions as
part of the normal agent flow. This design adds an optional dedicated decision
provider that can answer typed, non-generative decision questions before or
alongside the normal LLM flow.

The design must:

1. Preserve current UAG behavior by default.
2. Require explicit opt-in before Jev or Laya is initialized or called.
3. Treat Jev and Laya as interchangeable implementations behind a UAG-owned
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
- make Jev or Laya mandatory dependencies,
- automatically download or initialize a decision model when no provider is
  selected,
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

- import Jev or Laya runtime packages,
- initialize Jev or Laya clients/models,
- download decision-model assets,
- probe decision-model endpoints,
- add decision-model startup latency,
- alter prompts, tool selection, routing, or agent behavior.

This is a strict backward-compatibility requirement.

## Configuration

Following the project convention, the CLI option is authoritative and the
environment variable is a fallback.

Proposed CLI option:

```bash
uag --decision-provider none
uag --decision-provider jev
uag --decision-provider laya
```

Proposed environment variable:

```text
UAGENT_DECISION_PROVIDER=none
UAGENT_DECISION_PROVIDER=jev
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

Provider-specific options should use a provider namespace rather than leaking
into generic UAG settings. Exact option names should be added only when the
adapter implementation needs them.

Examples:

```text
UAGENT_DECISION_PROVIDER=laya
UAGENT_LAYA_MODEL=auto
UAGENT_LAYA_DEVICE=auto
```

and, if Jev needs a remote endpoint:

```text
UAGENT_DECISION_PROVIDER=jev
UAGENT_JEV_ENDPOINT=...
UAGENT_JEV_API_KEY=...
```

Secrets continue to follow the existing `.env.sec` handling.

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
    OpenAI / Claude / ...          none / jev / laya
                                          |
                                 UAG Decision API
```

The UAG core must depend on UAG-owned request/result types. Provider adapters are
responsible for translating those types to Jev- or Laya-specific APIs.

Suggested package layout:

```text
src/uagent/decision/
    __init__.py
    base.py
    models.py
    registry.py
    none.py
    jev.py
    laya.py
```

This deliberately does not use `src/uagent/providers/`, which is the LLM provider
namespace today.

## Common UAG decision model

Provider-specific concepts such as Laya's native typed question names must not
become the UAG public abstraction.

A UAG-owned request model should describe generic decision questions, for
example:

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
    model="...",
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

The exact implementation may use dataclasses or the project's existing data
model conventions, but the provider boundary must remain explicit.

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

## Jev adapter

The Jev adapter owns all Jev-specific details:

- dependency/client import,
- client or endpoint construction,
- request translation,
- response translation,
- provider-specific errors,
- provider-specific raw metadata.

The core must not depend on Jev response schemas.

Jev should only be imported and initialized after the resolved provider is
`jev`.

## Laya adapter

The Laya adapter owns all Laya-specific details:

- lazy package import,
- checkpoint/model selection,
- device selection,
- mapping UAG `boolean` / `choice` / `score` questions to Laya-native typed
  decisions,
- result conversion,
- provider-specific confidence/calibration metadata,
- resource cleanup where required.

Laya should only be imported, initialized, and allowed to load/download a model
after the resolved provider is `laya`.

The adapter must not expose Laya-specific question types as the UAG core API.

## Dependency policy

Jev and Laya must remain optional.

They should not be imported by module import side effects on the default path and
should not become unconditional core dependencies.

If UAG's existing optional-dependency auto-install mechanism is reused, the
installer may run only after the user explicitly selected the corresponding
decision provider.

The important behavior is:

```text
provider=none  -> no Jev/Laya dependency work
provider=jev   -> Jev dependency path may run
provider=laya  -> Laya dependency path may run
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
universal probability scale across Jev and Laya.

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
UAGENT_DECISION_SHADOW_PROVIDER=jev
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

Decision provider (Jev/Laya)
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
[INFO] Decision provider = laya
[INFO] Decision model    = ...
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

For a remote provider such as a network-backed Jev deployment, UAG must treat the
state sent for decision as externally transmitted data and apply the same secret
and privacy discipline used for other remote services.

For local Laya execution, UAG should not imply that data leaves the machine
unless the selected adapter/checkpoint source actually causes a network action.
Model download behavior should be documented separately from inference behavior.

## Implementation sequence

### PR 1: common opt-in infrastructure

- Add shared decision-provider configuration.
- Default to `none`.
- Add UAG-owned request/result types.
- Add registry/factory and `none` behavior.
- Add tests proving the default path remains unchanged.
- Do not add Jev or Laya dependencies yet.

### PR 2: Jev adapter

- Add Jev optional dependency handling.
- Implement request/result translation.
- Add adapter unit tests with mocked Jev boundaries.
- Document Jev-specific configuration.

### PR 3: Laya adapter

- Add Laya optional dependency handling.
- Implement typed-question mapping.
- Add adapter unit tests without requiring model download in the normal test
  suite.
- Document model/device/checkpoint behavior.

### PR 4: first decision site and evaluation logging

- Select one low-risk policy decision.
- Preserve the existing UAG decision as fallback.
- Record provider result, latency, agreement, and fallback behavior.
- Do not use raw confidence as an automatic execution threshold.

### Later PRs

- Add additional decision sites based on measured value.
- Add shadow providers if needed.
- Add calibrated thresholds only where UAG-specific evaluation supports them.

## Tests required for implementation

At minimum, implementation should verify:

1. No option and no environment variable resolve to `none`.
2. `--decision-provider` overrides the environment variable.
3. `none` does not import Jev or Laya modules.
4. `none` does not change existing LLM/tool behavior.
5. Selecting `jev` initializes only Jev.
6. Selecting `laya` initializes only Laya.
7. Missing optional dependencies produce an actionable error only when selected.
8. Provider failures never become implicit negative decisions.
9. Common result serialization does not leak provider-specific objects.
10. CLI, GUI, Web, and A2A resolve the same shared setting.
11. Startup output never exposes credentials.
12. Adapter tests do not require network/model downloads in the normal CI path.

## Acceptance criteria

The architecture is considered correctly integrated when a stock UAG invocation
without new configuration behaves exactly as before, while an explicitly
selected Jev or Laya provider can be initialized through the common decision API
without altering the existing LLM-provider registry.
