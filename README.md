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

## Release Notes

- Fixed an issue where `[REPLY] >` could appear twice in CLI confirmation prompts.

---

## For Developers

For developer-focused information, see `src/uagent/docs/DEVELOP.md`.

Additional docs:
- `src/uagent/docs/RUNTIME_INIT.md` (startup initialization: workdir/banner/long-term memory)
- `src/uagent/docs/WEB_UI_LOGGING.md` (Web UI logging/message paths)

---

## Web Inspector (playwright_inspector)

You can use Playwright Inspector to capture manual browsing flows (URL transitions / DOM / screenshots / event logs).

Prerequisites:
- `playwright` is installed
- Browser setup is done (e.g. `python -m playwright install`)

Docs:
- `src/uagent/docs/WEBINSPECTER.md`
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

See **`QUICKSTART.md`** for the Windows-oriented installation steps using a distributed `.whl`.

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
