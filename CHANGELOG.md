# Changelog

## [0.6.4] - 2026-08-20

### Added

- feat: add unified structured output support across compatible providers
- docs: add enterprise policy editing guidance

### Changed

- fix: map Gemini function responses to the supported `user` content role
- fix: allow deletion of numeric `.org` backup files without an additional confirmation prompt
- fix: normalize MCP tool results as JSON
- style: apply Ruff and Black formatting across the project
- test: add coverage for Ollama request compatibility


## [0.6.3] - 2026-08-19

### Added

- feat: add structured observability event envelopes and normalize event-specific payloads
- feat: add a Mermaid-to-editable-Excel flowchart conversion tool

### Changed

- fix: enforce strict enterprise endpoint allowlists
- docs: refresh task-store scope, generated code-map summary, and provider configuration guidance
- test: make Computer Use errors locale independent
- refactor: keep OpenAI fast mode out of the setup wizard

### Removed

- remove the obsolete standalone Mermaid Excel converter package sources and tests

## [0.6.2] - 2026-08-18

### Added

- feat(i18n): complete localized Computer Use messages and tool catalog translations across supported locales
- feat(i18n): wire host and Computer Use internationalization, including shared policy confirmations
- feat(cli): expand `:` command and argument tab completion for logs, auto-pilot, plugins, memories, and profiles

### Changed

- docs: update Computer Use internationalization implementation guidance
- docs: document test-only dependency installation and CI-equivalent local checks
- docs: document auto-pilot termination semantics and translate the tool flow documentation to English
- docs: correct Auto-Pilot key descriptions in localized READMEs and standardize translation links
- docs: use absolute GitHub links for repository documentation while preserving the PyPI link
- test: add a space-steganography sample and detector for Unicode space experiments

## [0.6.0] - 2026-08-15

### Added

- feat: add distributed leader lease coordination and durable task checkpoints
- feat: add resilient remote agent task control, checkpoint recovery, and streamed A2A task events
- feat: add dependency-aware DAG scheduling and persistent task storage
- feat: add enterprise policy enforcement across credentials, MCP, skills, and plugins
- feat: add shared credential storage and lifecycle/observability integration across runtimes

### Changed

- fix(deps): align the pinned `llmcapa` dependency with the installed 0.5.4 release
- ci: separate and complete test dependencies across supported platforms
- docs: update improvement roadmap, local CI checks, architecture, and policy guidance

## [0.5.72] - 2026-08-13

### Changed

- fix(openrouter): extract reasoning from the official OpenRouter SDK response (`reasoning` field, not `reasoning_content`)
- fix(bitchat): correct mistranslation of `nostr` status across all locales
- feat(bitchat): add BLE receive/connect debug logging (gated by `UAGENT_BITCHAT_DEBUG=1`)

## [0.5.71] - 2026-08-11

### Added

- feat(packaging): lazily install optional language tokenizer dependencies only when the related tools are used
- feat(packaging): lazily install BLE dependencies and defer optional tool imports

### Changed

- fix(packaging): finish lazy optional dependency loading across document, spreadsheet, PDF, presentation, screenshot, semantic-search, and cryptographic tools
- fix(packaging): initialize the `pythainlp` cache safely
- fix(mcp): correct MCP client import handling
- fix(cli): correct i18n command and option syntax
- fix(status): keep Python IDLE shell status output free of ANSI color control sequences
- docs: update localized tool headings, descriptions, and README tool listings
- docs: document repository analysis and coverage tools

## [0.5.70] - 2026-08-11

### Changed

- fix(deps): pin `llmcapa` to the verified 0.5.1 release

## [0.5.69] - 2026-08-11

### Added

- feat(tools): add the Pint-based `quantities` unit conversion and physical quantity tool
- feat(tools): add Yahoo! Japan Transit route search with candidate routes, fare breakdowns, and query-preserving source links
- feat(tools): add `geodesic_distance` for Haversine straight-line distance and optional reverse geocoding
- feat(transit): add a bundled MLIT N02 station master for resolving ambiguous station names by destination proximity

