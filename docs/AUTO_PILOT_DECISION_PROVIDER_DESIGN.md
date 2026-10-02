# Auto-Pilot Decision Provider Reviewer Design

## Status

Implemented design for using UAG's opt-in Decision Provider layer as the
completion reviewer for `:auto` / auto-pilot.

This document is intentionally narrower than the general Decision Provider
architecture. The first concrete runtime decision site is now implemented:
when a Decision Provider is explicitly enabled, auto-pilot uses a typed
`COMPLETE` / `CONTINUE` decision before falling back to the existing LLM
reviewer on provider failure or invalid output.

The general Decision Provider architecture is proposed separately in
`docs/DECISION_PROVIDER_DESIGN.md` (PR #120 at the time this document was
written).

## Why auto-pilot is the first decision site

UAG already contains a decision-only LLM call in auto-pilot.

After each main auto-pilot work round, UAG asks a reviewer whether the goal is:

- `COMPLETE`, or
- `CONTINUE`.

The reviewer runs in a separate judgment context and does not execute tools. In
other words, the current implementation already uses a normal generative LLM as
a decision model.

That makes auto-pilot completion review a better first integration target than
inventing a new routing decision such as tool selection or model routing.

The expected benefit is straightforward:

```text
Current auto-pilot

main LLM work
    -> reviewer LLM judgment
    -> main LLM work
    -> reviewer LLM judgment
    -> ...

With a Decision Provider

main LLM work
    -> Laya / TypeSafe-Jev decision
    -> main LLM work
    -> Laya / TypeSafe-Jev decision
    -> ...
```

The main LLM remains responsible for reasoning, generation, tool use, and task
execution. The Decision Provider is responsible only for the bounded completion
judgment.

## Goals

The first integration should:

1. Use the configured Decision Provider for auto-pilot `COMPLETE` / `CONTINUE`
   judgment.
2. Preserve current behavior exactly when the Decision Provider is `none`.
3. Preserve sentinel mode and completion-regex behavior unchanged.
4. Fall back to the existing LLM reviewer if the Decision Provider cannot make a
   valid judgment.
5. Keep `UAGENT_AP_*` reviewer configuration useful as the fallback LLM reviewer.
6. Avoid using Decision Provider confidence as an uncalibrated universal safety
   threshold.
7. Avoid exposing raw secrets or unbounded conversation/tool output to the
   Decision Provider.
8. Keep enterprise policy, `absconfirm`, human confirmation, round limits, and
   interrupt behavior outside Decision Provider authority.
9. Work through the shared auto-pilot loop so CLI, GUI, Web, and other callers
   receive identical semantics.
10. Provide enough structured logging to compare decision providers against the
    existing LLM reviewer.

## Non-goals

This first use case does not:

- route tools,
- select the main LLM provider or model,
- decide which sub-agent should run,
- generate tool arguments,
- replace normal LLM reasoning,
- replace enterprise policy,
- bypass `absconfirm`,
- bypass explicit human confirmation,
- change sentinel mode,
- change completion-regex behavior,
- make a Decision Provider mandatory for auto-pilot,
- trust `confidence` as a universal correctness or risk score,
- require the Decision Provider to generate free-text reviewer feedback.

Those can be evaluated as later decision sites only after the first integration
is measured.

## Current implementation

The current implementation lives primarily in:

```text
src/uagent/util_cmd_auto.py
```

Important symbols are:

```text
_handle_cmd_auto()
_run_auto_pilot_loop()
_ask_reviewer_judgment()
_build_judgment_messages()
_parse_reviewer_judgment()
_sentinel_judgment()
_completion_regex_matches()
```

The implemented normal path is:

```text
initial goal
    -> main LLM
    -> _run_auto_pilot_loop()
         -> completion regex check
         -> sentinel judgment, if enabled
         -> Decision Provider, if explicitly enabled
              -> valid COMPLETE / CONTINUE: use result
              -> unavailable / invalid / error: LLM reviewer fallback
         -> otherwise _ask_reviewer_judgment()
              -> run_llm_rounds(judgment_mode=True)
         -> COMPLETE: stop
         -> CONTINUE: append follow-up prompt
         -> main LLM
         -> repeat
```

