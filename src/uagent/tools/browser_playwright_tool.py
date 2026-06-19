# src/uagent/tools/browser_playwright_tool.py
from __future__ import annotations

import asyncio
import json
from typing import Any, List, Dict
from pathlib import Path

from .context import get_callbacks
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:browser_playwright"

TOOL_SPEC: dict[str, Any] = {
    "tool_level": 1,
    "type": "function",
    "tool_genre": "external",
    "function": {
        "name": "browser_playwright",
        "description": _(
            "tool.description",
            default="Execute a sequence of browser actions using Playwright. Supports navigation, interaction, extraction, mouse/keyboard control, session, network, multi-page, accessibility, console, uploads, mobile emulation, and more.",
        ),
        "x_search_terms": [
            "browser_playwright", "playwright", "browser automation", "screenshot", "scraping",
            "iframe", "download", "trace", "clipboard", "http auth", "inject script", "resize viewport"
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "actions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": [
                                    "goto", "click", "fill", "wait", "content", "screenshot", "press",
                                    "scroll", "select", "hover", "evaluate", "extract_json", "wait_until",
                                    "get_attributes", "mouse_move", "mouse_click", "mouse_drag", "mouse_wheel",
                                    "keyboard_type", "save_storage", "intercept_network", "switch_page", "close_page",
                                    "get_accessibility_tree", "capture_console", "set_input_files", "element_screenshot",
                                    "block_resources", "handle_dialog", "check_visibility", "export_pdf", "route_mock",
                                    "switch_to_frame", "switch_to_parent_frame", "download", "trace_start", "trace_stop",
                                    "clipboard_read", "clipboard_write", "inject_script", "resize_viewport"
                                ]
                            },
                            "url": {"type": "string"},
                            "selector": {"type": "string"},
                            "value": {"type": "string"},
                            "key": {"type": "string"},
                            "timeout": {"type": "integer"},
                            "direction": {"type": "string", "enum": ["up", "down"]},
                            "expression": {"type": "string"},
                            "schema": {"type": "object"},
                            "condition": {"type": "string", "enum": ["load", "domcontentloaded", "networkidle", "visible", "hidden", "text"]},
                            "text": {"type": "string"},
                            "attributes": {"type": "array", "items": {"type": "string"}},
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "to_x": {"type": "number"},
                            "to_y": {"type": "number"},
                            "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
                            "click_count": {"type": "integer", "default": 1},
                            "delta_x": {"type": "number"},
                            "delta_y": {"type": "number"},
                            "delay": {"type": "integer", "default": 100},
                            "path": {"type": "string", "description": _("param.path.description", default="File path to save output (used by content, screenshot, export_pdf, etc.).")},
                            "paths": {"type": "array", "items": {"type": "string"}},
                            "url_pattern": {"type": "string"},
                            "index": {"type": "integer"},
                            "resource_types": {"type": "array", "items": {"type": "string"}},
                            "action": {"type": "string", "enum": ["accept", "dismiss"]},
                            "prompt_text": {"type": "string"},
                            "mock_data": {"type": "object", "description": "JSON data to return for route_mock."},
                            "script": {"type": "string", "description": "JavaScript code or URL to inject."},
                            "script_type": {"type": "string", "enum": ["content", "url"], "default": "content"},
                            "width": {"type": "integer"},
                            "height": {"type": "integer"}
                        },
                        "required": ["type"]
                    }
                },
                "headless": {"type": "boolean", "default": True},
                "storage_state": {"type": "string"},
                "mobile_device": {"type": "string"},
                "user_agent": {"type": "string"},
                "viewport": {"type": "object", "properties": {"width": {"type": "integer"}, "height": {"type": "integer"}}},
                "locale": {"type": "string"},
                "timezone_id": {"type": "string"},
                "record_video_dir": {"type": "string"},
                "geolocation": {"type": "object", "properties": {"latitude": {"type": "number"}, "longitude": {"type": "number"}, "accuracy": {"type": "number"}}},
                "extra_http_headers": {"type": "object", "description": "Custom HTTP headers."},
                "color_scheme": {"type": "string", "enum": ["light", "dark", "no-preference"]},
                "http_credentials": {
                    "type": "object",
                    "properties": {"username": {"type": "string"}, "password": {"type": "string"}},
                    "description": "HTTP Basic authentication credentials."
                },
                "trace": {
                    "type": "object",
                    "properties": {
                        "screenshots": {"type": "boolean", "default": True},
                        "snapshots": {"type": "boolean", "default": True}
                    },
                    "description": "Enable Playwright tracing. Trace will be saved at the end."
                },
                "trace_path": {"type": "string", "default": "trace.zip", "description": "Path to save the trace zip file."}
            },
            "required": ["actions"]
        }
    }
}