### Changed

- feat(i18n): add complete localized catalogs for the new tools
- docs: update tool counts, parallel-safe counts, transit, quantities, and geodesic-distance documentation
- fix(packaging): include tool data resources in source and wheel distributions
- fix(status): normalize generic LLM status labels while preserving reasoning state
- fix(types): resolve mypy issues in token, cloud API, and pybitchat helpers

## [0.5.68] - 2026-08-07

### Added

- feat(code_map): add modular project analysis with multilingual symbols, relations, manifests, lockfiles, caches, CMake, and renderers
- feat(code_map): add COBOL COPY/CALL and Objective-C/Objective-C++ include analysis
- feat(http): add the generic HTTP request tool
- feat(forecast): add regression forecasting models and localized options

### Changed

- feat(code_map): expose dependency edges, transitive dependency metadata, local classpath candidates, TFM metadata, and deterministic version conflict reporting
- refactor(tools): keep `code_map_tool.py` as the stable facade for split internals
- fix(i18n): keep the complete `code_map_tool.json` catalog at the public facade path
- fix(screenshot): tolerate mocked capture backends that do not materialize an image file
- docs: update localized documentation and tool catalogs

## [0.5.67] - 2026-08-06

### Added

- feat(tools): add the localized CMake project indexer with tests
- feat(tools): add Visual Studio solution and MSBuild indexers with localization

### Changed

- docs: standardize multilingual MCP guide links
- i18n: improve localized search-term handling and Visual Studio catalog coverage

## [0.5.66] - 2026-08-05

### Added

- feat(tools): expand the catalog with AWS, Azure, GCP, VBA, LotusScript, and Makefile tooling
- feat(i18n): add runtime localization catalog and translation maintenance scripts
- feat(tools): add forecasting and pybitchat tool specifications

### Changed

- docs: refresh tool counts, cloud API documentation, and localized README content
- fix(config): expose the GUI entry point under `project.gui-scripts`
- fix(search): align Janome POS handling with the active tokenizer output

## [0.5.65] - 2026-08-04

### Added

- feat(network): add offline `capture_analyze` orchestration for pcap analysis and local process correlation
- feat(network): add conservative `normal` / `review` / `suspicious` / `unknown` traffic classification
- feat(network): add loopback-only experimental live capture with bounded duration and packet count
- feat(network): classify TCP retransmission evidence as `confirmed`, `possible`, or `capture_duplicate`
- test(network): add loopback capture integration coverage and retransmission classification tests

### Documentation

- docs(network): document the network toolkit roadmap, safety policy, release status, and experimental live-capture scope

### Internationalization

- i18n: translate Responses API lifecycle messages and capture-analysis tool metadata across supported locales

## [0.5.64] - 2026-08-03

### Changed

- remove tool-result caching and obsolete cache reuse tests
- add PFN provider adapter and tests
- translate localized README documentation blocks

## [0.5.63] - 2026-08-02

### Fixed

- fix(stream): prevent an extra blank line when reasoning output ends with a newline
- fix(bitchat): improve Android Noise XX interoperability, BLE padding, handshake recovery, fragment pacing, and duplicate-message suppression
- fix(skills): handle native structured tool responses and invalidate response/provider caches when applying a skill

### Documentation

- docs: document Android/Python bitchat Noise interoperability findings and remaining runtime checks

## [0.5.62] - 2026-07-31

### Added

- feat(bitchat): add `:bitchat start` / `:bitchat stop` dynamic commands to start/stop the BLE Mesh node
- feat(bitchat): register the existing `:bitchat peers` command in CMD_SPECS (was implemented but not registered)
- test: add TDD tests for `:bitchat start` / `:bitchat stop` handlers and CMD_SPECS registration
- i18n: add en/ja messages for the node start/stop commands

### Performance

- perf(cli): speed up dynamic-command tab completion — snapshot the command map once per completion request and never block on first-time plugin import (background warmup keeps loading; partial results are fine)
- perf(tools): cache `get_dynamic_commands_map()` results (invalidated on register/unregister); add `get_dynamic_subcommands()` helper and `block=False` non-blocking mode (~80x faster map lookups)

