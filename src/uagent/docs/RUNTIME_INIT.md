# RUNTIME_INIT (shared startup initialization)

This document describes the shared startup-initialization API exposed through `src/uagent/runtime_init.py` (a compatibility/re-export layer). The concrete implementations live in `runtime_workdir.py`, `runtime_banner.py`, `runtime_env.py`, and `runtime_memory.py`.

What it does (shared across CLI/Web/GUI):

- Decide and validate `workdir` (`--workdir/-C`, `UAGENT_WORKDIR`, or auto)
- Validate startup environment when needed (`validate_or_exit_startup_env(context=...)`)
- Create the directory and `chdir`
- Build startup banner text (INFO lines)
- Append personal long-term memory and shared memory as system messages

Design policy:

- `runtime_init.py` should not print directly; it returns strings/flags and the UI decides how to display them.
- `runtime_init.py` also loads `.env` from the current working directory at import time when `python-dotenv` is available.

______________________________________________________________________
