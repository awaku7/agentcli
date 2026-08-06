---
name: browser4-cli
title: "Browser4 CLI — AI Agent Browser Automation Skill"
description: "Browser automation CLI for AI agents — Chrome/Chromium via CDP with accessibility-tree snapshots. Navigate, interact, extract, crawl, swarm, and loop. Covers every CLI command with decision trees and copy-paste templates."
allowed-tools: Bash(browser4-cli:*)
tier: decision
---

# Browser Automation with browser4-cli

Browser4 CLI is a **coroutine-safe, high-performance browser automation engine** for AI agents.
It uses Chrome DevTools Protocol (CDP) with accessibility-tree snapshots for element interaction
and raw HTML snapshots for data extraction.

- **Session management**: auto-open/reconnect browsers, named sessions, attach to existing Chrome
- **Element interaction**: click, fill, type, press, select, check, uncheck, drag — all via accessibility refs
- **Data extraction**: CSS selectors, X-SQL queries, regex grep, LLM-powered extraction
- **Bulk processing**: recursive crawl, parallel swarm, repeated loop
- **Output modes**: human-readable, JSON (`--json`), quiet (`--quiet`)

## Quick Reference: Command Families

| Family | Purpose | Key commands |
|--------|---------|-------------|
| Session | Start/stop/reuse browser sessions | `open`, `goto`, `close`, `close-all`, `kill-all`, `attach`, `list`, `status` |
| Navigation | Move between pages | `goto <url>`, `go-back`, `go-forward`, `reload` |
| Snapshot | Capture page structure (accessibility tree) | `snapshot [-v N] [--auto-diff]`, `snapshot grep <pattern>` |
| Interaction | Click, type, fill forms | `click <ref>`, `fill <ref> <value>`, `type <ref> <text>`, `press <key>`, `select`, `check`, `uncheck`, `drag` |
| Extract (CSS) | Extract data via CSS selectors | `htmlsnapshot`, `htmlsnapshot get text/html/attr <selector>`, `get all`, `grep`, `inspect` |
| Extract (X-SQL) | Structured multi-field extraction | `htmlsnapshot query --sql "SELECT ..."` |
| Extract (AI) | Natural-language extraction | `extract "..."`, `summarize`, `agent run "..."` |
| Bulk | Multi-page traversal | `crawl`, `swarm`, `loop` |
| Storage | Cookies, localStorage, sessionStorage | `state-save`, `state-load`, `cookie-get`, `cookie-set`, `local-storage-*`, `session-storage-*` |
| Visual | Screenshots, viewport control | `screenshot [--filename f.png]`, `scroll`, `wait`, `resize`, `tab-*` |
| Script | Execute JS in page | `eval "JS code" [--json]` |

______________________________________________________________________

## 1. Core Loop (Copy-Paste Template)

Every browser4-cli session follows this pattern:

```bash
# 1. NAVIGATE — auto-opens/reconnects session
browser4-cli goto "https://example.com"

# 2. SNAPSHOT — capture accessibility tree with refs
browser4-cli snapshot -v 0

# 3. INTERACT — use refs from snapshot
browser4-cli fill <ref> "<value>"
browser4-cli press Enter

# 4. RE-SNAPSHOT — verify changes
browser4-cli wait --load networkidle
browser4-cli snapshot -v 0 --auto-diff

# 5. EXTRACT — get data
browser4-cli htmlsnapshot get text "<css-selector>" --all
```

______________________________________________________________________

## 2. Session & Lifecycle

### Named Sessions

Isolate browser state (cookies, localStorage, tabs) with `-s <name>`:

```bash
browser4-cli -s mysession goto "https://example.com"
browser4-cli -s mysession snapshot
browser4-cli -s mysession close
```

`goto` auto-opens/reconnects — you rarely need to manage sessions manually.

### Session Commands

