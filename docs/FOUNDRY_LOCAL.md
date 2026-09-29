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

Direct Foundry SDK integration can be added separately later if needed.
