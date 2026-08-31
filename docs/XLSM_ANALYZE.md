# XLSM Static Analysis

`xlsm_analyze` is a read-only inspection tool for Excel macro-enabled workbooks (`.xlsm`). It extracts workbook structure and embedded VBA source without opening Excel or executing macros.

## Why it matters

Important business logic is often hidden across worksheets, formulas, event handlers, and VBA modules. `xlsm_analyze` turns that logic into a traceable report that can be reviewed before modernization, migration, auditing, or web-system planning.

## What it analyzes

### Workbook structure

- Worksheet names and dimensions
- Non-empty cell counts
- Formulas and their cell addresses
- Merged ranges
- Workbook links when available through the underlying workbook

### VBA

- Embedded VBA modules and source code
- `Sub`, `Function`, and `Property` procedures
- Procedure line numbers
- `Call` and callable-name references
- Approximate module-level call inventory
- Potentially risky operations, including:
  - `Shell` execution
  - File creation, deletion, copying, and directory access
  - HTTP or other network access
  - External workbook opening and link updates
  - Database access

## Output formats

- **JSON** for downstream tooling and automated review
- **Markdown** for people-readable reports and documentation

Use `include_source=false` when the report should contain metadata and findings without the extracted VBA source.

## Example

```text
xlsm_analyze(
  input_path="finance_model.xlsm",
  output_path="finance_model_analysis.md",
  output_format="markdown",
  include_source=true
)
```

## Encrypted files

For password-protected Office files, pass `password` to the converter or analyzer. If `msoffcrypto-tool` is missing, it is installed automatically. The file is decrypted only to a temporary file for analysis, which is deleted afterward. VBA-project-level protection or unsupported encryption may still prevent source extraction.

## Safety and platform support

- VBA is extracted and analyzed statically; it is never executed.
- `oletools` reads the embedded `vbaProject.bin` directly and does not require Microsoft Excel.
- Worksheet inspection uses `openpyxl`.
- The analysis path is designed to work on Windows, macOS, and Linux.
- Password-protected, corrupted, obfuscated, or unsupported workbook content may produce warnings or incomplete results.

## Scope and limitations

This tool reports evidence found in the workbook; it does not claim to prove complete program behavior. VBA that is generated dynamically, heavily obfuscated, or dependent on Excel COM/runtime behavior may require manual review. The results should be treated as an audit and discovery aid, not as a replacement for security review or business-owner validation.
