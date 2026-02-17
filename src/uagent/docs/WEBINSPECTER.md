# WEBINSPECTER (playwright_inspector)

`playwright_inspector` records a manual browser session using Playwright and saves artifacts so you can analyze/debug later (often with an LLM).

Prerequisites:
- Playwright installed
- Browsers installed (e.g. `python -m playwright install`)

Outputs (under the current workdir):
- `webinspect/{prefix}/final.html` / `final.png`
- `webinspect/{prefix}/flow.jsonl`
- `webinspect/{prefix}/snapshots/`

---
