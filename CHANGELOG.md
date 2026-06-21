# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
