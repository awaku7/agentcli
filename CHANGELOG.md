# Changelog

## [0.5.45] - 2026-07-12

### Added
- New tools: `diff_files` (compare two files line by line) and `apply_patch` (apply unified diff patches) with full 34-language i18n.
- Tool genres: `dev`, `web`, `utility` added to genre bitmap and genre control system.

### Fixed
- `tests/test_llmcapa.py`: corrected `expect_vision` flags for `Llama-3.2-90B-Vision-Instruct` and `Llama-4-Scout-17B-16E` (both support vision).

### Changed
- llmcapa dependency bumped to >=0.3.1.
- README and 33 translations: tool count updated to 170, parallel-safe to 111.
- AGENTS.md: tool genre list updated to include `dev`, `web`, `utility`.

## [0.5.44] - 2026-07-11

### Added
- llmcapa v0.3.0 support: pass `provider` argument to `llmcapa.get()` for accurate model lookup.
- Test suite `test_llmcapa.py` (37 tests): verify provider model specs across all 70 llmcapa providers.
- Documentation: `docs/llmcapa_improvements.md` with improvement requests for llmcapa.
- Documentation: `translate_text` tool usage documented in i18n workflow sections.

### Fixed
- `cmd_exec_json_tool`: exception handling for subprocess.run, unified `error` key in return value, empty string cwd guard.
- `pwsh_exec_tool`: all error messages now i18n'd, fragile `confirm_if_needed` replace removed, timeout placeholder fixed.
- `bash_exec_tool`: exception handling for subprocess.run, all error messages now i18n'd.

### Changed
- i18n documentation consolidated: `DEVELOP_I18N.md` now covers both host-side (gettext) and tool-side (JSON) i18n in one file.
- README and 33 translations: tool count updated to 171, parallel-safe to 89, provider count to 21.
- Removed all `.org` backup files (73 files total).
- Removed stub docs `DEVELOP_TOOL_I18N.md` and `ADD_LOCALE.md` (merged into unified guide).
- llmcapa dependency bumped to >=0.3.0.

# Changelog

## [0.5.43] - 2026-07-10

### Added
- 2idx tools: preprocess, decorator/annotation skip, function depth detection, multi-line join for jv2idx, kt2idx, php2idx, rs2idx, ts2idx.

### Fixed
- Fixed 44 ruff invalid-syntax errors (`except X,Y` → `except (X,Y)`).
- Fixed 8 ruff warnings across the codebase.
- Removed unnecessary `core=` parameter from `compress_history_with_llm`.

### Changed
- Removed `cmd_exec_tool` (superseded by `cmd_exec_json_tool`).
- Applied Black formatting to 49 files.
- Updated 2idx tool JSON schemas to match new capabilities.

## [0.5.42] - 2026-07-10

### Added
- i18n: applied x_search_terms translations for 33 languages across all tool JSON files (59+ files).
- VSCode: human_ask integration with chat panel, reasoning level dropdown, FIM code completion.
- VSCode: configurable tool result display (UAGENT_VSCODE_SHOW_TOOL_RESULT).
- Web UI: multimodal image input and display support.
- Web UI: attachment handling with data_url optimization and WebSocket max_size config.
- Grok/xAI: full xai_sdk integration with comprehensive parameter and tool use support.
- Tool management: dynamic per-tool auto-unload with Fibonacci bump threshold.
- tool_catalog: auto-load top result on query.
- Documentation: TOOL_TRANSLATION_METHODOLOGY.md with delimiter strategy sections.

### Fixed
- OpenAI Responses API: content normalization for 2nd+ rounds and previous_response_id.
- OpenAI Responses API: stale previous_response_id error handling.
- Web UI: image attachment rendering and tool message display.
- Debug output: redirect to sys.__stdout__/sys.__stderr__ for proper diagnosis.
- Various: cleanup of debug logs, temp files, and CONFIG debug log.

### Changed
- Provider capabilities centralized in provider_caps.
- Removed debug temp files; updated .gitignore.

## [0.5.41] - 2026-07-08

### Added
- New tool `lint_js_ts`: lint JavaScript/TypeScript files using Biome with 34-language i18n.
- New tool `mdformat_check`: check/auto-fix Markdown formatting with YAML front matter support.
- New provider `novita`: OpenAI-compatible API provider with reasoning support.
- i18n: full 34-language UI translations for all tools (mdformat, lint_js_ts, lint_format).
- Web UI: reasoning_content display (streaming + non-streaming), tool overlay, favicon.
- CLI: reasoning_content shown in gray for Responses API (non-streaming).

### Fixed
- Image generation: `fmt` → `output_format` keyword for GPT image models.
- Image generation: filter DALL-E-only quality values (standard/hd) for GPT models.
- Image generation: map background values to valid options (transparent/opaque/auto).
- Tool registration: renamed `run()` → `run_tool()` for proper module registration.
- mypy: fixed type errors in echonet_control, responses parser, uagent_llm, web.py.
- ruff: replaced `dir()` with `locals().get()` for reasoning_content.
- OpenAI Responses API: note that gpt-5.x models don't send reasoning_text.delta during streaming.

### Changed
- Frontend rebuilt with fixed asset filenames, SVG favicon.
- Provider list centralized in `provider_caps.ALL_PROVIDERS`.
- Removed backup files (*.org*), node_modules; updated .gitignore.
- mdformat/mdformat-frontmatter moved from core dependencies to auto-install on demand.

## [0.5.40] - 2026-07-07

### Added
- `generate_zai`: new tool for generating ZhipuAI (ZAI) compatible code from prompts.
- `reverse_geocode`: new tool using Nominatim for reverse geocoding with 39-language i18n.
- `code_map`: add ontology (JSON-LD) export, import/relation extraction, and i18n support.
- GUI/Web/A2A/VSCode: `.env.sec` files are now automatically created/overwritten when missing.
- `translate_text`: extended supported languages for broader coverage.

### Fixed
- Responses retry state and tool utility edge cases.
- `browser_playwright_run` and `run_tool` alias restored.
- i18n: `:tools reload` message now translated for all 34 locales.

### Changed
- GPT-5.4+ tool list display adjusted.
- Docs: tool counts updated to 171 tools (87 parallel-safe), reverse_geocode added to IoT table.
- Docs: JSON-LD ontology and Mermaid dependency graph added to DEVELOP.md.
- Remove unused skills/servicenow-open/ directory.
