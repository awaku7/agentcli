# Changelog

## [0.5.39] - 2026-07-06

### Fixed
- ECHONET Lite: `echonet_control` ON/OFF byte values were inverted (ON=0x30, OFF=0x31). Now correctly sends 0x30 for ON and 0x31 for OFF.
- ECHONET Lite: `echonet_property_get` now retries up to 4 times within timeout when no response is received, improving reliability on congested networks.
- `responses_state_*.json`: default path changed to `~/.uag/` (user home .uag directory) with optional `UAGENT_RESPONSES_STATE_DIR` override. Removed `os.path.expanduser()` dependency for Windows compatibility.
- Docs: update relative links in QUICKSTART, translated READMEs, COMMUNICATION.md after migration to docs/.

### Changed
- `responses_state_*.json`: now written to `UAGENT_WORKDIR` (e.g. `~/.uag/`) instead of `getcwd()`.

### Added
- ENVIRONMENT.md: document `RESPONSES_STATE_FILE` and `RESPONSES_STATE_DIR` environment variables.

### Chore
- `.gitignore`: add `responses_state_*.json`, remove stale sakura state file.

## [0.5.38] - 2026-07-06

### Added
- ECHONET Lite: i18n all 55 EOJ class names in 34 languages via tool JSON + `_get_eoj_localized_name()`. Japanese locale returns native names; other locales use translated names from `echonet_scan_tool.json`.
- ECHONET Lite: manufacturer names, device type display, raw EOJ code mapping in scan results.
- i18n: pip install messages in `_pip_auto.py` translated to 34 languages.

### Changed
- ECHONET Lite: pyhems-inspired fixes (TID handling, multicast membership, port 3610 binding) + cache TTL + refresh parameter.
- ECHONET Lite: `_eoj_class_name()` now uses `detect_lang()` directly instead of gettext for EOJ class names.
- i18n: `tools/i18n_helper.detect_lang()` aligned with `uagent.i18n.detect_lang()` fallback chain (getdefaultlocale + Windows console code page detection).

### Performance
- `modbus_scan`: parallelized with ThreadPoolExecutor + TCP pre-check for faster discovery.

### Documentation
- IOT_USECASE.md: add documentation for EOJ class name localization in echonet_* tools.

### Fixed
- i18n: `human_ask` and other tool JSON translations now correctly display in Japanese on Windows when `locale.getlocale()` returns `(None, None)`.

### Chore
- Remove stray `_mfr_list.pdf`.
- `.gitignore`: add `.mypy_cache/` and `.ruff_cache/`.
- lint: remove unused variables, organize imports.

## [0.5.37] - 2026-07-04

### Added
- ECHONET Lite: scan tool now displays EOJ class names in the user's locale (Japanese → Japanese names, other → English).

### Fixed
- ECHONET Lite: scan now creates socket with `IPPROTO_UDP` and sends on port 3610; multicast memberships are now properly joined per-interface.
- ECHONET Lite: `TID` in request packets is now a random 16-bit value instead of a fixed value to avoid deduplication filters.

### Changed
- ECHONET Lite: cache TTL reduced from 600 s to 30 s; `--refresh` flag added to bypass cache on scan.
- ECHONET Lite: node details now include manufacturer name derived from `0x8A` property map.

## [0.5.36] - 2026-07-03

