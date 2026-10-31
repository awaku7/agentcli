"""Regression checks for Web chat scroll-follow behavior."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_chat_scroll_follows_only_when_near_bottom() -> None:
    source = (ROOT / "frontend/src/lib/components/Chat.svelte").read_text(
        encoding="utf-8"
    )

    assert "onscroll={handleChatScroll}" in source
    assert "const bottomThreshold = 80;" in source
    assert "followLatest = distance <= bottomThreshold;" in source
    assert "if (!followLatest || !chatBox || scrollScheduled) return;" in source
    assert (
        "if (followLatest && chatBox) chatBox.scrollTop = chatBox.scrollHeight;"
        in source
    )


def test_shipped_chat_bundle_preserves_scroll_follow_gate() -> None:
    bundle = (ROOT / "src/uagent/static/assets/index.js").read_text(encoding="utf-8")

    assert 'ho("scroll",l,handleChatScroll)' in bundle
    assert "box.scrollHeight-box.scrollTop-box.clientHeight<=80" in bundle
    assert "if(!followLatest||!a(o)||scrollScheduled)return" in bundle
    assert "followLatest&&a(o)&&(a(o).scrollTop=a(o).scrollHeight)" in bundle


def test_shipped_chat_bundle_receives_scroll_events() -> None:
    """Exercise the bundled direct-event helper and auto-follow guard."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js unavailable")

    bundle = ROOT / "src/uagent/static/assets/index.js"
    script = r"""
const fs = require("node:fs");
const assert = require("node:assert/strict");
const js = fs.readFileSync(process.argv[1], "utf8");
const helperStart = js.indexOf("function el(");
const helperEnd = js.indexOf("function D(", helperStart);
assert(helperStart >= 0 && helperEnd > helperStart);
const helpers = js.slice(helperStart, helperEnd);
const documentStub = { body: {} };
const ho = new Function(
  "Oo", "to", "vr", "Zo", "document", "window", "HTMLMediaElement",
  helpers + "return ho;"
)(() => {}, callback => callback(), callback => callback(), () => {},
  documentStub, {}, class {});
const start = js.indexOf("let followLatest=!0,scrollScheduled=!1;");
const end = js.indexOf("Rt(()=>{a(r).length&&u()})", start);
assert(start >= 0 && end > start);
const behavior = js.slice(start, end);
const registration = js.match(/ho\("scroll",l,handleChatScroll\)/);
assert(registration, "scroll must use a direct listener, not delegated D()");
const frames = [];
const element = new EventTarget();
element.scrollHeight = 1000;
element.clientHeight = 300;
element.scrollTop = 700;
const api = new Function(
  "a", "o", "l", "ho", "requestAnimationFrame",
  behavior + registration[0] + ";return {u,following:()=>followLatest};"
)(() => element, {}, element, ho, callback => frames.push(callback));
const flush = () => { while (frames.length) frames.shift()(); };

api.u();
api.u();
assert.equal(frames.length, 1, "scroll requests should coalesce");
flush();

element.scrollTop = 100;
element.dispatchEvent(new Event("scroll"));
assert.equal(api.following(), false, "scrolling away pauses following");
api.u();
assert.equal(frames.length, 0);
assert.equal(element.scrollTop, 100);

element.scrollTop = 700;
element.dispatchEvent(new Event("scroll"));
assert.equal(api.following(), true, "returning to bottom resumes following");
api.u();
flush();
assert.equal(element.scrollTop, 1000);

element.scrollTop = 700;
element.dispatchEvent(new Event("scroll"));
api.u();
element.scrollTop = 100;
element.dispatchEvent(new Event("scroll"));
flush();
assert.equal(element.scrollTop, 100, "pending frame must not steal scroll");
"""
    subprocess.run(
        [node, "-e", script, str(bundle)],
        check=True,
        capture_output=True,
        text=True,
    )