The fallback reviewer can use the main LLM provider or a separately configured
reviewer provider through `UAGENT_AP_*` environment variables.

Current reviewer failures are conservative: only an explicit `COMPLETE` stops
the reviewer path; failure or ambiguous output becomes `CONTINUE`.

## Proposed flow

The Decision Provider is inserted only at the existing reviewer decision point.

```text
_run_auto_pilot_loop()
    |
    +-- explicit stop / inactive auto-pilot
    |
    +-- completion regex matched
    |      -> COMPLETE
    |
    +-- UAGENT_AUTO_SENTINEL=1
    |      -> existing sentinel judgment
    |
    +-- decision provider != none
    |      -> decision-provider auto review
    |           |
    |           +-- valid COMPLETE / CONTINUE
    |           |      -> use decision
    |           |
    |           +-- unavailable / error / invalid result
    |                  -> existing LLM reviewer fallback
    |
    +-- decision provider == none
           -> existing LLM reviewer
```

This precedence is important. Explicit deterministic mechanisms remain ahead of
probabilistic review:

1. user/host stop request,
2. completion regex,
3. sentinel mode,
4. Decision Provider,
5. legacy LLM reviewer fallback.

## Configuration semantics

The Decision Provider configuration is defined by the general Decision Provider
design.

Examples:

```text
UAGENT_DECISION_PROVIDER=none
```

```text
UAGENT_DECISION_PROVIDER=typesafe
UAGENT_DECISION_TYPESAFE_DEPNAME=jev-latest
UAGENT_DECISION_TYPESAFE_BASE_URL=https://api.typesafe.ai
UAGENT_DECISION_TYPESAFE_API_KEY=...
```

```text
UAGENT_DECISION_PROVIDER=laya
UAGENT_DECISION_LAYA_DEPNAME=laya-multilingual
UAGENT_DECISION_LAYA_DEVICE=auto
```

### `none`

`none` preserves current auto-pilot behavior exactly:

```text
main LLM work
    -> current LLM reviewer
```

No Decision Provider module, client, model, endpoint, or model asset should be
initialized because auto-pilot is running.

### `typesafe` / `laya`

When a Decision Provider is explicitly selected, the first authoritative runtime
site is auto-pilot review:

```text
main LLM work
    -> selected Decision Provider
```

No extra auto-pilot-specific provider selector is required for the initial
implementation. Selecting a non-`none` Decision Provider is already an explicit
opt-in.

A future per-site enable/disable mechanism may be added if UAG gains several
independent Decision Provider sites, but it should not be required for the first
site.

## Relationship with `UAGENT_AP_*`

`UAGENT_AP_*` currently configures a separate LLM reviewer.

That configuration should remain valid and should become the fallback reviewer
configuration when a Decision Provider is active.

Example:

```text
UAGENT_DECISION_PROVIDER=laya
UAGENT_DECISION_LAYA_DEPNAME=laya-multilingual

UAGENT_AP_PROVIDER=openai
UAGENT_AP_DEPNAME=gpt-5-mini
```

Runtime behavior:

```text
Laya judgment succeeds
    -> use Laya result

Laya judgment fails / is invalid
    -> use configured UAGENT_AP_* LLM reviewer

fallback LLM reviewer also fails
    -> preserve current conservative CONTINUE behavior
```

If `UAGENT_AP_*` is not configured, fallback remains the current main-provider
reviewer behavior.

This preserves backward compatibility while avoiding a new fallback subsystem.

## Decision request

Auto-pilot review needs only one typed decision question.

Conceptually:

```python
DecisionQuestion(
    id="auto_pilot_goal_status",
    kind="choice",
    instruction=(
        "Determine whether the auto-pilot goal is fully complete. "
        "Choose COMPLETE only when the required work is finished and no "
        "material work remains. Choose CONTINUE when additional work is "
        "required or completion is uncertain."
    ),
    choices=("COMPLETE", "CONTINUE"),
)
```

The decision is deliberately binary because that matches the current auto-pilot
state transition.

A provider used for this site must support Decision Provider `choice` semantics.
`llmcapa` can be used to validate that the configured decision model exposes
`decision_output` and includes `choice` in its supported question kinds.

If the selected model does not support the required decision shape, UAG should
warn and use the existing LLM reviewer rather than failing auto-pilot startup.

## Decision state

The Decision Provider must not receive an unbounded raw transcript.

The state should be derived from the same bounded information the current
reviewer uses, with a structured representation where practical.

Recommended state shape:

```python
{
    "goal": "...",
    "round": 2,
    "max_rounds": 10,
    "recent_conversation": [
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."},
    ],
    "recent_tool_results": [
        {
            "tool": "...",
            "status": "success|failed",
            "summary": "...",
        }
    ],
}
```

Recommended bounds should initially mirror the existing reviewer behavior:

- at most 6 recent user/assistant messages,
- bounded per-message text,
- at most 4 recent tool results,
- bounded tool-result summaries,
- existing secret masking before state construction.

The implementation should reuse or refactor the existing masking and summarizing
logic instead of maintaining a second incompatible reviewer-history policy.

## Result mapping

The runtime only needs:

```text
COMPLETE
CONTINUE
```

Mapping:

```text
decision answer == COMPLETE
    -> judgment = COMPLETE

decision answer == CONTINUE
    -> judgment = CONTINUE

missing / malformed / unsupported answer
    -> Decision Provider failure
    -> legacy LLM reviewer fallback
```

The Decision Provider result may also contain:

```text
confidence
probabilities
latency
provider/model metadata
```

These values are useful for observability and evaluation but are not required to
control the first implementation.

## Reviewer feedback

The current LLM reviewer can return:

```text
CONTINUE: <reason>
```

and UAG feeds that reviewer note into the next continuation prompt.

A typed Decision Provider is not required to generate free text. Therefore the
initial Decision Provider path should not invent or synthesize feedback.

For a Decision Provider `CONTINUE` result:

```text
feedback = ""
```

The normal continuation prompt remains valid:

```text
Continue. Goal: <goal>
```

This is an intentional trade-off for the first integration.

Later, if measurements show that missing reviewer feedback materially increases
round count or reduces completion quality, UAG can evaluate a second typed
question such as a coarse missing-work category. Free-text generation should not
be added to the Decision Provider contract merely to reproduce the old reviewer
message.

## Failure behavior

Decision Provider failure must never be interpreted as a negative decision or as
`COMPLETE`.

Failure includes:

- provider initialization failure,
- endpoint/network error,
- local Laya runtime/model-load error,
- timeout,
- unsupported decision capability,
- malformed provider response,
- missing answer,
- answer outside `COMPLETE` / `CONTINUE`,
- adapter exception.

Required behavior:

```text
Decision Provider failure
    -> existing LLM reviewer
    -> if LLM reviewer fails, current conservative CONTINUE behavior
```

This differs intentionally from simply mapping Decision Provider failure to
`CONTINUE`: falling back to the established reviewer preserves current UAG
semantics and gives the user the best chance of a correct completion judgment.

The fallback should be visible in logs/telemetry.

## Confidence handling

The first implementation must not contain logic such as:

```text
confidence >= 0.8 -> trust COMPLETE
```

unless that threshold has been validated for the specific model and UAG task
distribution.

This is especially important for Laya because its bundled `llmcapa` capability
records intentionally report:

```text
calibrated_confidence = false
```

Provider confidence and probabilities should initially be logged as diagnostic
data only.

A later calibrated policy may choose to require stronger evidence before
accepting `COMPLETE`, but that must be based on measured UAG data rather than a
hard-coded universal threshold.