```bash
# Open a new session (optionally with URL)
browser4-cli open [url] [--headed|--headless] [--profile <path>] [--profile-mode <mode>]

# Navigate — auto-opens if no session exists
browser4-cli goto <url>

# Attach to an existing Chrome/Edge via CDP
browser4-cli attach --cdp chrome                # by channel name
browser4-cli attach --cdp http://localhost:9222   # by CDP URL
browser4-cli attach --cdp 9222                    # by port

# Close
browser4-cli close                                 # current session
browser4-cli close-all                              # all sessions (keep backend)
browser4-cli kill-all                               # stop backend + kill all processes

# Status & list
browser4-cli status                                 # server health, version
browser4-cli list [--all]                           # session list with reuse/refresh status
browser4-cli stop                                   # gracefully stop server
browser4-cli delete-data                            # delete session data
```

### Browser Profile Management

```bash
# Create a profile (e.g., for persistent login)
browser4-cli open --profile /path/to/profile --profile-mode persistent
```

______________________________________________________________________

## 3. Navigation

```bash
browser4-cli goto <url>          # Navigate — auto-opens session
browser4-cli go-back             # Previous page
browser4-cli go-forward          # Next page
browser4-cli reload              # Reload current page
```

______________________________________________________________________

## 4. Snapshot (Accessibility Tree)

Captures a YAML accessibility tree with element refs for interaction.

```bash
# Basic snapshot (viewport 0 = top of page)
browser4-cli snapshot -v 0

# Multiviewport — snapshot multiple scroll positions
browser4-cli snapshot -v 0,1,2

# With auto-diff (compare vs previous snapshot)
browser4-cli snapshot -v 0 --auto-diff

# Grep snapshot content (find elements by text/pattern)
browser4-cli snapshot grep "search term"
browser4-cli snapshot grep "price.*\\d+"        # regex
browser4-cli snapshot grep -i "error"            # case-insensitive
```

Snapshot output example:

```yaml
- generic [ref=e7]:
  - link "News" [ref=e191]:
    - /url: https://example.com/news
  - textbox "Search query" [ref=e35]
  - button "Search" [ref=e25]
```

**IMPORTANT — Ref Lifecycle:**

- **Safe (refs survive)**: `fill`, `type`, `press`, `check`, `uncheck`, `select` — property-only changes
- **Unsafe (re-snapshot after)**: `click` on links/buttons, `goto`, `reload`, tab switches — DOM restructuring
- **Gray area**: `click` on checkboxes/radio buttons, dropdown toggles — may or may not mutate DOM
- **Rule of thumb**: you can fill an entire form from a single snapshot. Only re-snapshot if a ref fails.

______________________________________________________________________

## 5. Page Interaction

All interaction commands use **refs** (e.g., `e5`, `e12`) from the latest snapshot.

```bash
# Click an element
browser4-cli click <ref>                    # left click
browser4-cli click <ref> right              # right click
browser4-cli click <ref> middle             # middle click
browser4-cli click <ref> --count 2          # double click

# Fill a text input (replaces existing content)
browser4-cli fill <ref> "text value"

# Type text (appends, character by character — slower, more realistic)
browser4-cli type <ref> "slow text"

# Press keyboard keys
browser4-cli press Enter                    # key name
browser4-cli press Tab
browser4-cli press Escape
browser4-cli press Control+a                # keyboard shortcuts
browser4-cli press "Hello World"

# Checkboxes & radio buttons
browser4-cli check <ref>                    # check (no-op if already checked)
browser4-cli uncheck <ref>                  # uncheck (no-op if unchecked)

# Select dropdown options
browser4-cli select <ref> "option-value"    # by value
browser4-cli select <ref> --label "Option"  # by label text
browser4-cli select <ref> --index 2         # by index

# Drag and drop
browser4-cli drag <source-ref> <target-ref>
```

______________________________________________________________________

## 6. Data Extraction

### 6a. HTML Snapshot (CSS Selectors) — *No LLM key needed*

First capture a fresh HTML snapshot:

