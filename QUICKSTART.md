# QUICKSTART (uag / Windows)

This document explains how to install a distributed `uag` wheel (`uag-<VERSION>-py3-none-any.whl`) with **pip**, and verify the minimum setup using the CLI (`uag`).

Target OS: Windows

---

## 6. Install Git (required)

`uag` checks that Git is installed at startup. Install Git beforehand.

### 6.1 Git for Windows

1. Download the installer from https://git-scm.com/download/win
2. After installation, open a **new terminal** and verify:

```bat
git --version
```

### 6.2 If winget is available

```bat
winget install --id Git.Git -e
```

---

## 7. Start and minimal configuration (CLI)

### 7.1 Start

```bat
uag
```

If `uag` is not found:

```bat
python -m uagent
```

Exit:

- `:exit`

### 7.2 Minimum required environment variables

`uag` will exit if no LLM provider configuration is provided.

- Required: `UAGENT_PROVIDER`
- Required: the API key corresponding to the selected `UAGENT_PROVIDER` (e.g. `UAGENT_OPENAI_API_KEY`)

Minimal example (OpenAI):

```bat
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=YOUR_API_KEY
uag
```

### 7.3 (Optional) Auto shrink_llm

If you frequently hit context limits, you can enable automatic summarization.

- `UAGENT_SHRINK_CNT` (default: `100`)
  - When the number of non-system messages (user/assistant/tool) reaches this count, uag automatically runs the equivalent of `:shrink_llm`.
  - Set `0` to disable.
- `UAGENT_SHRINK_KEEP_LAST` (default: `20`)
  - How many recent non-system messages to keep after summarization.

Notes:
- Auto shrink is **disabled** when `UAGENT_PROVIDER=gemini` or `UAGENT_PROVIDER=claude`.
- When shrink runs (manual or auto), the current session log is rewritten to match the compressed history, and a one-generation backup is created under `<log_dir>/.backup/`.

For provider-specific details (required environment variables, base URL, model settings, etc.), see:

- [`README.md`](README.md) (Provider section)
- [`AGENTS.md`](AGENTS.md) (list of environment variables)

---

## 8. Smoke test prompts (examples)

Notes:
- In this environment, you can restore the previous conversation with `:load 0`.

After starting `uag`, type instructions at the prompt.

Examples:

- Explore the folder structure
  - "Analyze this folder and tell me important files, structure, and how to run it."
- Read a specific file
  - "Read [`README.md`](README.md) and summarize the key points."

---

## 9. Next to read

- [`README.md`](README.md) (overview / Provider / Web Inspector, etc.)
- [`AGENTS.md`](AGENTS.md) (tools list / environment variables / MCP shortest example)
- `uag docs develop` / `uag docs webinspect`

---

## 0. Documentation (`uag docs`)

After installation, bundled documents are available via `uag docs`.

```bat
uag docs
uag docs webinspect
uag docs develop
uag docs --open webinspect
```

---

## 1. Prerequisites

- Python **3.11+** (`requires-python = ">=3.11"` in `pyproject.toml`)
- (Recommended) Use a virtual environment (venv)
- After installation, start with `uag` (or `python -m uagent` if `uag` is not found)

---

## 2. Prepare a working folder

- Place the distributed `uag-<VERSION>-py3-none-any.whl` into a working folder
- Run the commands below in that folder

---

## 3. Create a virtual environment (recommended)

Run in the working folder:

```bat
python -m venv .venv
.\\.venv\\Scripts\\activate
```

(If you use PowerShell, you may need to update the execution policy and then re-run `activate`.)

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

---

## 4. Install the wheel with pip

Check the wheel file name:

```bat
dir *.whl
```

Install specifying the file name:

```bat
python -m pip install .\\uag-<VERSION>-py3-none-any.whl
```

(If there is only one wheel file, this is also fine.)

```bat
python -m pip install .\\uag-*.whl
```

---

## 5. Verify installation

```bat
uag --help
where uag
python -c \"import uagent; print(getattr(uagent, '__version__', 'ok'))\" 
```

If `where uag` does not find the command, you can start with:

```bat
python -m uagent --help
```

---
