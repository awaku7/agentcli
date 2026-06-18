# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.11] - 2026-06-18

### Added
- Z.AI (Zhipu AI) provider support (`UAGENT_PROVIDER=zai`). Default model: `glm-5.2`.
- Local GeoIP database support: offline IP geolocation via mmdb file (`UAGENT_GEOIP_DB_PATH` or bundled `dbip-city-lite.mmdb`).
- `get_geoip` now accepts optional `ip` parameter for arbitrary IP lookup.
- Tool parallel execution (async) support with `x_parallel_safe` opt-in flag.
- Tool genre mask (`--tool-genre-mask`), tool-less mode (`--no-use-tool`).
- Safety confirmation prompt before `skills_install`.
- UPnP Phase 2: device info tool, scan filters, shared module.
- `TOOL_ASYNC.md` design document.
- `LICENSE-THIRD-PARTY.md` for DB-IP Lite (CC-BY 4.0) attribution.
- Archive merge: restored all local development changes, preserving origin/main updates.

### Fixed
- `get_geoip` tool registration (`tool_level` 1 to 0) so it appears in the tool list.
- `:tools on/off` import path corrected to `genre_control_tool`.
- `:cp`/`:mv` commands now support quoted paths, removed workdir restriction.
- DeepSeek 400 error recovery and sanitize_messages improvement.

### Changed
- Restored locale files with added translations for Z.AI, --use-tool/--no-use-tool, and Basic genre (all 30 locales).
- llmcapa dependency updated to 0.2.2.

## [0.5.12] - 2026-06-18

### Fixed
- VertexAI: skip `include_server_side_tool_invocations` (not supported by Enterprise Agent Platform).
- Gemini: filter dangling `required` keys in tool schema to avoid 400 INVALID_ARGUMENT.
- Claude/Gemini: use `provider` parameter instead of hardcoded strings in `_rate_limit_retry_step`.
- `_call_claude_round` / `_call_gemini_round`: pass `provider` from caller to fix NameError.

## [Unreleased]

### Added
- Xiaomi MiMo (`mimo`) provider support: OpenAI-compatible API with reasoning/thinking mode.
  - `UAGENT_MIMO_API_KEY`, `UAGENT_MIMO_BASE_URL` (default: `https://api.xiaomimimo.com/v1`), `UAGENT_MIMO_DEPNAME` (default: `mimo-v2.5-pro`).
  - Uses DeepSeek's reasoning path for `reasoning_content` handling.
  - env_validate, util_providers, setup_cli, runtime_banner updated.
  - ENVIRONMENT.md documentation updated.

## [0.5.10] - 2026-06-18

### Fixed
- get_geoip tool registration (`tool_level` 1 to 0) so it appears in the tool list.
- llmcapa dependency updated to 0.2.2.

## [0.5.9] - 2026-06-16

### Added
- ClawHub marketplace support: `skills_mp_search` now accepts `source` parameter (`skillsmp` / `clawhub`) to search and browse community Agent Skills from either marketplace.
- Full 30-language i18n for skills_mp_search tool (15 keys translated across all supported locales).

### Changed
- README updated in all 30 languages to document SkillsMP and ClawHub marketplace access.

## [0.5.8] - 2026-06-15

### Added
- Multiline input mode with prompt_toolkit TextArea (Ctrl+X to submit, Esc to cancel, fallback to legacy `"""end` mode).
- Tool genre selection UI: GUI (Tools menu), Web (checkboxes in header), A2A server (startup dialog).
- Tool genre selection disabled while busy (IDLE only).
- get_geoip tool moved to IoT genre (conditional loading via genre mask).
- Web UI: real-time sync of final assistant messages after LLM rounds.
- Web UI: GET/POST /api/tool-genres endpoints for dynamic genre toggling.
- Human_ask prompt now shows `[REPLY] >` prompt in CLI.

## [0.5.7] - 2026-06-15

### Changed
- Renamed provider identifier from `kimi` to `moonshot` (UAGENT_PROVIDER=moonshot).
- Renamed environment variables from `UAGENT_KIMI_*` to `UAGENT_MOONSHOT_*`.
- Applied black formatting across 39 files for consistent code style.
- Fixed ruff lint errors (invalid exception syntax, unused imports, one-line statements).
- Fixed mypy type errors (dict annotation, used-before-def, truthy-function check).

## [0.5.6] - 2026-06-15

### Added
- USB camera tool (`usb_camera`): capture photos, list devices, query capabilities (cross-platform).
- Alibaba Cloud (Qwen) provider for image analysis.
- Kimi (Moonshot AI) provider for image analysis.
- DeepSeek vision backend (requires vision-capable endpoint).
- `list_caps` action for USB camera to show supported resolutions and FPS.

### Changed
- Shortened tool descriptions across all 30 locales (~8K chars / ~2K tokens reduction).
- Removed alias parameters from tool specs (path/filename, root_path/path, etc.).
- Removed dead `system_prompt` fields from all tool specs.
- Renamed 31 param keys to shorter names (output_format→fmt, max_results→limit, etc.).
- Cross-platform USB camera support (dshow/v4l2/avfoundation).

### Fixed
- Docstring type hints consistency.
