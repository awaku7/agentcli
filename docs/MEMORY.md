# Memory and Profile Architecture

This document describes the mechanisms, storage, and lifecycle of Long-term Memory, Shared Memory, and User Profiles in **uag**.

______________________________________________________________________

## 1. Overview of Memory Types

| Memory Type | Storage File | Purpose | Management Tools / Commands |
| :--- | :--- | :--- | :--- |
| **Long-term Memory** | `~/.uag/logs/long_memory.jsonl` | Persistent notes about the user or environment. | `add_long_memory`, `get_long_memory` |
| **Shared Memory** | `~/.uag/logs/shared_memory.jsonl` | Shared context across multiple agents or sessions. | `add_shared_memory`, `get_shared_memory` |
| **User Profile** | `scheck_profile.jsonl` | Automatically learned environment, preferences, and constraints. | `:profile`, `:profile-fromlog`, `:profile-clear` |

______________________________________________________________________

## 2. Long-term & Shared Memory

### Session Store (enabled by default)

Session history is stored in SQLite by default for structured search, tool auditing, and summaries. Set `UAGENT_SESSION_BACKEND=jsonl` to use JSONL only, or `dual` to write both formats.

```text
UAGENT_SESSION_STORE=1
UAGENT_SESSION_BACKEND=sqlite
# Unset: user state directory/sessions/sessions.sqlite3
UAGENT_SESSION_STORE_PATH=
UAGENT_MEMORY_BACKEND=sqlite
# Unset: user state directory/memory.sqlite3
UAGENT_MEMORY_DB=
```

The CLI stores user, assistant, and tool messages, tool-call metadata, and session summaries. The project display name is the workspace directory name (for example, `F:\KAIHATSU\agentcli` becomes `agentcli`), while a hashed project key and original path distinguish same-named workspaces. Credentials, tokens, cookies, and common API-key formats are redacted before persistence.

Session memory candidates are extracted only from explicit `remember:` or `記憶:` markers. They are not written to long-term memory unless explicitly approved.

### Mechanism

- **Long-term Memory** is used to store stable, persistent facts (e.g., "The user prefers Python for scripting").
- **Shared Memory** is designed for multi-agent or cross-session collaboration.
- Long-term Memory uses SQLite by default; JSONL remains available as a compatibility backend. Shared Memory uses its configured shared store.
- Provider-facing Memory is selected per turn through the V2 projection path rather than sending every stored note broadly.

### Security Constraint

- **Never store sensitive credentials** (passwords, API keys, tokens) in long-term or shared memory.

### Default turn projection

The runtime prepares a read-only, turn-local projection of profile guidance and
relevant Memory evidence. It does not rewrite the user's original message or add
the projection to durable history.

Memory V2 defaults are:

```env
UAGENT_MEMORY_PROJECTION=1
UAGENT_MEMORY_STRICT_SCOPE=1
UAGENT_MEMORY_OWNER=
UAGENT_MEMORY_PROJECT=
```

`UAGENT_MEMORY_OWNER` is optional. When unset, the current OS login ID is used
as the V2 local owner. On Windows, `USERDOMAIN\\username` is used when the
domain is available. New Memory writes therefore receive an owner even when the
user has not configured one explicitly.

At projection time, legacy records without owner metadata are treated as owned
by the current OS login user. This does not rewrite the stored record. Missing
project metadata is not inferred; project-unknown legacy records are excluded by
Strict Scope.

Set `UAGENT_MEMORY_PROJECTION=0` to roll back to the compatibility path. Set
`UAGENT_MEMORY_STRICT_SCOPE=0` only when intentionally evaluating legacy-unknown
compatibility. See [Memory Evaluation Gates](MEMORY_EVALUATION.md) for the
measured rollout decision.

______________________________________________________________________

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
1. **Normalization**: Items are cleaned, compacted, and summarized if they exceed length limits.
1. **Smart Merge & LLM Deduplication**:
   - Newly extracted findings are merged with the existing profile.
   - To prevent redundant or highly similar items (e.g., "Prefers Python" vs "Prefers Python for scripting"), **uag** uses an LLM-based deduplication function (`_deduplicate_profile_with_llm`).
   - If the LLM deduplication fails or times out, the system gracefully falls back to the original merged list.
1. **Limits**: The maximum number of items in `preferences` and `constraints` is capped at **20** (configured via `UAGENT_PROFILE_MAX_ITEMS`).

______________________________________________________________________

## 4. System Message Injection Order

The compatibility startup path may still construct broad Memory/Profile system
blocks before the provider call. Memory V2 then applies its frozen turn-local
projection at the shared LLM-round boundary:

1. **Base System Prompt**
1. **Compatibility Long-term / Shared Memory / Profile blocks**
1. **Memory V2 projection preparation**
1. **Provider-facing replacement with Applicable User Guidance and selected Memory Evidence**
1. **Active Skill Messages / other runtime context as applicable**

When turn projection is applied, broad startup Memory blocks are removed from
the provider-facing request before relevant evidence is added. Derived
projection content is excluded from durable history.
