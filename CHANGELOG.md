# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.1] - 2026-06-12

### Added
- Startup genre prompt translations were added across all localized catalogs.

### Fixed & Improved
- Startup genre prompt handling was cleaned up for the first-menu flow.

## [0.5.0] - 2026-06-11

### Added
- UPnP IGD discovery now deduplicates repeated service entries and prefers the actual WANIPConnection service.
- UPnP port mapping now defaults to a 60-minute lease when not specified.
- GeoIP tool search priority was lowered so it stays out of normal tool discovery.

### Fixed & Improved
- Matter device, endpoint, and cluster listings now dedupe by controller_id and bridge_id.
- ECHONET Lite interface resolution now avoids virtual adapters and falls back more reliably.
- IoT use-case docs and related tests were refreshed for the current tool layout.

## [0.4.46] - 2026-06-10

### Added
- **Classic Bluetooth Scanning Support**:
  - Extended the `ble_ops` tool to support scanning both Classic Bluetooth and BLE devices simultaneously using PySide6.
  - Added a new `scan_mode` parameter to the `ble_ops` tool.
  - Fixed a bug in BLE scanning where the `BLEDevice` object did not have the `rssi` attribute.

## [0.4.45] - 2026-06-10

### Added
- **Dynamic Reasoning & Thinking Budget Support**:
  - Integrated `llmcapa` to dynamically check if a model supports reasoning effort (Claude) or thinking budget (Gemini).
  - Updated `llmcapa` dependency to `0.1.1`.

## [0.4.44] - 2026-06-10

### Added
- **llmcapa Integration**:
  - Integrated `llmcapa` library to dynamically resolve model context windows and calculate auto-shrink limits.
  - Removed the large hardcoded `DEFAULT_SHRINK_LIMITS` dictionary in favor of dynamic calculation.
  - Added support for `UAGENT_SHRINK_RATIO` environment variable (default: `0.5`) to customize the safety margin.

## [0.4.43] - 2026-06-09

### Added
- **Token-based Auto-shrink Trigger**:
  - Implemented token-based auto-shrink trigger with model-specific defaults to manage context size efficiently.
- **Package Structure Refactoring**:
  - Reorganized the `uagent` package structure into `providers`, `runtime`, and `tools` for better maintainability.

### Fixed & Improved
- **Configuration Defaults**:
  - Changed default `UAGENT_SHRINK_CNT` to 0 (disabled) to prevent unexpected context shrinking.

## [0.4.42] - 2026-06-08

### Added
- **Generative UI (Artifacts) Support**:
  - Implemented real-time HTML/CSS/JS code block extraction and rendering in a dedicated preview panel.
  - Added interactive "Open in Preview" button for assistant-generated HTML content.
  - Added automatic code block folding (`<details>`) in chat UI to keep the conversation clean.

### Fixed & Improved
- **Web UI Enhancements**:
  - Improved text contrast for chat bubbles in dark mode.
  - Fixed text wrapping and formatting for ASCII art and terminal outputs in chat bubbles.

## [0.4.41] - 2026-06-07

### Added
- **Developer Tool Genre Expansion**:
  - Added `tool_genre="devel"` to `system_reload`, `git_ops`, `playwright_inspector`, and `binary_edit` tools.
- **Web UI Enhancements**:
  - Display external URL on startup and fixed related tests.

### Fixed & Improved
- **Internationalization (i18n)**:
  - Removed `_t()` from 400 BadRequest and updated all locales to achieve 0 `same_as_en` entries.
  - Completed translations for all 28 languages to achieve 0 empty entries.
  - Added Japanese translations for 22 newly extracted strings.
  - Rebuilt POT and PO/MO files based on `babel.cfg` scope.
- **Gemini Stability & i18n**:
  - Added i18n support and 28 language translations for Gemini stream interruption error messages.
  - Supported `UAGENT_GEMINI_MAX_OUTPUT_TOKENS` and displayed error on stream interruption.

## [0.4.40] - 2026-06-06