```bash
browser4-cli htmlsnapshot                              # capture + metadata
browser4-cli htmlsnapshot summary                       # compressed page summary (WPSI)
browser4-cli htmlsnapshot export [--file output.html]   # save raw HTML to file
```

#### Get — single/match (first match only)

```bash
browser4-cli htmlsnapshot get text ".product-title"            # visible text
browser4-cli htmlsnapshot get html ".content"                   # inner HTML
browser4-cli htmlsnapshot get attr "img.hero" src               # attribute value
```

#### Get All — multiple matches (returns JSON array)

```bash
browser4-cli htmlsnapshot get all text "h2 a"                   # all product titles
browser4-cli htmlsnapshot get all attr ".item" data-id           # all data-id attrs
browser4-cli htmlsnapshot get all html "article"                 # all article HTMLs
browser4-cli htmlsnapshot get all text ".price" --limit 5        # first 5
browser4-cli htmlsnapshot get all text ".price" --offset 10      # skip first 10
```

#### Grep — search snapshot HTML with regex

```bash
browser4-cli htmlsnapshot grep "\\d+\\.\\d+"                    # find prices
browser4-cli htmlsnapshot grep "error" --all                     # all matches, no pagination
browser4-cli htmlsnapshot grep "pattern" --page 1 --page-size 50 # paginated
```

#### Inspect — analyze DOM structure, suggest CSS selectors

```bash
browser4-cli htmlsnapshot inspect                     # full analysis
browser4-cli htmlsnapshot inspect "div.product"       # specific selector
browser4-cli htmlsnapshot inspect ":root" --max 5     # limit suggestions
```

### 6b. X-SQL Queries — Correlated multi-field extraction

For structured data (title + price + URL per item), use X-SQL:

```bash
# Inline (simple queries)
browser4-cli htmlsnapshot query --sql "
  SELECT
    dom_base_uri(dom) AS url,
    dom_first_text(dom, 'h2 a') AS title,
    dom_first_text(dom, '.price') AS price
  FROM load_and_select(@url, '.product-card')
"

# From file (recommended — no escaping issues)
browser4-cli htmlsnapshot query --sql @query.sql

# From stdin
browser4-cli htmlsnapshot query --sql-stdin < query.sql
```

### 6c. AI-Powered Extraction — *Needs LLM key*

```bash
# Synchronous extraction from current page
browser4-cli extract "product name, price, ratings"

# With schema
browser4-cli extract "headlines and authors" \
  --schema '{"fields":[{"name":"title","type":"string"},{"name":"author","type":"string"}]}'

# Summarize page content
browser4-cli summarize "summarize the reviews"
browser4-cli summarize --selector "#reviews"

# Autonomous multi-step task (async)
browser4-cli agent run "Go to amazon.com, search for headphones, extract top 5 results"
browser4-cli agent status agent-task-1          # poll until COMPLETED
browser4-cli agent result agent-task-1          # fetch results
```

### 6d. Eval — Execute JavaScript

```bash
browser4-cli eval "document.title"                      # returns string
browser4-cli eval "JSON.stringify(window.performance)"  # complex JS
browser4-cli eval --json "document.querySelectorAll('.item').length"  # JSON output

# Pass JS from stdin (avoid quoting issues on Windows)
browser4-cli eval --stdin < script.js
browser4-cli eval --file script.js
```

______________________________________________________________________

## 7. Bulk Processing

### Crawl — Sequential multi-page processing

```bash
# Link discovery (depth 1+)
browser4-cli crawl "https://example.com" --out-link-selector "a[href]" --depth 1

# Bulk fetch from URL list (depth 0)
browser4-cli crawl --seed-file urls.txt --depth 0

# Bulk + X-SQL extraction to CSV
browser4-cli crawl --seed-file urls.txt --sql @extract.sql --format csv -o results.csv

# Refresh cache
browser4-cli crawl "https://example.com" --refresh
```

### Swarm — Parallel high-throughput scraping

```bash
# Create a swarm
browser4-cli swarm create

# Query with seed file
browser4-cli swarm query --seed-file urls.txt --sql "
  SELECT dom_first_text(dom, 'h1') AS title FROM load_and_select(@url, 'body')
"
```