### Fixed

- fix(cli): preserve fast consecutive human_ask replies in CLI — skip the stdin typeahead flush right after a previous human_ask reply (e.g. :skills number selection then y confirmation) so quick replies are not discarded; passwords always flush
- fix(bitchat): implement missing Phase 2-6 pybitchat components — `NoiseXXStateMachine` / `TransportCipher` (Noise XX handshake), `sign_announce` / `verify_announce` / `PeerRegistry`, `MessageDeduplicator` / `RelayController`, `CourierEnvelope` / `CourierStore`; keep existing Fragment implementation
- fix(bitchat): accept pre-reload `CourierEnvelope` instances in `CourierStore.store()` (tolerates `tools.reload_plugins()` re-imports)
- fix(bitchat): keep `pybitchat_shared` runtime state alive across tool reloads — `_load_plugins()` no longer `importlib.reload()`s already-imported helper modules (no `TOOL_SPEC`/`run_tool`), so `_LLM_EVENT_QUEUE` / `_CHAT_MODE` / `_RUNNING` survive `start_tools_warmup()` and `reload_plugins()`; fixes chat_mode="llm" peer messages being displayed but never injected into the LLM
- test: add `tests/test_pybitchat_llm_inject_reload.py` (LLM event queue + chat mode survive `reload_plugins()`; injection reaches the queue)
- fix(gpt54): re-export `_select_tool_specs_for_gpt54` from `uagent_llm` (alias of `llm_tool_narrowing._select_tool_specs_legacy`)
- fix(gpt54): narrow legacy tool selection to helpers + catalog hits + dynamically loaded tools instead of sending every loaded tool (matches TOOL_FLOW.md)
- fix(gpt54): update `test_gpt54_tool_search.py` to the current `UAGENT_GPT54_TOOL_SEARCH=native/legacy/off` design (default native, openai/azure only)
- fix(i18n): add missing en/ja keys for pybitchat nostr/on/via params; fix `err.payload_required` ja translation
- fix(i18n): replace non-ASCII arrows/dashes in pybitchat_shared.py comments and messages (utilities i18n check)
- fix(i18n): fill missing same-as-en keys for 18 tool JSONs (bacnet/modbus/opcua/browser_playwright/csv2idx/echonet/json2idx/lint_format/log2idx/tools_control etc.) via `translate_text` engine; wrap literal descriptions in `_()` for browser_playwright_tool/tools_control_tool; i18n sub_agent_tool status returns; replace non-ASCII in \_matter_common/index_tool_helpers/nostr_transport
- fix(i18n): wrap user-facing string literals in utilities with `_()` (21 modules: \_genre_control_util/\_matter_log/_secp256k1/bacnet_shared/bitchat_geo/dali_shared/email_utils/generate_grok/generate_zai/modbus_shared/mqtt_shared/nostr_transport/opcua_shared/os_scheduler_helper/rust_helper/ucp_shared/vision_\*) and add `make_tool_translator` where missing — `test_tools_utilities_no_user_facing_string_literals` now passes
- fix(i18n): localize pybitchat display/inject messages (handshake/peer/file/scan/service/Nostr notifications, "sending as plain text (unencrypted)" etc.) via `_()` with %(name)s placeholders; add `pybitchat_shared.json` with en/ja translations
- fix(logs): `:logs` now shows the same message count that `:load` reports ("Conversation message count") — the count includes the re-inserted system prompt, preserved `[SKILL]`/`[HOOK]` system messages, user/assistant/tool messages, plus the auto-restored `[CWD]` marker when its directory still exists (previously `:logs` counted only user+assistant, so it differed by tool messages + 1)
- fix(load): `:load` workdir auto-restore now actually works — `[CWD]` is extracted from the raw log lines instead of the normalized messages (which strip non-[SKILL]/[HOOK] system messages); the restored `[CWD]` marker is included in the reported count
- feat(web): `/api/logs/{index}/preview` uses the same total_messages semantics as CLI `:logs`/`:load` and adds `total_tool` / `preserved_system` fields
- test: add `tests/test_logs_load_count_consistency.py` (CLI `:logs` count == `:load` count, incl. `[CWD]` bonus and raw-line cwd extraction)
- fix(i18n): fill 727 missing tool-JSON keys across 32 langs via unique-string dedup + translate_text (timeout descriptions for bacnet/modbus/opcua, new browser_playwright params, csv2idx/echonet_scan/json2idx/lint_format/log2idx/tools_control keys); restore `{total}` placeholder in fa `msg.index_output` for cl2idx/dds2idx/excel2idx/ppt2idx/rpg2idx; drop 1183 orphaned extra keys (en-removed) from bluesky/switchbot_batch/upnp_igd_control/usb_camera/vision_deepseek/vision_ollama/echonet_cache/forecast — `scripts/i18n_tools_check.py` now passes with 0 errors