### Added
- **Gemini Built-in Google Search Support**:
  - Added support for Gemini's built-in Google Search (Google Search Grounding) in Gemini API and Vertex AI.
  - Controlled via the `UAGENT_GEMINI_WEB_SEARCH` environment variable, enabled (ON) by default. When active, local web search tools are automatically disabled.
- **Dynamic Skill Help Enhancements**:
  - Added dynamic skill command help functionality.
  - Localized the skill installation tool (`skills_install_tool`).
  - Added `.uag` skill root to the skill discovery path.

### Changed & Optimized
- **`replace_in_file` Tool Optimization**:
  - Enhanced diagnostics for match limit (`match_hits`) and added directory exclusion in recursive scans, significantly improving performance.
- **Claude Integration Enhancements**:
  - Enhanced dynamic `max_tokens` configuration, thinking block parsing, and multimodal image support.
  - Avoid setting a default temperature for Claude unless explicitly configured via `UAGENT_CLAUDE_TEMPERATURE`.
  - Omitted `temperature` when `output_config` is used and added fallback handling for deprecated parameters in the Claude API.
- **Gemini Stability Improvements**:
  - Applied empty response nudge handling and optimized safety settings to prevent silent blocking.
  - Formatted `test_list_dir_tool`, removed `test_libcst_transform_smoke`, and fixed translation issues in `sub_agent_tool`.

## [0.4.39] - 2026-05-22

### Added
- **Locale MO Rebuild**:
  - Rebuilt all compiled `.mo` translation files after locale updates.
  - Refreshed multilingual message catalogs across the repository.

## [0.4.38] - 2026-05-22

### Added
- **Specialized Sub-Agent Tool (`run_sub_agent`)**:
  - Implemented safe, orchestrated specialized sub-agents under the control of the parent orchestrator.
  - Supported roles: `planner` (planning), `reviewer` (code audit), `summarizer` (context compression), `patch_designer` (safe patch proposing), and `error_analyst` (error/exception debugging).
  - Built-in `DuplicateCallGuard` to strictly prevent infinite looping on identical tasks.
  - Implemented strict path-pinning guardrails to secure file accessibility.
- **Multilingual Support (30 Languages)**:
  - Created complete localization resource JSON (`sub_agent_tool.json`) covering 30 global languages.
  - Verified and passed all translation smoke tests (`test_tools_i18n_smoke.py`).
- **Sub-Agent Extensions Roadmap (`TODO_subagent.md`)**:
  - Added a dedicated roadmap ledger to manage future sub-agent extensions and implementation logs.
- **Skill Maintenance**:
  - Repaired broken YAML frontmatter in metadata sections across all SKILL.md files to restore agent `:skills` tool discovery compatibility.

---

## [0.4.37] - 2026-05-22

### Changed
- **Modernization to Python 3.11+**:
  - Upgraded code syntax across all repository files to leverage Python 3.11+ features.
  - Standardized modern typing syntax and cleaned up deprecated imports.
- **Sub-Agent Architecture Design**:
  - Formulated initial architecture blueprint for orchestrated and guardrailed sub-agents.

## [0.4.36] - 2026-05-15

### Changed
- **Search Term Normalization**:
  - Normalized all `x_search_terms` fields across tool-spec JSON definitions for cleaner indexing.

## [0.4.35] - 2026-05-10

### Added
- **Batch State Tool & Architecture**:
  - Introduced `batch_state` tracking ledger, state designs, and extensive verification smoke tests.
- **Locale & Prompts Refresh**:
  - Re-synced and updated various core locale resources and system LLM prompts.

## [0.4.34] - 2026-05-02

### Added
- **Expanded Locales Support**:
  - Added fully translated blocks for `bn` (Bengali), `fa` (Persian), `mn` (Mongolian), and `mr` (Marathi) languages.
  - Synchronized and updated multilingual translation references in root `README.md`.
- **Multilingual Catalog Search**:
  - Added tokenization enhancements to better index and search tools in multiple foreign languages.

## [0.4.32] - 2026-04-25

### Added
- **Rich Log & Attachment Handling**:
  - Implemented robust parsing for ANSI-colored logs and custom attachment structures.
  - Added an HTML rendering helper for rich terminal outputs.
