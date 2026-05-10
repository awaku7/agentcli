from .i18n_helper import make_tool_translator
from .context import get_callbacks

_ = make_tool_translator(__file__)

import json
import os
import subprocess
import sys
import time
from typing import Any, Dict

BUSY_LABEL = True
STATUS_LABEL = "tool:playwright_inspector"


def _emit_debug(message: str) -> None:
    cb = get_callbacks().debug
    if cb is not None:
        try:
            cb(message)
        except Exception:
            pass


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "playwright_inspector",
        "description": _(
            "tool.description",
            default=(
                "Launch Playwright Inspector to capture browser operations. Opens the specified URL "
                "and saves the page state (HTML and image) after the user clicks the Resume button. "
                "Additionally, saves numbered per-navigation HTML/PNG under pages/, keeps latest.html updated, "
                "writes index.jsonl, and records navigation, network, console events, DOM events, and page summaries in a JSONL file."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": _(
                        "param.url.description",
                        default="Initial URL to open (default: about:blank).",
                    ),
                },
                "prefix": {
                    "type": "string",
                    "description": _(
                        "param.prefix.description",
                        default="Prefix for saved filenames (default: debug_capture).",
                    ),
                },
            },
        },
    },
}


def run_playwright_inspector(
    url: str = "about:blank", prefix: str = "debug_capture"
) -> str:
    """Launch Playwright Inspector and save the state and navigation snapshots after user operations."""

    _emit_debug(f"Launching Playwright Inspector: url={url!r}, prefix={prefix!r}")

    payload = {
        "url": url,
        "prefix": prefix,
        "started_at": time.time(),
        "ui_started": _("ui.started", default="--- PLAYWRIGHT INSPECTOR STARTED ---"),
        "ui_resume_prompt": _(
            "ui.resume_prompt",
            default="After operations, please click Resume (▷) in the Inspector.",
        ),
        "ui_captured": _(
            "ui.captured",
            default="--- CAPTURED: {html}, {png}, {flow}, {snapshots}/ ---",
        ),
    }

    logic_code = r"""
import asyncio
import json
import os
import re
import sys
import time
from typing import Any, Dict, List

from playwright.async_api import async_playwright


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def _sanitize_for_filename(s: str, max_len: int = 80) -> str:
    s = (s or "").strip()
    if not s:
        return "blank"
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s)
    s = s.strip("._-")
    if not s:
        return "blank"
    if len(s) > max_len:
        s = s[:max_len]
    return s


class FlowLogger:
    def __init__(self, path: str):
        self.path = path
        self._fp = open(path, "a", encoding="utf-8")

    def log(self, obj: Dict[str, Any]) -> None:
        obj = dict(obj)
        obj.setdefault("ts", time.time())
        obj.setdefault("ts_iso", _now_iso())
        self._fp.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self._fp.flush()

    def close(self) -> None:
        try:
            self._fp.close()
        except Exception:
            pass


def make_event_record(event_type: str, page_id: str, **fields: Any) -> Dict[str, Any]:
    record: Dict[str, Any] = {"type": event_type, "page_id": page_id}
    record.update(fields)
    return record


def make_page_summary(page_id: str, page_url: str, recent_actions: List[Dict[str, Any]]) -> Dict[str, Any]:
    return make_event_record(
        "page_summary",
        page_id,
        url=page_url,
        recent_action_count=len(recent_actions),
        recent_action_types=[item.get("type") for item in recent_actions[-5:]],
    )


async def main() -> None:
    if len(sys.argv) < 2:
        raise RuntimeError("missing JSON argument")

    payload = json.loads(sys.argv[1])
    url = payload.get("url") or "about:blank"
    prefix = payload.get("prefix") or "debug_capture"
    ui_started = payload.get("ui_started")
    ui_resume_prompt = payload.get("ui_resume_prompt")
    ui_captured = payload.get("ui_captured")

    prefix_dir_name = _sanitize_for_filename(prefix)
    base_dir = os.path.join("webinspect", prefix_dir_name)
    flow_path = os.path.join(base_dir, "flow.jsonl")
    snapshots_dir = os.path.join(base_dir, "snapshots")
    pages_dir = os.path.join(base_dir, "pages")
    latest_html_path = os.path.join(base_dir, "latest.html")
    index_path = os.path.join(base_dir, "index.jsonl")
    os.makedirs(snapshots_dir, exist_ok=True)
    os.makedirs(pages_dir, exist_ok=True)

    logger = FlowLogger(flow_path)
    index_logger = FlowLogger(index_path)
    page_seq = 0

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(channel="msedge", headless=False)
        except Exception:
            browser = await p.chromium.launch(headless=False)

        context = await browser.new_context(viewport={"width": 1280, "height": 1024})

        async def wire_page(page):
            nonlocal page_seq
            page_seq += 1
            page_id = f"p{page_seq}"
            action_seq = 0
            page_actions: List[Dict[str, Any]] = []
            logger.log(make_event_record("page_open", page_id, url=page.url, summary="Opened page"))

            def emit_dom_event(event_name: str, detail: Dict[str, Any]) -> None:
                nonlocal action_seq
                action_seq += 1
                detail = dict(detail)
                record = make_event_record(
                    "dom_event",
                    page_id,
                    event=event_name,
                    action_id=action_seq,
                    **detail,
                )
                page_actions.append(record)
                logger.log(record)

            async def inject_observer() -> None:
                await page.add_init_script(r'''
(() => {
  if (window.__UAG_OBSERVER_INSTALLED__) return;
  window.__UAG_OBSERVER_INSTALLED__ = true;

  const send = (event, detail) => {
    try {
      console.log("__UAG_EVENT__" + JSON.stringify({event, detail, ts: Date.now()}));
    } catch (e) {}
  };

  const describe = (el) => {
    if (!el || !el.tagName) return {};
    const out = {
      tag: el.tagName.toLowerCase(),
      id: el.id || "",
      name: el.getAttribute && el.getAttribute("name") || "",
      text: (el.innerText || el.value || "").toString().trim().slice(0, 200),
      aria_label: el.getAttribute && el.getAttribute("aria-label") || "",
      role: el.getAttribute && el.getAttribute("role") || "",
      cls: el.className && typeof el.className === "string" ? el.className.slice(0, 120) : "",
    };
    try {
      out.selector = el.id ? `#${el.id}` : out.name ? `${out.tag}[name="${out.name}"]` : out.tag;
    } catch (e) {}
    return out;
  };

  document.addEventListener("click", (e) => {
    const t = e.target;
    send("click", {target: describe(t), x: e.clientX, y: e.clientY});
  }, true);

  document.addEventListener("input", (e) => {
    const t = e.target;
    const value = t && "value" in t ? String(t.value || "") : "";
    send("input", {target: describe(t), value_length: value.length, checked: !!(t && t.checked)});
  }, true);

  document.addEventListener("submit", (e) => {
    const t = e.target;
    send("submit", {target: describe(t)});
  }, true);
})();
                ''')


            async def on_console(msg):
                try:
                    text = msg.text
                    if text.startswith("__UAG_EVENT__"):
                        raw = text[len("__UAG_EVENT__"):]
                        data = json.loads(raw)
                        emit_dom_event(data.get("event", "dom_event"), data.get("detail") or {})
                        return
                    logger.log({"type": "console", "level": msg.type, "text": text})
                except Exception:
                    pass

            def on_request(req):
                try:
                    logger.log(make_event_record("request", page_id, url=req.url, method=req.method, resource_type=req.resource_type))
                except Exception:
                    pass

            async def on_response(resp):
                try:
                    logger.log(make_event_record("response", page_id, url=resp.url, status=resp.status, ok=resp.ok))
                except Exception:
                    pass

            def on_page_error(err):
                try:
                    logger.log(make_event_record("pageerror", page_id, error=str(err)))
                except Exception:
                    pass

            page.on("request", on_request)
            page.on("console", lambda m: asyncio.create_task(on_console(m)))
            page.on("pageerror", on_page_error)
            page.on("response", lambda r: asyncio.create_task(on_response(r)))
            await inject_observer()

            snap_lock = asyncio.Lock()
            snap_idx = 0

            async def save_snapshot(reason: str, nav_url: str) -> None:
                nonlocal snap_idx
                async with snap_lock:
                    snap_idx += 1
                    idx = snap_idx

                    try:
                        await page.wait_for_load_state("domcontentloaded", timeout=5000)
                    except Exception:
                        pass

                    safe = _sanitize_for_filename(nav_url)
                    snapshot_base = os.path.join(snapshots_dir, f"{idx:04d}_{reason}_{safe}")
                    page_base = os.path.join(pages_dir, f"{idx:04d}_{reason}_{safe}")

                    title = ""
                    try:
                        title = await page.title()
                    except Exception:
                        pass

                    try:
                        html = await page.content()
                    except Exception:
                        html = ""

                    for path in (snapshot_base + ".png", page_base + ".png"):
                        try:
                            await page.screenshot(path=path)
                        except Exception:
                            pass

                    for path in (snapshot_base + ".html", page_base + ".html", latest_html_path):
                        try:
                            with open(path, "w", encoding="utf-8") as f:
                                f.write(html)
                        except Exception:
                            pass

                    record = make_event_record(
                        "snapshot",
                        page_id,
                        reason=reason,
                        url=nav_url,
                        title=title,
                        index=idx,
                        html=os.path.basename(page_base + ".html"),
                        png=os.path.basename(page_base + ".png"),
                        snapshot_html=os.path.basename(snapshot_base + ".html"),
                        snapshot_png=os.path.basename(snapshot_base + ".png"),
                        latest_html=os.path.basename(latest_html_path),
                    )
                    page_actions.append(record)
                    logger.log(record)
                    index_logger.log(record)

            def on_frame_navigated(frame):
                try:
                    if frame != page.main_frame:
                        return
                    nav_url = frame.url
                    nav_record = make_event_record("navigated", page_id, url=nav_url, summary="Main frame navigated")
                    page_actions.append(nav_record)
                    logger.log(nav_record)
                    asyncio.create_task(save_snapshot("navigated", nav_url))
                except Exception:
                    pass

            page.on("framenavigated", on_frame_navigated)

            return page_id

        page = await context.new_page()
        page_id = await wire_page(page)

        if url != "about:blank":
            logger.log({"type": "goto", "page_id": page_id, "url": url, "summary": "Navigating to initial URL"})
            await page.goto(url)

        print(ui_started)
        print(ui_resume_prompt)

        await page.pause()

        final_png = os.path.join(base_dir, "final.png")
        final_html = os.path.join(base_dir, "final.html")

        try:
            await page.screenshot(path=final_png)
        except Exception:
            pass

        try:
            content = await page.content()
            for path in (final_html, latest_html_path):
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
        except Exception:
            pass

        try:
            logger.log(make_page_summary(page_id, page.url, page_actions[-20:]))
        except Exception:
            pass
        final_record = make_event_record("final", page_id, url=page.url, html=final_html, latest_html=latest_html_path, png=final_png, snapshots_dir=snapshots_dir, flow=flow_path, summary="Captured final page state")
        logger.log(final_record)
        index_logger.log(final_record)

        await browser.close()
        logger.close()
        index_logger.close()
        print(ui_captured.format(html=final_html, png=final_png, flow=flow_path, snapshots=snapshots_dir))


if __name__ == "__main__":
    asyncio.run(main())
"""

    temp_script = f"temp_inspector_{os.getpid()}.py"
    with open(temp_script, "w", encoding="utf-8") as f:
        f.write(logic_code)

    try:
        argv = [sys.executable, temp_script, json.dumps(payload, ensure_ascii=False)]
        result = subprocess.run(argv, capture_output=True, text=True)
        if result.returncode != 0:
            return _(
                "err.child_failed",
                default="[playwright_inspector error] Child process failed:\n{stderr}",
            ).format(stderr=result.stderr or "")

        return _(
            "out.ok",
            default="Capture complete: {prefix}.html, {prefix}.png, {prefix}.flow.jsonl, {prefix}_snapshots/, pages/, index.jsonl, latest.html created.\n{stdout}",
        ).format(prefix=prefix, stdout=result.stdout or "")
    except Exception as e:
        return f"[playwright_inspector error] {type(e).__name__}: {e}"
    finally:
        try:
            if os.path.exists(temp_script):
                os.remove(temp_script)
        except Exception:
            pass


def run_tool(args: Dict[str, Any]) -> str:
    url = args.get("url", "about:blank")
    prefix = args.get("prefix", "debug_capture")
    return run_playwright_inspector(url, prefix)


if __name__ == "__main__":
    print(run_playwright_inspector())
