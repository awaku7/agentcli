```
██╗   ██╗ █████╗  ██████╗ ███████╗███╗   ██╗████████╗ ██████╗██╗     ██╗
██║   ██║██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝██╔════╝██║     ██║
██║   ██║███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   ██║     ██║     ██║
██║   ██║██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   ██║     ██║     ██║
╚██████╔╝██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   ╚██████╗███████╗██║
 ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝╚══════╝╚═╝
```

# uag (Local AI Agent)

uag is an interactive local agent that can execute commands, manipulate files, and read various data formats (PDF/PPTX/Excel, etc.) on your PC.

- CLI: `uag` / `python -m uagent`
- GUI: `uagg` / `python -m uagent.gui`
- Web: `uagw` / `python -m uagent.web`
- A2A server: `uaga` / `python -m uagent.a2a.server`

______________________________________________________________________

## Why uag

- Local-first tool execution with a wide practical tool surface
- Multiple UI entry points: CLI, GUI, and Web
- Multiple providers: Azure OpenAI / OpenAI-compatible, Bedrock, OpenRouter, Ollama, Gemini, Claude, Grok, NVIDIA
- Provider/model switching with session continuity (carry conversation context across LLM changes)
- End-to-end i18n support: localized host UI (`UAGENT_LANG`) plus optional TO_LLM/FROM_LLM translation for LLM communication
- Strong file/document handling: text, PDF, PPTX, Excel, screenshots, and images
- Session continuity and history controls: `:logs` / `:load`, manual `:shrink_llm`, and optional auto-shrink
- MCP support for discovering and calling external tool servers
- Safer operations through confirmation, path restrictions, masking, and smoke tests
- Startup initialization is centralized in `src/uagent/runtime_init.py` for workdir resolution, startup banners, and memory injection
- GPT-5.4+ Responses optimization: lightweight tools prompt, `tool_catalog`, and narrowed tool exposure per request

______________________________________________________________________

## Minimal Usage

## A2A (Agent2Agent) server

uag can also expose an A2A-compatible HTTP server as a separate process (does not affect the existing CLI/GUI/Web behavior).

### Start server

```bash
# required for authenticated endpoints
export UAGENT_A2A_TOKEN=YOUR_TOKEN

# default: host=0.0.0.0, port=8765
uaga
# or
python -m uagent.a2a.server
```

### Configuration (env)

- `UAGENT_A2A_TOKEN`: required for authenticated endpoints. If empty, authenticated endpoints are disabled.
- `UAGENT_A2A_CONCURRENCY`: max concurrent requests (default: `1`).
- `UAGENT_A2A_ENGINE`: backend engine for handling requests (default: `uag`; tests may use `echo`).
- `UAGENT_A2A_BASE_URL`: client-side base URL (default: `http://127.0.0.1:8765`).
- `UAGENT_SIMPLE_PROMPT`: defaults to `1`. Set `0`/`false`/`no`/`off` to disable the readline-based prompt path (useful if the CLI redraws strangely).

### Client usage (optional)

You do not need an A2A client for normal `uag` CLI/GUI/Web usage.
Use the client only when you want to call the A2A server from another process or application.

## Language / i18n

Host-side UI strings are localized via gettext catalogs.

- Language selection: set `UAGENT_LANG` (examples: `en`, `ja`, `zh_CN`, `zh_TW`, `es`, `fr`, `ko`, `th`).
- If `UAGENT_LANG` is unset or unsupported, uag falls back to English.

Examples:

Windows (cmd):

```bat
set UAGENT_LANG=ko
uag
```

macOS/Linux:

```bash
export UAGENT_LANG=ko
uag
```

See `src/uagent/docs/ADD_LOCALE.md` for how to add a new locale.

Developer notes:

- After editing `src/uagent/locales/*/LC_MESSAGES/uag.po`, regenerate `.mo` files:

```bash
python scripts/compile_locales.py
```

- Run i18n QC (writes reports under `outputs/i18n/`):

```bash
python scripts/po_qc_summary.py
```

See also: `src/uagent/docs/DEVELOP_I18N.md`.

### Start

```bash
uag
# or
python -m uagent
```

### Specify workdir (working directory)

Usually you do not need to set this explicitly.

- CLI: `uag -C ./work`
- GUI: `uag gui -C ./work` (or `python -m uagent.gui -C ./work`)
- Web: `UAGENT_WORKDIR=./work uag web` (for Web UI, specify via environment variable)

Exit:

- `:exit`

### Tips (conversation continuity)

- `:logs`\
  Show available session logs.
- `:logs 20`\
  Show up to 20 logs.
- `:logs --all`\
  Show all logs.
- `:load 0`\
  Load the latest session log and continue the conversation.