async def execute_actions(actions: List[Dict[str, Any]], headless: bool, **kwargs) -> Dict[str, Any]:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"ok": False, "error": "playwright is not installed."}

    results = []
    intercepted_data = []
    console_logs = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context_args = {}

        # -- mobile device config first, so user args can override --
        if kwargs.get("mobile_device"):
            device_config = p.devices.get(kwargs["mobile_device"])
            if device_config:
                context_args.update(device_config)

        for key in ["user_agent", "viewport", "locale", "timezone_id", "extra_http_headers", "color_scheme"]:
            if kwargs.get(key):
                context_args[key] = kwargs[key]

        if kwargs.get("storage_state"):
            ss_path = kwargs["storage_state"]
            if Path(ss_path).exists():
                context_args["storage_state"] = ss_path
            else:
                return {
                    "ok": False,
                    "error": f"storage_state file not found: {ss_path}"
                }
        if kwargs.get("record_video_dir"):
            context_args["record_video_dir"] = kwargs["record_video_dir"]
        if kwargs.get("http_credentials"):
            context_args["http_credentials"] = kwargs["http_credentials"]

        # -- geolocation: merge permissions with any existing ones --
        if kwargs.get("geolocation"):
            context_args["geolocation"] = kwargs["geolocation"]
            existing_permissions = context_args.get("permissions", [])
            if "geolocation" not in existing_permissions:
                context_args["permissions"] = existing_permissions + ["geolocation"]

        context = await browser.new_context(**context_args)
        page = await context.new_page()
        page.on("console", lambda msg: console_logs.append({"type": msg.type, "text": msg.text}))

        # Track disposable listeners so we can remove them on next call
        dialog_listeners: list[callable] = []
        response_listeners: list[callable] = []

        # Start trace if configured (tool-level)
        trace_opts = kwargs.get("trace")
        if trace_opts:
            await context.tracing.start(
                screenshots=trace_opts.get("screenshots", True),
                snapshots=trace_opts.get("snapshots", True)
            )

        # Track current frame for iframe support
        current_frame = page.main_frame

        def _require_frame() -> None:
            """Return error dict if current_frame is None; otherwise None."""
            if current_frame is None:
                raise RuntimeError("No active page/frame. All pages have been closed.")

        try:
            for action in actions:
                a_type = action.get("type")
                timeout = action.get("timeout", 10000)

                if a_type == "switch_to_frame":
                    _require_frame()
                    frame_element = await current_frame.wait_for_selector(
                        action["selector"], timeout=timeout
                    )
                    current_frame = await frame_element.content_frame()
                    if current_frame is None:
                        current_frame = page.main_frame
                        return {
                            "ok": False,
                            "error": f"Selector '{action['selector']}' did not resolve to an iframe."
                        }
                    results.append({"type": "switch_to_frame", "selector": action["selector"]})

                elif a_type == "switch_to_parent_frame":
                    _require_frame()
                    parent = current_frame.parent_frame
                    current_frame = parent if parent else page.main_frame
                    results.append({"type": "switch_to_parent_frame"})

                elif a_type == "download":
                    _require_frame()
                    async with page.expect_download(timeout=timeout) as download_info:
                        if "selector" in action:
                            await current_frame.click(action["selector"], timeout=timeout)
                    download = await download_info.value
                    save_path = action.get("path", download.suggested_filename)
                    await download.save_as(save_path)
                    results.append({
                        "type": "download",
                        "path": str(Path(save_path).absolute()),
                        "suggested_filename": download.suggested_filename,
                        "url": download.url
                    })

                elif a_type == "trace_start":
                    await context.tracing.start(
                        screenshots=action.get("screenshots", True),
                        snapshots=action.get("snapshots", True)
                    )
                    results.append({"type": "trace_start"})

                elif a_type == "trace_stop":
                    t_path = action.get("path", kwargs.get("trace_path", "trace.zip"))
                    await context.tracing.stop(path=t_path)
                    results.append({"type": "trace_stop", "path": str(Path(t_path).absolute())})

                elif a_type == "clipboard_read":
                    _require_frame()
                    text = await current_frame.evaluate("navigator.clipboard.readText()")
                    results.append({"type": "clipboard_read", "text": text})

                elif a_type == "clipboard_write":
                    _require_frame()
                    text = action.get("value", "")
                    await current_frame.evaluate(
                        f"navigator.clipboard.writeText({json.dumps(text)})"
                    )
                    results.append({"type": "clipboard_write"})

                elif a_type == "inject_script":
                    _require_frame()
                    if action.get("script_type", "content") == "url":
                        await current_frame.add_script_tag(url=action["script"])
                    else:
                        await current_frame.add_script_tag(content=action["script"])
                    results.append({"type": "inject_script"})

                elif a_type == "resize_viewport":
                    w = action.get("width", 1280)
                    h = action.get("height", 720)
                    await page.set_viewport_size({"width": w, "height": h})
                    results.append({"type": "resize_viewport", "width": w, "height": h})

                # --- existing actions below ---

                elif a_type == "export_pdf":
                    pdf_path = action.get(
                        "path", f"output_{int(asyncio.get_event_loop().time())}.pdf"
                    )
                    await page.pdf(path=pdf_path)
                    results.append({
                        "type": "export_pdf",
                        "path": str(Path(pdf_path).absolute())
                    })

                elif a_type == "route_mock":
                    pattern = action.get("url_pattern", "**/*")
                    data = action.get("mock_data", {})
                    await page.unroute(pattern)
                    await page.route(
                        pattern,
                        lambda route, _data=data: route.fulfill(json=_data)
                    )
                    results.append({"type": "route_mock", "pattern": pattern})

                elif a_type == "check_visibility":
                    _require_frame()
                    results.append({
                        "type": "visibility_check",
                        "selector": action["selector"],
                        "is_visible": await current_frame.is_visible(
                            action["selector"], timeout=timeout
                        )
                    })

                elif a_type == "handle_dialog":
                    # Remove previous dialog listeners to prevent accumulation
                    for prev_listener in dialog_listeners:
                        page.remove_listener("dialog", prev_listener)
                    dialog_listeners.clear()

                    dialog_action = action.get("action", "accept")
                    prompt_text = action.get("prompt_text")

                    def _make_handler(_a: str, _t: str | None):
                        def handler(d):
                            asyncio.create_task(
                                d.accept(_t) if _a == "accept" else d.dismiss()
                            )
                        return handler

                    listener = _make_handler(dialog_action, prompt_text)
                    page.on("dialog", listener)
                    dialog_listeners.append(listener)

                    results.append({
                        "type": "handle_dialog",
                        "action": dialog_action
                    })

                elif a_type == "block_resources":
                    blocked = set(action.get("resource_types", ["image"]))
                    # Register without destroying other route handlers.
                    # Playwright uses LIFO ordering: the newest route handler fires first.
                    # If it calls continue_(), the next handler gets a chance.
                    await page.route(
                        "**/*",
                        lambda r, _blocked=blocked: (
                            r.abort() if r.request.resource_type in _blocked
                            else r.continue_()
                        )
                    )
                    results.append({
                        "type": "block_resources",
                        "resource_types": list(blocked)
                    })

                elif a_type == "element_screenshot":
                    _require_frame()
                    el = await current_frame.wait_for_selector(
                        action["selector"], timeout=timeout
                    )
                    s_path = action.get(
                        "path", f"el_{int(asyncio.get_event_loop().time())}.png"
                    )
                    if el:
                        await el.screenshot(path=s_path)
                    results.append({
                        "type": "element_screenshot",
                        "path": str(Path(s_path).absolute())
                    })

                elif a_type == "set_input_files":
                    if "paths" in action:
                        files = action["paths"]
                    elif "path" in action:
                        files = [action["path"]]
                    else:
                        files = []
                    await page.set_input_files(
                        action["selector"], files, timeout=timeout
                    )

                elif a_type == "capture_console":
                    results.append({"type": "console_logs", "data": list(console_logs)})

                elif a_type == "get_accessibility_tree":
                    snapshot = await page.accessibility.snapshot()
                    results.append({"type": "accessibility_tree", "data": snapshot})

                elif a_type == "switch_page":
                    idx = action.get("index", 0)
                    if idx < len(context.pages):
                        page = context.pages[idx]
                        current_frame = page.main_frame
                        await page.bring_to_front()
                    else:
                        return {
                            "ok": False,
                            "error": f"Page index {idx} out of range (have {len(context.pages)} pages)."
                        }

                elif a_type == "close_page":
                    await page.close()
                    if context.pages:
                        page = context.pages[-1]
                        current_frame = page.main_frame
                    else:
                        current_frame = None

                elif a_type == "intercept_network":
                    # Remove previous response listeners to prevent accumulation
                    for prev_listener in response_listeners:
                        page.remove_listener("response", prev_listener)
                    response_listeners.clear()

                    pattern = action.get("url_pattern", "")

                    def _make_handler(_pat: str):
                        def handler(r):
                            if _pat in r.url:
                                intercepted_data.append({"url": r.url})
                        return handler

                    listener = _make_handler(pattern)
                    page.on("response", listener)
                    response_listeners.append(listener)

                    results.append({
                        "type": "intercept_network",
                        "url_pattern": pattern
                    })

                elif a_type == "goto":
                    _require_frame()
                    wu = action.get("wait_until", "networkidle")
                    to = action.get("timeout", 30000)
                    await current_frame.goto(
                        action["url"], wait_until=wu, timeout=to
                    )

                elif a_type == "click":
                    _require_frame()
                    await current_frame.click(action["selector"], timeout=timeout)

                elif a_type == "fill":
                    _require_frame()
                    await current_frame.fill(
                        action["selector"], action["value"], timeout=timeout
                    )

                elif a_type == "press":
                    _require_frame()
                    await current_frame.press(
                        action["selector"], action["key"], timeout=timeout
                    )

                elif a_type == "keyboard_type":
                    _require_frame()
                    if "selector" in action:
                        await current_frame.focus(action["selector"])
                    await page.keyboard.type(
                        action["value"], delay=action.get("delay", 100)
                    )

                elif a_type == "wait":
                    _require_frame()
                    await current_frame.wait_for_selector(
                        action["selector"], timeout=timeout
                    )

                elif a_type == "wait_until":
                    cond = action.get("condition", "load")
                    if cond in ["load", "domcontentloaded", "networkidle"]:
                        await page.wait_for_load_state(cond, timeout=timeout)
                    elif cond in ["visible", "hidden"]:
                        _require_frame()
                        await current_frame.wait_for_selector(
                            action["selector"], state=cond, timeout=timeout
                        )
                    elif cond == "text":
                        text = action.get("text", "")
                        if not text:
                            return {"ok": False, "error": "text is required when condition='text'."}
                        await page.wait_for_function(
                            f'document.body.innerText.includes({json.dumps(text)})',
                            timeout=timeout
                        )
                    else:
                        return {"ok": False, "error": f"Unknown wait_until condition: {cond}"}

                elif a_type == "hover":
                    _require_frame()
                    await current_frame.hover(action["selector"], timeout=timeout)

                elif a_type == "scroll":
                    _require_frame()
                    d = action.get("direction", "down")
                    factor = "window.innerHeight" if d == "down" else "-window.innerHeight"
                    await current_frame.evaluate(f"window.scrollBy(0, {factor})")

                elif a_type == "select":
                    _require_frame()
                    await current_frame.select_option(
                        action["selector"], action["value"], timeout=timeout
                    )

                elif a_type == "evaluate":
                    _require_frame()
                    results.append({
                        "type": "evaluate",
                        "data": await current_frame.evaluate(action["expression"])
                    })

                elif a_type == "extract_json":
                    _require_frame()
                    schema = action.get("schema", {})
                    extracted = {}
                    for k, v in schema.items():
                        els = await current_frame.query_selector_all(v)
                        texts = [await el.inner_text() for el in els]
                        extracted[k] = texts
                    results.append({"type": "extract_json", "data": extracted})

                elif a_type == "get_attributes":
                    _require_frame()
                    elements = await current_frame.query_selector_all(action["selector"])
                    attr_results = []
                    for el in elements:
                        entry = {"text": await el.inner_text()}
                        for n in action.get("attributes", []):
                            entry[n] = await el.get_attribute(n)
                        attr_results.append(entry)
                    results.append({"type": "get_attributes", "data": attr_results})

                elif a_type == "mouse_move":
                    await page.mouse.move(action["x"], action["y"])

                elif a_type == "mouse_click":
                    await page.mouse.click(
                        action.get("x", 0),
                        action.get("y", 0),
                        button=action.get("button", "left"),
                        click_count=action.get("click_count", 1)
                    )

                elif a_type == "mouse_drag":
                    btn = action.get("button", "left")
                    await page.mouse.move(action["x"], action["y"])
                    await page.mouse.down(button=btn)
                    await page.mouse.move(action["to_x"], action["to_y"])
                    await page.mouse.up(button=btn)

                elif a_type == "mouse_wheel":
                    await page.mouse.wheel(
                        action.get("delta_x", 0), action.get("delta_y", 0)
                    )

                elif a_type == "save_storage":
                    p_path = action.get("path", "storage_state.json")
                    await context.storage_state(path=p_path)
                    results.append({
                        "type": "save_storage",
                        "path": str(Path(p_path).absolute())
                    })

                elif a_type == "content":
                    _require_frame()
                    html = await current_frame.content()
                    c_path = action.get("path")
                    if c_path:
                        Path(c_path).write_text(html, encoding="utf-8")
                        results.append({
                            "type": "content",
                            "path": str(Path(c_path).absolute())
                        })
                    else:
                        results.append({
                            "type": "content",
                            "data": html
                        })

                elif a_type == "screenshot":
                    s_path = action.get(
                        "path", f"debug_{int(asyncio.get_event_loop().time())}.png"
                    )
                    await page.screenshot(path=s_path)
                    results.append({
                        "type": "screenshot",
                        "path": str(Path(s_path).absolute())
                    })

            if intercepted_data:
                results.append({"type": "intercepted_network", "data": intercepted_data})

            # Stop tool-level trace at end
            if trace_opts:
                t_path = kwargs.get("trace_path", "trace.zip")
                await context.tracing.stop(path=t_path)
                results.append({
                    "type": "trace",
                    "path": str(Path(t_path).absolute())
                })

            v_path = None
            if kwargs.get("record_video_dir"):
                vid = page.video
                if vid:
                    p = vid.path()
                    if p:
                        v_path = str(Path(p).absolute())

            return {
                "ok": True,
                "results": results,
                "final_url": page.url,
                "video_path": v_path
            }

        except RuntimeError as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:
            return {"ok": False, "error": str(e), "last_url": page.url}
        finally:
            await browser.close()


def browser_playwright_run(args: dict[str, Any]) -> dict[str, Any]:
    # Copy to avoid mutating caller's dict; keep all keys (including trace*)
    # so they reach execute_actions via kwargs.
    cleaned = dict(args)
    actions = cleaned.pop("actions", [])
    headless = cleaned.pop("headless", True)
    try:
        return asyncio.run(execute_actions(actions, headless, **cleaned))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                execute_actions(actions, headless, **cleaned)
            )
        finally:
            loop.close()


# Alias for tool loader
run_tool = browser_playwright_run
