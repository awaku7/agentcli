```
██╗   ██╗ █████╗  ██████╗ ███████╗███╗   ██╗████████╗ ██████╗██╗     ██╗
██║   ██║██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝██╔════╝██║     ██║
██║   ██║███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   ██║     ██║     ██║
██║   ██║██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   ██║     ██║     ██║
╚██████╔╝██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   ╚██████╗███████╗██║
 ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝╚══════╝╚═╝
```

# uag (Local Tool-Execution Agent)

uag is an interactive local agent that can execute commands, manipulate files, and read various data formats (PDF/PPTX/Excel, etc.) on your PC.

- CLI: `uag` / `python -m uagent`
- GUI: `uagg` / `python -m uagent.gui`
- Web: `uagw` / `python -m uagent.web`

---

## Minimal Usage

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

---

## History compression (manual / auto)

Manual commands:
- `:shrink [keep_last]` (default `keep_last=40`): keep the last N non-system messages and drop the rest.
- `:shrink_llm [keep_last]` (default `keep_last=20`): summarize older history into one system message and keep the last N non-system messages.

Optional auto shrink (OpenAI-compatible providers only; disabled for Gemini/Claude):
- `UAGENT_SHRINK_CNT` (default: `100`)
  - When the number of non-system messages (user/assistant/tool) reaches this count, uag automatically runs the equivalent of `:shrink_llm`.
  - Set `0` to disable.
- `UAGENT_SHRINK_KEEP_LAST` (default: `20`): how many recent non-system messages to keep after auto summarization.

Log rewrite behavior:
- When shrink runs, the current session log (`UAGENT_LOG_FILE` / `core.LOG_FILE`) is rewritten to match the compressed in-memory history.
- A one-generation backup is created under `<log_dir>/.backup/`.


---

## Provider (OpenAI-compatible handling)

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

- `UAGENT_PROVIDER=claude` uses **Anthropic Claude**.
  - Required: `UAGENT_CLAUDE_API_KEY`
  - Optional: `UAGENT_CLAUDE_DEPNAME`

See `env.sample.*` for provider/key configuration examples.

---

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

---

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

Allowed providers for `analyze_image`: `openai`, `azure`, `gemini`, `nvidia`.

---

## Release Notes

- Added optional **auto shrink_llm** (for OpenAI-compatible providers only).
  - `UAGENT_SHRINK_CNT` (default: `100`): when the number of non-system messages (user/assistant/tool) reaches this count, uag automatically runs the equivalent of `:shrink_llm`.
  - `UAGENT_SHRINK_CNT=0`: disable auto shrink.
  - `UAGENT_SHRINK_KEEP_LAST` (default: `20`): how many recent non-system messages to keep after summarization.
  - Auto shrink is disabled for `UAGENT_PROVIDER=gemini` and `UAGENT_PROVIDER=claude`.
- When shrink runs (manual `:shrink` / `:shrink_llm` or auto), the current session log is rewritten to match the compressed in-memory history.
  - A one-generation backup is created under `<log_dir>/.backup/`.


---

## For Developers

For developer-focused information, see [`src/uagent/docs/DEVELOP.md`](src/uagent/docs/DEVELOP.md).

Additional docs:
- [`src/uagent/docs/RUNTIME_INIT.md`](src/uagent/docs/RUNTIME_INIT.md) (startup initialization: workdir/banner/long-term memory)
- [`src/uagent/docs/WEB_UI_LOGGING.md`](src/uagent/docs/WEB_UI_LOGGING.md) (Web UI logging/message paths)

---

## Web Inspector (playwright_inspector)

You can use Playwright Inspector to capture manual browsing flows (URL transitions / DOM / screenshots / event logs).

Prerequisites:
- `playwright` is installed
- Browser setup is done (e.g. `python -m playwright install`)

Docs:
- [`src/uagent/docs/WEBINSPECTER.md`](src/uagent/docs/WEBINSPECTER.md)
- `uag docs webinspect` (available even in wheel environments)

---

## Documentation (`uag docs`)

Even when installed from a wheel (whl), bundled documents are available via `uag docs`.

```bash
uag docs
uag docs webinspect
uag docs develop
uag docs --path webinspect
uag docs --open webinspect
```

---

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
- For development use, `python -m pip install -e .` (or `python -m pip install -e \".[web]\"` if you use the Web UI).

---
