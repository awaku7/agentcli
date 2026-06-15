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

## Key Environment Variables

### 1. Provider Selection (`UAGENT_PROVIDER`)

Specifies the primary provider to use at startup (Required).

- Values: `openai`, `azure`, `bedrock`, `openrouter`, `ollama`, `gemini`, `vertexai`, `grok`, `claude`, `nvidia`, `deepseek`, `alibaba`, `kimi`

### 2. LLM Provider Settings

Each provider requires specific variables. You can override the default model using `UAGENT_<PROVIDER>_DEPNAME`.

| Provider | Authentication & Endpoint | Model ID (Optional) |
| :--- | :--- | :--- |
| **OpenAI** | `UAGENT_OPENAI_API_KEY`, `UAGENT_OPENAI_BASE_URL` | `UAGENT_OPENAI_DEPNAME` |
| **Azure OpenAI** | `UAGENT_AZURE_API_KEY`, `UAGENT_AZURE_BASE_URL`, `UAGENT_AZURE_API_VERSION` | `UAGENT_AZURE_DEPNAME` |
| **Claude (Anthropic)** | `UAGENT_CLAUDE_API_KEY` | `UAGENT_CLAUDE_DEPNAME` |
| **Google (Gemini)** | `UAGENT_GEMINI_API_KEY` | `UAGENT_GEMINI_DEPNAME` |
| **Google (Vertex AI)** | `UAGENT_VERTEXAI_API_KEY` (optional: `UAGENT_VERTEXAI_PROJECT`, `UAGENT_VERTEXAI_LOCATION`) | `UAGENT_VERTEXAI_DEPNAME` (required) |
| **AWS Bedrock** * | `UAGENT_BEDROCK_BASE_URL`, `UAGENT_BEDROCK_API_KEY` | `UAGENT_BEDROCK_DEPNAME` |
| **OpenRouter** | `UAGENT_OPENROUTER_API_KEY`, `UAGENT_OPENROUTER_BASE_URL` | `UAGENT_OPENROUTER_DEPNAME` |
| **Ollama** | `UAGENT_OLLAMA_BASE_URL` (Default: `http://localhost:11434/v1`) | `UAGENT_OLLAMA_DEPNAME` |
| **Grok (xAI)** | `UAGENT_GROK_API_KEY`, `UAGENT_GROK_BASE_URL` | `UAGENT_GROK_DEPNAME` |
| **NVIDIA** | `UAGENT_NVIDIA_API_KEY`, `UAGENT_NVIDIA_BASE_URL` | `UAGENT_NVIDIA_DEPNAME` |
| **DeepSeek** | `UAGENT_DEEPSEEK_API_KEY`, `UAGENT_DEEPSEEK_BASE_URL` (Default: `https://api.deepseek.com`) | `UAGENT_DEEPSEEK_DEPNAME` (Default: `deepseek-v4-flash`) |
| **Alibaba Cloud (Qwen)** | `UAGENT_ALIBABA_API_KEY`, `UAGENT_ALIBABA_BASE_URL` (Default: `https://dashscope.aliyuncs.com/compatible-mode/v1`) | `UAGENT_ALIBABA_DEPNAME` (Default: `qwen3.5-plus`) |
| **KIMI (Moonshot AI)** | `UAGENT_KIMI_API_KEY`, `UAGENT_KIMI_BASE_URL` (Default: `https://api.moonshot.cn/v1`) | `UAGENT_KIMI_DEPNAME` (Default: `kimi-k2`) |

> \* **Note on AWS Bedrock**: The current `uag` implementation expects an OpenAI-compatible endpoint for Bedrock.

#### Google Cloud Settings

Used by Gemini / Vertex AI features that need Google Cloud access.

- `UAGENT_GOOGLE_CREDENTIALS`: Path to Google Cloud service account JSON or JSON string (optional).
- `UAGENT_GOOGLE_LOCATION`: Google Cloud location/region (e.g., `asia-northeast1`).

### 3. Basic Agent Behavior

- `UAGENT_LANG`: Host UI language (e.g., `en`, `ja`, `zh_CN`, `zh_TW`, `ko`, `th`, `es`, `fr`, `de`, `it`, `pt_BR`, `ru`).
- `UAGENT_WORKDIR`: Default working directory for agent operations.
- `UAGENT_STREAMING`: Enable/disable streaming LLM responses (`1`: Enabled(default), `0`: Disabled).
- `UAGENT_VERBOSITY`: Output verbosity level (`off`, `low`, `medium`, `high`).
- `UAGENT_DEBUG_ENDPOINT`: Set to `1` to output endpoint and model info at startup.

