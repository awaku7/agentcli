# Tool Translation Methodology

## Overview

uAgent tools expose a `x_search_terms` field in each tool's JSON definition. This
field contains language‑specific keywords that enable users to discover tools by
searching in their native language — without requiring a separate translation
layer at runtime.

Each tool JSON has the following structure (per language):

```json
{
  "en": {
    "description": "...",
    "x_search_terms": ["bacnet", "bacnet/ip", "scan", "discover"]
  },
  "ja": {
    "description": "...",
    "x_search_terms": ["バックネット", "バックネット/IP", "スキャン", "発見"]
  },
  ...
}
```

## Supported Languages (33)

| Language          | Code    |
|-------------------|---------|
| Arabic            | ar      |
| Bengali           | bn      |
| Czech             | cs      |
| German            | de      |
| Greek             | el      |
| Spanish           | es      |
| Persian           | fa      |
| Finnish           | fi      |
| French            | fr      |
| Hebrew            | he      |
| Hindi             | hi      |
| Hungarian         | hu      |
| Indonesian        | id      |
| Italian           | it      |
| Japanese          | ja      |
| Korean            | ko      |
| Mongolian         | mn      |
| Marathi           | mr      |
| Norwegian Bokmål  | nb      |
| Dutch             | nl      |
| Polish            | pl      |
| Portuguese        | pt      |
| Portuguese (BR)   | pt_BR   |
| Romanian          | ro      |
| Russian           | ru      |
| Swedish           | sv      |
| Swahili           | sw      |
| Thai              | th      |
| Turkish           | tr      |
| Ukrainian         | uk      |
| Vietnamese        | vi      |
| Chinese (Simpl.)  | zh_CN   |
| Chinese (Trad.)   | zh_TW   |

## Data Flow

```
Source of truth (English)
       │
       ├──→ en x_search_terms → tool JSON (en)
       │
       ├──→ x_search_terms_en → Python .py file (for catalog search)
       │
       └──→ translate_text API → 33 languages → tool JSON (each lang)
```

### 1. English x_search_terms (JSON)

Each tool JSON defines `en.x_search_terms` as an array of searchable terms,
ordered by specificity (most specific first). The first term is the primary
search key, subsequent terms are alternative aliases.

### 2. Python x_search_terms_en

The same terms are duplicated in the Python tool file as a module‑level
variable `x_search_terms_en`. This allows the `catalog_tool` to search without
loading and parsing JSON files.

```python
x_search_terms_en = [
    "bacnet scan",
    "bacnet_scan",
    "bacnet",
    "BACNET",
    "discover",
    "bacnet/ip",
    "devices",
    "local",
    "network",
    "sends",
]
```

### 3. Translation Pipeline

#### 3a. Delimiter Strategy (二重区切り方式)

The pipeline must translate 59 tools × 33 languages without losing the
mapping between translated terms and their source tool files. A **two‑level
delimiter scheme** solves this:

```
Level 1 (inner):  |  (pipe)     — separates terms within a single tool
Level 2 (outer):  list index     — separates the 59 tools (implicit via API)
```

**Level 1 — Inner delimiter `|`**

Each tool's `x_search_terms_en` is joined with ` | ` (space‑pipe‑space).
This `|` was chosen because:

- It never appears naturally in search terms (unlike `/`, `-`, `,`, or spaces)
- The LLM translates it verbatim — Gemini reliably preserves `|` in output
- A single term like `bacnet/ip` or `on/off/open/close/level` stays intact
  because `/` is not the delimiter

Example for one tool's source line:

```
bacnet scan | bacnet_scan | bacnet | BACNET | discover | bacnet/ip | devices
```

**Level 2 — Outer delimiter (implicit list indexing)**

The 59 source lines are NOT concatenated into a single string. Instead,
`translate_text` is called with a **Python list** of 59 strings, where each
element is one tool's pipe‑joined line. The API sends them to the LLM as a
JSON array.

This avoids the need for any outer separator character — the list position
itself is the mapping key: output[0] → first tool file, output[1] → second
tool file, and so on.

#### 3b. Prompt Design

The prompt instructs the LLM to preserve the pipe delimiter and proper nouns:

```
Translate the following 59 items of search terms from English to {target_lang}.
Each item contains terms separated by "|". Maintain the same separator.
Preserve proper nouns (BACNET, ECHONET, MODBUS, MQTT, OPCUA, UPNP, etc.).
Translate the rest naturally.
```

Key design points:

- "Preserve proper nouns" stops the LLM from translating protocol names like
  BACNET → "Bâtiment Automatisation et de Contrôle" (French expansion)
- "Maintain the same separator" ensures the `|` count stays consistent
- The LLM returns exactly 59 output strings, one per input line

#### 3c. Post‑processing

```python
# For one language's output (list of 59 strings):
for i, line in enumerate(llm_output):
    terms = [s.strip() for s in line.split("|") if s.strip()]
    tool_json[lang]["x_search_terms"] = terms
```

The strip() call handles any whitespace the LLM may add around `|`.

#### 3d. Translation Granularity

For 59 tools, a **single API call per language** (sending all 59 lines at
once) is optimal:

- Context window is large enough (Gemini 2.5 Pro handles 59 lines easily)
- Single call ensures consistent style across all tools in one language
- Total: 33 API calls (one per language) + 1 English baseline = 34 calls

### 4. Positional File Mapping

The 59 tool files are processed in **alphabetical order** of their filename.
The sorted list is:

```python
FILES = [
    "bacnet_cov_subscribe_tool.json",   # → translated line [0]
    "bacnet_cov_unsubscribe_tool.json", # → translated line [1]
    "bacnet_read_tool.json",            # → translated line [2]
    ...
    "upnp_scan_tool.json",              # → translated line [58]
]
```

This sorted order must never change between translation and application,
otherwise terms would map to the wrong tool.

## Format Rules

1. Each `x_search_terms` array contains terms in order of relevance
2. The first term is always the "display name" (e.g. "bacnet scan")
3. The second term is the function/command name (e.g. "bacnet_scan")
4. Subsequent terms are alternative keywords and aliases
5. Proper nouns (protocol names, brands) appear in both original and translated
   forms (e.g. `bacnet | BACNET` in English → `バックネット | バクネット` in Japanese)
6. Terms are kept short (≤3 words per term preferred)

## Adding a New Language

1. Collect the 59 `x_search_terms_en` from each tool file
2. Join each into a pipe‑delimited string
3. Call `translate_text` with the list of 59 strings
4. Parse the output: split each string on `|`, strip, store in JSON
5. Update the support matrix in this document

## Adding a New Tool

1. Add `en.x_search_terms` to the tool JSON
2. Add `x_search_terms_en` to the Python file
3. Insert the corresponding pipe‑delimited line at the correct position
   in the 59‑entry array (or regenerate all translations)

## Verification

After translation, verify with:

```python
import json, os
tools_dir = "src/uagent/tools"
count = 0
for fname in os.listdir(tools_dir):
    if not fname.endswith("_tool.json"): continue
    with open(os.path.join(tools_dir, fname)) as f:
        data = json.load(f)
    for lang, val in data.items():
        if isinstance(val, dict) and val.get("x_search_terms", []):
            count += 1
print(f"Translated entries: {count}")
```
