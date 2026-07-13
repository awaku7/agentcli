---
title: "X-SQL Reference: DOM & String Functions"
description: "X-SQL query language for structured data extraction from HTML. DOM functions, CSS selector functions, string manipulation, and common patterns."
tier: catalog
---

# X-SQL Reference

X-SQL is a SQL dialect for extracting structured data from HTML pages. It uses the **H2 database** SQL dialect with DOM UDFs.

## SQL Pattern

All queries MUST use this pattern:

```sql
SELECT <expressions>
FROM DOM_LOAD_AND_SELECT(url, cssQuery [, offset, limit])
[WHERE <conditions>]
[ORDER BY <expression> [ASC|DESC]]
[LIMIT <n>]
```

**No CTEs (`WITH`), subqueries in `FROM`, `EXPLODE`, or joins.** The only valid table source is `DOM_LOAD_AND_SELECT`.

**URL parameter:** Use the **unquoted** `@url` placeholder (replaced server-side). Do NOT use `'.'`.

## Common Patterns

### Scrape a list page

```sql
SELECT
    DOM_FIRST_TEXT(DOM, '.title') AS title,
    DOM_FIRST_FLOAT(DOM, '.price', 0.0) AS price,
    DOM_FIRST_HREF(DOM, 'a.title-link') AS link,
    DOM_FIRST_IMG(DOM, 'img.thumbnail') AS image
FROM DOM_LOAD_AND_SELECT(@url, '.product-card', 1, 20)
WHERE DOM_IS_NOT_NIL(DOM)
  AND STR_IS_NOT_BLANK(DOM_FIRST_TEXT(DOM, '.title'));
```

### Extract page metadata

```sql
SELECT
    DOM_DOC_TITLE(DOM) AS page_title,
    DOM_FIRST_TEXT(DOM, 'meta[name="description"]') AS meta_desc,
    DOM_FIRST_IMG(DOM, 'article img') AS hero_image
FROM DOM_LOAD_AND_SELECT(@url, ':root');
```

### Fallback chain (try multiple selectors)

```sql
SELECT ARRAY_FIRST_NOT_BLANK(
    MAKE_ARRAY(
        DOM_FIRST_TEXT(DOM, 'h1.product-title'),
        DOM_FIRST_TEXT(DOM, '.product-name'),
        DOM_FIRST_TEXT(DOM, 'title'),
        'Unknown Product'
    )
) AS product_name
FROM DOM_LOAD_AND_SELECT(@url, 'body');
```

## Frequently Used DOM Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `DOM_FIRST_TEXT(dom, css)` | String | First matching text |
| `DOM_FIRST_HREF(dom, css)` | String | First matching href |
| `DOM_FIRST_ATTR(dom, css, attr)` | String | First matching attribute |
| `DOM_FIRST_FLOAT(dom, css, default)` | Float | First matching number |
| `DOM_FIRST_IMG(dom, css)` | String | First matching image src |
| `DOM_TEXT(dom)` | String | Visible text of element |
| `DOM_HTML(dom)` | String | Inner HTML |
| `DOM_ATTR(dom, name)` | String | Attribute value |
| `DOM_BASE_URI(dom)` | String | Document base URL |
| `DOM_TAG_NAME(dom)` | String | HTML tag name |
| `DOM_HREF(dom)` | String | href attribute |
| `DOM_SRC(dom)` | String | src attribute |
| `DOM_DOC_TITLE(dom)` | String | Page title |
| `DOM_CSS_SELECTOR(dom)` | String | Best CSS selector for element |
| `DOM_IS_NOT_NIL(dom)` | Boolean | Element exists |
| `DOM_TEXT_LEN(dom)` | Int | Text length in chars |

## Frequently Used String Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `STR_TRIM(s)` | String | Remove leading/trailing whitespace |
| `STR_NORMALIZE_SPACE(s)` | String | Collapse whitespace, trim |
| `STR_DEFAULT_IF_BLANK(s, default)` | String | Fallback for empty strings |
| `STR_ABBREVIATE(s, maxLen)` | String | Truncate with ellipsis |
| `STR_FIRST_FLOAT(s, default)` | Float | Extract first number from text |
| `STR_IS_NOT_BLANK(s)` | Boolean | Non-empty check |

## Frequently Used Array Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `ARRAY_FIRST_NOT_BLANK(arr)` | String | First non-empty item |
| `MAKE_ARRAY(v1, v2, ...)` | Array | Create array from values |

## Load Options

Control page loading by appending options to the URL:

```sql
FROM DOM_LOAD_AND_SELECT('https://example.com -expires 1h -njr 3', ':root')
```

| Option | Description |
|--------|-------------|
| `-expires 1h/1d/30m` | Cache TTL |
| `-njr N` | Max navigation jumps |
| `-i 1d` | Inlining interval |
| `--refresh` | Force fresh fetch |
