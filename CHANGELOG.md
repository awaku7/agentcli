# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
