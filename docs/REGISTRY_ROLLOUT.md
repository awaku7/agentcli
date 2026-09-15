# Provider Runtime Registry Rollout

The provider runtime registry is enabled by default for the migrated OpenAI
and Azure round paths. It covers streaming and non-streaming Chat Completions,
Responses, tool calls, structured output, and multimodal inputs. Inception
uses its dedicated event adapter for Chat Completions streaming and is enabled
by default independently of the OpenAI/Azure route.

The registry also projects the existing OpenAI/Azure generation options:

- reasoning effort, including one budgeted quality retry for
  `UAGENT_REASONING=auto`;
- `UAGENT_VERBOSITY` for Responses;
- clamped `UAGENT_MAX_TOKENS` and Chat `UAGENT_TOP_P`;
- OpenAI-only `UAGENT_OPENAI_FAST_MODE` (`service_tier=fast`);
- Responses `context_management` compaction and explicit `tool_choice=auto`.

Use these opt-out switches to return a specific path to the legacy executor:

| Variable | Set to `0` / `off` to disable |
|---|---|
| `UAGENT_PROVIDER_REGISTRY` | All registry routing for OpenAI and Azure |
| `UAGENT_PROVIDER_REGISTRY_RESPONSES` | Responses API registry routing only |
| `UAGENT_PROVIDER_REGISTRY_TOOLS` | Tool-call registry routing only |
| `UAGENT_PROVIDER_REGISTRY_INCEPTION` | Inception event-adapter routing only |

Providers that do not yet have a registered runtime continue to use their
legacy path. `UAGENT_REASONING=auto` is handled by the registry with one
budgeted quality retry when its initial effort produces an unusable answer.

For the current integration state and the remaining work, see
[UAG Registry Handoff](./uag-registry-handoff.md).
