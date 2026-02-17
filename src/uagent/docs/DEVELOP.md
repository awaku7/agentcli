# DEVELOP (for developers)

This document contains developer notes for **uag** (a local tool-execution agent).

- Entry points:
  - CLI: `python -m uagent` (command: `uag`)
  - GUI: `python -m uagent.gui` (command: `uagg`)
  - Web: `python -m uagent.web` (command: `uagw`)

Key modules:
- Core: `src/uagent/core.py`
- LLM loop / tool execution: `src/uagent/uagent_llm.py`
- Provider/client wiring: `src/uagent/util_providers.py`
- Tool runtime helpers: `src/uagent/util_tools.py`
- Startup initialization: `src/uagent/runtime_init.py`

---