## [0.5.61] - 2026-07-30

### Added

- feat: Azure OpenAI GPT Realtime support with GA and preview endpoint formats
- feat: Amazon Bedrock Nova Sonic bidirectional realtime voice adapter
- feat: automatic installation of optional Bedrock realtime SDK when selected
- feat: setup wizard configuration for Azure, Bedrock, and other realtime providers
- docs: update README and localized README files with realtime provider support

### Fixed

- fix: handle c-key interrupts consistently across Gemini and other providers

## [0.5.60] - 2026-07-29

### Added

- feat(realtime): update Gemini realtime API protocol and default model (gemini-3.1-flash-live-preview)
- docs: update DEVELOP.md and multi-language READMEs with latest \*2idx tool count (26)

### Removed

- chore: remove benchmark directory and obsolete development review notes

## [0.5.59] - 2026-07-28

### Added

- feat: full-duplex Realtime voice with pywebrtc-audio WebRTC AEC3
- feat: OpenAI Realtime Function Calling for the read-only get_current_time tool
- docs: update all localized README files with Realtime/AEC3 and Function Calling guidance

### Fixed

- fix: synchronize AEC3 far-end reference with actual speaker playback
- fix: add optional Realtime audio diagnostics and remove duplicate README sections

### Changed

- chore: apply Black formatting and resolve all Ruff findings

## [0.5.58] - 2026-07-27

### Added

- feat: add pybitchat BLE Mesh tools with chat mode auto-forward
- feat: Nostr transport, Noise XX handshake, geo channels, secp256k1 helpers for bitchat
- feat: add OS-level NTP sync info to get_current_time output
- docs: add docs/BITCHAT.md and expand COMMUNICATION docs

### Fixed

- fix: avoid stale [REPLY] prompt after human_ask reply due to race condition
- fix: remove spurious blank line before instruction files prompt
- fix(pybitchat): TypeError in geo join - is_running is property not method
- fix: PacketFlag.HAS_RECIPIENT undefined name; CommandResult TYPE_CHECKING import

### Changed

- chore: ruff/black cleanup across src (unused imports, E731 lambda→def, formatting)

## [0.5.57] - 2026-07-26

### Added

- feat: :skills list KEYWORD / :skills find KEYWORD for filtering skills by name or description
- feat: add Together AI and Vercel AI Gateway providers, llm_novita reasoning_effort

### Fixed

- fix: remove duplicate Forecast rows in 29 language READMEs

### Changed

- docs: update all 34 language READMEs - 170→183 tools, add Forecast category in each language
- docs: update provider lists in docs/README.ja.md and DEVELOP.md file count
- i18n: add Together AI / Vercel AI Gateway to 32 translation provider lists
- chore: remove test/ directory (test_apply_patch.py)

## [0.5.56] - 2026-07-26

### Added

- Forecast tool: LLM-based time series forecasting with auto-install of dependencies, i18n, CI integration, plot support, and TDD tests. Models: StatsForecast, AutoARIMA, AutoETS, Theta, MSTL, Prophet, LightGBM, CatBoost, TimesFM, Chronos.
- `:skills list KEYWORD` / `:skills find KEYWORD` for filtering installed skills by name or description.