## Safety and authority boundaries

The auto-pilot Decision Provider decides only whether the current goal appears
complete enough to stop the auto-pilot loop.

It must not override:

- `absconfirm`,
- enterprise policy,
- tool allow/deny rules,
- human confirmation requirements,
- interrupt/stop requests,
- max-round limits,
- completion regex,
- sentinel protocol,
- authentication/authorization,
- permission checks.

In particular, a `COMPLETE` decision stops further autonomous work. It never
grants permission to perform a tool action.

Likewise, a `CONTINUE` decision does not authorize a tool. The subsequent main
LLM round remains subject to all existing UAG policy and confirmation mechanisms.

## Sentinel interaction

Sentinel mode remains an explicit alternative completion protocol.

When:

```text
UAGENT_AUTO_SENTINEL=1
```

UAG should continue to use the target model's `<AUTO_COMPLETE>` /
`<AUTO_CONTINUE>` marker and should not invoke either the Decision Provider or
the LLM reviewer.

This preserves the current single-model, no-extra-review-call mode.

## Completion-regex interaction

A configured completion regex is deterministic and already runs before the
reviewer call.

That precedence should remain unchanged:

```text
completion regex matched
    -> stop
    -> do not call Decision Provider
```

## Round-limit interaction

Round limits remain host-controlled.

The Decision Provider does not decide whether max-round limits are ignored or
extended.

Current behavior remains:

```text
review says CONTINUE
    -> increment round
    -> max-round check
    -> either stop or run next main round
```

## Suggested implementation structure

The auto-pilot module should depend on the common Decision Provider abstraction,
not on TypeSafe or Laya directly.

Conceptual helper:

```python
def _ask_auto_pilot_decision(
    messages: list[dict[str, Any]],
    core: Any,
    *,
    decision_provider: DecisionProvider,
) -> tuple[str, str] | None:
    """Return (judgment, feedback), or None to request legacy fallback."""
```

Possible flow inside `_run_auto_pilot_loop()`:

```python
if _sentinel_mode_enabled():
    judgment = _sentinel_judgment(messages)
    feedback = ""
else:
    result = None
    if decision_provider.is_enabled:
        result = _ask_auto_pilot_decision(
            messages,
            core,
            decision_provider=decision_provider,
        )

    if result is None:
        judgment, feedback = _ask_reviewer_judgment(
            _judge_provider,
            _judge_client,
            _judge_depname,
            messages,
            core,
            make_client_fn=make_client_fn,
        )
    else:
        judgment, feedback = result
```

The exact dependency-injection mechanism should follow the common Decision
Provider infrastructure introduced by the implementation PR. The auto-pilot
module should not read provider-specific API keys or initialize provider-specific
clients itself.

## Lazy initialization

The strict opt-in rule still applies.

When the effective Decision Provider is `none`:

- no Laya import,
- no Laya model load,
- no model asset download,
- no TypeSafe client creation,
- no TypeSafe endpoint probe,
- no Decision Provider latency.

If possible, even an enabled Decision Provider should be initialized lazily on
its first real decision call rather than merely because UAG started.

This matters for Laya because local model initialization may be significantly
more expensive than the decision itself.

## Observability

The first implementation should make the source of the auto-pilot judgment
obvious.

Suggested human-readable output:

```text
[AUTO:judge:decision] provider=laya model=laya-multilingual judgment=CONTINUE
```

and on fallback:

```text
[AUTO:judge:decision] provider=laya failed; falling back to LLM reviewer
```

Structured telemetry/log fields should include, where available:

```text
decision.site = auto_pilot_review
decision.provider
decision.model
decision.answer
decision.confidence
decision.latency_ms
decision.fallback
decision.error_type
auto_pilot.round
```

Raw prompt/state content should not be emitted into telemetry by default.

## Evaluation and rollout

