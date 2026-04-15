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

---

## Key Environment Variables

### 1. Provider Selection (`UAGENT_PROVIDER`)

Specifies the primary provider to use at startup (Required).

- Values: `openai`, `azure`, `gemini`, `bedrock`, `openrouter`, `ollama`, `grok`, `nvidia`, `claude`

### 2. LLM Provider Settings

Each provider requires specific variables. You can override the default model using `UAGENT_<PROVIDER>_DEPNAME`.

| Provider | Authentication & Endpoint | Model ID (Optional) |
| :--- | :--- | :--- |
| **OpenAI** | `UAGENT_OPENAI_API_KEY`, `UAGENT_OPENAI_BASE_URL` | `UAGENT_OPENAI_DEPNAME` |
| **Azure OpenAI** | `UAGENT_AZURE_API_KEY`, `UAGENT_AZURE_BASE_URL`, `UAGENT_AZURE_API_VERSION` | `UAGENT_AZURE_DEPNAME` |
| **Claude (Anthropic)** | `UAGENT_CLAUDE_API_KEY` | `UAGENT_CLAUDE_DEPNAME` |
| **Google (Gemini)** | `UAGENT_GEMINI_API_KEY` | `UAGENT_GEMINI_DEPNAME` |
| **Google (Vertex AI)** | `UAGENT_VERTEXAI_API_KEY`, `UAGENT_VERTEXAI_PROJECT`, `UAGENT_VERTEXAI_LOCATION` | `UAGENT_VERTEXAI_DEPNAME` |
| **AWS Bedrock** * | `UAGENT_BEDROCK_BASE_URL`, `UAGENT_BEDROCK_API_KEY` | `UAGENT_BEDROCK_DEPNAME` |
| **OpenRouter** | `UAGENT_OPENROUTER_API_KEY`, `UAGENT_OPENROUTER_BASE_URL` | `UAGENT_OPENROUTER_DEPNAME` |
| **Ollama** | `UAGENT_OLLAMA_BASE_URL` (Default: `http://localhost:11434/v1`) | `UAGENT_OLLAMA_DEPNAME` |
| **Grok (xAI)** | `UAGENT_GROK_API_KEY`, `UAGENT_GROK_BASE_URL` | `UAGENT_GROK_DEPNAME` |
| **NVIDIA** | `UAGENT_NVIDIA_API_KEY`, `UAGENT_NVIDIA_BASE_URL` | `UAGENT_NVIDIA_DEPNAME` |

> \* **Note on AWS Bedrock**: The current `uag` implementation expects an OpenAI-compatible endpoint for Bedrock.

### 3. Basic Agent Behavior

- `UAGENT_LANG`: Host UI language (e.g., `en`, `ja`, `zh_CN`, `zh_TW`, `ko`, `th`, `es`, `fr`, `de`, `it`, `pt_BR`, `ru`).
- `UAGENT_WORKDIR`: Default working directory for agent operations.
- `UAGENT_STREAMING`: Enable/disable streaming LLM responses (`1`: Enabled(default), `0`: Disabled).
- `UAGENT_VERBOSITY`: Output verbosity level (`low`, `medium`, `high`).
- `UAGENT_DEBUG_ENDPOINT`: Set to `1` to output endpoint and model info at startup.

### 4. Advanced Features (Responses API, Reasoning, etc.)

- `UAGENT_RESPONSES`: Set to `1` to enable the "Responses API" for supported providers (Azure/OpenAI/Bedrock/OpenRouter/Ollama).
- `UAGENT_REASONING`: Reasoning effort level for reasoning models (`auto`, `minimal`, `low`, `medium`, `high`).
- `UAGENT_STREAMING_DEBUG`: Set to `1` to dump each streaming event (JSON) to `outputs/streaming_debug/`.

### 5. Image Generation and Analysis

- `UAGENT_IMG_GENERATE_PROVIDER`: Provider for image generation (Default: `UAGENT_PROVIDER`).
- `UAGENT_<PROVIDER>_IMG_GENERATE_DEPNAME`: Model ID for image generation (e.g., `dall-e-3`).
- `UAGENT_IMG_ANALYSIS_PROVIDER`: Provider for image analysis (Default: `UAGENT_PROVIDER`).
- `UAGENT_IMAGE_OPEN`: Whether to automatically open images after generation (`0` to disable).

### 6. Translation Features (Optional)

Enables automatic translation of user inputs and LLM responses.

- `UAGENT_TRANSLATE_PROVIDER`: Translation engine.
    - `argos`: Local translation using [Argos Translate](https://github.com/argosopentech/argos-translate) (Requires `pip install argostranslate`).
    - `openai`, `azure`, `openrouter`, `openai_compat`: Any OpenAI-compatible API.
    - *Note: Native Gemini/Claude are not supported for translation yet.*
- `UAGENT_TRANSLATE_TO_LLM`: Target language for user inputs (e.g., `en`). Input is skipped if it already looks like English.
- `UAGENT_TRANSLATE_FROM_LLM`: Target language for LLM responses (e.g., `ja`).
- `UAGENT_TRANSLATE_DEPNAME`: Model ID to use for translation (Required for API providers).
- `UAGENT_TRANSLATE_API_KEY`: API key for translation (Optional, defaults to `UAGENT_API_KEY`).
- `UAGENT_TRANSLATE_BASE_URL`: Base URL for translation (Optional, defaults to `UAGENT_BASE_URL`).

### 7. Memory and Semantic Search

- `UAGENT_MEMORY_FILE`: Path to store long-term memory notes.
- `UAGENT_SHARED_MEMORY_FILE`: Path to store shared long-term memory.
- `UAGENT_EMBEDDING_API_URL`: URL for the embedding API used for semantic search.

---

## Security and Encryption (`uag_envsec`)

If you prefer not to store sensitive API keys in plain text within the `.env` file, you can encrypt it using `uag_envsec`.

1. **Encryption**: Run `uag_envsec .env` and enter a password.
2. **Usage**: `uag` will automatically detect `.env.sec` at startup and prompt for a password to decrypt and load it.
