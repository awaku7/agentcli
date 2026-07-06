# :auto — Automated multi-round execution command

`:auto` makes uag **repeat a task across multiple LLM rounds**.
Use it for long-running analysis, editing, research, or any task that needs more than a single message.

---

## Basic usage

```
:auto <goal> [--max-rounds N]
```

Examples:

```
:auto translate README.md to Japanese
:auto analyze the project codebase and produce a summary
:auto investigate the bug and fix it --max-rounds 20
```

---

## What happens

When `:auto` runs, it starts the following loop:

```
Round 1: LLM executes toward the goal → LLM responds / runs tools
         ↓
        Reviewer asks "goal achieved?"
         ↓ "not yet" → continue

Round 2: "Continue" → LLM runs → reviewer judges
         ↓ "not yet"

Round 3: ... (repeat)
```

Each round has two steps:

| Step | Role |
|---|---|
| **Step A** (main query) | LLM continues working toward the goal |
| **Step B** (reviewer judgment) | A separate LLM call decides "COMPLETE or CONTINUE?" |

---

## How to stop

There are three ways to stop `:auto`:

| Method | Description |
|---|---|
| **`x` key** | Stops immediately, even mid-LLM-response (recommended) |
| **Reviewer says `COMPLETE`** | Auto-pilot stops when the goal is deemed achieved |
| **`--max-rounds N` reached** | Default is 10; change with `--max-rounds` |

Use `:auto off` to cancel before it starts, but use the **`x` key** to stop it while running.

---

## Options

| Option | Default | Description |
|---|---|---|
| `--max-rounds N` | `10` | Maximum number of rounds. Use e.g. `--max-rounds 30` for complex tasks |

---

## Separate LLM for reviewer (optional)

By default, the reviewer (Step B) uses the **same provider and model** as the main query (Step A).
You can specify a **different LLM** for the reviewer via environment variables with the `UAGENT_AP_` prefix.

Example: main = Claude, reviewer = OpenAI GPT-4o-mini

```bash
set UAGENT_PROVIDER=claude
set UAGENT_CLAUDE_API_KEY=sk-ant-...
set UAGENT_AP_PROVIDER=openai
set UAGENT_AP_OPENAI_API_KEY=sk-...
set UAGENT_AP_OPENAI_DEPNAME=gpt-4o-mini
```

Example: main = GPT-4o, reviewer = Gemini Flash (cheaper)

```bash
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=sk-...
set UAGENT_AP_PROVIDER=gemini
set UAGENT_AP_GEMINI_API_KEY=AIza...
set UAGENT_AP_GEMINI_DEPNAME=gemini-2.0-flash
```

How it works:

- Set `UAGENT_AP_PROVIDER` to the desired reviewer provider.
- Any `UAGENT_AP_*` variable is mapped to `UAGENT_*` (without `AP_`) when creating the reviewer client.
- If `UAGENT_AP_PROVIDER` is not set, the reviewer uses the same LLM as the main query (default behavior).
- Any provider supported by `make_client()` can be used; see [ENVIRONMENT.md](ENVIRONMENT.md) for provider-specific variables.

---

## Tips

### Write specific goals

- Good: `:auto refactor src/ to pass all existing tests`
- Bad: `:auto fix it`

The more specific the goal, the easier it is for the reviewer to say "COMPLETE".

### Give enough rounds

Complex tasks may need many rounds. Start with the default (10) and increase if needed.

### Combine with other commands

Press `x` during auto-pilot to interrupt, then manually adjust before continuing.

---

## How it works (brief architecture)

```
CLI: ":auto translate README to Japanese"
  │
  ├─ _handle_cmd_auto()          # parse goal, set flags
  ├─ run_llm_rounds()            # Step A: first LLM execution
  └─ _run_auto_pilot_loop()      # loop control
       │
       ├─ run_llm_rounds()        # Step A: continued LLM execution
       └─ _ask_reviewer_judgment() # Step B: reviewer judgment
            └─ run_llm_rounds(judgment_mode=True)  # separate context
```

- Main query and reviewer judgment use the **same provider and API path** (Responses API included).
- Reviewer judgment runs in a **separate message context**; it does not modify the conversation history.

---

## Notes

- `:auto` calls the LLM API **twice per round** (Step A + Step B).
  More rounds = higher API costs.
- Tool execution (file read/write, etc.) only happens in Step A.
  The reviewer judgment (Step B) does not execute any tools.
