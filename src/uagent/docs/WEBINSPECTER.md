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
