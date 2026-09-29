# Microsoft Foundry Local

UAG treats Foundry Local as a normal local OpenAI-compatible endpoint.

Configure:

```text
UAGENT_PROVIDER=foundry_local
UAGENT_FOUNDRY_LOCAL_BASE_URL=http://localhost:<port>/v1
UAGENT_FOUNDRY_LOCAL_DEPNAME=phi-4-mini   # optional
UAGENT_FOUNDRY_LOCAL_API_KEY=...          # optional
```

The base URL must be loopback (`localhost`, `127.0.0.1`, `::1`, etc.). UAG does not start Foundry Local, download or load models, probe localhost, or use the Foundry Local SDK in this integration.

For llmcapa, UAG maps provider name `foundry_local` to `foundry-local` and otherwise uses the existing llmcapa lookup behavior shared with other providers.

UAG uses the existing OpenAI-compatible transports and capability handling. No Foundry-specific Responses, tools, model-search, or capability-routing rules are added.

## Opt-in diagnostics

For live Foundry Local troubleshooting, enable provider-specific diagnostics on stderr:

```text
UAGENT_DEBUG_FOUNDRY_LOCAL=1
```

Diagnostics are disabled by default. They never print prompt text, response text, or tool arguments. Instead, they record metadata derived from the final HTTP payload actually sent to localhost:

- model / transport / streaming
- message count
- tool count and tool names
- latest user-content character count and SHA-256
- SHA-256 of the full messages/input value
- SHA-256 of the final HTTP request body
- SHA-256 of non-streaming responses or Registry streamed response text

Comparing `last_user_sha256` and `request_sha256` for two different inputs helps distinguish a UAG-side stale/fixed input from a case where distinct payloads reach Foundry Local.

The existing `UAGENT_DEBUG_OPENAI_RUNTIME=1` switch continues to enable Foundry Local diagnostics for backward compatibility. Prefer `UAGENT_DEBUG_FOUNDRY_LOCAL=1` when only this local provider needs investigation.

Direct Foundry SDK integration can be added separately later if needed.
