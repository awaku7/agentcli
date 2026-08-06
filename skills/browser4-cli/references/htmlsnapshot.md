---
title: "HTML Snapshot — Static DOM Extraction & Inspection"
description: "Reference for htmlsnapshot commands: capture, get, get all, grep, inspect, export, summary, and query (X-SQL)."
tier: catalog
---

# HTML Snapshot Reference

The `htmlsnapshot` family operates on a **static HTML snapshot** — the raw HTML of the current page parsed into a queryable DOM. Unlike interactive `snapshot` (accessibility-tree refs for click/fill), `htmlsnapshot` extracts structured data via CSS selectors and X-SQL queries.

## Comparison: snapshot vs htmlsnapshot

| Feature | `snapshot` | `htmlsnapshot` |
|---------|-----------|----------------|
| Data source | Accessibility tree | Raw HTML DOM |
| Element addressing | Refs (`e5`) | CSS selectors only |
| X-SQL support | No | Yes (`query`) |
| Interactive element list | No | Yes (capture returns interactiveElements) |
| Selector discovery | No | Yes (`inspect`) |
| Output | YAML accessibility tree | HTML/text/JSON |

## Commands

### Capture

```bash
browser4-cli htmlsnapshot                                          # capture fresh snapshot + metadata
browser4-cli htmlsnapshot summary                                   # compressed page summary (WPSI)
browser4-cli htmlsnapshot export [--file output.html]               # save raw HTML to file
```

### Get — First match

```bash
browser4-cli htmlsnapshot get text "<selector>"                     # visible text
browser4-cli htmlsnapshot get html "<selector>"                     # inner HTML
browser4-cli htmlsnapshot get attr "<selector>" <attr-name>         # attribute value
```

### Get All — All matches (JSON array)

```bash
browser4-cli htmlsnapshot get all text "<selector>"                 # all matching text
browser4-cli htmlsnapshot get all html "<selector>"                 # all matching HTML
browser4-cli htmlsnapshot get all attr "<selector>" <attr-name>     # all attribute values
browser4-cli htmlsnapshot get all text "<selector>" --limit 5       # first 5
browser4-cli htmlsnapshot get all text "<selector>" --offset 10     # skip first 10
```

### Grep — Search HTML with regex

```bash
browser4-cli htmlsnapshot grep "<pattern>"                          # regex search (paginated, 2K lines/page)
browser4-cli htmlsnapshot grep "<pattern>" --all                    # all matches, no pagination
browser4-cli htmlsnapshot grep "<pattern>" --page 1 --page-size 50
```

### Inspect — Analyze DOM structure

```bash
browser4-cli htmlsnapshot inspect                                   # full page analysis
browser4-cli htmlsnapshot inspect "div.product"                     # specific selector
browser4-cli htmlsnapshot inspect ":root" --max 10 --depth 3       # limit results + depth
```

### Query — X-SQL (correlated multi-field)

See [x-sql.md](x-sql.md) for full function reference.

```bash
browser4-cli htmlsnapshot query --sql "SELECT ... FROM load_and_select(@url, ':root')"
browser4-cli htmlsnapshot query --sql @query.sql                    # read from file
browser4-cli htmlsnapshot query --sql-stdin < query.sql              # read from stdin
```

## Troubleshooting Empty Results

If `htmlsnapshot get` returns empty when elements exist:

1. Run `browser4-cli htmlsnapshot` first to capture a fresh snapshot
2. Verify selector with `htmlsnapshot grep <pattern>`
3. Check page load: AJAX content may take time (`wait --load networkidle`)
4. Use `htmlsnapshot inspect` to discover working selectors
