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

Model capability metadata comes from llmcapa using the exact pair:

```python
llmcapa.get(model_name, provider="foundry-local")
```

The original model name is preserved exactly, including `/`. If that lookup misses, UAG does not retry a bare suffix, prefix search, unscoped lookup, or a different llmcapa provider.

UAG provides its existing OpenAI-compatible Chat Completions and Responses transports. The exact llmcapa Capability decides which model-dependent features may be used. In particular, Responses requires `responses_api=True`, including when `UAGENT_RESPONSES=1` is set, and function calling/tools require positive function-calling evidence. False or unknown capability evidence keeps those features disabled rather than guessing.

Direct Foundry SDK integration can be added separately later if needed.
