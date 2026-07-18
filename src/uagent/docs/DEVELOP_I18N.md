# DEVELOP_I18N.md — Unified Internationalization Guide

This document covers **all** i18n mechanisms in uag:

1. **Host side** (gettext `.po`/`.mo`) — for `core.py`, `cli.py`, `gui.py`, `web.py`, `runtime/`, `providers/`, etc.
2. **Tool side** (JSON key-based) — for `tools/*_tool.py` and their `*_tool.json` translation files.

Both systems share the same goal: user-facing strings are translated while the code stays in English.

______________________________________________________________________

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Host-Side i18n (gettext)](#host-side-i18n-gettext)
- [Tool-Side i18n (JSON)](#tool-side-i18n-json)
- [Adding a New Locale](#adding-a-new-locale)
- [QC and Validation](#qc-and-validation)
- [Checklist](#checklist)

______________________________________________________________________

## Architecture Overview

| Aspect | Host side | Tool side |
|--------|-----------|-----------|
| **Mechanism** | gettext (`.po` / `.mo`) | JSON key-value per tool |
| **Translation files** | `src/uagent/locales/<lang>/LC_MESSAGES/uag.po` + `.mo` | `src/uagent/tools/<tool_name>_tool.json` |
| **Import** | `from .i18n import _` | `_ = make_tool_translator(__file__)` |
| **Default language** | English (`msgid`) | English (`"en"` key in JSON) |
| **Fallback** | gettext returns `msgid` if missing | `_("key", default="...")` if JSON key missing |
| **Config file** | `babel.cfg` (project root) | (none; JSON files are self-contained) |
| **Locale count** | 29 shipped locales | Varies per tool (typically en + ja + others) |

______________________________________________________________________

## Host-Side i18n (gettext)

### Scope

Files covered: `core.py`, `cli.py`, `gui.py`, `web.py`, `a2a/*.py`, `utils/*.py`, `providers/*.py`, `runtime/*.py`, `scheduler/*.py`, `docs/*.py`, `uag_envsec/*.py`.

### Translator setup

```python
from .i18n import _

print(_("Loaded long-term memory."))
print(_("Failed: %(err)s") % {"err": e})
print("[WARN] " + _("Failed to read: %(path)s") % {"path": p})
```

### Conventions

1. **All user-facing strings must go through `_()`**. Avoid hardcoded non-English text.

2. **Use `%(name)s` placeholders** instead of f-strings. This keeps msgid stable for translators.

   ```python
   # Do
   print(_("[FATAL] Failed to set workdir: %(err)s") % {"err": e})
   # Avoid
   print(f"[FATAL] Failed to set workdir: {e}")
   ```

3. **Keep log prefixes stable**. Prefixes like `[INFO]`, `[WARN]`, `[ERROR]`, `[FATAL]` stay in English.

   ```python
   print("[WARN] " + _("Failed to read startup file: %(path)s (%(err)s)") % {...})
   ```

4. **Multi-line strings** can be one msgid. Ensure the msgid in code exactly matches the `.po` file.

5. **SYSTEM_PROMPT handling**: defined as a translatable msgid in `core.py`.

   ```python
   SYSTEM_PROMPT_MSGID = """\
   ...English...\
   """
   SYSTEM_PROMPT = _(SYSTEM_PROMPT_MSGID)
   ```

### Translation workflow

```bash
# 1. Extract POT from source code
pybabel extract -F babel.cfg -o src/uagent/locales/uagent.pot .

# 2. Rebuild English PO from POT
python scripts/po_rebuild_en.py

# 3. Update non-English PO (e.g. Japanese)
python scripts/po_rebuild_non_en.py src/uagent/locales/ja/LC_MESSAGES/uag.po

# 4. Translate new entries in the .po file
#    Use the `translate_text` tool (or any PO editor) to fill in msgstr.
#    The tool preserves %(name)s placeholders automatically when
#    protect_placeholders=True (default).
#    After translating, remove `#, fuzzy` markers.
#    vim src/uagent/locales/ja/LC_MESSAGES/uag.po

# 5. Compile .mo
python scripts/compile_locales.py

# 6. QC check
python scripts/po_qc_summary.py
```

**Scripts reference:**

| Script | Purpose |
|--------|---------|
| `scripts/po_rebuild_en.py` | Rebuild English `.po` from POT (maps `msgid` → `msgstr`) |
| `scripts/po_rebuild_non_en.py <path>` | Merge POT into existing non-English `.po`, preserving translations |
| `scripts/compile_locales.py` | Compile all `.po` → `.mo` (no gettext tools required) |
| `scripts/po_qc_summary.py` | Scan all `.po` files for untranslated/fuzzy/same-as-English entries |

### babel.cfg

The `babel.cfg` file at the project root defines which packages are scanned and which keywords are recognized. When adding a new host-side package, add an entry:

```
[python: src/uagent/<new_pkg>/*.py]
encoding = utf-8
keywords = _ _t tr ngettext:1,2
```

______________________________________________________________________

## Tool-Side i18n (JSON)

### Scope

Each tool in `src/uagent/tools/*_tool.py` has its own translation file at `src/uagent/tools/<name>_tool.json`.

### Translator setup

```python
from .i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)

TOOL_SPEC = {
    "function": {
        "description": _("tool.description", default="Analyzes code."),
        "parameters": {
            "properties": {
                "path": {
                    "description": _("param.path.description", default="Target file path."),
                }
            }
        }
    }
}
```

- First argument = lookup key in JSON.
- `default=` = English fallback (used when JSON key is missing or language block absent).

### JSON file structure

```json
{
  "en": {
    "tool.description": "Analyzes code.",
    "param.path.description": "Target file path.",
    "err.not_found": "File not found: %(path)s"
  },
  "ja": {
    "tool.description": "u30b3u30fcu30c9u3092u89e3u6790u3057u307eu3059u3002",
    "param.path.description": "u5bfeu8c61u30d5u30a1u30a4u30ebu306eu30d1u30b9u3002",
    "err.not_found": "u30d5u30a1u30a4u30ebu304cu898bu3064u304bu308au307eu305bu3093: %(path)s"
  },
  "id": {
    "tool.description": "Menganalisis kode.",
    "err.not_found": "Berkas tidak ditemukan: %(path)s"
  }
}
```

- Language codes: standard BCP-47 (`ja`, `ko`, `zh_CN`, `pt_BR`, `id`, etc.).
- `en` is mandatory (fallback for missing languages).
- When adding a new language, add a new top-level key.

### Key naming conventions

| Pattern | Example | Purpose |
|---------|---------|---------|
| `tool.description` | `"Analyzes code."` | TOOL_SPEC description |
| `x_search_terms` | `["analyze", "code"]` | Search keywords for tool discovery |
| `param.<name>.description` | `"Target file path."` | Parameter description |
| `err.<name>` | `"File not found: %(path)s"` | Error messages returned to LLM |
| `msg.<name>` | `"Operation successful."` | Status/success messages |
| `confirm.<name>` | `"Are you sure?"` | User confirmation prompts |

### Placeholder conventions

- Use `%(name)s` format (same as host side).
- Keep placeholders **unchanged** in translations.
- Use `translate_text` tool with `protect_placeholders=True` (default) when machine-translating.

### Workflow for adding/modifying tool i18n

```bash
# 1. Add/edit _() calls in the .py file
# 2. Add/edit keys in the corresponding .json file
# 3. Translate new values using translate_text tool:
#    translate_text(
#      texts=["new key text"],
#      target_lang="ja",
#      source_lang="en",
#      protect_placeholders=True   # preserves %(name)s automatically
#    )
#    # File mode example:
#    # translate_text(
#    #   path="README.md",
#    #   output_path="README.ja.md",
#    #   target_lang="ja",
#    #   protect_placeholders=True,
#    #   overwrite=False,
#    # )
#    # Efficient batch (recommended for many keys/langs):
#    # python scripts/tool_json_i18n_batch.py status --langs ja,es,de
#    # python scripts/tool_json_i18n_batch.py run --tools my_tool --langs es --apply
#    # Artifacts land in tmp/tool_json_i18n/<lang>/ (gitignored).
# 4. Validate syntax
python -m py_compile src/uagent/tools/<name>_tool.py

# 5. (Optional) Run i18n consistency check
python scripts/i18n_tools_check.py

# 6. Test by loading the tool (uag CLI) or system_reload
```

**Script reference:**

| Script | Purpose |
|--------|---------|
| `scripts/i18n_tools_check.py` | Validate all `*_tool.json` files for missing keys, broken placeholders, etc. |
| `scripts/tool_json_i18n_batch.py` | Extract missing values to `tmp/`, batch-translate via `translate_text`, merge back. |

### Note about return values

Error messages returned to the LLM (e.g. `"error.exit_code"`) should also be translated via `_()`, as the LLM responds in the user's language. Wrap them:

```python
_("error.exit_code", default="command exited with code %(returncode)s") % {"returncode": proc.returncode}
```

______________________________________________________________________

## Adding a New Locale

### Host side (gettext)

1. Create directory: `mkdir -p src/uagent/locales/<lang>/LC_MESSAGES/`
2. Copy English template: `cp src/uagent/locales/en/LC_MESSAGES/uag.po src/uagent/locales/<lang>/LC_MESSAGES/uag.po`
3. Edit metadata: Change `"Language: en\n"` to `"Language: <lang>\n"`
4. Translate `msgstr` entries using `translate_text` tool (or any PO editor).
   The tool preserves `%(name)s` placeholders when `protect_placeholders=True`.
5. Compile: `python scripts/compile_locales.py`
6. Commit both `.po` and `.mo`

### Tool side (JSON)

**Recommended (batch via tmp/):**

```bash
python scripts/tool_json_i18n_batch.py status --langs fr
python scripts/tool_json_i18n_batch.py run --tools <name> --langs fr --apply
python scripts/i18n_tools_check.py
```

This extracts only missing English values into `tmp/tool_json_i18n/<lang>/`,
translates them with `protect_placeholders=True`, then merges back without
touching JSON keys/structure.

**Manual (single strings):**

1. Open the tool's `*_tool.json`
2. Add a new top-level key for the language (e.g. `"fr": { ... }`)
3. Use `translate_text` to translate values:
   ```
   translate_text(
     texts=["English value 1", "English value 2"],
     target_lang="fr",
     source_lang="en",
     protect_placeholders=True   # preserves %(name)s automatically
   )
   ```
4. Copy the translated strings into the JSON under the new language key
5. Keep all placeholders `%(...)s` unchanged
6. Optionally verify with `python scripts/i18n_tools_check.py`

______________________________________________________________________

## QC and Validation

### Host side

```bash
# Compile check
python scripts/compile_locales.py

# Full QC report
python scripts/po_qc_summary.py

# Python syntax check
python -m compileall -q src/uagent
```

### Tool side

```bash
# Python syntax check
python -m py_compile src/uagent/tools/<name>_tool.py

# I18n consistency check
python scripts/i18n_tools_check.py

# Placeholder integrity check (manual)
# Ensure %(name)s placeholders in JSON match those in _() calls
```

### Common pitfalls

| Pitfall | Consequence | Prevention |
|---------|-------------|------------|
| `%(error)s` stored as literal backslash-n in JSON | Output shows `\\n` instead of newline | Use actual newline characters in JSON |
| Placeholder format mismatch (`{name}` vs `%(name)s`) | `KeyError` at runtime | Use `%(name)s` consistently |
| Missing `en` key in JSON | `KeyError` if locale not found | Always include `en` block |
| `.po` edited but `.mo` not recompiled | Changes invisible at runtime | Run `compile_locales.py` before commit |

______________________________________________________________________

## Checklist

### Host-side changes

- [ ] msgid is English
- [ ] Wrapped with `_()`
- [ ] Uses `%(name)s` placeholders instead of f-strings
- [ ] `.po` file updated (at least `ja`)
- [ ] `.mo` regenerated (`python scripts/compile_locales.py`)
- [ ] `po_qc_summary.py` checked
- [ ] `python -m compileall -q src/uagent` passes

### Tool-side changes

- [ ] New `_("key", default="...")` calls added
- [ ] Corresponding keys added to `*_tool.json`
- [ ] `en` block present and complete
- [ ] Placeholders `%(...)s` preserved in all translations
- [ ] `python -m py_compile` passes
- [ ] `python scripts/i18n_tools_check.py` passes (if applicable)
- [ ] For LLM-facing error messages: wrapped with `_()` (user expects translated errors)
