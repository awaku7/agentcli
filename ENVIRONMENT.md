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

### 1. LLM Provider Settings

Set one or more of the following depending on the providers you wish to use.

| Provider | Required/Recommended Variables |
| :--- | :--- |
| **OpenAI** | `UAGENT_OPENAI_API_KEY` |
| **Anthropic** | `UAGENT_ANTHROPIC_API_KEY` |
| **Google (Gemini)** | `UAGENT_GEMINI_API_KEY` |
| **Azure OpenAI** | `UAGENT_AZURE_OPENAI_API_KEY`, `UAGENT_AZURE_BASE_URL`, `UAGENT_AZURE_DEPLOYMENT_ID` |
| **AWS (Bedrock)** | `UAGENT_AWS_REGION`, `UAGENT_AWS_ACCESS_KEY_ID`, `UAGENT_AWS_SECRET_ACCESS_KEY` |
| **OpenRouter** | `UAGENT_OPENROUTER_API_KEY` |
| **Ollama** | `UAGENT_OLLAMA_BASE_URL` (Default: `http://localhost:11434`) |
| **Grok (xAI)** | `UAGENT_GROK_API_KEY` |
| **NVIDIA** | `UAGENT_NVIDIA_API_KEY` |
| **DeepSeek** | `UAGENT_DEEPSEEK_API_KEY` |

### 2. Basic Agent Behavior

- `UAGENT_LANG`: Specifies the host UI language.
  - `en`: English
  - `ja`: Japanese
- `UAGENT_WORKDIR`: Default working directory for agent operations.
- `UAGENT_VERBOSITY`: Output verbosity level (`low`, `medium`, `high`).

### 3. History Management (Auto-Shrink)

To control token consumption, `uag` can automatically delete or summarize old messages when a conversation becomes too long.

- `UAGENT_SHRINK_CNT`: Number of messages to trigger auto-shrink (Default: `100`).
- `UAGENT_SHRINK_KEEP_LAST`: Number of latest messages to keep after shrinking (Default: `20`).

### 4. Memory and Tools

- `UAGENT_MEMORY_FILE`: Path to store long-term memory notes.
- `UAGENT_SHARED_MEMORY_FILE`: Path to store shared long-term memory across sessions.
- `UAGENT_EMBEDDING_API_URL`: URL for the embedding API used for semantic search.

---

## Security and Encryption (`uag_envsec`)

If you prefer not to store sensitive API keys in plain text within the `.env` file, you can encrypt it using `uag_envsec`.

1. **Encryption**:
   ```bash
   uag_envsec .env
   ```
   After entering a password, an encrypted `.env.sec` file and a local key file `.uagent.key` will be created.
   
2. **Usage**:
   `uag` will automatically decrypt and load `.env.sec` at startup (requires password entry).

---

## Advanced Settings

- `UAGENT_RESPONSES`: Set to `1` to enable the "Responses API" for supported providers like OpenAI.
- `UAGENT_REASONING`: Specifies the reasoning effort for reasoning models like o1 (`auto`, `low`, `medium`, `high`).
- `UAGENT_CMD_ENCODING`: Encoding used to decode stdout from external command execution.
