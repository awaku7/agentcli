# Changelog

## [0.5.29] - 2026-06-29

### Added
- Sakana AI (Fugu) provider support: new LLM backend with Responses API integration.
- Auto-enable Responses API for sakana (and other RESPONSES_PROVIDERS) by default.
- Add sakana.ai to setup wizard (setup_cli.py).
- Interrupt feature: press `c` key or click Stop button to cancel ongoing tool execution.

### Changed
- Auto-disable tools/thinking on 400 error for non-supporting models to avoid redundant retries.

### Documentation
- Add Sakana AI (Fugu) to provider list and Responses API documentation.
- Add Sakana AI to all 34 language README provider lists.
- Add HuggingFace to all 34 language README provider lists.
- Add interrupt feature (c-key/Stop button) to all 34 language README translations.
- Add interrupt feature (c-key/Stop button) to Japanese README.ja.md.

### Chores
- Update llmcapa dependency from 0.2.6 to 0.2.8.


## [0.5.28] - 2026-06-28

### Changed
- Made zhipuai an optional dependency (moved to `[zai]` extra). Falls back to OpenAI SDK when not installed.


## [0.5.27] - 2026-06-27

### Added
- Setup wizard now detects existing `.env` / `.env.sec` files and environment variables (UAGENT_*) as defaults.
- Setup wizard now supports LM Studio, MiniMax, and HuggingFace providers.

### Fixed
- Skip tool schema compat sync for strict OpenAI-compatible APIs (HuggingFace) to avoid HTTP 400 errors.
- Strip `tool_genre` from tool specs before sending to LLM to reduce token usage.
- Use local `.uagent.key` first for `.env.sec` decryption in setup wizard.
- Removed local `.uagent.key` support; use default key only for `.env.sec` operations.

### Documentation
- Added HuggingFace (hf) provider documentation to ENVIRONMENT.md and README.
- Added missing provider sections (Z.AI, MiniMax) and fixed Japanese table formatting.

### Chores
- Fixed ruff lint errors across codebase.
- Applied black formatting to 11 files.

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [0.5.26] - 2026-06-26

### Added
- `set_timer` now supports OS-level scheduling with `--inject-message` (Windows: schtasks, Linux: systemd-run/at, macOS: at).
- New `--enable-tool` CLI argument to enable individual tool names; used in os_persist timers instead of `--tool-genre-mask`.
- Z.AI provider separated from DeepSeek path; now uses official `zhipuai` SDK with OpenAI-compatible fallback.
- Show workdir in timer batch file for better traceability.
- Redirect uag output to log file for debugging schtasks issues.
- Pass current tool genre mask to OS-scheduled uag invocation.

### Fixed
- Prevented `sys.argv` fallback from capturing `--inject-message` value as a file path.
- Preserved `UAGENT_*` env vars in Windows scheduled task batch file.
- Windows self-delete batch file now includes pause for visibility.
- Read `TOOL_SPECS` directly instead of `_genre_control_util` to avoid reload issue.

### Changed
- Removed `--tool-genre-mask` from os_persist timer command in favor of `--enable-tool` only.

### Removed
- Removed env var capture from timer batch file to avoid leaking secrets in plaintext.

### Chores
- Added `zhipuai>=2.1.5` dependency. Updated `llm_deepseek` docstrings to remove z.ai references.

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.25] - 2026-06-26

### Changed
- Changed default `UAGENT_SHRINK_RATIO` from 0.1 back to 0.5 to reduce compression frequency.
- Updated `llmcapa` dependency from 0.2.5 to 0.2.6.

### Refactored
- Removed `qrcode` from core dependencies; `generate_qr_code_tool` now lazy-imports qrcode at runtime.
- Added `_sanitize_for_json` helper for JSON-safe conversion of YAML values.
- Applied `_sanitize_for_json` in `_read_text_file` and `parse_frontmatter_yaml`.

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.24] - 2026-06-25

### Added
- Real-time display of tool calls/results in VSCode chat panel (intermediate messages via WebSocket).
- Encoding fix for stderr/stdout (UTF-8 reconfigure) to prevent garbled Japanese output.

### Changed
- Changed default `UAGENT_SHRINK_RATIO` from 0.5 to 0.1.
- Increased wsClient call timeout from 60s to 600s.
- Restored ws_handler with `make_client` directly; added llmcapa fallback for shrink.
- Applied ruff fix (remove unused imports) and black formatting.

### Fixed
- Corrected relative import paths in `a2a/server.py`.

### Chores
- Removed `patch_markdown.py` and its backup files.
- Updated `package.json` compile script.

## [0.5.23] - 2026-06-24
