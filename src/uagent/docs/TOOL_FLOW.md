# Tool Sending Flow

This document describes how uagent selects, sends, loads, unloads, and manages tools across providers and API modes. It also documents the Responses API lifecycle and continuation state.

## Overview

The way tools are sent to an LLM depends on the provider and the selected mode.

## Tool-dispatch modes

### A. Chat Completions API (for example, DeepSeek)

```python
req_tools = tools.get_tool_specs() if send_tools_this_round else None
```

- `tools.get_tool_specs()` returns all currently registered tools from `TOOL_SPECS`.
- Registration is controlled by `tool_level`, `tool_genre`, and the genre mask.
- By default, only core tools are registered. Other tools are loaded dynamically through `tool_catalog` and `tool_load`.
- `UAGENT_GPT54_TOOL_SEARCH` has no effect in this mode.

### B. Responses API + OpenAI/Azure + GPT-5.4 or later (default: native mode)

```python
responses_tool_specs = None  # build_responses_request calls get_tool_specs()
```

- All tool specifications are sent to the server and server-side `tool_search` narrows them.
- Management tools (`tool_catalog`, `tool_load`, and `unload_tool`) are included.
- Auto-unload is skipped when `_is_gpt54_tool_search_target()` is true.
- Compaction is applied automatically according to `_get_shrink_max_tokens()` thresholds.

### C. Responses API + OpenAI/Azure + GPT-5.4 or later + legacy mode

Set:

```text
UAGENT_GPT54_TOOL_SEARCH=legacy
```

```python
responses_tool_specs = _select_tool_specs_legacy(call_messages)
```

- Initially, only `tool_catalog`, `tool_load`, `unload_tool`, and `human_ask` are sent.
- The LLM searches for a required tool with `tool_catalog`, then loads it with `tool_load`.
- `_select_tool_specs_legacy()` narrows the initial tool set using the user message.

### D. Responses API + OpenAI/Azure + GPT-5.4 or later + native mode

Set:

```text
UAGENT_GPT54_TOOL_SEARCH=native
```

- All tools are sent, as in mode B.
- Management tools are omitted because server-side `tool_search` is used.
- `_should_preload_lazy_specs()` becomes true, bypassing genre filtering and forcing all tools to be registered.

## Mode selection

| Mode | `_get_gpt54_tool_search_mode()` | `_should_preload_lazy_specs()` | Notes |
|---|---|---:|---|
| Default (A/B) | `native` | `False` | See the native paths |
| Legacy (C) | `legacy` | `False` | Must be explicitly selected |
| Native (D) | `native` | `True` | Requires `UAGENT_GPT54_TOOL_SEARCH=native` |

## Auto-unload skip conditions

Auto-unload is performed only when the following condition is false:

```python
if not (
    _should_preload_lazy_specs()
    or _is_gpt54_tool_search_target(...)
    or bool(core.responses_state.get("previous_response_id"))
):
    # auto-unload
```

Auto-unload is skipped when any of these conditions is true:

1. `_should_preload_lazy_specs()` is true (explicit native mode).
1. `_is_gpt54_tool_search_target()` is true (OpenAI/Azure + GPT-5.4 or later Responses API).
1. `previous_response_id` is set (Responses API continuation for any provider).

## Dynamic loading with `tool_catalog`

Instead of sending every tool to the LLM at the start, tools can be loaded on demand.

### Flow

1. Initially, only `tool_catalog`, `tool_load`, `unload_tool`, and `human_ask` are sent.
1. When the LLM calls `tool_catalog`, it receives the available-tool list.
   - With a `query`, the highest-scoring unloaded tool may be loaded automatically.
   - The response contains the automatically loaded tool name in `auto_loaded`.
   - The tool's `loaded` field is set to `true`.
1. Other required tools can be loaded explicitly with `tool_load(tool_name)`.
1. Loaded tools are added to the tool list for subsequent rounds.
1. A tool can be explicitly removed with `unload_tool(tool_name)`.
1. A tool that has not been used for the configured number of rounds is automatically unloaded. The default is 10 rounds, controlled by `UAGENT_AUTO_UNLOAD_ROUNDS`.

Automatically loaded tools are also eligible for auto-unload because they are registered in `_LOADED_SINGLE_TOOLS`.

### Applicability

