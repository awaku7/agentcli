# Environment Variables and Configuration

`uag` uses environment variables to manage LLM provider credentials and control agent behavior. These variables are typically stored in a `.env` file in your current working directory.

## Setup Wizard

The easiest way to configure your environment is by running the interactive setup wizard:

```bash
uag_setup
# or
python -m uagent.setup_cli
```

### Automatic Setup

If required environment variables (such as provider settings) are missing when you start `uag`, the system will **automatically launch the setup wizard**. Once completed, your settings will be saved to `.env`, and the agent will be ready to use.

______________________________________________________________________

### 1. Provider selection

- `UAGENT_PROVIDER` (required): LLM provider name.
  Supported values: `azure`, `openai`, `bedrock`, `openrouter`, `ollama`, `gemini`, `vertexai`, `claude`, `grok`, `nvidia`, `deepseek`, `zai`, `alibaba`, `moonshot`, `mimo`, `lmstudio`, `minimax`, `hf`, `novita`, `sakana`, `sakura`.
- `UAGENT_USE_TOOL`: Set to `0`, `false`, `no`, or `off` to disable tool sending to LLM.

#### Azure OpenAI

Required if `UAGENT_PROVIDER=azure`:

- `UAGENT_AZURE_BASE_URL` (required)
- `UAGENT_AZURE_DEPNAME` (required): deployment / model name
- `UAGENT_AZURE_API_KEY` (required)
- `UAGENT_AZURE_API_VERSION` (required, e.g. `2025-03-01-preview`)

#### OpenAI

Required if `UAGENT_PROVIDER=openai`:

- `UAGENT_OPENAI_API_KEY` (required)
- `UAGENT_OPENAI_BASE_URL` (optional, default: `https://api.openai.com/v1`)
- `UAGENT_OPENAI_DEPNAME` (optional, default: `gpt-5.4-nano`)

##### PLaMo (Preferred Networks)

PLaMo provides an OpenAI-compatible Chat Completions API, so it can be used with the existing `openai` provider without adding a separate provider key.

```bat
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=<PLaMo API key>
set UAGENT_OPENAI_BASE_URL=https://api.platform.preferredai.jp/v1
set UAGENT_OPENAI_DEPNAME=plamo-3.0-prime
set UAGENT_RESPONSES=0
```

PLaMo exposes `/v1/chat/completions`, not the Responses API. Keep `UAGENT_RESPONSES=0` so requests use the Chat Completions path. Tool calling and streaming use the existing OpenAI-compatible implementation.

#### Bedrock

Required if `UAGENT_PROVIDER=bedrock`:

- `UAGENT_BEDROCK_DEPNAME` (required, e.g. `us.anthropic.claude-sonnet-4-20250514`)
- `UAGENT_BEDROCK_ACCESS_KEY` (required)
- `UAGENT_BEDROCK_SECRET_KEY` (required)
- `UAGENT_BEDROCK_REGION` (optional, default: `us-west-2`)

#### OpenRouter

Required if `UAGENT_PROVIDER=openrouter`:

- `UAGENT_OPENROUTER_API_KEY` (required)
- `UAGENT_OPENROUTER_DEPNAME` (optional, default: `gpt-5.4-nano`)

#### Ollama

Required if `UAGENT_PROVIDER=ollama`:

- `UAGENT_OLLAMA_DEPNAME` (required)
- `UAGENT_OLLAMA_BASE_URL` (optional, default: `http://localhost:11434/v1`)

#### Google Gemini

Required if `UAGENT_PROVIDER=gemini`:

- `UAGENT_GEMINI_API_KEY` (required)
- `UAGENT_GEMINI_DEPNAME` (optional, default: `gemini-2.5-pro-exp-03-25`)

#### Google Vertex AI

Required if `UAGENT_PROVIDER=vertexai`:

- `UAGENT_VERTEXAI_PROJECT` (required)
- `UAGENT_VERTEXAI_LOCATION` (required, e.g. `us-central1`)
- `UAGENT_VERTEXAI_DEPNAME` (required)
- `UAGENT_VERTEXAI_CREDENTIALS` (required): Path to Google Cloud service account JSON.

#### Claude (Anthropic)

Required if `UAGENT_PROVIDER=claude`:

- `UAGENT_CLAUDE_API_KEY` (required)
- `UAGENT_CLAUDE_DEPNAME` (optional, default: `claude-sonnet-4-20250514`)

#### Grok

Required if `UAGENT_PROVIDER=grok`:

- `UAGENT_GROK_API_KEY` (required)
- `UAGENT_GROK_DEPNAME` (optional)

