# Add a new locale (gettext)

This project uses **gettext** catalogs with domain **`uag`**.

- Catalog root: `src/uagent/locales/`
- Per-locale files:
  - PO: `src/uagent/locales/<lang>/LC_MESSAGES/uag.po`
  - MO: `src/uagent/locales/<lang>/LC_MESSAGES/uag.mo`
- Extraction template (POT): `src/uagent/locales/uag.pot`

This document describes how to add a new locale (example: `zh_CN`).

Currently shipped locales (host-side user-facing strings): `en`, `ja`, `zh_CN`, `zh_TW`, `es`, `fr`, `ko`.

## Policy / scope

- We only translate **user-facing strings**.
- Tool-derived strings under `src/uagent/tools/**` are **excluded** (different i18n mechanism).

## Prerequisites

- Python environment that can run `pybabel` (Babel).
- Babel is expected to be installed (if not, install it in your env):

```bash
pip install Babel
```

## 1. Create or update the POT

From the repository root:

```bash
pybabel extract -F babel.cfg -o src/uagent/locales/uag.pot .
```

Notes:
- `babel.cfg` defines which source file patterns are scanned.

## 2. Initialize the locale

Example for `zh_CN`:

```bash
pybabel init -D uag -i src/uagent/locales/uag.pot -d src/uagent/locales -l zh_CN
```

This creates:

- `src/uagent/locales/zh_CN/LC_MESSAGES/uag.po`

## 3. Prune entries to the user-facing subset

We keep the catalogs aligned across languages by pruning tool-derived entries.

Recommended approach:
- Start from `src/uagent/locales/uag.pot` (or an existing en/ja PO)
- Remove entries whose occurrence path starts with `src/uagent/tools/`

(We intentionally keep only the same user-facing subset that JA/EN ship.)

## 4. Translate

Edit the new PO file:

- Translate `msgstr`.
- Preserve placeholders:
  - Python mapping placeholders like `%(name)s`, `%(err)r`, etc.
- Keep command names / env var names as-is (`UAGENT_*`, `:help`, etc.).

## 5. Compile `.mo`

From repo root:

```bash
python scripts/compile_locales.py
```

This compiles all `uag.po` into `uag.mo`.

## 6. Ensure the runtime can select the locale

Language selection is done via `UAGENT_LANG`.

- Set e.g. `UAGENT_LANG=zh_CN` and run:

Windows (cmd):
```bat
set UAGENT_LANG=zh_CN
python scheck.py
```

If the locale tag is not recognized, update normalization logic in:

- `src/uagent/i18n.py` (`_normalize_lang_tag`)

## 7. Validate

Basic checks:

- The app shows translated strings when `UAGENT_LANG` is set.
- `.po` is parseable and `.mo` is generated.

Optional (recommended) PO sanity checks with `polib`:

```bash
python -c "import polib; polib.pofile('src/uagent/locales/zh_CN/LC_MESSAGES/uag.po'); print('OK')"
```

## 8. Commit

Commit the following:

- `src/uagent/i18n.py` (only if language normalization needed changes)
- `src/uagent/locales/<lang>/LC_MESSAGES/uag.po`
- `src/uagent/locales/<lang>/LC_MESSAGES/uag.mo`
- `src/uagent/locales/uag.pot` (if you updated extraction)
- `babel.cfg` (if you changed extraction rules)

Example:

```bash
git add src/uagent/i18n.py src/uagent/locales/zh_CN/LC_MESSAGES/uag.po src/uagent/locales/zh_CN/LC_MESSAGES/uag.mo
git commit -m "Add zh_CN locale (user-facing strings)"
git push
```
