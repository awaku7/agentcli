# Changelog

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