#### NVIDIA

Required if `UAGENT_PROVIDER=nvidia`:

- `UAGENT_NVIDIA_API_KEY` (required)
- `UAGENT_NVIDIA_DEPNAME` (optional)

#### DeepSeek

Required if `UAGENT_PROVIDER=deepseek`:

- `UAGENT_DEEPSEEK_API_KEY` (required)
- `UAGENT_DEEPSEEK_BASE_URL` (optional, default: `https://api.deepseek.com`)
- `UAGENT_DEEPSEEK_DEPNAME` (optional, default: `deepseek-v4-flash`)

#### Z.AI (Zhipu AI)

Required if `UAGENT_PROVIDER=zai`:

- `UAGENT_ZAI_API_KEY` (required): Zhipu AI API key.
- `UAGENT_ZAI_BASE_URL` (optional, default: `https://api.z.ai/api/paas/v4/`).
- `UAGENT_ZAI_DEPNAME` (optional, default: `glm-5.2`).

#### Alibaba Cloud (Qwen)

Required if `UAGENT_PROVIDER=alibaba`:

- `UAGENT_ALIBABA_API_KEY` (required)
- `UAGENT_ALIBABA_BASE_URL` (optional)
- `UAGENT_ALIBABA_DEPNAME` (optional, default: `qwen3.5-plus`)

#### Moonshot (KIMI)

Required if `UAGENT_PROVIDER=moonshot`:

- `UAGENT_MOONSHOT_API_KEY` (required)
- `UAGENT_MOONSHOT_DEPNAME` (optional, default: `kimi-k2`)

#### Xiaomi MiMo

Required if `UAGENT_PROVIDER=mimo`:

- `UAGENT_MIMO_API_KEY` (required)
- `UAGENT_MIMO_BASE_URL` (optional)
- `UAGENT_MIMO_DEPNAME` (optional, default: `mimo-v2.5-pro`)

#### LM Studio

Required if `UAGENT_PROVIDER=lmstudio`:

- `UAGENT_LMSTUDIO_BASE_URL` (optional, default: `http://localhost:1234/v1`)
- `UAGENT_LMSTUDIO_DEPNAME` (optional, default: `local-model`)

> \* **Note on AWS Bedrock**: The current `uag` implementation expects an OpenAI-compatible endpoint for Bedrock.

#### Google Cloud Settings

Used by Gemini / Vertex AI features that need Google Cloud access.

- `UAGENT_GOOGLE_CREDENTIALS`: Path to Google Cloud service account JSON or JSON string (optional).
- `UAGENT_GOOGLE_LOCATION`: Google Cloud location/region (e.g., `asia-northeast1`).

#### MiniMax

Required if `UAGENT_PROVIDER=minimax`:

- `UAGENT_MINIMAX_API_KEY` (required): MiniMax API key.
- `UAGENT_MINIMAX_BASE_URL` (optional, default: `https://api.minimax.io`).
- `UAGENT_MINIMAX_DEPNAME` (optional, default: `MiniMax-M3`).

#### HuggingFace (Inference API / Serverless)

Required if `UAGENT_PROVIDER=hf`:

- `UAGENT_HF_API_KEY` (required): Your HuggingFace API token (HF_TOKEN).
- `UAGENT_HF_BASE_URL` (optional, default: `https://router.huggingface.co/v1`).
- `UAGENT_HF_DEPNAME` (optional, default: `openai/gpt-oss-120b`).

> **Note**: HuggingFace provides an OpenAI-compatible Inference API endpoint. Tool calling may have limitations depending on the model used.

#### Novita AI

Required if `UAGENT_PROVIDER=novita`:

- `UAGENT_NOVITA_API_KEY` (required): Novita AI API key.
- `UAGENT_NOVITA_BASE_URL` (optional, default: `https://api.novita.ai/openai`).
- `UAGENT_NOVITA_DEPNAME` (optional, default: `tensent/hy3`).

#### Sakana AI (Fugu)

Required if `UAGENT_PROVIDER=sakana`:

- `UAGENT_SAKANA_API_KEY` (required): Sakana AI API key.
- `UAGENT_SAKANA_BASE_URL` (optional, default: `https://api.sakana.ai/v1`).
- `UAGENT_SAKANA_DEPNAME` (optional, default: `fugu`).

#### SAKURA AI Engine

Required if `UAGENT_PROVIDER=sakura`:

