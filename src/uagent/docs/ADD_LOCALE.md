# Add or Update a Locale (gettext)

This project uses **gettext** catalogs with domain **`uag`** for user-facing strings and system prompts.

- Catalog root: `src/uagent/locales/`
- Per-locale files:
  - PO (Source): `src/uagent/locales/<lang>/LC_MESSAGES/uag.po`
  - MO (Binary): `src/uagent/locales/<lang>/LC_MESSAGES/uag.mo`
- Template (POT): `src/uagent/locales/uag.pot`

---

## 1. Extracting Strings from Source (Updating POT)

When you add new messages to the code or change existing ones, you must update the `uag.pot` template.

### The Command
From the repository root, run `xgettext` with the following arguments to correctly handle Python multiline strings and keywords:

```bash
# Get the file list (excluding tools directory)
# Windows (PowerShell):
$srcFiles = Get-ChildItem -Path src/uagent/*.py, src/uagent/a2a/*.py | Select-Object -ExpandProperty FullName

# Extract
xgettext --package-name=uag --language=Python --keyword=_ --keyword=ngettext:1,2 --from-code=UTF-8 --output=src/uagent/locales/uag.pot $srcFiles
```

**Key Arguments:**
- `--language=Python`: Essential for parsing triple quotes (`"""`).
- `--keyword=_ --keyword=ngettext:1,2`: Tells xgettext which functions contain translatable strings.
- `--from-code=UTF-8`: Ensures non-ASCII characters are handled correctly.

---

## 2. Updating Existing Locales (Code Change Flow)

After updating `uag.pot`, you must merge the changes into all existing `.po` files.

### Merge and Clean up
For each language (e.g., `ja`, `de`):

```bash
# 1. Merge new strings and mark changed ones as fuzzy
msgmerge --update --backup=none src/uagent/locales/ja/LC_MESSAGES/uag.po src/uagent/locales/uag.pot

# 2. Remove obsolete messages that are no longer in the source
msgattrib --no-obsolete --output=src/uagent/locales/ja/LC_MESSAGES/uag.po src/uagent/locales/ja/LC_MESSAGES/uag.po
```

**Next Steps:**
- Search for `#, fuzzy` in the `.po` file, review the changes, update the `msgstr`, and **delete the `#, fuzzy` line**.
- Fill in any new `msgstr ""` (untranslated) entries.

---

## 3. Adding a New Locale

The fastest and most reliable way to add a new locale (e.g., `fr`) is to use the existing English catalog as a template.

1.  **Create the directory**: `mkdir -p src/uagent/locales/fr/LC_MESSAGES`
2.  **Copy the template**: Copy `src/uagent/locales/en/LC_MESSAGES/uag.po` to the new location.
3.  **Update metadata**: Open the new `uag.po` and change `"Language: en\n"` to `"Language: fr\n"`.
4.  **Translate**: Replace the English strings in `msgstr` with your translation.

---

## 4. Translation Guidelines

- **Placeholders**: Keep `%(name)s`, `%(err)r`, etc., exactly as they are.
- **System Tags**: Keep technical tags like `[INFO]`, `[WARN]`, `[ERROR]`, `[TOOL]` in English to maintain log consistency.
- **Multiline Strings**: Ensure system prompts (starting with `## Mission`, etc.) maintain their structure and ending newlines (`\n`).
- **Encoding**: Files **must** be saved in **UTF-8 (without BOM)**.

---

## 5. Compilation and Validation

Before committing, you must compile the `.po` file into a binary `.mo` file.

### Compile
```bash
msgfmt -c -v src/uagent/locales/<lang>/LC_MESSAGES/uag.po -o src/uagent/locales/<lang>/LC_MESSAGES/uag.mo
```
- `-c`: Check for syntax errors (will catch invalid escape sequences).
- `-v`: Verbose (shows translation statistics).

### Verify in Runtime
Set the language environment variable and run the agent:
```bash
# Windows
set UAGENT_LANG=ja
python -m uagent
```

---

## 6. Commitment Policy

Always commit both the `.po` and the `.mo` files to ensure the translations are immediately available to users without requiring them to have gettext tools installed.