### Fixed

- Prophet wrapper: `predict(int)` returns only forecast horizon, `predict(DataFrame)` column rename fix, disable yearly_seasonality for better quarterly fit.
- LightGBM/CatBoost: feature count mismatch between train and predict; Prophet predict bugs; reorder auto-select tiers per forecast_modules priority list.
- StatsForecast v2.x API compatibility (forecast needs df argument); update TimesFM to TimesFM_2p5_200M_torch; LightGBM/CatBoost last_feats bug. All 9 models verified end-to-end.
- Remove duplicate Forecast category rows in 29 language READMEs.

### Changed

- README and 33 language translations: tool count updated from 170 to 183, add Forecast category.
- i18n: forecast_tool.json translated to all 34 languages (via tool_json_i18n_batch).
- Remove test/ directory (test_apply_patch.py) - unused test file cleanup.

## [0.5.55] - 2026-07-24

### Fixed

- WEB startup link i18n: correct msgstr for msgid "Starting server on" in he/hu/el/ro/bn/ko so localhost URLs read naturally; regenerate matching .mo (CRLF-safe).
- welcome: non-English GitHub README URL now points to `docs/README.{lang}.md` (en stays root `README.md`).

## [0.5.54] - 2026-07-24

### Added

- IBM i source index tools (genre=`index`, mode=`index`|`section`):
  - `cl2idx` — CL/CLP/CLLE (`.cl`/`.clp`/`.clle`): continuation join, multi-line comments, SEU sequence strip, IF/DO/SELECT↔END stack `end_line`, DCL labels, common commands (RTVJOBA/CHKOBJ/SNDRCVF, etc.).
  - `dds2idx` — DDS PF/LF/DSPF/PRTF (`.pf`/`.lf`/`.dspf`/`.prtf`/`.dds`): fixed-column SEU multi-layout scoring, DSPF const/SFLCTL/INDARA, TEXT/COLHDG field labels, file-type score, **REF/REFFLD workdir-local follow** (type annotation on `R` fields), **DSPF indicator/attr decode** (conditioning indicators, DSPATR/COLOR/CF args, packed constants).
  - `rpg2idx` — RPG/RPGLE/SQLRPGLE (`.rpg`/`.rpgle`/`.sqlrpgle`): free-form (`**free`/`**end-free`, ctl-opt, dcl-\*, begsr/endsr, /copy|/include, `...` continuation) and fixed-form F/D/P/C/H/I/O-spec (BEGSR case preserved, SEU strip).
- Regression tests: `tests/test_cl2idx_tool.py`, `tests/test_dds2idx_tool.py`, `tests/test_rpg2idx_tool.py`.
- Review-plan gap regression tests for `go2idx`, `kt2idx`, `cs2idx`, `swift2idx`, `jv2idx`.
- Review-plan regression tests for `md2idx`, `dart2idx`, `php2idx`, `rs2idx`, `ts2idx`.
- Regression tests: `tests/test_py2idx_tool.py`, `tests/test_cpp2idx_tool.py` (full \*2idx suite now 16 tools).

### Changed

- `dds2idx`: REF/REFFLD simple follow within workdir — resolve `REF(file)`/`REF(lib/file)`, annotate `R`/`REFFLD` fields with source types (`CUSTID R 10A <= CUSTPF.CUSTID`), mark unresolved targets.
- `go2idx`: method receiver labels, generic func/type, struct|interface labels, type aliases.
- `kt2idx`: extension fun, data/sealed labels, companion name, multi-line preprocess.
- `cs2idx`: file-scoped namespace; brace-stack member attach / pop order fix.
- `swift2idx`: actor/protocol/extension labels; async/throws in modifiers.
- `jv2idx`: annotation/record labels; multi-line text-block state across lines.
- `ts2idx`: class_stack/brace pop order (cs pattern); remove unused `matched` (F841).
- `dart2idx`: `extension Name on Type` pattern order.
- `php2idx`: `_parse` uses `_preprocess()` (attributes + multi-line join).
- `cpp2idx`: brace-stack aligned with `cs2idx` (pop finished same-level scopes before push; `inside_function` suppresses nested heuristics) so same-line `struct`/`class` no longer swallows following free functions as members.
- Tool JSON i18n: full non-en locales for `cl2idx`/`dds2idx`/`rpg2idx` (33 langs; `x_search_terms_en` kept English).
- Plugin enabled status one-liner shared across CLI/Web/GUI (`format_enabled_plugins_status` / `load_plugins_status_at_startup`); i18n msgids for instruction-load INFO lines.