The first use case is especially suitable for measured comparison because the
existing LLM reviewer provides a natural baseline.

Useful metrics:

- Decision Provider latency,
- legacy reviewer latency,
- LLM reviewer calls avoided,
- provider failure/fallback rate,
- number of auto-pilot follow-up rounds,
- rate of `COMPLETE` vs `CONTINUE`,
- premature-completion reports,
- max-round exhaustion rate,
- total main-LLM calls per auto-pilot task.

The most important error is a false `COMPLETE`, because it stops work early.
A false `CONTINUE` usually costs an extra round but is less likely to leave the
user's goal unfinished.

### Optional shadow evaluation

If the common Decision Provider layer gains shadow mode, auto-pilot should be the
first recommended evaluation site.

Shadow behavior:

```text
Decision Provider judgment
    -> log only

legacy LLM reviewer judgment
    -> authoritative runtime result
```

Agreement and disagreement can then be measured before the decision model is
made authoritative for a given deployment.

Shadow execution must remain explicit and must not cause Laya/TypeSafe to load or
run when no shadow provider is configured.

## Test matrix

The implementation PR should cover at least the following cases.

### Backward compatibility

1. `UAGENT_DECISION_PROVIDER=none` uses the existing LLM reviewer.
2. No decision-provider package/client/model is initialized in `none` mode.
3. Existing `UAGENT_AP_*` override behavior remains unchanged in `none` mode.

### Decision Provider result

4. Decision Provider returns `COMPLETE` -> auto-pilot stops.
5. Decision Provider returns `CONTINUE` -> auto-pilot proceeds to the next main
   round.
6. `CONTINUE` from a typed provider uses empty reviewer feedback and still
   produces a valid continuation prompt.

### Fallback

7. Decision Provider raises -> existing LLM reviewer is called.
8. Decision Provider returns malformed answer -> existing LLM reviewer is called.
9. Configured decision model lacks `choice` capability -> existing LLM reviewer
   is called with a warning.
10. Decision Provider fails and fallback LLM reviewer also fails -> preserve
    current conservative `CONTINUE` semantics.

### Existing completion mechanisms

11. Completion regex match -> no Decision Provider call.
12. Sentinel mode -> no Decision Provider call and no LLM reviewer call.
13. User/host stop -> no additional decision call after stop is observed.
14. Max rounds remain enforced after `CONTINUE`.

### Policy boundaries

15. Decision Provider cannot suppress `absconfirm`.
16. Decision Provider cannot change enterprise policy result.
17. Decision Provider `CONTINUE` does not itself authorize any tool call.

### State handling

18. Decision state is bounded.
19. Existing secret masking is applied before sending state.
20. Tool results use bounded summaries rather than raw unbounded output.

### Provider-specific behavior

21. TypeSafe/Jev adapter can answer the common `choice` request.
22. Laya adapter can answer the same common `choice` request.
23. Laya remains an optional/lazy dependency.
24. Laya confidence is observable but does not become an implicit completion
    threshold.

## Implementation sequence

Recommended PR sequence:

1. Merge the general Decision Provider architecture and common opt-in
   infrastructure.
2. Add TypeSafe and/or Laya adapters behind the common interface.
3. Add the auto-pilot review decision site defined in this document.
4. Add observability and comparison metrics.
5. Optionally add shadow evaluation.
6. Only after measurement, consider additional Decision Provider sites such as
   retry classification, sub-agent selection, or model/tool routing.

## Decision

The first UAG runtime use of a dedicated Decision Provider should be auto-pilot
completion review.

The scope is intentionally narrow:

```text
Question:
    Is the current auto-pilot goal COMPLETE or should it CONTINUE?

Decision Provider:
    TypeSafe/Jev or Laya

Fallback:
    existing LLM reviewer

Default:
    none -> existing behavior unchanged
```

This gives UAG a concrete, measurable Decision Provider use case without
inventing a new control plane or changing the authority of the main LLM, tools,
policies, or user confirmations.
