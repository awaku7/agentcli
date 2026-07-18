# llmcapa Integration Notes

Status of **uag** (agentcli) vs **llmcapa** capability database.

- llmcapa version targeted by uag: **>=0.4.1**
- Shared helper: `src/uagent/llmcapa_util.py`
- Tests: `tests/test_llmcapa.py`, `tests/test_llmcapa_util.py`

## What uag already uses

| Area | Integration |
|---|---|
| Lookup | `get_capability()` with uag→llmcapa provider aliases (`gemini→google`, `grok→xai`, `bedrock→amazon`, …) |
| Vision | `provider_allows_chat_vision()` + `supports_vision` / image_input |
| Context shrink | `get_context_window()` × `UAGENT_SHRINK_RATIO` |
| Max tokens | `clamp_max_tokens()` on main chat/responses, Claude/Gemini/Grok/Ollama/FIM, profile/translate/sub-agent |
| Reasoning | `get_reasoning_effort_values()` / thinking_budget flags on Claude/DeepSeek/ZAI/OpenRouter/Gemini |
| Responses API | `provider_allows_responses_api()` (static provider set + model flag) |
| FIM | `provider_allows_fim()` (static provider set + model flag) |
| Token count | `count_messages_tokens()` with resolved model id |
| Cost | `estimate_cost()` in `:model v`, sub-agent usage logs |
| Deprecated | startup banner WARN + `:model` WARN |

## Remaining upstream gaps (llmcapa side)

These are still useful upstream improvements; uag already mitigates many via aliases/fallbacks.

### 1. Sparse / local providers

| uag provider | Notes |
|---|---|
| `lmstudio` | User-installed local models; static DB often incomplete |
| `hf` | Huge catalog; only a subset is practical offline |
| `sakura` | May still have limited coverage depending on llmcapa release |

### 2. Provider naming

uag normalizes these in `llmcapa_util.provider_candidates()`:

| uag | llmcapa candidates |
|---|---|
| `bedrock` | `amazon`, `bedrock` |
| `gemini` / `vertexai` | `google`, … |
| `grok` | `xai`, `grok` |
| `alibaba` | `qwen`, `alibaba` |
| `moonshot` | `moonshot`, `moonshotai` |
| `mimo` | `xiaomi`, `mimo` |
| `azure` | `azure-openai`, `azure-foundry`, `openai` |

### 3. Incomplete rows

Some catalog rows still have `context_window=0` / `max_output_tokens=0` (especially image/audio or incomplete Foundry rows). uag treats non-positive values as unknown and falls back.

### 4. Model id variants

Short names and deployment aliases still vary (`openai/o3-mini` vs `o3-mini`, dated DeepSeek ids, etc.). uag retries bare ids and prefix search as a last resort.

## Design rules in uag

1. **Never hard-fail** when llmcapa is missing or a model is unknown — keep previous defaults.
2. Provider static sets (`RESPONSES_PROVIDERS`, `FIM_SUPPORTED_PROVIDERS`, `CHAT_VISION_PROVIDERS`) remain the implementation gate; llmcapa only tightens model-level allow/deny when known.
3. Prefer provider-specific env knobs, then shared `UAGENT_TEMPERATURE` / `UAGENT_TOP_P` / `UAGENT_MAX_TOKENS`.