### Fixed

- `dds2idx`: DSPF indicator/attribute decode — conditioning indicators, `DSPATR`/`COLOR`/`CFnn` args on fields, packed constant lines (`5  2'Name'` → layout; no longer misread form-type `A` as field name).
- `*2idx` `mode=section` off-by-one: 1-based `entry["line"]` was used as 0-based slice start, so single-line defs returned empty string. Corrected `_source_lines` / `get_section` in dart/rs/ts/cpp/cs/jv/go/kt/swift (others already converted or correct).
- Responses API `previous_response_id` / OpenRouter: do not send `previous_response_id` on OpenRouter (compat strip + provider gate, same as Grok). On stale/invalid rid or `invalid_prompt` / `APIResponseValidationError` (string `error.code`), clear rid, set `_stale_rid_occurred`, and retry once with full local history. Tests: `test_previous_response_id_compat.py`, `test_openrouter_round_helpers.py`.
- Web/GUI: project instruction selection (AGENTS.md etc.) via human_ask modal — no server-stdin block on TTY; connect-time room bootstrap.
- human_ask: pending/reconnect re-send, ignore empty replies, Skip, interrupt unblocks waiter, WAIT status while asking.
- LLM Stop: `LLMWaitInterrupted` during threaded LLM wait; web worker reaches IDLE in `finally`.
- Web chat surfaces startup INFO for loaded instructions / skip / plugin status / long-term memory (i18n; `get_loaded_instruction_paths()` instead of English marker parse).
- WEB STATUS console leak on Windows: set `core._is_web=True` in `init_web()` before any `set_status`.

### Notes

