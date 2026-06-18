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

- Values: `openai`, `azure`, `bedrock`, `openrouter`, `ollama`, `gemini`, `vertexai`, `grok`, `claude`, `nvidia`, `deepseek`, `alibaba`, `kimi`, `mimo`

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
| **Xiaomi MiMo** | `UAGENT_MIMO_API_KEY`, `UAGENT_MIMO_BASE_URL` (Default: `https://api.xiaomimimo.com/v1`) | `UAGENT_MIMO_DEPNAME` (Default: `mimo-v2.5-pro`) |

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
  - Supported: `openai`, `azure`, `gemini`, `vertexai`, `ollama`, `alibaba` (Qwen-VL via DashScope), `kimi` (Moonshot AI), `deepseek` (vision-capable endpoint required).
  - `UAGENT_IMG_ANALYSIS_DEPNAME`: Override model for image analysis (optional).
  - Provider-specific `UAGENT_<PROVIDER>_API_KEY` / `UAGENT_<PROVIDER>_BASE_URL` env vars apply.
  - Default models: `gpt-4o-mini` (openai), `qwen-vl-max` (alibaba), `kimi-k2` (kimi).
- `UAGENT_IMAGE_OPEN`: Whether to automatically open images after generation (`0` to disable).

### 6. Audio Speech and Transcription

- `UAGENT_AUDIO_PROVIDER`: Provider for audio speech/transcription (Default: `UAGENT_PROVIDER`; supported: `openai`, `azure`, `gemini`, `vertexai`).
- `UAGENT_AZURE_SPEECH_DEPNAME`: Azure speech deployment name.
- `UAGENT_OPENAI_SPEECH_DEPNAME`: OpenAI speech model/deployment name.
- `UAGENT_GEMINI_SPEECH_DEPNAME`: Gemini/VertexAI speech model name (Default: `ja-JP-Neural2-B`).
- `UAGENT_AZURE_TRANSCRIBE_DEPNAME`: Azure transcription deployment name.
