# Changelog

## [0.5.36] - 2026-07-04

### Added
- SAKURA AI Engine (sakura) provider support: new LLM backend using OpenAI-compatible API.
- Sakura provider entry in setup wizard (setup_cli.py), provider detection, and client creation.
- Sakura temperature setting support in llm_round_helpers.py.

### Changed
- `runtime_banner.py`: add base_url display for sakura provider.

### Documentation
- Add SAKURA AI Engine to provider lists in README.md, AGENTS.md, DEVELOP.md, DEVELOP.ja.md, and ENVIRONMENT.md.
- Add sakura/sakana environment variable sections to ENVIRONMENT.md.

## [0.5.35] - 2026-07-04

### Added
- Contributing section added to `README.md` and all 34 translated README files under `docs/`.
- Responses state file name now sanitizes all Windows-invalid filename characters via `re.sub`.

### Changed
- `_get_responses_state_file` in `core.py`: replaced chained `.replace()` calls with `re.sub(r'[\\/:*?"<>|]', "_", ...)` for cross-platform filename safety.

## [0.5.34] - 2026-07-04

### Added
- Server-side compaction for Responses API (OpenAI/Azure GPT-5.4+ with `UAGENT_RESPONSES=1`). Automatically applied using the same threshold as local auto-shrink. Compaction events are logged.
- Tool flow documentation (`src/uagent/docs/TOOL_FLOW.md`) covering genre mask, tool_catalog dynamic loading, and GPT-5.4+ native tool_search.
- Tool descriptions updated: `get_windows_gps` now prioritized for GPS location, `get_geoip` demoted to low-precision IP-based estimation.

### Changed
- `responses_state.json` split into provider/model-specific files (`responses_state_{provider}_{model}.json`). Corrupted JSON files are automatically deleted.
- Auto-unload now skips when `previous_response_id` is set (any provider, not just OpenAI/Azure).
- `_should_preload_lazy_specs` default changed to `False` (previously `True`), fixing accidental exclusion of management tools for non-GPT-5.4 providers.

### Fixed
- `saved_model` None check in `_check_responses_state_provider` preventing AttributeError when no pending state exists.

## [0.5.33] - 2026-07-02

### Added
- Auto-unload mechanism for tools: unused tools unloaded after 5 rounds, used-but-stale tools after `UAGENT_AUTO_UNLOAD_ROUNDS` (default 10). Core tools (`tool_catalog`, `tool_load`, `unload_tool`) are protected.
- `:tools list` now shows remaining rounds before auto-unload.
- `translate_text` now supports `.po` file format with dynamic placeholder detection.

### Fixed
- `_TOOL_LAST_ROUND` not being updated after tool execution because `messages[-1]` was a tool result (role=tool), not assistant. Changed to search backwards for the last assistant message with tool_calls.
- `_TOOL_LAST_ROUND` being reset for all tools every round (iterated full message history instead of last message only).
- `UnboundLocalError` in `run_llm_rounds` when accessing `assistant_text` before assignment.
- `:tools list` no longer displays remaining rounds for core tools (`tool_catalog`, `tool_load`, `unload_tool`).
- `windows_gps_tool` now sets `TOOL_SPEC=None` on non-Windows to suppress loading and catalog display.

### Changed
- Completed all tool i18n translations, removed stale keys, filled missing translations.
- Regenerated POT and rebuilt all 34 language PO files.

### Documentation
- `vup-build-release-whl` skill: auto-detect distribution destination (GitHub/GitLab) via `git remote origin` URL.

## [0.5.32] - 2026-07-01

### Added
- `:profile-fromlog` now defaults to the most recent 100 log files.

### Fixed
- Add missing `_()` wrappers for user-facing print messages in host-side files (llm_helpers, llm_round_helpers, profile_manager, llm_deepseek, llm_zai, scheckgui).

### Changed
- i18n: regenerate POT and rebuild all 34 language PO files (575 entries, 0 empty).
- i18n: translate all untranslated entries across 34 languages via Google Translate.
- i18n: fix placeholder keys translated by Google Translate in 21 locale files.

## [0.5.31] - 2026-07-01

### Added
- APM (Agent Package Manager) skill integration: tab completion, DEVELOP.md docs, and skills_apm_tool.py.

### Fixed
- Rename loop variable _ to label in setup_cli.py to avoid UnboundLocalError on gettext _().

### Changed
- Sync i18n README translations: adjustments and content updates across 34 languages.

### Documentation
- Rewrite AGENTS.md from Japanese agent instructions to English project overview.

## [0.5.30] - 2026-06-30

### Added
- Auto-pilot mode (`:auto` command) with judgment_mode, reviewer feedback propagation, and separate judge LLM via `UAGENT_AP_PROVIDER`.
- Auto-pilot loop and Stop button integration in GUI/Web interface.
- `pdf_export` tool: export conversation to PDF. Extend `:logs` with `pdf` subcommand.
- `translate_text`: add `protect_placeholders` option to preserve printf specifiers during translation.

### Fixed
- Auto-pilot COMPLETE judgment delayed by one round.
- Unterminated string literals in `util_tools.py` (print/_ calls split across lines).
- `list_dir` paginate argument handling.
- Restore broken printf specifiers in bn, el, hu, mn, ro locale files from Google Translate corruption.
- Restore `%(feedback)s` pattern corrupted by Google Translate in all locale PO files.
- Increase `max_tokens` for reviewer judgment from 10 to 50.

### Changed
- Skip `human_ask` during auto-pilot mode.
- Refactor LLM client creation to once-per-loop pattern.
- Convert all non-README.md documentation links to relative paths.

### Documentation
- Add workdir-relative-path note to system prompt.
- Add `browser_playwright` hint to `fetch_url` tool description.
- Add auto-pilot documentation (`AUTO_REVIEW.md`, `README_AUTO.md`, `docs/README_AUTO.ja.md`).

### Chores
- Apply ruff format to `tools/__init__.py` and `welcome.py`.
- i18n: fill empty PO entries via translation across all locale files.


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