| Case | Is `tool_catalog` used? |
|---|---|
| Chat Completions API (for example, DeepSeek) | Yes; remaining tools are loaded dynamically after genre filtering |
| Responses API + GPT-5.4 or later (default) | No; all tools are sent and the server performs `tool_search` |
| Responses API + GPT-5.4 or later + `legacy` | Yes; `_select_tool_specs_legacy()` uses it explicitly |
| Responses API + GPT-5.4 or later + `native` | No; `tool_catalog` itself is omitted |

### Implementation

- `tool_catalog`, `tool_load`, and `unload_tool` are implemented in `tools/catalog_tool.py`.
- These tools belong to the `devel` genre and use `tool_level=0`, so they are always enabled.
- `_select_tool_specs_legacy()` analyzes user messages and adds related tools to the initial set.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `UAGENT_GPT54_TOOL_SEARCH` | unset (`native`) | `native`, `legacy`, or `off` |
| `UAGENT_RESPONSES` | automatic | Set to `1` to force Responses API support |
| `UAGENT_AUTO_UNLOAD_ROUNDS` | `10` | Number of unused rounds before unloading a tool |

# Responses API management and state

This section documents the common Responses API management interface, provider support, and JSONL continuation-state policy. The tool-flow sections above remain authoritative for tool dispatch.

## Management design

Responses management is implemented as a provider-independent interface. OpenAI and Azure currently provide the strongest support. The interface is separate from the normal Responses Create path and covers Retrieve, Cancel, Delete, List input items, Count input tokens, and Compact operations where supported.

## Scope and implementation status

### P0 implemented

- Common management interface
- OpenAI and Azure support
- Retrieve a response
- Cancel a response
- Count input tokens
- Integration with `previous_response_id`
- Ctrl-C and Web Stop integration

### Phase 2

- Manual compact
- Capability switching between server compact and local shrinking
- Capability support for OpenRouter, DeepSeek, and Bedrock

### Phase 3

- List input items
- Delete a response
- Live verification for Ollama, Alibaba/Qwen, LM Studio, and Sakana

### Out of scope

- A Responses API implementation for llama.cpp
- Full conversion between Responses API and Chat Completions
- Abstracting every provider-specific API feature

## Common interface

A provider-management module is kept separate from the existing `client.responses.create()` path.

```python
class ResponsesManager(Protocol):
    def retrieve(self, response_id: str) -> Any: ...
    def cancel(self, response_id: str) -> Any: ...
    def delete(self, response_id: str) -> Any: ...
    def list_input_items(
        self, response_id: str, *, limit: int | None = None
    ) -> list[Any]: ...
    def count_input_tokens(
        self, *, model: str, input: Any, tools: list[dict] | None = None
    ) -> int: ...
    def compact(self, response_id: str) -> Any: ...
```

The manager receives the provider's OpenAI SDK client. If an operation is unsupported, it returns `UnsupportedResponsesOperation`; it must not silently fall back to Chat Completions.

## Capabilities

Capabilities describe which management operations are available for a provider and model.

```python
@dataclass(frozen=True)
class ResponsesCapabilities:
    create: bool = False
    streaming: bool = False
    retrieve: bool = False
    cancel: bool = False
    delete: bool = False
    list_input_items: bool = False
    count_input_tokens: bool = False
    compact: bool = False
    previous_response_id: bool = False
```

Initial capability matrix:

| Provider | Create | Retrieve | Cancel | Count tokens | Compact | Previous ID |
|---|---:|---:|---:|---:|---:|---:|
| OpenAI | yes | yes | yes | yes | yes | yes |
| Azure | yes | yes | yes | yes | yes | yes |
| OpenRouter | yes | no | no | no | no | no |
| DeepSeek | yes | no | no | no | no | no |
| Bedrock | yes | unknown | unknown | unknown | unknown | unknown |
| Ollama | yes | unknown | unknown | unknown | unknown | unknown |
| Alibaba / Qwen | probe | unknown | unknown | unknown | unknown | unknown |
| LM Studio | probe | no | no | no | no | no |
| Sakana / Fugu | yes | unknown | unknown | unknown | unknown | unknown |
| llama.cpp | no | no | no | no | no | no |

`unknown` means that the feature has not been verified and is treated as unsupported until live verification succeeds.

## Response state

The existing `responses_state` is retained and extended with management information:

```json
{
  "provider": "openai",
  "model": "gpt-5.4",
  "previous_response_id": "resp_...",
  "active_response_id": "resp_...",
  "active_response_started_at": 0,
  "last_response_status": "completed"
}
```

### State updates

- At Create start, `active_response_id` is unset.
- On successful Create, save `previous_response_id` and `active_response_id`.
- On successful Cancel, set `last_response_status=cancelled` and discard the continuation ID.
- If Retrieve returns 404 or an expired response, discard the continuation ID and start a new session.
- Do not reuse an ID after changing provider or model.
- If tool continuation fails, use the existing `clear_responses_continuation()` path.

### Storage policy

- Never store API keys or prompt contents.
- Store only the response ID, provider, model, status, and timestamps.
- Use the existing provider/model-specific state file until JSONL migration is complete.

## Cancel

```text
User Ctrl-C / Web Stop
  -> read active_response_id
  -> check Capability.cancel
  -> call responses.cancel(response_id)
  -> stop local streaming/waiting as well
  -> clear active_response_id
  -> do not reuse an incomplete previous_response_id
```

If Cancel is unsupported or no response ID exists, perform only local interruption and notify the user that provider-side cancellation is unavailable.

## Retrieve

Retrieve is used for saved `previous_response_id` validation at startup, before resuming a session, for status commands, and when a response must be verified before cancellation.

- A 404, expired response, or provider mismatch clears the saved ID and starts a new session.
- A network error preserves the ID and is treated as retryable.

## Count input tokens

Use the following priority order:

1. The provider's Responses token-count API.
1. The local `llmcapa` estimate.
1. A conservative context-limit threshold when the count is unknown.

When images, tool schemas, or reasoning settings are present, prefer the provider result. Unsupported APIs must not disable the existing local shrinking behavior.

## Compact

- OpenAI/Azure: use server-side compact.
- OpenRouter/DeepSeek: do not use server-side compact.
- Unverified providers: fall back to local shrinking.
- Manual compact is exposed through the UI command when available.

After compact, save the returned response ID as the next `previous_response_id`. If compact fails, do not immediately discard the old ID; retry or choose local shrinking.

## Error handling

| Error | Handling |
|---|---|
| Unsupported | Fall back locally and record a debug message |
| 404 / invalid response ID | Discard the continuation ID and start a new session |
| 401 / 403 | Notify the user; do not retry automatically |
| 429 | Follow the existing rate-limit retry policy |
| Timeout / network error | Preserve the ID and treat it as retryable |
| Malformed response | Discard the ID safely and preserve diagnostic information |

## Testing plan

### Unit tests

- Capability selection
- ID discard when provider or model changes
- Retrieve success, 404, and timeout
- Cancel success, unsupported operation, and missing ID
- Token-count API success, failure, and local fallback
- Compact support and fallback
- State-file save and load

### Mock integration tests

- OpenAI Responses manager
- Azure Responses manager
- Ctrl-C through Cancel API
- Cancellation during streaming
- ID discard after interrupted tool continuation

### Live verification

1. OpenAI
1. Azure OpenAI
1. OpenRouter
1. DeepSeek
1. Bedrock

Features that cannot be verified live remain `unknown` and are not enabled implicitly.

## Implementation order

1. Add `ResponsesCapabilities` and the unsupported-operation exception.
1. Implement Retrieve for OpenAI/Azure.
1. Manage `active_response_id`.
1. Connect Cancel with Ctrl-C and Web Stop.
1. Add Count input tokens and local fallback.
1. Add manual Compact.
1. Verify other provider capabilities.
1. Add List input items and Delete.

# Responses API status and priorities

> **Current status: P0 implemented; live verification continues.**
>
> The common Responses management wrapper and CLI operations are implemented. Remaining work is live verification, regression testing, and confirmation of the Web Stop path.

## Current support

| Operation | Status | Notes |
|---|---|---|
| Create a response | Implemented | Uses `client.responses.create()` for normal and streaming calls |
| Retrieve a response | Implemented | `ResponsesManager.retrieve()` / `:response status` |
| Delete a response | Implemented | `ResponsesManager.delete()` / `:response delete` |
| List input items | Implemented | `ResponsesManager.list_input_items()` / `:response items` |
| Count input tokens | Implemented | `ResponsesManager.count_input_tokens()` / `:response tokens` |
| Cancel a response | Implemented | `ResponsesManager.cancel()` / `:response cancel` and Ctrl-C |
| Compact a response | Partial | Requests server-side compaction through `context_management` during Create |

