# vLLM provider

UAG can use a running vLLM OpenAI-compatible server through **Responses API** or **Chat Completions**. In automatic mode, UAG selects Responses only when llmcapa confirms support for the configured model; set `UAGENT_RESPONSES=0` to force Chat Completions. UAG does not start vLLM, download models, or manage the server process.

## Configure UAG

```dotenv
UAGENT_PROVIDER=vllm
UAGENT_VLLM_BASE_URL=http://localhost:8000/v1
UAGENT_VLLM_DEPNAME=local-model
# Optional: set this only if the vLLM server is configured with --api-key.
# UAGENT_VLLM_API_KEY=change-me
# Optional; default is 120 seconds.
# UAGENT_VLLM_TIMEOUT_SEC=120
```

`UAGENT_VLLM_DEPNAME` is required and must exactly match a model ID returned by the server's `/v1/models` endpoint. If you use `--served-model-name`, configure the same value here. The default base URL is `http://localhost:8000/v1`. An API key is optional; without one UAG sends the OpenAI-compatible placeholder key `dummy`. UAG prefers `UAGENT_VLLM_API_KEY` and also accepts the standard `VLLM_API_KEY` environment variable.

UAG reads the matching model's `max_model_len` from `/v1/models` as the live context limit, ahead of the catalog value. If the server instead reports separate `max_input_tokens` and `max_output_tokens`, UAG uses the input limit for context budgeting and clamps generation to the output limit. If the endpoint is unreachable or these fields are absent, UAG falls back to llmcapa. The metadata lookup has a five-second timeout by default; change it with `UAGENT_VLLM_PROPS_TIMEOUT_SEC`.

Responses API continuation with `previous_response_id` is tested against the running server on the first real follow-up. If the server accepts it, UAG uses it; if rejected (for example, because vLLM's Responses store is disabled), UAG retries with full conversation history and remembers that result until the UAG process restarts. vLLM's store can be enabled with `VLLM_ENABLE_RESPONSES_API_STORE=1`; vLLM keeps stored responses in memory, so consider that tradeoff before enabling it. Vision remains unavailable through this provider adapter. Structured-output routing is gated by llmcapa model metadata and still requires support in the vLLM server/model. Tool calls work when the served model supports them and the vLLM server is started with a compatible tool-call parser, for example `--enable-auto-tool-choice --tool-call-parser <parser-for-model>`.

## Reasoning effort safety

`UAGENT_REASONING` controls reasoning effort, but vLLM models differ in the values they actually accept. UAG sends `reasoning_effort` (Chat Completions) or `reasoning.effort` (Responses) **only when llmcapa's vLLM-specific model row explicitly advertises `supports_reasoning_effort=true` and includes the requested value in `reasoning_effort_values`**. Values recorded for other providers or generic llmcapa defaults do not establish vLLM compatibility.

If an explicitly configured value cannot be verified, UAG omits the request parameter and emits a runtime warning rather than sending a potentially unsupported value. This includes `UAGENT_REASONING=off`: UAG sends `none` only when that value is verified, so otherwise the server/model's default reasoning behavior remains in effect. Automatic effort selection (`auto`) silently falls back to model defaults when not verified.

Numerical `thinking_token_budget` is a separate vLLM feature and is not inferred from an effort level. Support for forwarding that budget is tracked in [the implementation plan](plans/VLLM_REASONING_BUDGET.md).

## Start vLLM

Start the server separately, for example:

```sh
vllm serve <model> --host 127.0.0.1 --port 8000 --served-model-name local-model
```

Then set `UAGENT_VLLM_DEPNAME=local-model`. If you expose the server beyond loopback, protect it with an API key and appropriate network controls; the UAG API key setting only provides client authentication and does not secure the server's network exposure by itself.
