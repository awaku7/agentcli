# QUICKSTART (uag / Windows)

This document explains how to install `uag` from **PyPI** with `pip` and verify the minimum setup using the CLI (`uag`).

Target OS: Windows

______________________________________________________________________

## 1. Prerequisites

- Python **3.11+** (`requires-python = ">=3.11"` in `pyproject.toml`)
- (Recommended) Use a virtual environment (venv)
- After installation, start with `uag` (or `python -m uagent` if `uag` is not found)

______________________________________________________________________

## 2. Install Git (required)

`uag` checks that Git is installed at startup. Install Git beforehand.

### 2.1 Git for Windows

1. Download the installer from https://git-scm.com/download/
1. After installation, open a **new terminal** and verify:

```bat
git --version
```

### 2.2 If winget is available

```bat
winget install --id Git.Git -e
```

______________________________________________________________________

## 3. Create a virtual environment (recommended)

Run in the working folder where you want to use `uag`:

```bat
python -m venv .venv
.\.venv\Scripts\activate
```

(If you use PowerShell, you may need to update the execution policy and then re-run `activate`.)

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

______________________________________________________________________

## 4. Install `uag` from PyPI with pip

Upgrade pip first if needed:

```bat
python -m pip install --upgrade pip
```

Install `uag`:

```bat
python -m pip install uag
```

If you want to pin a version:

```bat
python -m pip install "uag==0.4.6"
```

______________________________________________________________________

## 5. Verify installation

```bat
uag --help
where uag
python -c "import uagent; print(getattr(uagent, '__version__', 'ok'))"
```

If `where uag` does not find the command, you can start with:

```bat
python -m uagent --help
```

______________________________________________________________________

## 6. Start and minimal configuration (CLI)

### 6.1 Start

```bat
uag
```

### 6.1.1 (Optional) Start A2A server

A2A runs as a separate process and does not change the existing `uag` behavior.

```bat
set UAGENT_A2A_TOKEN=YOUR_TOKEN
uaga
```

See [ENVIRONMENT.md](ENVIRONMENT.md) for `UAGENT_A2A_*` settings such as auth, host, port, reload, public base URL, concurrency, and engine.

If `uag` is not found:

```bat
python -m uagent
```

Exit:

- `:exit`

### 6.2 Minimum required environment variables

`uag` will exit if no LLM provider configuration is provided.

- Required: `UAGENT_PROVIDER`
- Required: the API key corresponding to the selected `UAGENT_PROVIDER` (e.g. `UAGENT_OPENAI_API_KEY`)

Minimal example (OpenAI):

```bat
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=YOUR_API_KEY
uag
```

Sample files are available under `samples/`:

- Canonical template: `samples/env.sample.env`
- Generated shell variants: `samples/env.sample.sh` / `samples/env.sample.ps1` / `samples/env.sample.bat`
- Provider-specific templates: `samples/provider.*.env.sample`
- Usage details: `samples/README.md`

Recommended (wheel/pip install): run `uag_setup` to generate a `.env` (and optionally `env.sh` / `env.ps1` / `env.bat`) in the current directory.
If required provider variables are missing, `uag` will automatically launch the setup wizard and re-check the environment after you finish it.

```bat
uag_setup
```

(Repository development) Run the interactive wizard (numbered selection + back `b`) to generate/update shell-specific variants under `samples/` with the intended encoding/newlines:

```bat
python samples/generate_env_samples.py
```

### 6.3 (Optional) Responses API knobs (reasoning / verbosity)

If you use the **Responses API** (`UAGENT_RESPONSES=1`) with Azure/OpenAI/Bedrock/OpenRouter/Ollama, you can optionally control reasoning effort and output verbosity.

For Bedrock, uag uses a Bedrock-specific Responses request builder (string `input`) to avoid OpenAI-compatible gateway validation errors for message-list `input`.

For other providers, uag falls back to the provider-specific or ChatCompletions path at runtime. Gemini / Claude / Vertex AI use their native APIs and ignore `UAGENT_RESPONSES`.

Example:

```bat
set UAGENT_RESPONSES=1
set UAGENT_REASONING=auto
set UAGENT_VERBOSITY=medium
```

In-session commands (CLI/GUI/Web):

- `:r [0|1|2|3|auto|minimal|xhigh]` (no arg: keep current)
- `:v [0|1|2|3]` (no arg: keep current)

For details, see the "Optional Responses API knobs (reasoning / verbosity)" section in [`README.md`](README.md).

### 6.4 (Optional) Auto shrink_llm

If you frequently hit context limits, you can enable automatic summarization.

- `UAGENT_SHRINK_CNT` (default: `100`)
  - When the number of non-system messages (user/assistant/tool) reaches this count, uag automatically runs the equivalent of `:shrink_llm`.
  - Set `0` to disable.
- `UAGENT_SHRINK_KEEP_LAST` (default: `20`)
  - How many recent non-system messages to keep after summarization.

Notes:

- Auto shrink works for all providers.
- When shrink runs (manual or auto), the current session log is rewritten to match the compressed history, and a one-generation backup is created under `<log_dir>/.backup/`.

For provider-specific details (required environment variables, base URL, model settings, etc.), see:

- [`README.md`](README.md) (Provider section)
- [`AGENTS.md`](AGENTS.md) (list of environment variables)

______________________________________________________________________

## 7. Smoke test prompts (examples)

Notes:

- In this environment, you can restore the previous conversation with `:load 0`.

After starting `uag`, type instructions at the prompt.

Examples:

- Explore the folder structure
  - "Analyze this folder and tell me important files, structure, and how to run it."
- Read a specific file
  - "Read [`README.md`](README.md) and summarize the key points."

______________________________________________________________________

## 8. Next to read

- [`README.md`](README.md) (overview / Provider / Web Inspector, etc.)
- [`AGENTS.md`](AGENTS.md) (tools list / environment variables / MCP shortest example)
- `uag docs develop` / `uag docs webinspect`

______________________________________________________________________

## 9. Documentation (`uag docs`)

After installation, bundled documents are available via `uag docs`.

```bat
uag docs
uag docs webinspect
uag docs develop
uag docs --open webinspect
```