### Loop — Repeated execution with persistence

```bash
# Run every hour
browser4-cli loop -- eval "document.title" -i 3600

# Run with counter
browser4-cli loop -- goto "https://example.com/page-\${i}" -i 86400 -n 30
```

______________________________________________________________________

## 8. Browser Storage Management

```bash
# Save/load session state (cookies, localStorage, sessionStorage)
browser4-cli state-save auth.json
browser4-cli state-load auth.json

# Cookie commands
browser4-cli cookie-get [name]                # get specific or all cookies
browser4-cli cookie-set <name> <value>         # set a cookie
browser4-cli cookie-delete <name>              # delete a cookie
browser4-cli cookie-clear                      # clear all cookies

# localStorage
browser4-cli local-storage-get [key]
browser4-cli local-storage-set <key> <value>
browser4-cli local-storage-delete <key>
browser4-cli local-storage-clear

# sessionStorage
browser4-cli session-storage-get [key]
browser4-cli session-storage-set <key> <value>
browser4-cli session-storage-delete <key>
browser4-cli session-storage-clear
```

______________________________________________________________________

## 9. Visual Capture & Viewport

```bash
# Screenshot
browser4-cli screenshot [--filename page.png] [--fullpage] [--selector ".main"]

# Scroll
browser4-cli scroll <x> <y>                  # pixel scroll
browser4-cli scroll 0 500                     # scroll down 500px

# Wait
browser4-cli wait 2000                        # ms
browser4-cli wait --load networkidle          # wait for network idle
browser4-cli wait --selector ".loaded"        # wait for element

# Viewport
browser4-cli resize <width> <height>          # e.g., 1920 1080

# Tab management
browser4-cli tab-list                         # list open tabs
browser4-cli tab-switch <index>               # switch to tab by index
browser4-cli tab-new <url>                    # new tab + navigate
browser4-cli tab-close [index]                # close tab (default: current)
```

______________________________________________________________________

## 10. Global Flags

These flags can appear before any command:

```
-s <name>, --session <name>    Named session label
--server <url>                 Override Browser4 server URL
--json                         Emit machine-parseable JSON to stdout
-q, --quiet                    Suppress normal output, show only errors
--proxy <url>                  Manual HTTP proxy for downloads
--help, -h                     Print help
--version, -v                  Print version
```

______________________________________________________________________

## 11. Decision Trees

### Choosing an Extraction Method

```
Need data from a page?
├─ Need to interact first (click, fill, scroll)?
│  → snapshot + refs, then extract
├─ Static page, single value?
│  → htmlsnapshot get text "<selector>"
├─ Static page, ALL matches of one field?
│  → htmlsnapshot get all text "<selector>"
├─ Multiple correlated fields (title+price+url per item)?
│  → htmlsnapshot query with X-SQL (DOM_LOAD_AND_SELECT)
├─ Need JS evaluation?
│  → eval --json
├─ Natural language ("find the price")?
│  → extract (needs LLM key)
├─ High volume, many pages?
│  → crawl (sequential) or swarm (parallel) with --sql
└─ Repeated monitoring?
   → loop -- eval "..." -i 3600
```

### Bulk Processing Approach

```
Need to process multiple pages?
├─ Single list page?
│  → htmlsnapshot query with DOM_LOAD_AND_SELECT
├─ Known URLs in a file?
│  → crawl --seed-file urls.txt --depth 0 --sql @query.sql
├─ Crawl from a start URL?
│  → crawl <url> --out-link-selector "a[href]" --depth N
├─ Parallel execution (high throughput)?
│  → swarm create → swarm query --seed-file ...
├─ Repeated monitoring?
│  → loop -- eval "..." -i 3600
└─ A few URLs in a script?
   → for url in ...; do browser4-cli goto "$url"; ... done
```

### get vs get all vs query