- `UAGENT_SAKURA_API_KEY` (required): SAKURA AI Engine API key.
- `UAGENT_SAKURA_BASE_URL` (optional, default: `https://api.ai.sakura.ad.jp/v1`).
- `UAGENT_SAKURA_DEPNAME` (optional, default: `llm`).
- `UAGENT_SAKURA_TEMPERATURE` (optional): Temperature setting for the model.

### 3. Basic Agent Behavior

- `UAGENT_LANG`: Host UI language (e.g., `en`, `ja`, `zh_CN`, `zh_TW`, `ko`, `th`, `es`, `fr`, `de`, `it`, `pt_BR`, `ru`).
- `UAGENT_WORKDIR`: Default working directory for agent operations.
- `UAGENT_WEB_HOST`: Web server bind address (default: `127.0.0.1`). Set to `0.0.0.0` to allow external access.
- `UAGENT_STREAMING`: Enable/disable streaming LLM responses (`1`: Enabled(default), `0`: Disabled).
- `UAGENT_VERBOSITY`: Output verbosity level (`off`, `low`, `medium`, `high`).
- `UAGENT_DEBUG_ENDPOINT`: Set to `1` to output endpoint and model info at startup.
- `UAGENT_PARALLEL_WORKERS`: Number of threads for parallel tool execution (default: `8`). Increase for more concurrency on I/O-bound tasks.
- `UAGENT_AUTO_UNLOAD_ROUNDS`: Automatically unload tools that haven't been used for this many LLM rounds (default: `10`). Set to `0` to disable auto-unload.

#### LLM Parameters (OpenAI-compatible)

Optional parameters passed directly to the LLM API.

- `UAGENT_MAX_TOKENS`: Maximum number of tokens in the response.
- `UAGENT_TOP_P`: Nucleus sampling parameter (e.g. `0.9`).
- `UAGENT_STOP`: Comma-separated stop sequences (e.g. `stop,because`).
- `UAGENT_SEED`: Random seed for reproducible generation.
- `UAGENT_FREQUENCY_PENALTY`: Frequency penalty (e.g. `0.5`).
- `UAGENT_PRESENCE_PENALTY`: Presence penalty (e.g. `0.5`).
- `UAGENT_RESPONSE_FORMAT`: Response format (`json` for JSON mode).

### 4. Advanced Features (Responses API, Reasoning, etc.)

- `UAGENT_RESPONSES`: Set to `1` to enable the "Responses API" for supported providers (Azure/OpenAI/Bedrock/OpenRouter/Ollama).
- `UAGENT_OPENAI_FAST_MODE`: Set to `1`/`true`/`yes`/`on` to request OpenAI Fast mode (`service_tier=fast`). OpenAI only; ignored by Azure and other providers.
- `UAGENT_REASONING`: Reasoning effort level for reasoning models (`off`, `auto`, `minimal`, `low`, `medium`, `high`, `xhigh`).
- `UAGENT_REASONING_EFFORT`: Reasoning effort level for Grok / xAI models (`none`, `low`, `medium`, `high`).
- `UAGENT_STREAMING_DEBUG`: Set to `1` to dump each streaming event (JSON) to `outputs/streaming_debug/`.
- `UAGENT_RESPONSES_STATE_FILE`: absolute path to a specific Responses API state file (overrides auto path).
- `UAGENT_RESPONSES_STATE_DIR`: directory for Responses API state files (optional; default: `~/.uag/`).

### 5. Built-in Web Search

Configuration settings for built-in web search (grounding) features provided directly by LLM backends.

- **`UAGENT_GEMINI_WEB_SEARCH`**: Controls Gemini / Vertex AI's built-in Google Search (Google Search Grounding).
  - Set to `1`, `true`, `yes`, `on`, or **leave unset (default)** to enable. When active, local web search tools are automatically disabled.
  - Set to `0`, `false`, `no`, `off` to disable and fall back to local web search tools.

## Realtime Audio
- `UAGENT_AUDIO_REALTIME_PROVIDER`: Provider override (`openai`, `grok`, `xai`, `google`, `gemini`, `vertexai`).
- `UAGENT_GEMINI_API_KEY` / `UAGENT_GOOGLE_API_KEY` / `GEMINI_API_KEY` / `GOOGLE_API_KEY`: API key for Gemini Realtime.
- `UAGENT_GEMINI_REALTIME_DEPNAME` / `UAGENT_GOOGLE_REALTIME_DEPNAME`: Realtime model deployment name (default `gemini-2.0-flash-exp`).
- `UAGENT_GEMINI_REALTIME_VOICE` / `UAGENT_GOOGLE_REALTIME_VOICE`: Prebuilt voice name (default `Puck`).
