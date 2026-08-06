# WEBINSPECTER (playwright_inspector)

`playwright_inspector` records a manual browser session using Playwright and saves artifacts so you can analyze/debug later (often with an LLM).

Prerequisites:

- Playwright installed
- Browsers installed (e.g. `python -m playwright install`)

Outputs (under the current workdir):

- `webinspect/{prefix}/final.html` / `final.png`
- `webinspect/{prefix}/latest.html`
- `webinspect/{prefix}/flow.jsonl`
- `webinspect/{prefix}/index.jsonl`
- `webinspect/{prefix}/pages/`
- `webinspect/{prefix}/snapshots/`

Flow events are JSONL records intended for later inspection by an LLM. The log includes page navigation, request/response, console, pageerror, DOM events, and page summaries when available.

`index.jsonl` lists the numbered captures with URL, title, timestamp, and file names. `latest.html` always tracks the most recently saved HTML.

______________________________________________________________________

## 1. Use cases

Use `playwright_inspector` when a human must complete a browser flow, such as authentication, before the resulting DOM and network evidence can be analyzed. Typical uses include capturing authenticated pages, identifying failed API requests during navigation, and preserving console or page errors.

## 2. Usage and arguments

Open the initial URL, operate the browser manually, and press **Resume (▷)** in the Inspector to finalize the capture.

- `url`: initial URL; defaults to `about:blank`
- `prefix`: sanitized directory prefix; defaults to `debug_capture`

## 3. Saved artifacts

Artifacts are saved under `webinspect/{prefix}/` in the current workdir:

- `final.html` / `final.png`: final DOM and screenshot
- `latest.html`: most recently saved HTML
- `flow.jsonl`: navigation, network, console, pageerror, DOM, and summary events
- `index.jsonl`: capture index with URL, title, timestamp, and filenames
- `pages/`: per-navigation HTML and screenshots
- `snapshots/`: DOM and screenshots for main-frame URL transitions

## 4. Reading the event log

`flow.jsonl` and `index.jsonl` contain one JSON object per line. Important event types include `goto`, `navigated`, `snapshot`, `request`, `response`, `console`, `pageerror`, and `final`. Start with `flow.jsonl` chronologically, then inspect the relevant snapshot HTML.

## 5. LLM analysis workflow

Provide `flow.jsonl` and only the relevant `snapshots/*.html` or `final.html` to an LLM. Ask it to identify the navigation preceding a 4xx/5xx response, extract form field names, or correlate console errors with page transitions. Treat URLs, request data, and captured HTML as potentially sensitive.

## 6. Packaging and documentation access

For wheel installations, consider including this document as package data, exposing it through `importlib.resources`, adding a CLI command such as `uag docs webinspect`, and linking it from project metadata.