### 4. Advanced Features (Responses API, Reasoning, etc.)

- `UAGENT_RESPONSES`: Set to `1` to enable the "Responses API" for supported providers (Azure/OpenAI/Bedrock/OpenRouter/Ollama).
- `UAGENT_REASONING`: Reasoning effort level for reasoning models (`off`, `auto`, `minimal`, `low`, `medium`, `high`, `xhigh`).
- `UAGENT_STREAMING_DEBUG`: Set to `1` to dump each streaming event (JSON) to `outputs/streaming_debug/`.

### 5. Built-in Web Search

Configuration settings for built-in web search (grounding) features provided directly by LLM backends.

- **`UAGENT_GEMINI_WEB_SEARCH`**: Controls Gemini / Vertex AI's built-in Google Search (Google Search Grounding).
  - Set to `1`, `true`, `yes`, `on`, or **leave unset (default)** to enable. When active, local web search tools are automatically disabled.
  - Set to `0`, `false`, `no`, `off` to disable and fall back to local web search tools.
- **`UAGENT_OPENAI_WEB_SEARCH`**: Controls OpenAI Responses API's built-in web search.
  - Set to `1`, `true`, `yes`, `on` to enable (disabled by default).
  - Additional controls include `UAGENT_OPENAI_WEB_SEARCH_TYPE` (search type), `UAGENT_OPENAI_WEB_SEARCH_CONTEXT_SIZE` (context size), etc.

### 5. Image Generation and Analysis

- `UAGENT_IMG_GENERATE_PROVIDER`: Provider for image generation (Default: `UAGENT_PROVIDER`).
- `UAGENT_<PROVIDER>_IMG_GENERATE_DEPNAME`: Model ID for image generation (e.g., `dall-e-3`).
- `UAGENT_IMG_ANALYSIS_PROVIDER`: Provider for image analysis (Default: `UAGENT_PROVIDER`).
  - Supported: `openai`, `azure`, `gemini`, `vertexai`, `ollama`, `alibaba` (Qwen-VL via DashScope), `deepseek` (vision-capable endpoint required).
  - Requires the corresponding `UAGENT_<PROVIDER>_API_KEY/DEPNAME/BASE_URL` env vars.
- `UAGENT_IMAGE_OPEN`: Whether to automatically open images after generation (`0` to disable).

### 6. Audio Speech and Transcription

- `UAGENT_AUDIO_PROVIDER`: Provider for audio speech/transcription (Default: `UAGENT_PROVIDER`; supported: `openai`, `azure`, `gemini`, `vertexai`).
- `UAGENT_AZURE_SPEECH_DEPNAME`: Azure speech deployment name.
- `UAGENT_OPENAI_SPEECH_DEPNAME`: OpenAI speech model/deployment name.
- `UAGENT_GEMINI_SPEECH_DEPNAME`: Gemini/VertexAI speech model name (Default: `ja-JP-Neural2-B`).
- `UAGENT_AZURE_TRANSCRIBE_DEPNAME`: Azure transcription deployment name.
- `UAGENT_OPENAI_TRANSCRIBE_DEPNAME`: OpenAI transcription model/deployment name.
- `UAGENT_AUDIO_OPEN`: Whether to automatically open generated audio after speech output (`0` to disable).

### 7. Translation Features (Optional)

Enables automatic translation of user inputs and LLM responses.

- `UAGENT_TRANSLATE_PROVIDER`: Translation engine.
  - `openai`, `azure`, `openrouter`, `openai_compat`: OpenAI-compatible API を使う翻訳。
  - `gemini`: Google Gemini を使う翻訳。
  - `claude`: Anthropic Claude を使う翻訳。
- `UAGENT_TRANSLATE_TO_LLM`: Target language for user inputs (e.g., `en`). Input is skipped if it already looks like English.
- `UAGENT_TRANSLATE_FROM_LLM`: Target language for LLM responses (e.g., `ja`).
- `UAGENT_TRANSLATE_DEPNAME`: Model ID to use for translation (Required for API providers).
- `UAGENT_TRANSLATE_API_KEY`: API key for translation (Optional, defaults to `UAGENT_API_KEY`).
- `UAGENT_TRANSLATE_BASE_URL`: Base URL for translation (Optional, defaults to `UAGENT_BASE_URL`).