## Provider support levels

The levels below describe the current agentcli implementation path, not complete official provider certification.

| Provider | Level | Create / streaming | Continuation | Auto-compact | Notes |
|---|:---:|---|---|---|---|
| OpenAI | A | Supported | Supported | Supported | Standard Responses request builder |
| Azure OpenAI | A | Supported | Supported | Supported | OpenAI-compatible path; verify API and model differences |
| Amazon Bedrock | B | Supported | Attempted | Attempted | Input is converted to one string and tool definitions are flattened |
| OpenRouter | B | Supported | Disabled | Disabled | Uses local history after converting input to text |
| DeepSeek | B | Supported | Unsupported | Unsupported | Stateless; currently assumes `deepseek-v4-flash` |
| Ollama | C | Generic path | Provider-dependent | Provider-dependent | Adjusts `extra_body` and `max_output_tokens`; live verification required |
| Alibaba / Qwen | C | Generic path | To verify | To verify | No dedicated Responses compatibility path |
| LM Studio | C | Generic path | To verify | To verify | Depends on the local server version |
| Sakana AI / Fugu | C | Generic path | To verify | To verify | Fugu is an automatic Responses API target |
| llama.cpp | D | Unsupported | Unsupported | Unsupported | Standard `llama-server` is Chat Completions-oriented |

### Meaning of levels

- **A**: Create, streaming, tool calling, continuation, and auto-compact are supported by the implementation path.
- **B**: Create, streaming, and tool calling work, but provider-specific transformations or disabled features are required.
- **C**: Create can be attempted through a generic OpenAI-compatible path; continuation and compact require verification.
- **D**: The Responses path is not recommended by the current implementation.

## Common provider constraints

- Retrieve, Delete, List input items, Count input tokens, and Cancel are available through `ResponsesManager` and `:response` commands.
- Continuation and auto-compact refer to parameters on Create requests, not only management endpoints.
- OpenRouter removes `previous_response_id` and `context_management` and sends local history as text.
- DeepSeek is treated as stateless and does not use `previous_response_id` or `context_management`.
- Bedrock, Ollama, Alibaba/Qwen, LM Studio, and Sakana behavior varies by gateway and model.
- For llama.cpp, use Chat Completions with `UAGENT_RESPONSES=0`.

## Priorities

Verify OpenAI/Azure first, then verify Ollama, Alibaba/Qwen, LM Studio, and Sakana capabilities.

1. Cancel a response and connect Ctrl-C, Web Stop, timeout, and provider-side cancellation.
1. Retrieve a response and validate `previous_response_id`.
1. Count input tokens for context limits, compaction, and cost estimation.
1. Add manual Compact to the existing automatic compact path.
1. List input items when server-side history is required.
1. Delete a response when history deletion or sensitive-data removal is required.

## References