- `:load <index>`\
- `:skills`\
  List Agent Skills, choose one, and load its `SKILL.md` into the session.
- `:skills status`\
  Show the active skill system messages.
- `:skills clear`\
  Remove active skill system messages.
- Loaded skills are stored in the session log and restored on `:load`.

______________________________________________________________________

## Tool discovery for GPT-5.4+ Responses

When Responses API is enabled and the selected model is `gpt-5.4` or later within the GPT-5 line, uag uses a lighter tool-loading path.

- Full tool definitions are not sent up front on every request
- A lightweight tools prompt is used instead of enumerating the whole tool surface
- `tool_catalog` can be used to discover relevant tools first
- The actual tool specs passed to the model are narrowed based on the user request
- A safe fallback subset is kept when catalog hits are empty

This reduces prompt/tool payload size while preserving the existing full-tool behavior for other models.

______________________________________________________________________

## History compression (manual / auto)

Manual commands:

- `:shrink [keep_last]` (default `keep_last=40`): keep the last N non-system messages and drop the rest.
- `:shrink_llm [keep_last]` (default `keep_last=20`): summarize older history into one system message and keep the last N non-system messages.

Optional auto shrink (all providers):

- `UAGENT_SHRINK_CNT` (default: `100`)
  - When the number of non-system messages (user/assistant/tool) reaches this count, uag automatically runs the equivalent of `:shrink_llm`.
  - Set `0` to disable.
- `UAGENT_SHRINK_KEEP_LAST` (default: `20`): how many recent non-system messages to keep after auto summarization.

Log rewrite behavior:

- When shrink runs, the current session log (`UAGENT_LOG_FILE` / `core.LOG_FILE`) is rewritten to match the compressed in-memory history.
- A one-generation backup is created under `<log_dir>/.backup/`.

______________________________________________________________________

## Optional Responses API knobs (reasoning / verbosity)

When using the **Responses API** (`UAGENT_RESPONSES=1`) with Azure/OpenAI/Bedrock, you can optionally control reasoning effort and output verbosity.

For Bedrock, uag uses a Bedrock-specific Responses request builder (string `input`) to match OpenAI-compatible gateway constraints.

If `UAGENT_RESPONSES=1` is set with a provider that does not support the Responses API, uag falls back to ChatCompletions at runtime. Ollama is treated as Responses-capable.

- `UAGENT_REASONING`:
  - `auto`: automatically choose `reasoning.effort` per request (Responses API only; streaming is forced off; may retry once on low-quality output)
  - `minimal|low|medium|high|xhigh`: send `reasoning={"effort":...}`
  - `off` / unset / empty: do not send `reasoning`
- `UAGENT_VERBOSITY`:
  - `low|medium|high`: send `text={"verbosity":...}`
  - `off` / unset / empty: do not send `text.verbosity`

In-session commands (CLI/GUI/Web):

- `:r [0|1|2|3|auto|minimal|xhigh]` (no arg: keep current)
- `:v [0|1|2|3]` (no arg: keep current)

______________________________________________________________________

## Provider

`uag` supports multiple LLM providers.

- `UAGENT_PROVIDER=openai` is treated as **OpenAI-compatible** (including OpenAI-compatible endpoints).

  - Required: `UAGENT_OPENAI_API_KEY`
  - Optional: `UAGENT_OPENAI_BASE_URL` (default: `https://api.openai.com/v1`)
  - Optional: `UAGENT_OPENAI_DEPNAME`

- `UAGENT_PROVIDER=azure` uses **Azure OpenAI**.

  - Required: `UAGENT_AZURE_BASE_URL`
  - Required: `UAGENT_AZURE_API_KEY`
  - Required: `UAGENT_AZURE_API_VERSION`
  - Optional: `UAGENT_AZURE_DEPNAME`

- `UAGENT_PROVIDER=bedrock` uses **Bedrock (OpenAI-compatible gateway)**.

  - Required: `UAGENT_BEDROCK_BASE_URL`
  - Required: `UAGENT_BEDROCK_API_KEY`
  - Optional: `UAGENT_BEDROCK_DEPNAME`

- `UAGENT_PROVIDER=openrouter` uses **OpenRouter** (a unified OpenAI-compatible API).

  - Required: `UAGENT_OPENROUTER_API_KEY`
  - Optional: `UAGENT_OPENROUTER_BASE_URL` (default: `https://openrouter.ai/api/v1`)
  - Optional: `UAGENT_OPENROUTER_DEPNAME`
  - Optional: OpenRouter model fallback (OpenRouter extension)
    - Enabled only when `UAGENT_OPENROUTER_DEPNAME="openrouter/auto"` (does not affect other providers/models)
    - If you set `UAGENT_OPENROUTER_FALLBACK_MODELS` (comma-separated), `models=[...]` is added to the Chat Completions request.
      - Example: `UAGENT_OPENROUTER_FALLBACK_MODELS="anthropic/claude-4.5-sonnet,openai/gpt-4o,mistral/mistral-x"`

