# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