- IBM i \*2idx (`cl2idx` / `dds2idx` / `rpg2idx`) implementation track complete; no open implementation work.
- Residual **out of scope** (documented in `SPEC_CL2IDX_DDS2IDX.md` §5.9/§10 and DEVELOP): EBCDIC; `ibmi2idx` dispatcher (do not add); `dds2idx` multi-lib/full object resolve, full DSPATR bit-combo semantics, PRTF rendering, ICF/binary; `rpg2idx` full fixed-column dialect variants, deep embedded-SQL semantics, `/IF` expression evaluation.
- `rpg2idx`: embedded SQL, `/IF` conditional compile, and common fixed-column paths are implemented (index-level only for SQL//IF).
- `dds2idx`: REF/REFFLD follow (same workdir, depth 1) and DSPF indicator/attr/const decode are implemented.

## [0.5.53] - 2026-07-20

### Added

- `echonet_scan` network `scope` filter (`all`/`local`/`external`/`self`/`local_other`) with per-node scope fields and summary counts; cache key includes scope.
- Dependency: `xai-sdk>=1.17.0` for Grok/xAI gRPC path.

### Changed

- BACnet tools (`bacnet_scan`/`read`/`write`) share `bacnet_shared` background event-loop lifecycle for BAC0 2025+ async who_is/read/write/disconnect; refcount + optional keep-alive for COV.

### Fixed

- Single-tool enable reloads the matched tool module (and `*_shared` helper when present) so source edits apply without process restart.

## [0.5.52] - 2026-07-19

### Added

- Plugin `commands/*` registered as namespaced `:` commands (`:plugin`, `:plugin sub`, `:plugin:sub`); core-reserved top-level names refused; activate/deactivate lifecycle.
- Plugin enable/startup activates MCP, agents, and hooks; bare `:plugin install <name>` resolves from registered marketplaces (Claude Code style).
- hooks: SessionStart/Setup/UserPromptSubmit stdout as `[HOOK]` system context; UserPromptSubmit block decisions on CLI/GUI/Web; `${CLAUDE_PLUGIN_ROOT}` / `${UAGENT_PLUGIN_ROOT}` expansion.
- i18n: gettext for `:model` / capa UI; residual UI strings; `po_i18n_batch`; Grok audio models in `:model`; pot/po/mo refresh.
- Runtime process-exit policy: helpers raise instead of bare `sys.exit`; tool host contains tool `SystemExit`/`Exception` (docs in DEVELOP.md §6.1).
- mypy: `typings/numpy` stub shadow + numpy `follow_imports = skip` for 3.11 baseline.

### Changed

- Plugin `remove`: deactivate components, clear `enabledPlugins` key and `pluginConfigs`, then rmtree (not leave enabled=true residue).
- auto-unload user copy: "productive rounds" → "LLM rounds" (all locales).

### Fixed

- Empty assistant / no-tool recovery hardened for Grok (history/UI-only WARN, next-turn recovery).
- exec: isolate child stdin so CLI does not exit on EOF.
- Agent tool loops, Responses previous_response_id, catalog steering, short session logs.
- OpenRouter SDK import no longer shadows test injection; safer provider/client init errors.

## [0.5.51] - 2026-07-19

### Added

- hooks: SessionStart/Setup/UserPromptSubmit stdout → `[HOOK]` system context injection (plain text + `additionalContext` JSON); Web/GUI deferred apply; log reload keeps `[HOOK]` like `[SKILL]`.
- `:help`: overview and per-command detail including CMD_SPEC.
- `translate_text`: brand/product term protection during translation.
- tmp-based batch translator for tool JSON i18n.

### Fixed

- Empty assistant / no-tool loop: drop blank assistant turns from history, keep WARN out of model messages, add next-turn recovery prompt; raise default `UAGENT_EMPTY_NO_TOOL_MAX` for grok/xai to 5.
- Empty-no-tool follow-up: defer recovery into the next real user turn (no stacked synthetic users), log WARN as UI-only assistant for Web, skip empty assistant append before history, strip `_uagent_ui_only`/`_uagent_internal` in sanitize.
- Grok: show reasoning effort in CLI status (`LLM:` / `LLM:auto->...`).
- Grok/Responses: stream reasoning continuously without breaking lines on `.` / `!` / `?`.
- i18n: repair empty and remaining same-as-en tool JSON values; protect param names; apply translate_text/audio_speech locales.
- lint: remove unused variable; apply ruff/black cleanup across touched modules.

## [0.5.50] - 2026-07-18

### Added

- llmcapa: shared `llmcapa_util` lookup (provider aliases), vision gating, max-token clamp, shrink ctx, richer `:model v`.
- llmcapa: resolve tokenizer model ids; gate Responses/FIM with capability data; clamp Ollama/FIM/Grok max tokens.
- llmcapa: clamp profile/translate/sub-agent max tokens; sub-agent usage cost estimate; deprecated model WARN on banner/`:model`; refresh integration docs.
- llmcapa: vision tools (analyze_image backends) check vision support and clamp max tokens.
- llmcapa: DeepSeek/ZAI/Novita shared max_tokens; image/embedding capability checks for generate_image/img2img/semantic_search.
- llmcapa: `supports_audio_input` / `check_audio_input_support` for STT gating (catalog miss allows; not completion max_tokens).
- llmcapa: `supports_audio_output` / `check_audio_output_support` for TTS gating (catalog miss allows; not completion max_tokens).
- `audio_transcribe`: Grok/xAI batch STT via POST `/v1/stt` (multipart file or url); provider aliases `grok`/`xai`; default model `grok-stt-batch`; diarize/keyterm/filler_words/format options.
- `audio_speech`: Grok/xAI TTS via POST `/v1/tts` (requests); provider aliases `grok`/`xai`; defaults model `grok-tts`, voice `eve`; language/speed/codec mapping.
- Management tool loop detection: fingerprint by target (`tool_load:name`); `unload_tool(target)` and auto-unload via `disable_single_tool` clear that target's load streak so unload→reload is not blocked.

### Changed

- llmcapa dependency bumped to >=0.4.1.

## [0.5.49] - 2026-07-15

### Added

- Background tools warmup after CLI/GUI/Web startup to reduce first `:` command latency.
- `switchbot-ble`: multi-device advertisement status decoding per official BLE API.
- Design notes for browser_playwright session extension and scale tool.

### Fixed

- `shrink_llm`: stop stacking multiple history-summary system messages; merge prior summaries into one rolling summary.
- `shrink_llm`: add hysteresis so auto-compression does not re-trigger immediately after a successful shrink.
- Grok: use simple_xai_chat for history compress/profile LLM paths.
- Grok: prevent double-printing streamed assistant replies.

### Changed

- Tools plugin load remains lazy, but is prewarmed in a background thread after startup.

## [0.5.48] - 2026-07-13

### Added

- TOOL_CREATOR_GUIDE.md translated into 33 languages via Google Translate.
- `translate_text` tool: newline placeholder changed to ⏎ (U+23CE) for better translation fidelity.
- `<<<BLOCKNNNN/>>>` marker format for code block preservation during translation.

### Changed

- `translate_text`: placeholder `[=BR=]` replaced with `⏎` (U+23CE) to avoid Google Translate corruption.
- Tool documentation: 33 language versions of TOOL_CREATOR_GUIDE.md available in `docs/`.

### Fixed

- Code block markers in translated documents now properly survive Google Translate restructuring.

## [0.5.47] - 2026-07-13

### Added

- WEB UI: Reasoning display ON/OFF toggle button in Settings panel.
- Desktop GUI: Reasoning display 🧠 toggle button in status bar.
- WEB UI: Command results (`:tools list`, `:help`, etc.) now displayed in chat.
- `git_ops`: `rm` command support.

### Fixed

- High-contrast mode: toggle knob now has outline for visibility.
- `catalog_tool.py`: restored missing `run_tool()` function (caused all management tools to fail loading in dev mode).
- Desktop GUI: font size menu check marks now correctly reflect current size.
- `read_file_tool.py`: fixed truncation without trailing newline.

### Changed

- Unified `scheck.py` launcher: merged all mode entry points (cli, gui, web, a2a, ws, setup) into single script.
- UnifiedPanel.svelte: cleaner styling with consistent border-radius, spacing, and button styles.
- Renamed `create-tool` skill directory to match frontmatter name.

## [0.5.46] - 2026-07-13

### Added

- sub-agent Phase 1-3 complete: multi-turn conversations, all-tools support, chain tool, cost tracking, dynamic role assignment, structured logging.
- reasoning: `:r` command toggle behavior (no argument toggles ON/OFF), `max` level (`:r max` / `:r m`), numeric aliases (4=xhigh, 5=max), display off control.
- llmcapa integration: `reasoning_effort_values` validation for Claude/DeepSeek/ZAI/OpenRouter providers.
- i18n: translations for 8 new parameters across 34 languages, `sub_agent_chain_tool.json` created for 34 languages.

### Fixed

- Cross-platform fixes for `apply_patch`, `cmd_exec_json`, `replace_in_file`, `list_windows_titles` (bug fixes and platform compatibility).

### Changed

- llmcapa dependency bumped to >=0.3.3.
- reasoning: removed `ultra` level (kept `xhigh` and `max` only). OpenRouter effort values now properly passed.
- Cleaned up unused files from repository.

## [0.5.45] - 2026-07-12

### Added

- New tools: `diff_files` (compare two files line by line) and `apply_patch` (apply unified diff patches) with full 34-language i18n.
- Tool genres: `dev`, `web`, `utility` added to genre bitmap and genre control system.

### Fixed

- `tests/test_llmcapa.py`: corrected `expect_vision` flags for `Llama-3.2-90B-Vision-Instruct` and `Llama-4-Scout-17B-16E` (both support vision).

### Changed

- 2026-07-12

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
