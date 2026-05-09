# DEVELOP_I18N.md

This document describes i18n (internationalization) conventions for the **host application (core/cli/gui/web)**.

> Note: i18n for **tools** (under `src/uagent/tools/`) is handled differently (per-tool translators). This file intentionally focuses on the host side.

## Goals / Policy

- **English is the default language**.
- **Japanese is provided as an additional translation** via gettext.
- Shipped locales: `ar`, `cs`, `de`, `es`, `fi`, `fr`, `hi`, `id`, `it`, `ja`, `ko`, `nb`, `nl`, `pl`, `pt`, `pt_BR`, `ru`, `sv`, `th`, `uk`, `vi`, `zh_CN`, `zh_TW`.
- Translation must be **fail-safe**:
  - If a translation is missing, the program must keep working and show the English msgid.
- Prefer translating **user-facing output**.
- Comments/docstrings should be in **English when reasonable**.

## Architecture Overview

### Domain

- Gettext domain: `uag`
- Locale files:
  - `src/uagent/locales/ja/LC_MESSAGES/uag.po`
  - `src/uagent/locales/ja/LC_MESSAGES/uag.mo`
  - (optional) `src/uagent/locales/en/LC_MESSAGES/uag.po` (template)

### Host-side translator

Host modules import:

```py
from .i18n import _
```

`_()` returns a translated string via gettext, and falls back to msgid if missing.

## What is “host-side” (this document’s scope)

- `src/uagent/core.py`
- `src/uagent/cli.py`
- `src/uagent/gui.py`
- `src/uagent/web.py`
- Other non-tool helper modules that directly emit user-facing messages.

## Conventions

### 1) All user-facing strings must go through gettext

Do:

```py
print("[INFO] " + _("Loaded long-term memory."))
```

Avoid (host-side):

```py
print("長期記憶を読み込みました")
print(f"[WARN] エラー: {e}")
```

### 2) Prefer named placeholders (`%(name)s`) over f-strings

This keeps msgid stable and friendly for translators.

Do:

```py
print(_("[FATAL] Failed to set workdir: %(err)s") % {"err": e}, file=sys.stderr)
```

Avoid:

```py
print(f"[FATAL] workdir の設定に失敗しました: {e}")
```

### 3) Keep log prefixes stable

Prefixes like `[INFO]`, `[WARN]`, `[ERROR]`, `[FATAL]` should stay stable. Translate the message body.

Example:

```py
print("[WARN] " + _("Failed to read startup file: %(path)s (%(err)s)") % {...})
```

### 4) Multi-line user messages

- Multi-line strings can be translated as one msgid.
- Ensure the msgid is exactly the same in code and in `.po`.

## SYSTEM_PROMPT handling

`SYSTEM_PROMPT` is treated as a translatable host-side string.

Pattern in `core.py`:

```py
SYSTEM_PROMPT_MSGID = """\
...English...\
"""
SYSTEM_PROMPT = _(SYSTEM_PROMPT_MSGID)
```

- The msgid is the English prompt.
- Japanese translation is stored in `uag.po`.

## Translation workflow (host-side)

### 1) Add/modify msgids in code

- Write msgids in English.
- Wrap with `_()`.
- If a host-side prompt needs runtime fallback when translations are empty, `tr()` may be used.

### 1.5) Extract POT

- When generating `uagent.pot`, include `tr` as a gettext keyword as well as `_` and `ngettext:1,2`.

### 2) Update `uag.po`

Add entries to:

- `src/uagent/locales/ja/LC_MESSAGES/uag.po`

Notes:

- Keep placeholders like `%(name)s` unchanged.
- Keep triple-quoted msgids exactly the same (including newlines).

### 3) Compile to `.mo`

Important:

- Do not edit `*.mo` by hand. Always edit `*.po` and regenerate `*.mo`.

This repository provides a small, dependency-free compiler:

```bash
python scripts/compile_locales.py
```

What it does:

- Recursively finds `*.po` under `src/uagent/locales/`
- Compiles each `.po` to a sibling `.mo`

Notes / limitations:

- `.po` files must be UTF-8.
- This script implements only a small subset of `msgfmt`:
  - `msgid` / `msgstr` only
  - supports multiline quoted strings
  - does **not** support plural forms or contexts.

(Optional) You can also run a syntax check:

```bash
python -m compileall -q src/uagent
```

## QC (translation sanity checks)

This repository provides a small QC helper:

```bash
python scripts/po_qc_summary.py
```

It scans `src/uagent/locales/*/LC_MESSAGES/*.po` and writes:

- `outputs/i18n/po_qc_summary.tsv`
- `outputs/i18n/{locale}_po_qc.txt`

Interpretation (high-level):

- `empty`: untranslated entries (`msgstr ""`).
- `fuzzy`: entries still marked `#, fuzzy`.
- `ascii_nonkey`: `msgstr` is ASCII-only but not key-like (often indicates leftover English).
- `same_as_en`: non-key `msgstr` equals English translation.
- `no_expected_script`: for `ja/zh/ko/th`, `msgstr` lacks expected script (can include false-positives for technical strings).
- `same_as_msgid`: `msgstr` equals `msgid` (often OK in this repo due to key-style msgids).

## Checklist (host-side)

When changing host-side messages:

- [ ] msgid is English
- [ ] wrapped with `_()`
- [ ] used named placeholders instead of f-strings where possible
- [ ] `uag.po` updated (ja)
- [ ] `.mo` regenerated (`python scripts/compile_locales.py`)
- [ ] `python scripts/po_qc_summary.py` checked (at least the affected locale)
- [ ] `python -m compileall -q src/uagent` passes

## Out of Scope

- Tool-side translations and per-tool translator keys (`make_tool_translator`, JSON key-based i18n, etc.).
- Client-side i18n for the Web UI (if implemented in JS/HTML).
