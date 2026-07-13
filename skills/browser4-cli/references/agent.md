---
title: "Agent — Autonomous Browser Task Execution"
description: "Reference for agent commands: run, status, result, extract, summarize. Submit natural-language tasks for autonomous browser execution."
tier: procedure
---

# Agent Reference

Submit natural-language tasks and let Browser4's AI agent plan and execute browser actions autonomously.

## Prerequisites

Requires an LLM API key. Configure one of:

| Provider | Env Vars |
|----------|----------|
| DeepSeek | `DEEPSEEK_API_KEY` |
| OpenRouter | `OPENROUTER_API_KEY`, `OPENROUTER_MODEL_NAME`, `OPENROUTER_BASE_URL` |
| OpenAI-compatible | `OPENAI_API_KEY`, `OPENAI_MODEL_NAME`, `OPENAI_BASE_URL` |

```bash
export DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

## Commands

### Agent Run — Autonomous multi-step task (async)

```bash
browser4-cli agent run "Go to amazon.com, search for 'wireless headphones', extract top 5"
browser4-cli agent status agent-task-1      # poll until COMPLETED
browser4-cli agent result agent-task-1      # fetch results
```

**Writing tasks:** Describe **what** you want, not how. Good: "extract the top 5 product titles and prices." Avoid step-by-step ref instructions.

### Agent Status

```bash
browser4-cli agent status <task-id>
```

Returns JSON with status field: `RUNNING`, `COMPLETED`, `FAILED`, `EXPECTATION_FAILED`.

### Agent Result

```bash
browser4-cli agent result <task-id>
```

Always confirm completion via `agent status` first.

### Extract — Synchronous LLM extraction

```bash
browser4-cli extract "product name, price, ratings"
browser4-cli extract "headlines and authors" --schema '{"fields":[{"name":"title","type":"string"},{"name":"author","type":"string"}]}'
```

### Summarize — Synchronous page summarization

```bash
browser4-cli summarize "summarize the reviews"
browser4-cli summarize --selector "#content"
```

## Error Recovery

| Symptom | Recovery |
|---------|----------|
| `agent run` exits non-zero | Check backend + LLM key |
| Task stuck RUNNING | Poll again — some tasks take minutes |
| Status/result unexpected | Inspect `status`, `statusCode`, `message` |
| Task lost after restart | Re-submit |
