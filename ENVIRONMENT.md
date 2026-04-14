# Environment Variables

This document describes the environment variables used by `uag`.

## Required Provider Settings

See the main README for a full list of supported providers and their specific environment variables (e.g., `UAGENT_OPENAI_API_KEY`, `UAGENT_AZURE_BASE_URL`).

## Common Settings

- `UAGENT_WORKDIR`: Working directory.
- `UAGENT_MEMORY_FILE`: Long-term memory file path.
- `UAGENT_SHARED_MEMORY_FILE`: Shared long-term memory file path.
- `UAGENT_EMBEDDING_API_URL`: Embedding API URL.
- `UAGENT_CMD_ENCODING`: Encoding for external command output.
- `UAGENT_LANG`: Host UI language (e.g., `en`, `ja`).

## Advanced Features

- `UAGENT_RESPONSES`: Set to `1` to enable Responses API.
- `UAGENT_SHRINK_CNT`: Auto-shrink threshold (default: `100`).
- `UAGENT_SHRINK_KEEP_LAST`: Messages to keep after auto-shrink (default: `20`).
- `UAGENT_REASONING`: Reasoning effort (`auto`, `low`, `medium`, `high`, etc.).
- `UAGENT_VERBOSITY`: Output verbosity (`low`, `medium`, `high`).

## Security and Encryption

`uag` supports encrypting sensitive environment variables.

- Tool: `uag_envsec`
- Encrypts `.env` to `.env.sec` using a password and a local key.
- Default key file: `.uagent.key` in the CWD.

Usage:
```bash
uag_envsec .env
```
