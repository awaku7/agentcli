# OpenTelemetry Phase 4C provider SDK diagnostics

Phase 4C is optional, metadata-only, and OFF by default. It is active only when
core OpenTelemetry is enabled and the resolved provider selector contains the
logical provider being called.

Supported selection is exact:

```text
--otel-provider-instrumentation openai
--otel-provider-instrumentation claude
--otel-provider-instrumentation openai,claude
UAGENT_OTEL_PROVIDER_INSTRUMENTATION=openai,claude
```

The closed selector vocabulary is `openai` and `claude`. `claude` selects the
Anthropic SDK path; `anthropic` is not an alias. Unknown tokens do not enable a
provider.

For a selected provider call, UAG creates at most one UAG-controlled child span
under the active canonical `chat` span:

```text
span name: provider_sdk
attribute: uag.provider.id = openai | claude
status: UNSET | OK | ERROR
```

No other provider-child attribute, event, link, or status description is emitted.
In particular, Phase 4C does not export model names, URLs, request/response IDs,
prompt/response/reasoning/tool bodies, headers, credentials, exception text or
stack traces, resource/instrumentation attributes, or vendor metadata.

The implementation is call-scoped at the existing UAG provider boundaries. It
does not install generic global provider or HTTP auto-instrumentation. Registry-
backed OpenAI rounds open the child only around `ProviderRuntime.run()`. Legacy
OpenAI and Claude paths open the child only around their normalized provider call.
Retries or streaming inside one logical round remain inside that single child, so
one canonical `chat` span cannot acquire duplicate provider diagnostic children.

Each successfully created canonical `chat` boundary creates one shared, one-shot
diagnostic state bound to the same observability backend. A `NOOP_SPAN` parent
never creates that state. The first selected child-creation attempt consumes the
claim even if child creation itself fails. Copied execution contexts share the same
locked state object, and scope exit closes that shared state, so parallel,
duplicated, or late copied-context calls cannot create a second or root provider
child after the canonical `chat` boundary has ended.

Provider-call exceptions mark the child `ERROR` but are deliberately not passed
through the child span context manager as exception payloads. The exception still
propagates normally to the existing canonical `chat` boundary, preserving Agent
behavior and existing parent-span failure handling. A normal provider result is
`OK`; an explicit cancelled terminal result is `UNSET`; normalized failed,
timed-out, or interrupted terminal results are `ERROR`.

Observability setup, child-span creation, status updates, and close failures are
best-effort. They never change the model request, response, retry behavior, tool
execution, or Agent result.

The normative source of truth remains
`docs/UAG_OPENTELEMETRY_PHASE4_CONTRACT.md`. Regression coverage lives in
`tests/test_observability_phase4_provider_sdk.py`.
