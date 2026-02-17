# RUNTIME_INIT (shared startup initialization)

This document describes the purpose and behavior of `src/uagent/runtime_init.py`.

What it does (shared across CLI/Web/GUI):
- Decide and validate `workdir` (`--workdir/-C`, `UAGENT_WORKDIR`, or auto)
- Create the directory and `chdir`
- Build startup banner text (INFO lines)
- Append personal long-term memory and shared memory as system messages

Design policy:
- `runtime_init.py` should not print directly; it returns strings/flags and the UI decides how to display them.

---
