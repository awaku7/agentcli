# Translation work file

Working set: `src/uagent/tools/*.json`

Status:
- Done: `search_files_tool.json`
- Done: `semantic_search_files_tool.json`
- Next: `calculator_tool.json`

Notes:
- Translate carefully in small batches.
- Keep keys unchanged.
- Preserve placeholders such as `{path}`, `{error}`, `{count}`, `{score:.4f}`.
- Preserve newlines and punctuation as much as possible.
- Validate JSON after every edit.
- Create/keep backup copies before overwriting files.

Target locales:
- `de`
- `it`
- `ru`
- `pt_BR`

Priority for the next batch:
1. `calculator_tool.json`
2. Other small, high-use tool JSON files
3. Larger tool JSON files
