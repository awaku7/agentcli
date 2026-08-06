---
title: "Crawl — Recursive Website Crawling & Bulk Extraction"
description: "Reference for the crawl command. Recursive crawling from a URL or seed file, with optional X-SQL extraction and multi-format output."
tier: procedure
---

# Crawl Reference

Recursive website crawling — start from a URL or seed file, follow links up to a configurable depth, and optionally extract structured data with X-SQL.

## Quick Start

```bash
# Link discovery from a single URL
browser4-cli crawl "https://example.com" --out-link-selector "a[href]"

# Bulk fetch from a seed file (no link discovery)
browser4-cli crawl --seed-file urls.txt --depth 0

# Bulk fetch + X-SQL extraction to CSV
browser4-cli crawl --seed-file urls.txt --sql @extract.sql --format csv -o results.csv
```

## Modes

### Link discovery mode (depth >= 1)

1. Load seed URL
1. Extract links matching `--out-link-selector` (CSS selector)
1. Optionally filter by `--out-link-pattern` (regex)
1. Deduplicate, limit to `--top-links`
1. Load each linked page
1. If depth > 1, recurse (skip visited URLs)

### Bulk fetch mode (depth = 0)

Load each URL directly without link discovery. Ideal for processing a list of known URLs.

### X-SQL extraction mode (with --sql)

Query executed against each crawled page. `@url` placeholder is replaced server-side.

## Flags

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| URL (positional) | | string | — | Starting URL (omit when using `--seed-file`) |
| `--seed-file` | | string | — | File with URLs, one per line |
| `--depth` | `-d` | int | 1 | 0 = fetch only; 1+ = follow links |
| `--out-link-selector` | `-ol` | string | — | CSS selector for link extraction |
| `--out-link-pattern` | `-olp` | regex | `.+` | Regex filter for links |
| `--top-links` | `-tl` | int | 20 | Max links per page |
| `--sql` | | string | — | X-SQL query (`@` prefix = file) |
| `--sql-stdin` | | bool | — | Read SQL from stdin |
| `--format` | | string | table | Output: `json`, `csv`, `table` |
| `--output` / `-o` | | string | — | Write to file |
| `--refresh` | | bool | — | Force fresh fetch |
| `--expires` | | string | — | Cache TTL: `1d`, `1h`, `30m` |
| `--page-load-timeout` | | string | — | Max wait per page |
| `--background` | | bool | — | Async execution |
