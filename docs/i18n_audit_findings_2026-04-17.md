# i18n audit findings (host-side, non-debug)

Date: 2026-04-17
Scope: `src/uagent/**` excluding `src/uagent/tools/**`

## Purpose

This file lists host-side strings that appear to be user-facing and are likely still outside gettext coverage, excluding obvious debug-only output.

## Candidate strings to review

### `src/uagent/cli_docs.py`
- `print("[docs] name is required", file=sys.stderr)`

### `src/uagent/core.py`
- `print(f":help  (help unavailable: {type(e).__name__}: {e})")`

### `src/uagent/gemini_cache_mgr.py`
- `raise ValueError("invalid cache meta")`

### `src/uagent/llm_claude.py`
- `raise RuntimeError("anthropic パッケージがインストールされていません。（pip install anthropic が必要です）")`

### `src/uagent/llm_errors.py`
- `print(f"[RATE_LIMIT] provider={provider} model={model} ...")`

### `src/uagent/runtime_init.py`
- `print(f"[WARN] Failed to decrypt .env.sec: {e}", file=sys.stderr)`

### `src/uagent/scheckgui.py`
- `print(f"[mode] reasoning={new_mode}")`

### `src/uagent/setup_cli.py`
- `print(f"  UAGENT_REASONING={st.reasoning}")`
- `print(f"  UAGENT_VERBOSITY={st.verbosity}")`
- `print(f"  UAGENT_WORKDIR={st.workdir}")`
- `print(f"  UAGENT_LANG={st.lang}")`

### `src/uagent/uagent_llm.py`
- `print("[SSL Info] certifi is not available")`
- `print(f"[SSL Info] certifi.where() = {certifi.where()}")`
- `print(f"[WARN] Auto shrink_llm failed: {type(e).__name__}: {e}")`
- `print(f"[Translate Error] {diag}")`

## Notes

- `src/uagent/llm_tool_narrowing.py` was intentionally excluded because its output is debug-only.
- Many other host-side strings are already wrapped with `_()` and appear to be translated.
- This list is a review queue, not a confirmed bug list.

## Next step

- Review each candidate and decide whether it should be wrapped with `_()`.
- If code changes are made, regenerate locale files and the compiled `.mo` file.
- Use `src/uagent/locales/en/LC_MESSAGES/uag.po` as the baseline template when updating locale files.
- Keep `uagent.pot`, `en.po`, and `ja.po` aligned after each `_()` change.

## Progress update

Date: 2026-04-17 15:25 JST

### Completed
- Resolved the duplicate `msgid` in `src/uagent/locales/ja/LC_MESSAGES/uag.po`.
- Ran `msgmerge` and `msgfmt` successfully for the Japanese locale.
- Completed translation synchronization for the currently selected host-side strings.

### Current locale status
- `ja.po` entries: 726
- translated: 289
- untranslated: 0
- fuzzy: 0
- obsolete: 437

### Scope notes
- This work stayed within host-side `src/uagent/**` and locale files.
- `src/uagent/tools/**` was not edited.

### Follow-up
- If new `_()` wrappers are added later, regenerate `uagent.pot`, `en.po`, and `ja.po` together.
- Keep the locale catalogs aligned after each i18n change.

## Final progress update

Date: 2026-04-17 15:25 JST

### Completed
- Reviewed and updated host-side i18n candidates under `src/uagent/**`.
- Added `_()` wrapping for the selected user-facing strings.
- Regenerated `src/uagent/locales/uagent.pot`.
- Synchronized `src/uagent/locales/en/LC_MESSAGES/uag.po` to match msgids.
- Synchronized `src/uagent/locales/ja/LC_MESSAGES/uag.po` and resolved the duplicate `msgid` issue.
- Removed obsolete entries from both `en.po` and `ja.po`.
- Rebuilt compiled locale files with `scripts/compile_locales.py`.

### Final locale status
- `en.po`: entries 289, translated 289, untranslated 0, fuzzy 0, obsolete 0
- `ja.po`: entries 289, translated 289, untranslated 0, fuzzy 0, obsolete 0

### Scope notes
- `src/uagent/tools/**` was not edited.
- The work stayed within host-side code and locale files.

### Follow-up
- If new `_()` wrappers are added later, regenerate `uagent.pot`, `en.po`, `ja.po`, and rebuild `.mo` files again.
- Keep the catalogs aligned after each i18n change.

## Procedure note: fixing gettext header warnings

When `msgfmt --check` reports header warnings such as missing `PO-Revision-Date`, `MIME-Version`, or `Content-Transfer-Encoding`:

1. Open the locale `.po` file.
2. Add or restore the standard header fields in the `msgid ""` / `msgstr ""` block.
3. Keep `Project-Id-Version`, `Language`, `Plural-Forms`, and translator metadata aligned with the project.
4. Re-run `msgfmt --check` on the `.po` file.
5. If the file is valid, recompile the locale assets if needed.

