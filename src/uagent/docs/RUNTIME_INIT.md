# RUNTIME_INIT (shared startup initialization)

This document describes the shared startup-initialization helpers exposed from `src/uagent/runtime_init.py`.

`runtime_init.py` is a compatibility/re-export layer. The concrete implementations live in:

- `runtime_workdir.py`
- `runtime_banner.py`
- `runtime_env.py`
- `runtime_memory.py`

What it covers (shared across CLI/Web/GUI):

- decide and validate `workdir` (`--workdir/-C`, `UAGENT_WORKDIR`, or auto)
- validate startup environment when needed (`validate_or_exit_startup_env(context=...)`)
- create the directory and `chdir`
- build startup banner text
- append personal long-term memory and shared memory as system messages
- load `.env` and `.env.sec` from the current working directory at import time when `python-dotenv` is available

Design policy:

- `runtime_init.py` does not print by itself; helpers return values and UI code decides how to display them.
- Import-time environment loading is best-effort. `.env` is loaded first with `override=False`, then `.env.sec` is decrypted and loaded with `override=True`.
- If `.uagent.key` exists in the current working directory, it is used to decrypt `.env.sec`.
- If the `.env.sec` sync prompt appears later and the user declines (`n` / `N`), the startup `UAGENT_*` snapshot is restored for the session and `.env.sec` is not updated.

______________________________________________________________________

## 1. Import-time environment loading

`runtime_init.py` loads environment files from the current working directory as soon as it is imported.

Load order:

1. `.env` if it exists (`override=False`)
1. `.env.sec` if it exists (decrypt and then `override=True`)

Notes:

- `.env.sec` is decrypted via `uag_envsec.secret_core.decrypt_text`.
- If `.uagent.key` exists in the current working directory, it is used as the key file.
- If decryption fails, a warning is printed to stderr:
  - `[WARN] Failed to decrypt .env.sec: ...`

______________________________________________________________________

## 2. Workdir decisions

### 2.1 Priority

`decide_workdir()` resolves the working directory in this order:

1. CLI argument: `--workdir` / `-C`
1. Environment variable: `UAGENT_WORKDIR`
1. Auto: the current directory (`./` as an absolute path)

### 2.2 Safety check

- If the resolved path already exists and is a file, `decide_workdir()` raises `NotADirectoryError`.

### 2.3 API

- `decide_workdir(cli_workdir: Optional[str], env_workdir: Optional[str]) -> WorkdirDecision`

`WorkdirDecision` contains:

- `chosen`: the original selection (CLI / ENV / auto)
- `chosen_source`: `"CLI"` / `"ENV(UAGENT_WORKDIR)"` / `"auto"`
- `chosen_expanded`: the `expanduser()`-resolved path

### 2.4 Apply workdir

`apply_workdir()` creates the directory and changes the current process directory.

- `os.makedirs(..., exist_ok=True)`
- `os.chdir(...)`

API:

- `apply_workdir(decision: WorkdirDecision) -> None`

______________________________________________________________________

## 3. Startup banner

`build_startup_banner()` generates the INFO/WARN lines shown during startup.

Representative output:

- `[INFO] workdir = ... (source: ...)`
- `[INFO] provider = ...`
- provider-specific lines:
  - `azure`: `base_url` + `api_version`
  - `openai` / `openrouter` / `grok` / `nvidia` / `bedrock` / `ollama`: `base_url`
  - `vertexai`: `project` + `location`
- If `UAGENT_RESPONSES=1` is set and the selected provider is not one of `azure`, `openai`, `bedrock`, `openrouter`, or `ollama` (excluding `gemini`, `claude`, and `vertexai`), a warning is appended:
  - `[WARN] UAGENT_RESPONSES=1 is set, but provider '...' does not support Responses API. Falling back to ChatCompletions.`
- `[INFO] LLM streaming = enabled` or `disabled`

API:

- `build_startup_banner(core, workdir: str, workdir_source: str) -> str`

Notes:

- Secrets such as API keys are never printed.
- `core.normalize_url()` is used when available; otherwise URLs are trimmed conservatively.
- `build_startup_banner()` does **not** print the Responses/ChatCompletions mode line itself. CLI/Web/GUI may print that separately after the banner.

______________________________________________________________________

## 4. Long-term memory system messages

`append_long_memory_system_messages()` consolidates the personal/shared long-term memory loading path.

- Personal long-term memory is loaded via `tools.long_memory`
- Shared memory is loaded via `tools.shared_memory` only when enabled
- Any generated system message is appended to `messages`
- Added messages are also passed to `core.log_message()`

API:

- `append_long_memory_system_messages(...) -> Dict[str, bool]`

Returned flags:

- `shared_enabled`: whether shared memory is enabled (`shared_memory_mod.is_enabled()`)

Notes:

- The function does not print.
- The function swallows internal exceptions and leaves warning handling to the caller.
- The current implementation does **not** prefix shared-memory content with a special label.
- The current implementation does **not** return `personal_appended` / `shared_appended` flags.

______________________________________________________________________

## 5. UI integration points

- CLI: `cli.py` uses these helpers inside startup capture before the main session loop.
- Web: `web.py` uses the same helpers during startup and history initialization.
- GUI: `gui.py` uses the same helpers during startup and worker initialization.

______________________________________________________________________

## 6. Exported names

`runtime_init.py` re-exports the common helpers used by the UIs:

- `WorkdirDecision`
- `apply_workdir`
- `decide_workdir`
- `build_startup_banner`
- `validate_or_exit_startup_env`
- `append_long_memory_system_messages`
