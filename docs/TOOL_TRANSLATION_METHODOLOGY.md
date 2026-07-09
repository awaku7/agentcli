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

The translation process uses the `translate_text` tool (a wrapper around
Gemini/LLM) with the following characteristics:

- **Input:** each translation call sends a concatenated list of the 59 raw
  `x_search_terms_en` strings (one per tool), separated by `|`
- **Output:** one `|`‑separated string per tool, preserving the exact order
- **Batch size:** 59 tools per language
- **Post‑processing:** each output string is split on `|`, whitespace‑stripped,
  and stored as a JSON array

**Prompt template (auto‑generated):**

```
Translate the following 59 lines of search terms from English to {target_lang}.
Each line contains terms separated by "|". Maintain the same separator.
Preserve proper nouns (BACNET, ECHONET, MODBUS, MQTT, OPCUA, UPNP, etc.).
Translate the rest naturally.
```

## Format Rules

1. Each `x_search_terms` array contains terms in order of relevance
2. The first term is always the "display name" (e.g. "bacnet scan")
3. The second term is the function/command name (e.g. "bacnet_scan")
4. Subsequent terms are alternative keywords and aliases
5. Proper nouns (protocol names, brands) appear in both original and translated
   forms (e.g. `bacnet | BACNET` in English → `バックネット | バクネット` in Japanese)
6. Terms are kept short (≤3 words per term preferred)

## Adding a New Language

1. Call `translate_text` with the 59‑line concatenated string
2. Parse the `|`‑separated output back into 59 arrays
3. Write each array to the corresponding `{lang}.x_search_terms` in the JSON
4. Update the support matrix in this document

## Adding a New Tool

1. Add `en.x_search_terms` to the tool JSON
2. Add `x_search_terms_en` to the Python file
3. Translate via the pipeline above (or add manually for a single tool)

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