### 8. Memory and Semantic Search

- `UAGENT_MEMORY_FILE`: Path to store long-term memory notes.
- `UAGENT_SHARED_MEMORY_FILE`: Path to store shared long-term memory.
- `UAGENT_EMBEDDING_PROVIDER`: Provider for embeddings (default: `UAGENT_PROVIDER`).
- `UAGENT_<PROVIDER>_EMBEDDING_BASE_URL`: Base URL for the embedding provider.
- `UAGENT_<PROVIDER>_EMBEDDING_API_KEY`: API key for the embedding provider.
- `UAGENT_<PROVIDER>_EMBEDDING_API_VERSION`: API version for Azure-style providers.
- `UAGENT_<PROVIDER>_EMBEDDING_DEPNAME`: Embedding model / deployment name.
- `UAGENT_ENABLE_SEMANTIC_SEARCH`: Enable or disable semantic search tooling.

### 9. Autonomous User Profiling Settings

Configure the autonomous profiling system that extracts your development environment and preferences from conversation logs.

- `UAGENT_ENABLE_PROFILING`: Enable or disable autonomous profiling (`1`: Enabled(default), `0`: Disabled).
- `UAGENT_PROFILE_FILE`: Path to store the extracted profile data (default: `scheck_profile.jsonl`).

### 10. Specialized Sub-Agent Configuration (Overrides)

You can override the provider, model name, and API key for specialized sub-agents (`planner`, `reviewer`, `summarizer`, `patch_designer`, `error_analyst`) executed via the `run_sub_agent` tool. If not specified, they inherit the main agent's configuration.

- **General Sub-Agent Overrides**:
  - `UAGENT_SUB_AGENT_PROVIDER`: Provider used for all sub-agents.
  - `UAGENT_SUB_AGENT_DEPNAME`: Model name used for all sub-agents.
  - `UAGENT_SUB_AGENT_API_KEY`: API key used for all sub-agents.

- **Function-Specific Overrides (Highest Priority)**:
  - `UAGENT_SUB_AGENT_<AGENT_NAME>_PROVIDER`: Provider for a specific sub-agent.
  - `UAGENT_SUB_AGENT_<AGENT_NAME>_DEPNAME`: Model name for a specific sub-agent.
  - `UAGENT_SUB_AGENT_<AGENT_NAME>_API_KEY`: API key for a specific sub-agent.
  *(※ `<AGENT_NAME>` must be one of `PLANNER`, `REVIEWER`, `SUMMARIZER`, `PATCH_DESIGNER`, `ERROR_ANALYST`)*

  *(Example: Setting `UAGENT_SUB_AGENT_SUMMARIZER_PROVIDER=gemini` and `UAGENT_SUB_AGENT_SUMMARIZER_DEPNAME=gemini-2.5-flash` allows you to route only the summarization tasks to the fast and cost-effective Gemini 2.5 Flash model)*

______________________________________________________________________

## A2A Server

`uaga` exposes an Agent2Agent-compatible HTTP server. Configure it with:

- `UAGENT_A2A_HOST`: Bind host for the server (default: `0.0.0.0`).
- `UAGENT_A2A_PORT`: Listening port (default: `8765`).
- `UAGENT_A2A_RELOAD`: Enable auto-reload during development.
- `UAGENT_A2A_PUBLIC_BASE_URL`: Public base URL advertised to clients.
- `UAGENT_A2A_CONCURRENCY`: Concurrency limit for task execution.
- `UAGENT_A2A_ENGINE`: A2A execution mode.
- `UAGENT_A2A_TOKEN`: Bearer token for authenticated endpoints. Leave empty to disable auth.

## Security and Encryption (`uag_envsec`)

If you prefer not to store sensitive API keys in plain text within the `.env` file, you can encrypt it using `uag_envsec`.

1. **Encryption**: Run `uag_envsec .env` and enter a password.
1. **Usage**: `uag` will automatically detect `.env.sec` at startup and prompt for a password to decrypt and load it.
1. **Update**: Use `uag_envsec add --file .env.sec --key NAME --value VALUE` to add or update a variable in an existing encrypted file.
