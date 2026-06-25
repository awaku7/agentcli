# Changelog

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

### Added
- Added `save_as` parameter to `fetch_url` tool for saving binary responses directly to file.
- Added browser_playwright suggestion when HTML content is detected via HTTP GET.
- Added markdown rendering for `:chat` responses.
- Made git optional at startup (removed `check_git_installation` from CLI startup).

### Fixed
- Fixed `browser_playwright` wait action: `selector` is now optional to prevent KeyError.
- Fixed broken chat panel by reverting problematic markdown JS changes.
- Fixed Hindi `Why uag` documentation (bullet 3 to 4, Devanagari A2A).

### Docs
- Added VSCODE.md with extension details and linked from README.
- Added VS Code extension info to all translation README files.
- Minor documentation fixes.

### Chores
- Prepared for VSCode marketplace release.

## [0.5.22] - 2026-06-23

### Added
- Added php2idx and cobol2idx tools for PHP and COBOL source code indexing.
- Added i18n support (34 locales) for all idx family tools.
- Added `:tools output` command to toggle tool result display on/off (34 langs).
- Added BM25 mode for `semantic_search_files` via `UAGENT_SEMANTIC_SEARCH_MODE=bm25` environment variable.
- Added `skip_llm_dedup` option to `smart_merge_profiles` to skip LLM-based deduplication during intermediate merges.
- Added `max_log_files` parameter to `profile_from_logs` to limit the number of log files processed.
- Added `max_content_chars` parameter to `_sanitize_log_for_profiling` to trim oversized messages (e.g. image data).
- Added support for `:profile fromlog N` and `:profile-fromlog N` syntax to specify the number of recent log files.

### Changed
- Updated tool count to 131 (total) / 76 (parallel-safe) / 13 (genres).
- Increased `chunk_size_limit` from 300 to 500 in `profile_from_logs` processing.
- LLM deduplication now runs once on the final merged profile instead of per-chunk, improving performance.
- Removed the redundant `:list` command alias; use `:logs` instead.

### Fixed
- Fixed GUI output HTML: changed `white-space` from `pre` to `pre-wrap` for proper word wrap.
- Fixed `graph_rag_search` being incorrectly invoked when BM25 mode is active.

### Performance
- Removed `sorted(list(...))` wrappers and optimized `startswith` to tuple-based lookups.

### Chores
- Fixed ruff lint issues (F821, F841, F401, E741) and ts2idx depth bug.
- Fixed E722 bare except usage across the codebase.
- Fixed mypy errors in rs2idx, py2idx, browser_playwright, and scheckgui.
- Added E701 and E702 to ruff ignore list for compact parser style.

## [0.5.21] - 2026-06-22

### Added
- Added VSCode extension support: TypeScript scaffold (`vscode-extension/`), WebSocket client, chat panel, and tree provider.
- Added `scheckws.py` wrapper to easily start the WebSocket server from the project root.
- Added chat handler to `ws_server`, wiring VSCode panel to call LLM.
- Integrated LLM chat via `run_cli_startup` + `run_llm_rounds` in `ws_handler`.

### Fixed
- Fixed TypeScript compilation issues: added `@types/node`, fixed `tsconfig.json`.
- Removed redundant `activationEvents` from VSCode extension (auto-detected by VS Code).
- Simplified chat handler with proper fallback message for unconfigured LLM.
- Replaced `ToolCallbacks.get_workdir()` with `os.getcwd()` in `ws_handler`.
- Fixed WebSocket handler: `tool_genre_mask` type, `should_exit` check, `providers` import, timeout settings, and workdir timing.

### Changed
- Updated `MANIFEST.in` and `.gitignore` to exclude `vscode-extension/` from PyPI distribution.

## [0.5.20] - 2026-06-25

### Added
- Added Gmail tools: `gmail_send` (SMTP) and `gmail_read` (IMAP) for sending/receiving emails.
- Added `parse_eml` tool for parsing .eml email files.
- Added `email_utils.py` shared module to reduce code duplication across email tools.
- Added full i18n (34 locales) for all three new tools.
- Added `mode_after` parameter to `replace_in_file` for independent regex mode on anchor_after.

