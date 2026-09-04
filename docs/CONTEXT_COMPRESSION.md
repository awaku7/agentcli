# Context compression and bounded model context

uag uses several layers to keep the active model context bounded. The goal is to reduce unnecessary input tokens without removing the files, tool results, or session data that the user may still need.

This document describes the current implementation. It also distinguishes deterministic behavior from provider-specific or LLM-assisted behavior.

## 1. Dynamic tool surface

Not every tool definition needs to be sent to the model on every turn.

- `tool_catalog` searches the available capabilities.
- `tool_load` enables only the tools required for the current task.
- `tool_catalog`, `tool_load`, and `unload_tool` remain available as management tools.
- GPT-5.4-compatible Responses API flows can use native server-side Tool Search.
- Legacy Tool Search mode narrows the tool specifications with `tool_catalog` on the client side.

This reduces the input tokens used by tool schemas, especially in installations with many tools.

## 2. Large textual tool results become Artifacts

When a textual tool result exceeds the Artifact threshold, uag stores the complete result as an Artifact and sends the model a bounded reference and preview instead of the full text.

The default limits are:

```text
UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS=100000
UAGENT_TOOL_RESULT_MAX_CHARS=12000
```

The model-visible representation contains the tool name, original length, an `artifact://` reference, the storage path, and a bounded preview. The full result remains available through the Artifact store.

The threshold can be changed with `UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS`. A value of `0` disables Artifact promotion. `UAGENT_TOOL_RESULT_MAX_CHARS` controls the ordinary bounded-result policy; `0` disables that ordinary limit.

## 3. Bounded Artifact retrieval

The `artifact_read` infrastructure tool retrieves only the requested portion of an Artifact:

- `start_line` selects the first line.
- `max_lines` is bounded to 500.
- `max_chars` is bounded to 50,000 characters.
- Both an Artifact ID and an `artifact://` URI can be used.

This makes it possible to inspect a small relevant range instead of reinjecting an entire file or command result into the next model turn.

`artifact_read` is intentionally text-only. If the Artifact is binary, it returns metadata and directs the caller to use one of the binary-safe tools below instead of decoding bytes as UTF-8:

- `artifact_info` returns the media type, size, hash, storage metadata, and session ownership without reading the payload.
- `artifact_export` copies the exact bytes to a workdir-local path and returns a file attachment reference without putting Base64 in the LLM context.

New Artifacts are stored below:

```text
~/.uag/artifacts/
```

Existing legacy Artifact paths remain readable for compatibility.

## 4. Binary payload isolation

Inline binary data is not sent as a textual tool result to the next model turn. Base64-shaped fields are replaced with a short marker such as:

```text
[binary payload omitted from LLM context]
```

The UI and remote clients can still receive in-memory attachments, and saved files remain available through their paths or Artifact references. This prevents images, audio, screenshots, and other binary payloads from inflating the textual model context.

The same class of binary payload is sanitized before SQLite and JSONL persistence, preventing it from returning as a large payload after a session reload.

## 5. Automatic history compression

uag can compress older conversation history when the message count or estimated token count reaches its configured limit.

The compression policy uses:

- the number of non-system messages;
- the model's resolved context window when available;
- `UAGENT_SHRINK_KEEP_LAST` (20 by default);
- `UAGENT_SHRINK_MAX_TOKENS` or a model-specific override;
- `UAGENT_SHRINK_CNT`; and
- `UAGENT_SHRINK_RATIO` (0.5 by default when a context window is known).

A model-specific limit can be supplied as:

```text
UAGENT_SHRINK_MAX_TOKENS_<MODEL_NAME>
```

A previous summary is not regenerated on every turn. Hysteresis requires enough new history to accumulate, or another token-budget overflow, before compression runs again.

## 6. LLM-assisted history summaries

When automatic compression uses the LLM, older user, assistant, and tool messages are summarized into a rolling system message while the recent tail is retained.

Long histories can be summarized in chunks. The relevant controls are:

```text
UAGENT_SHRINK_CHUNK_SIZE=100
UAGENT_SHRINK_SINGLE_SHOT=1
```

The summary is folded forward rather than creating an unbounded sequence of summary messages. This is an LLM-assisted operation and can require additional provider requests.

## 7. Deterministic fallback compression

If an LLM summary is unavailable, uag can keep the leading system messages and only the most recent messages. Tool-call boundaries are repaired so that the resulting history does not begin or end with an orphaned tool call.

The loader and sanitizer also remove model-irrelevant or invalid entries, including UI-only messages, internal control messages, broken log lines, unsupported roles, orphan tool results, and incomplete tool-call blocks.

When a session is reloaded, the current system prompt is restored and only relevant injected system messages, such as skill or hook context, are retained.

## 8. Context-overflow recovery

If a provider reports that the context window was exceeded, uag identifies a large recent history message and rolls back that message and the following history before retrying. This is a reactive fallback, not a replacement for normal budgeting.

## 9. Provider-side continuation and compaction

Where supported, the Responses API uses `previous_response_id` to continue a response chain without resending the entire provider-managed response history from the client.

Responses API flows also send provider-side compaction configuration using the same local shrink threshold. The exact behavior is provider-dependent; local Artifact and history policies remain the provider-neutral safeguards.

## 10. Token-counting efficiency

Token counts used for compression decisions are cached and updated incrementally when only new messages have been added. This does not directly reduce the model context, but it reduces the CPU cost and latency of deciding when compression is necessary.

## What is not yet a complete unified layer

The current implementation does not yet provide all of the following as one provider-neutral manager:

- a unified `ContextManager` and `ContextBudget`;
- a `ToolResultRecord` with importance and eviction metadata;
- semantic summaries that do not require an LLM;
- automatic retrieval and reinjection of relevant Artifacts;
- a central Result Manager guaranteeing Artifact conversion for every binary-producing tool; or
- priority-aware eviction across all system, history, tool-schema, and result categories.

In short, uag currently combines deterministic truncation, Artifact references, binary isolation, dynamic tool selection, history summaries, provider continuation, and overflow recovery. The design roadmap for a unified context layer is documented in [UAG_CONTEXT_MANAGEMENT_DESIGN.md](UAG_CONTEXT_MANAGEMENT_DESIGN.md).
