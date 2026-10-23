# vLLM provider

UAG can use a running vLLM OpenAI-compatible server through **Chat Completions**. UAG does not start vLLM, download models, or manage the server process.

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

`UAGENT_RESPONSES=1` does not select the Responses API for vLLM; this integration deliberately stays on Chat Completions. Vision and native structured-output capabilities are not advertised by this provider adapter. Tool calls work when the served model supports them and the vLLM server is started with a compatible tool-call parser, for example `--enable-auto-tool-choice --tool-call-parser <parser-for-model>`.

## Start vLLM

Start the server separately, for example:

```sh
vllm serve <model> --host 127.0.0.1 --port 8000 --served-model-name local-model
```

Then set `UAGENT_VLLM_DEPNAME=local-model`. If you expose the server beyond loopback, protect it with an API key and appropriate network controls; the UAG API key setting only provides client authentication and does not secure the server's network exposure by itself.