| Command | Returns | Best for |
|---------|---------|----------|
| `htmlsnapshot get text ".price"` | First match (string) | Single value, quick check |
| `htmlsnapshot get all text ".price"` | All matches (JSON array) | Validate selector returns expected count |
| `htmlsnapshot query --sql "SELECT ..."` | Correlated rows (table) | Title + price + URL per product card |

**Warning:** Multiple `get all` calls produce **unaligned arrays**. For correlated fields, use `query`.

______________________________________________________________________

## 12. Common Task Templates

### Login + Extract Data

```bash
browser4-cli goto "https://example.com/login"
browser4-cli snapshot -v 0
browser4-cli fill e5 "myusername"
browser4-cli fill e8 "mypassword"
browser4-cli press Enter
browser4-cli wait --load networkidle
browser4-cli snapshot -v 0
browser4-cli click e12                               # navigate to data page
browser4-cli wait --load networkidle
browser4-cli htmlsnapshot
browser4-cli htmlsnapshot query --sql "
  SELECT dom_first_text(dom, '.title') AS title,
         dom_first_text(dom, '.price') AS price
  FROM load_and_select(@url, '.product-card')
"
```

### Form Fill

```bash
browser4-cli goto "https://example.com/form"
browser4-cli snapshot -v 0
# Fill all fields from one snapshot (refs survive)
browser4-cli fill e1 "John"
browser4-cli fill e2 "Doe"
browser4-cli fill e3 "john@example.com"
browser4-cli select e4 --label "Option A"
browser4-cli check e5
browser4-cli click e6                                 # submit
browser4-cli wait --load networkidle
browser4-cli snapshot -v 0 --auto-diff                # verify result
```

### Extract Search Results

```bash
browser4-cli goto "https://www.amazon.com"
browser4-cli snapshot -v 0
browser4-cli fill e3 "wireless headphones"
browser4-cli press Enter
browser4-cli wait --load networkidle
browser4-cli htmlsnapshot
browser4-cli htmlsnapshot query --sql "
  SELECT
    dom_first_text(dom, 'h2 a') AS title,
    dom_first_text(dom, '.a-price-whole') AS price,
    dom_first_attr(dom, 'a.a-link-normal', 'href') AS link
  FROM load_and_select(@url, 'div[data-component-type=s-search-result]')
  LIMIT 5
"
```

### Screenshot + Save State

```bash
browser4-cli goto "https://example.com"
browser4-cli screenshot --filename page.png --fullpage
browser4-cli state-save session-state.json
```

### Attach to Existing Chrome

```bash
# Open Chrome with remote debugging, then:
browser4-cli attach --cdp chrome
browser4-cli snapshot
browser4-cli screenshot --filename live.png
browser4-cli eval "document.title"
```

______________________________________________________________________

## 13. Critical Warnings

> **Refs are ephemeral.** Re-snapshot after `click` (on links/buttons), `goto`, `reload`, tab switches. Form interactions (`fill`, `type`, `press`, `check`, `uncheck`, `select`) are safe — refs survive.

> **CSS selectors are tied to live websites.** They break when sites update. Prefer snapshot refs for interaction and X-SQL for structured extraction.

> **JSON output mode.** Use `--json` for machine-readable output. When using `--json`, only the JSON envelope appears on stdout — all tips and human-readable text are suppressed.

> **X-SQL file mode.** Prefer `--sql @file.sql` or `--sql-stdin` over inline SQL to avoid shell escaping issues, especially on Windows.

> **Never store refs across navigations.** They become invalid after any page load or DOM restructuring.

______________________________________________________________________

## References

Detailed reference documents are available in the `references/` directory:

- [htmlsnapshot.md](references/htmlsnapshot.md) — HTML snapshot commands, CSS extraction
- [x-sql.md](references/x-sql.md) — X-SQL DOM & string functions reference
- [agent.md](references/agent.md) — AI agent, extract, summarize commands
- [crawl.md](references/crawl.md) — Crawl command reference

See the official Browser4 documentation at https://browser4.io for the complete reference.
