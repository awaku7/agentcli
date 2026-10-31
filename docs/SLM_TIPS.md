# SLM TIPS (Small Language Model)

This document explains recommended settings when using **small language models** (e.g. Ollama 3B-14B, lightweight local models, quantized variants) with uag.

Small models often have limited instruction-following ability, narrower context windows, and lower tool-calling accuracy. The tips below help you adapt uag to work reliably within those constraints.

______________________________________________________________________

## 1. Reduce tool complexity

### 1.1 Limit tools individually

Small models struggle when too many tool definitions are presented. UAG discovers
tools with `tool_catalog` and loads them on demand through `tool_load`.
You can also explicitly preload only essential tools:

```bat
uag --enable-tool calculator
```

Tool genre names are descriptive metadata; genre-wide toggles and bitmasks are no
longer supported.

### 1.2 Disable tools entirely

If the model frequently produces invalid JSON tool calls or ignores tool results, disable tools completely:

```bat
uag --no-use-tool
```

During a session, you can toggle tools with:

```
:tools off
:tools on
```

______________________________________________________________________

## 2. Manage context limits

Small models typically have small context windows (4K-32K tokens). Keeping the conversation short is critical.

### 2.1 Auto-shrink

```bat
set UAGENT_SHRINK_CNT=50
set UAGENT_SHRINK_KEEP_LAST=10
uag
```

- `UAGENT_SHRINK_CNT`: number of non-system messages before auto-shrink triggers (default: 100, set 0 to disable).
- `UAGENT_SHRINK_KEEP_LAST`: how many recent messages to keep after summarization (default: 20).

For tiny models, start with `UAGENT_SHRINK_CNT=20` and `UAGENT_SHRINK_KEEP_LAST=5`.

### 2.2 Manual shrink during a session

```text
:shrink       -> summarize entire history, keep only the summary
:shrink 5     -> summarize history, keep last 5 messages
:shrink_llm   -> use the LLM to produce a summary (better quality, costs 1 round)
```

### 2.3 Start fresh

If context is too polluted, save and reload:

```text
:save my_session
:exit
uag
:load my_session
```

______________________________________________________________________

## 3. Recommended combinations by model size

### 3.1 Very small (3B-7B, e.g. Phi-3, Llama-3.2-3B, Qwen2.5-7B)

```bat
set UAGENT_SHRINK_CNT=20
set UAGENT_SHRINK_KEEP_LAST=5
uag
```

Tools often fail. If tool calls are unreliable, add `--no-use-tool`.

### 3.2 Medium (8B-14B, e.g. Llama-3.1-8B, Qwen2.5-14B, Mistral-7B)

```bat
set UAGENT_SHRINK_CNT=50
set UAGENT_SHRINK_KEEP_LAST=10
uag
```

Load additional individual tools with `--enable-tool` if needed.

### 3.3 Large small models (30B-70B quantized)

These can usually run with the default dynamic tool discovery settings.

______________________________________________________________________

## 4. Provider-specific notes

### 4.1 Ollama

Set `UAGENT_OLLAMA_MODEL` to your model name (e.g. `llama3.2:3b`, `qwen2.5:7b`). Some Ollama models do not advertise tool support. If tool calls are silently ignored, try `--no-use-tool`.

### 4.2 Other local backends

For llama.cpp, LocalAI, or vLLM behind an OpenAI-compatible endpoint, the same principles apply: reduce tool count, shrink context, and disable tools if JSON output is unreliable.

______________________________________________________________________

## 5. Additional tips

- **Start with a simple task**: ask the model to read a file or calculate something before giving multi-step instructions.
- **Use `:load 0`**: the most recent session is saved as index 0. You can resume it quickly.
- **`--non-interactive`**: useful for scripting. The model processes the initial input and exits immediately.