- [llama.cpp issue #19138: Support OpenAI Responses API](https://github.com/ggml-org/llama.cpp/issues/19138)

# JSONL storage policy for Responses state

## Purpose

Store `previous_response_id` in the current conversation JSONL instead of a dedicated state file. This keeps conversation history and Responses continuation state in the same session and allows returning to an earlier response chain when needed.

## Current problem

The legacy approach stores state in files such as:

```text
~/.uag/responses_state_<provider>_<model>.json
```

This makes it difficult to associate a response with a conversation, identify which conversation an ID belongs to, return to an earlier response, and keep `:load` or log reconstruction consistent.

## JSONL format

Add metadata records without a `role` field alongside ordinary messages:

```json
{
  "type": "responses_state",
  "schema_version": 1,
  "provider": "openai",
  "model": "gpt-5.4",
  "response_id": "resp_abc123",
  "status": "completed",
  "turn": 12,
  "created_at": "2026-08-05T10:00:00Z"
}
```

Required fields are `type`, `schema_version`, `provider`, `model`, `response_id`, `status`, and `created_at`. `turn` is optional but useful for ordering and display. Never store API keys, access tokens, or prompt-cache contents.

## Save timing

Save state only after a response completes successfully. Do not save a stream in progress, a cancelled response, an API error, an incomplete tool call, or a stale-ID retry. Record the ID only after confirming that the next turn can continue with it.

## Conditions for using a saved response

When `:load N` explicitly loads a log, use its newest completed Response as a continuation candidate only if all of the following are true:

- `status == "completed"`;
- `response_id` starts with `resp_`;
- saved provider and current provider match;
- saved model and current model/deployment match;
- the current provider supports `previous_response_id`;
- the record is not stale.

Do not reuse an ID after changing provider or model. For example:

```text
openai / gpt-5.4 -> openai / gpt-5.4-mini : invalid
azure / deployment-a -> openai / gpt-5.4   : invalid
```

For Azure, consider storing a non-secret endpoint identifier when the model name alone cannot uniquely identify the connection.

## Unsupported providers

Providers that do not support `previous_response_id` must not use saved IDs for continuation even if a JSONL record exists. The current explicit non-continuation providers are Grok, OpenRouter, and DeepSeek. They may display state, but must not use it to continue. Capability detection and runtime Responses conditions should be reused instead of relying only on a fixed provider list.

## Stale responses

A saved ID may refer to a deleted, expired, disabled, or interrupted response, or may no longer match the current input state. When continuation validation fails:

```text
validation failure
  -> clear previous_response_id
  -> record or mark stale state
  -> retry with a new Response chain
```

Preserve the existing stale-ID retry behavior.

## Relationship to current logs

Session logs use names such as:

```text
scheck_log_YYYYMMDD_HHMMSS.jsonl
```

Append a `responses_state` record after the corresponding completed assistant response:

```jsonl
{"role":"user","content":"What is the weather today?"}
{"role":"assistant","content":"..."}
{"type":"responses_state","schema_version":1,"provider":"openai","model":"gpt-5.4","response_id":"resp_abc123","status":"completed","turn":1,"created_at":"..."}
```

The normal message loader must ignore records without `role` when constructing the messages array.

## `:load` and log reconstruction

`rewrite_current_log_from_messages()` currently rebuilds JSONL from messages and could remove metadata records. Reconstruction must either preserve `responses_state` records from the original JSONL or keep them in memory and append them after reconstruction. Preserving original metadata is recommended.

When another JSONL is loaded, use its newest completed `responses_state` as a continuation candidate only after validating provider, model, capability, and freshness. If validation fails, load message history without setting a Response ID. Do not unconditionally delete state after `:load`.

`:load` prepends the selected log to the current session log and does not delete the source file. Subsequent conversation messages continue to be appended to the current session log. `:logs` should identify logs containing Response state.

## Deprecating dedicated state files

After migration to JSONL, deprecate:

```text
responses_state_<provider>_<model>.json
UAGENT_RESPONSES_STATE_DIR
UAGENT_RESPONSES_STATE_FILE
```

Do not automatically migrate legacy state files unless the correspondence to a conversation log is guaranteed. If migration is needed, require an explicit command that names the target log.

## Startup behavior

Do not unconditionally reuse an old Response at startup. Recommended behavior:

- let `:logs` identify logs containing Response state;
- validate the newest Response only when the user runs `:load N`;
- set the continuation ID only after validation succeeds;
- load message history without a Response ID when validation fails.

Automatic resume may be enabled explicitly, but should remain disabled by default for safety.

## Implementation order

1. Add JSONL `responses_state` read/write helpers.
1. Append metadata after successful Response completion.
1. Stop reading and writing the dedicated state files.
1. Show Response-state presence and a summary in `:logs`.
1. Validate the newest Response during `:load`.
1. Validate provider, model, and capabilities.
1. Integrate stale-ID fallback with existing handling.
1. Preserve metadata in `rewrite_current_log_from_messages()`.
1. Deprecate the old dedicated-state settings.
1. Test OpenAI/Azure, unsupported providers, model changes, `:load`, and log reconstruction.

## Acceptance criteria

- A state record is appended to the current JSONL after a Response completes.
- No new `responses_state_*.json` file is created.
- `:logs` identifies logs containing Response state.
- `:load N` validates and continues the newest Response for the same provider and model.
- Unsupported providers never use saved IDs for continuation.
- A stale ID cannot stop the next conversation.
- State records remain available after `:load`.
- State records survive log reconstruction.
- State records contain no secrets.