### Changed
- Updated tool count (112→116) and parallel-safe count (66→67).
- `create_file` now returns JSON `{"ok": false, "error": "..."}` instead of raising raw exceptions.
- `replace_in_file` match_hits now includes insert_before/insert_after/insert_at_line/insert_at_end positions.
- `replace_in_file` insert_at_end now ensures trailing newline before appending.
- `replace_in_file` insert_at_line now raises ValueError for out-of-range line_no.
- Fixed duplicate computation block in `replace_in_file` (dead code).

## [0.5.19] - 2026-06-22

### Added
- Added 'index' genre for source code navigation tools (11 idx tools for py/ts/cs/jv/dart/cpp/rs).
- Added Z.AI provider to provider list.
- Made ThreadPool size configurable via UAGENT_PARALLEL_WORKERS environment variable (default 8).
- Added idx family documentation to all 33 README translations, tool table, and DEVELOP docs.

### Changed
- Updated tool count (111→112) and parallel-safe count (55→66).
- Clarified parallel execution documentation (max 4 concurrently, 66 parallel-safe).
- Added UAGENT_PARALLEL_WORKERS and missing providers to ENVIRONMENT.md and ENVIRONMENT.ja.md.

## [0.5.18] - 2026-06-21

### Added
- Added MiniMax provider (OpenAI-compatible, endpoint https://api.minimax.io).
- Added Turkish (tr) README translation.
- Added README translations for el (Greek), he (Hebrew), hu (Hungarian), ro (Romanian).
- Added i18n locales for el/he/hu/ro in tool JSONs.
- Added world map SVG showing all translation languages in README.translations.md.
- Added `:provider` command specification for dynamic provider switching.
- Added i18n fix plan documentation for .po compilation and tool JSON translations.

### Changed
- Tools on/off genre control: shell metachar confirm disabled by default, file genre separated from generic execution tools.
- Restructured README.translations.md with categorized tables.
- Language names in README.translations.md changed to clickable links.
- Redrew world map with Miller projection and more detailed continents.
- Expanded md2idx translations to 30 languages.

### Fixed
- Removed SVG map file from repository (GitHub auto-links SVGs, breaking inline display).
- Embedded SVG as base64 data URI to prevent GitHub auto-linking.
- Display world map as inline image instead of SVG link.
- Used hardcoded SVG coordinates based on country bounds for accurate capital placement.
- Plotted language dots at capital cities instead of geographic centers.
- Reordered SVG elements so background renders behind paths.
- Fixed map aspect ratio to 1200x720 with equirectangular projection.
- Escaped ampersand in SVG legend text.
- Restored broken HTML/code blocks in 9 translated README files.
- Fixed heading number offset in md2idx tool.

### Chores
- Removed stale documentation files (old design docs, TBDs, brainstorming notes).

## [0.5.17] - 2026-06-20

### Fixed
- Fixed literal `{persist}` placeholders appearing in `catalog_tool.json` output (30 languages).
  - The `msg.load.ok` string contained `(persist={persist})` suffix that was not substituted
    because the caller does not pass a `persist` parameter.
  - Removed the unused `persist` parameter reference from `tools_control_tool.py`.
- Removed the `"""retry` / `"""end` mention from `human_ask` `ui.howto` display text
  in 10 locale translations (bn, fa, ko, mr, nb, sw, th, vi, zh_CN, zh_TW).

### Chores
- `.vs/` and `.uagent_web_uploads/` added to `.gitignore`.

## [0.5.16] - 2026-06-20

### Fixed
- Fixed 5408 truncated translations across all 77 tool JSON files (29 languages).
  - Translations that were cut off due to character limits in the original auto-translation
    have been re-translated using Google Translate.
  - Affected languages: ar, bn, cs, de, es, fa, fi, fr, hi, id, it, ja, ko, mn, mr, nb, nl,
    pl, pt, pt_BR, ru, sv, sw, th, tr, uk, vi, zh_CN, zh_TW.
