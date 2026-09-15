# Provider Runtime Registry Rollout

The provider runtime registry is enabled by default for the migrated OpenAI
and Azure round paths. It covers streaming and non-streaming Chat Completions,
Responses, tool calls, structured output, and multimodal inputs.

Use these opt-out switches to return a specific path to the legacy executor:

| Variable | Set to `0` / `off` to disable |
|---|---|
| `UAGENT_PROVIDER_REGISTRY` | All registry routing for OpenAI and Azure |
| `UAGENT_PROVIDER_REGISTRY_RESPONSES` | Responses API registry routing only |
| `UAGENT_PROVIDER_REGISTRY_TOOLS` | Tool-call registry routing only |

Providers that do not yet have a registered runtime continue to use their
legacy path. `UAGENT_REASONING=auto` is handled by the registry with one
budgeted quality retry when its initial effort produces an unusable answer.
