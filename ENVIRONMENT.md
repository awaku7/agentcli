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
  Supported values: `azure`, `openai`, `bedrock`, `openrouter`, `ollama`, `gemini`, `vertexai`, `claude`, `grok`, `nvidia`, `deepseek`, `zai`, `alibaba`, `moonshot`, `mimo`, `lmstudio`, `minimax`.
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

#### Bedrock

Required if `UAGENT_PROVIDER=bedrock`:

- `UAGENT_BEDROCK_MODEL` (required, e.g. `us.anthropic.claude-sonnet-4-20250514`)
- `UAGENT_BEDROCK_ACCESS_KEY` (required)
- `UAGENT_BEDROCK_SECRET_KEY` (required)
- `UAGENT_BEDROCK_REGION` (optional, default: `us-west-2`)

#### OpenRouter

Required if `UAGENT_PROVIDER=openrouter`:

- `UAGENT_OPENROUTER_API_KEY` (required)

#### Ollama

Required if `UAGENT_PROVIDER=ollama`:

- `UAGENT_OLLAMA_MODEL` (required)
- `UAGENT_OLLAMA_BASE_URL` (optional, default: `http://localhost:11434/v1`)

#### Google Gemini

Required if `UAGENT_PROVIDER=gemini`:

- `UAGENT_GEMINI_API_KEY` (required)
- `UAGENT_GEMINI_MODEL` (optional, default: `gemini-2.5-pro-exp-03-25`)

#### Google Vertex AI

Required if `UAGENT_PROVIDER=vertexai`:

- `UAGENT_VERTEXAI_PROJECT` (required)
- `UAGENT_VERTEXAI_LOCATION` (required, e.g. `us-central1`)
- `UAGENT_VERTEXAI_MODEL` (required)
- `UAGENT_VERTEXAI_CREDENTIALS` (required): Path to Google Cloud service account JSON.

#### Claude (Anthropic)

Required if `UAGENT_PROVIDER=claude`:

- `UAGENT_CLAUDE_API_KEY` (required)
- `UAGENT_CLAUDE_MODEL` (optional, default: `claude-sonnet-4-20250514`)

#### Grok

Required if `UAGENT_PROVIDER=grok`:

- `UAGENT_GROK_API_KEY` (required)
- `UAGENT_GROK_MODEL` (optional)

#### NVIDIA

Required if `UAGENT_PROVIDER=nvidia`:

- `UAGENT_NVIDIA_API_KEY` (required)
- `UAGENT_NVIDIA_MODEL` (optional)

#### DeepSeek

Required if `UAGENT_PROVIDER=deepseek`:

- `UAGENT_DEEPSEEK_API_KEY` (required)
- `UAGENT_DEEPSEEK_BASE_URL` (optional, default: `https://api.deepseek.com`)

#### Alibaba Cloud (Qwen)

Required if `UAGENT_PROVIDER=alibaba`:

- `UAGENT_ALIBABA_API_KEY` (required)
- `UAGENT_ALIBABA_BASE_URL` (optional)

#### Moonshot (KIMI)

Required if `UAGENT_PROVIDER=moonshot`:

- `UAGENT_MOONSHOT_API_KEY` (required)

#### Xiaomi MiMo

Required if `UAGENT_PROVIDER=mimo`:

- `UAGENT_MIMO_API_KEY` (required)
- `UAGENT_MIMO_BASE_URL` (optional)

#### LM Studio

Required if `UAGENT_PROVIDER=lmstudio`:

- `UAGENT_LMSTUDIO_BASE_URL` (optional, default: `http://localhost:1234/v1`)

> \* **Note on AWS Bedrock**: The current `uag` implementation expects an OpenAI-compatible endpoint for Bedrock.

#### Google Cloud Settings

Used by Gemini / Vertex AI features that need Google Cloud access.

- `UAGENT_GOOGLE_CREDENTIALS`: Path to Google Cloud service account JSON or JSON string (optional).
- `UAGENT_GOOGLE_LOCATION`: Google Cloud location/region (e.g., `asia-northeast1`).

### 3. Basic Agent Behavior

- `UAGENT_LANG`: Host UI language (e.g., `en`, `ja`, `zh_CN`, `zh_TW`, `ko`, `th`, `es`, `fr`, `de`, `it`, `pt_BR`, `ru`).
- `UAGENT_WORKDIR`: Default working directory for agent operations.
- `UAGENT_WEB_HOST`: Web server bind address (default: `127.0.0.1`). Set to `0.0.0.0` to allow external access.
- `UAGENT_STREAMING`: Enable/disable streaming LLM responses (`1`: Enabled(default), `0`: Disabled).
- `UAGENT_VERBOSITY`: Output verbosity level (`off`, `low`, `medium`, `high`).
- `UAGENT_DEBUG_ENDPOINT`: Set to `1` to output endpoint and model info at startup.
- `UAGENT_PARALLEL_WORKERS`: Number of threads for parallel tool execution (default: `8`). Increase for more concurrency on I/O-bound tasks.

### 4. Advanced Features (Responses API, Reasoning, etc.)

- `UAGENT_RESPONSES`: Set to `1` to enable the "Responses API" for supported providers (Azure/OpenAI/Bedrock/OpenRouter/Ollama).
- `UAGENT_REASONING`: Reasoning effort level for reasoning models (`off`, `auto`, `minimal`, `low`, `medium`, `high`, `xhigh`).
- `UAGENT_STREAMING_DEBUG`: Set to `1` to dump each streaming event (JSON) to `outputs/streaming_debug/`.

### 5. Built-in Web Search

Configuration settings for built-in web search (grounding) features provided directly by LLM backends.

- **`UAGENT_GEMINI_WEB_SEARCH`**: Controls Gemini / Vertex AI's built-in Google Search (Google Search Grounding).
  - Set to `1`, `true`, `yes`, `on`, or **leave unset (default)** to enable. When active, local web search tools are automatically disabled.
  - Set to `0`, `false`, `no`, `off` to disable and fall back to local web search tools.
