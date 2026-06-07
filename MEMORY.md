# Memory and Profile Architecture

This document describes the mechanisms, storage, and lifecycle of Long-term Memory, Shared Memory, and User Profiles in **uag**.

---

## 1. Overview of Memory Types

| Memory Type | Storage File | Purpose | Management Tools / Commands |
| :--- | :--- | :--- | :--- |
| **Long-term Memory** | `~/.uag/logs/long_memory.jsonl` | Persistent notes about the user or environment. | `add_long_memory`, `get_long_memory` |
| **Shared Memory** | `~/.uag/logs/shared_memory.jsonl` | Shared context across multiple agents or sessions. | `add_shared_memory`, `get_shared_memory` |
| **User Profile** | `scheck_profile.jsonl` | Automatically learned environment, preferences, and constraints. | `:profile`, `:profile-fromlog`, `:profile-clear` |

---

## 2. Long-term & Shared Memory

### Mechanism
- **Long-term Memory** is used to store stable, persistent facts (e.g., "The user prefers Python for scripting").
- **Shared Memory** is designed for multi-agent or cross-session collaboration.
- Both are stored as JSONL files under the logs directory.
- At startup, these memories are loaded and appended to the LLM's system messages.

### Security Constraint
- **Never store sensitive credentials** (passwords, API keys, tokens) in long-term or shared memory.

---

## 3. User Profile (Profiling System)

The profiling system automatically analyzes conversation logs to learn about the user's setup and preferences without manual intervention.

### Structure
The profile is stored as a single JSON object in `scheck_profile.jsonl` with the following schema:
```json
{
  "environment": {
    "os": "Windows",
    "shell": "pwsh",
    "editor": "VS Code"
  },
  "preferences": [
    "Prefers concise responses",
    "Prefers Japanese for communication"
  ],
  "constraints": [
    "Do not store secrets in long-term memory"
  ]
}
```

### Lifecycle & Smart Merge
1. **Extraction**: A background thread (`run_profiling_async`) periodically runs after conversation rounds to extract new profile findings using the LLM.
2. **Normalization**: Items are cleaned, compacted, and summarized if they exceed length limits.
3. **Smart Merge & LLM Deduplication**:
   - Newly extracted findings are merged with the existing profile.
   - To prevent redundant or highly similar items (e.g., "Prefers Python" vs "Prefers Python for scripting"), **uag** uses an LLM-based deduplication function (`_deduplicate_profile_with_llm`).
   - If the LLM deduplication fails or times out, the system gracefully falls back to the original merged list.
4. **Limits**: The maximum number of items in `preferences` and `constraints` is capped at **20** (configured via `UAGENT_PROFILE_MAX_ITEMS`).

---

## 4. System Message Injection Order

When a new LLM session starts, system messages are injected in the following strict order to establish the agent's persona and context:

1. **Base System Prompt** (Core instructions and safety guidelines)
2. **Long-term Memory Messages** (Loaded from `long_memory.jsonl`)
3. **Shared Memory Messages** (Loaded from `shared_memory.jsonl`)
4. **User Profile Message** (Formatted as `[USER PROFILE] ...`)
5. **Active Skill Messages** (Injected via `:skills` if a skill is active)