- `UAGENT_PROVIDER=nvidia` uses **NVIDIA (OpenAI-compatible)**.

  - Required: `UAGENT_NVIDIA_API_KEY`
  - Optional: `UAGENT_NVIDIA_BASE_URL` (default: `https://integrate.api.nvidia.com/v1`)
    - Please specify `/v1` (we do not recommend including `/v1/chat/completions` in the base URL)
  - Optional: `UAGENT_NVIDIA_DEPNAME`

- `UAGENT_PROVIDER=grok` uses **xAI Grok (OpenAI-compatible)**.

  - Required: `UAGENT_GROK_API_KEY`
  - Optional: `UAGENT_GROK_BASE_URL` (default: `https://api.x.ai/v1`)
  - Optional: `UAGENT_GROK_DEPNAME`

- `UAGENT_PROVIDER=gemini` uses **Google Gemini (google-genai)**.

  - Required: `UAGENT_GEMINI_API_KEY`
  - Optional: `UAGENT_GEMINI_DEPNAME`

- `UAGENT_PROVIDER=ollama` uses **Ollama**.

  - Optional: `UAGENT_OLLAMA_BASE_URL` (default: `http://localhost:11434/v1`)
  - Optional: `UAGENT_OLLAMA_API_KEY` (default: `dummy`)
  - Optional: `UAGENT_OLLAMA_DEPNAME`
  - Optional: Ollama request knobs
    - `UAGENT_OLLAMA_TEMPERATURE` (default: `0.7`)
    - `UAGENT_OLLAMA_TOP_P` (default: `0.9`)
    - `UAGENT_OLLAMA_TOP_K` (default: `40`)
    - `UAGENT_OLLAMA_REPEAT_PENALTY` (default: `1.1`)
    - `UAGENT_OLLAMA_KEEP_ALIVE` (default: `5m`)
    - `UAGENT_OLLAMA_NUM_CTX` (default: `4096`)
    - `UAGENT_OLLAMA_NUM_PREDICT` (default: `1024`)

- `UAGENT_PROVIDER=claude` uses **Anthropic Claude**.

  - Required: `UAGENT_CLAUDE_API_KEY`
  - Optional: `UAGENT_CLAUDE_DEPNAME`

See `samples/env.sample.env` for the canonical cross-provider template and `samples/provider.*.env.sample` for provider-specific templates.

- In this repository: run the interactive wizard `python samples/generate_env_samples.py` to generate `samples/env.sample.sh` / `samples/env.sample.ps1` / `samples/env.sample.bat` with the intended encoding and newline settings.
- After installing via pip/wheel: run `uag_setup` to generate your own `.env` (and optionally `env.sh` / `env.ps1` / `env.bat`) in the current directory.

For details, see `samples/README.md`.

### Env sample generation

Sample files are available under `samples/` (including `samples/README.md`).

Run the interactive wizard to configure and generate shell-specific variants:

```bash
python samples/generate_env_samples.py
```

Generated files and format:

- `samples/env.sample.sh` : UTF-8, LF
- `samples/env.sample.ps1` : UTF-8 with BOM (`utf-8-sig`), CRLF
- `samples/env.sample.bat` : CP932, CRLF

The wizard supports numbered selections and back navigation (`b`). Re-run it any time to update configuration.

______________________________________________________________________

## Optional Translation (TO_LLM / FROM_LLM)

By default, uag does **not** translate.

Enable translation by setting:

- `UAGENT_TRANSLATE_PROVIDER`: translation provider (OpenAI-compatible string, e.g. `openai` / `azure` / `openrouter` / `nvidia` / `grok`).
- `UAGENT_TRANSLATE_TO_LLM`: language tag to translate **into** before sending to the LLM (e.g. `en`).
- `UAGENT_TRANSLATE_FROM_LLM`: language tag to translate **into** for displaying LLM outputs (e.g. `ja`).

OpenAI-compatible translation settings:

- `UAGENT_TRANSLATE_DEPNAME`: model name for translation (required when translation is enabled).
- `UAGENT_TRANSLATE_API_KEY`: optional (falls back to the main provider key).
- `UAGENT_TRANSLATE_BASE_URL`: optional (falls back to the main provider base URL).

Notes:

- Translation is done **per call** (stateless).
- When translation is enabled, streaming is forced **off** to avoid mismatched partial outputs.

______________________________________________________________________

## Image Generation / Analysis

