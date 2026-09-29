# Microsoft Foundry Local

UAG treats Foundry Local as a normal local OpenAI-compatible Chat Completions endpoint.

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

UAG does not fall back to a different llmcapa provider when that lookup misses. Foundry Local is currently routed through the existing OpenAI-compatible Chat Completions transport; direct Foundry SDK integration can be added separately later if needed.