### Image Generation (`generate_image`)

- `UAGENT_IMG_GENERATE_PROVIDER`: Override the provider for image generation (fallback: `UAGENT_PROVIDER`).
- `UAGENT_IMAGE_OPEN`: Whether to automatically open the image after generation.
  - `1`: Open (default)
  - `0`: Do not open

Model / deployment name (provider-specific):

- `UAGENT_<PROVIDER>_IMG_GENERATE_DEPNAME` (required)
  - Examples: `UAGENT_OPENAI_IMG_GENERATE_DEPNAME`, `UAGENT_AZURE_IMG_GENERATE_DEPNAME`

Provider-specific credentials / endpoints:

- `UAGENT_<PROVIDER>_IMG_GENERATE_API_KEY` (required)
- `UAGENT_<PROVIDER>_IMG_GENERATE_BASE_URL` (optional for most providers; default may apply)
- Azure only: `UAGENT_AZURE_IMG_GENERATE_API_VERSION` (required)

Fallback behavior:

- If a `*_IMG_GENERATE_*` env var is not set, the tool also tries the main provider env (e.g. `UAGENT_OPENAI_API_KEY`, `UAGENT_OPENAI_BASE_URL`).

Notes:

- Depending on the provider SDK/API, supported sizes/features may differ.

### Image Analysis (`analyze_image`)

By default, the `analyze_image` tool uses the provider specified in `UAGENT_PROVIDER`. You can override this using specific environment variables.

- `UAGENT_RESPONSES=1`: If enabled, the `analyze_image` tool is hidden, and the agent uses multimodal capabilities of the main LLM directly (if supported).
- `UAGENT_IMG_ANALYSIS_PROVIDER`: Override the provider for image analysis.

Provider-specific overrides:

- `UAGENT_<PROVIDER>_IMG_ANALYSIS_DEPNAME`
- `UAGENT_<PROVIDER>_IMG_ANALYSIS_API_KEY`
- `UAGENT_<PROVIDER>_IMG_ANALYSIS_BASE_URL`

Allowed providers for `analyze_image`: `openai`, `azure`.

______________________________________________________________________

## Release Notes

- Added optional **auto shrink_llm** (all providers).
  - `UAGENT_SHRINK_CNT` (default: `100`): when the number of non-system messages (user/assistant/tool) reaches this count, uag automatically runs the equivalent of `:shrink_llm`.
  - `UAGENT_SHRINK_CNT=0`: disable auto shrink.
  - `UAGENT_SHRINK_KEEP_LAST` (default: `20`): how many recent non-system messages to keep after summarization.
- Added GPT-5.4+ Responses tool narrowing with `tool_catalog` and a lightweight tools prompt.
- Added smoke tests for MCP server management tools.
- When shrink runs (manual `:shrink` / `:shrink_llm` or auto), the current session log is rewritten to match the compressed in-memory history.
  - A one-generation backup is created under `<log_dir>/.backup/`.

______________________________________________________________________

## For Developers

For developer-focused information, see [`src/uagent/docs/DEVELOP.md`](src/uagent/docs/DEVELOP.md).

Additional docs:

- [`src/uagent/docs/RUNTIME_INIT.md`](src/uagent/docs/RUNTIME_INIT.md) (startup initialization: workdir/banner/long-term memory)
- [`src/uagent/docs/WEB_UI_LOGGING.md`](src/uagent/docs/WEB_UI_LOGGING.md) (Web UI logging/message paths)

______________________________________________________________________

## Web Inspector (playwright_inspector)

You can use Playwright Inspector to capture manual browsing flows (URL transitions / DOM / screenshots / event logs).

Prerequisites:

- `playwright` is installed
- Browser setup is done (e.g. `python -m playwright install`)

Docs:

- [`src/uagent/docs/WEBINSPECTER.md`](src/uagent/docs/WEBINSPECTER.md)
- `uag docs webinspect` (available even in wheel environments)

______________________________________________________________________

## Documentation (`uag docs`)

Even when installed from a wheel (whl), bundled documents are available via `uag docs`.

```bash
uag docs
uag docs webinspect
uag docs develop
uag docs --path webinspect
uag docs --open webinspect
```

______________________________________________________________________

## Install (distribution: wheel)

See **[`QUICKSTART.md`](QUICKSTART.md)** for the Windows-oriented installation steps using a distributed `.whl`.

- Distribution: GitHub **Releases** page (Assets: `.whl`)
- Wheel example: `uag-<VERSION>-py3-none-any.whl`

Example:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install ./uag-<VERSION>-py3-none-any.whl
```

Notes:

- `uag` requires **Python 3.11+**.
- For development use, `python -m pip install -e .`.

______________________________________________________________________
