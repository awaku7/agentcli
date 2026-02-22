from .i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)

import json
import os
import subprocess
import sys
import time
from typing import Any, Dict

# ツール実行中は Busy 表示にしたいので ON
BUSY_LABEL = True
STATUS_LABEL = "tool:playwright_inspector"

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "playwright_inspector",
        "description": (
            "Playwright Inspectorを起動してブラウザ操作をキャプチャします。指定したURLを開き、"
            "ユーザーがResumeボタンを押した後のページ状態をHTMLと画像で保存します。"
            "また、メインフレームのURL遷移ごとにDOM/スクリーンショットを連番保存し、"
            "遷移/ネットワーク/console等のイベントをJSONLで保存します。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "最初に開くURL（デフォルト: about:blank）",
                },
                "prefix": {
                    "type": "string",
                    "description": "保存するファイル名の接頭辞（デフォルト: debug_capture）",
                },
            },
        },
    },
}


def run_playwright_inspector(
    url: str = "about:blank", prefix: str = "debug_capture"
) -> str:
    """Playwright Inspector を起動し、ユーザー操作後の状態と遷移スナップショットを保存する。

    既存挙動（Resume後に最終HTML/PNG保存して終了）を維持しつつ、追加で以下を行う。

    - メインフレームの URL 遷移（framenavigated）をトリガに、DOM/PNGを連番で保存
      - 保存先: {prefix}_snapshots/
      - ファイル名: 0001_navigated_<sanitized>.html/png
    - 遷移・ネットワーク・console/pageerror を JSONL で保存
      - 保存先: {prefix}.flow.jsonl

    Args:
        url: 最初に開くURL（デフォルトは空白ページ）
        prefix: 保存するファイル（html/png/flow.jsonl）の接頭辞
    """

    payload = {
        "url": url,
        "prefix": prefix,
        "started_at": time.time(),
    }

    # 子プロセス側のロジック（埋め込み）
    # NOTE:
    # - url/prefix は埋め込みではなく argv(JSON) で受け取る
    # - これにより引用符等でスクリプトが壊れるのを避ける
    logic_code = r"""
import asyncio
import json
import os
import re
import sys
import time
from typing import Any, Dict, Optional

from playwright.async_api import async_playwright


def _now_iso() -> str:
    # ISO8601-ish (timezone naive)
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def _sanitize_for_filename(s: str, max_len: int = 80) -> str:
    s = (s or "").strip()
    if not s:
        return "blank"
    # replace scheme separators etc.
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


async def main() -> None:
    if len(sys.argv) < 2:
        print("Error: missing JSON argument", file=sys.stderr)
        sys.exit(1)

    payload = json.loads(sys.argv[1])
    url = payload.get("url") or "about:blank"
    prefix = payload.get("prefix") or "debug_capture"

    prefix_dir_name = _sanitize_for_filename(prefix)
    base_dir = os.path.join("webinspect", prefix_dir_name)
    flow_path = os.path.join(base_dir, "flow.jsonl")
    snapshots_dir = os.path.join(base_dir, "snapshots")
    os.makedirs(snapshots_dir, exist_ok=True)

    logger = FlowLogger(flow_path)

    async with async_playwright() as p:
        try:
            # 可能な限り Edge を使用
            browser = await p.chromium.launch(channel="msedge", headless=False)
        except Exception:
            browser = await p.chromium.launch(headless=False)

        context = await browser.new_context(viewport={"width": 1280, "height": 1024})
        page = await context.new_page()

        # --- event logging ---
        # request/response/console/pageerror
        def on_request(req):
            try:
                logger.log(
                    {
                        "type": "request",
                        "url": req.url,
                        "method": req.method,
                        "resource_type": req.resource_type,
                    }
                )
            except Exception:
                pass

        async def on_response(resp):
            try:
                logger.log(
                    {
                        "type": "response",
                        "url": resp.url,
                        "status": resp.status,
                        "ok": resp.ok,
                    }
                )
            except Exception:
                pass

        def on_console(msg):
            try:
                logger.log(
                    {
                        "type": "console",
                        "level": msg.type,
                        "text": msg.text,
                    }
                )
            except Exception:
                pass

        def on_page_error(err):
            try:
                logger.log({"type": "pageerror", "error": str(err)})
            except Exception:
                pass

        page.on("request", on_request)
        page.on("console", on_console)
        page.on("pageerror", on_page_error)
        page.on("response", lambda r: asyncio.create_task(on_response(r)))

        # --- snapshot on main-frame navigation ---
        snap_lock = asyncio.Lock()
        snap_idx = 0

        async def save_snapshot(reason: str, nav_url: str) -> None:
            nonlocal snap_idx
            async with snap_lock:
                snap_idx += 1
                idx = snap_idx

                # Best-effort: wait until DOMContentLoaded for this navigation
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=5000)
                except Exception:
                    pass

                safe = _sanitize_for_filename(nav_url)
                base = os.path.join(snapshots_dir, f"{idx:04d}_{reason}_{safe}")

                try:
                    await page.screenshot(path=base + ".png")
                except Exception:
                    # screenshot failures are non-fatal
                    pass

                try:
                    html = await page.content()
                    with open(base + ".html", "w", encoding="utf-8") as f:
                        f.write(html)
                except Exception:
                    pass

                logger.log(
                    {
                        "type": "snapshot",
                        "reason": reason,
                        "url": nav_url,
                        "index": idx,
                        "html": os.path.basename(base + ".html"),
                        "png": os.path.basename(base + ".png"),
                    }
                )

        def on_frame_navigated(frame):
            try:
                # main frame only
                if frame != page.main_frame:
                    return
                nav_url = frame.url
                logger.log({"type": "navigated", "url": nav_url})
                asyncio.create_task(save_snapshot("navigated", nav_url))
            except Exception:
                pass

        page.on("framenavigated", on_frame_navigated)

        # initial navigation
        if url != "about:blank":
            logger.log({"type": "goto", "url": url})
            await page.goto(url)

        print("--- PLAYWRIGHT INSPECTOR STARTED ---")
        print("操作後、Inspectorの Resume (▷) を押してください。")

        # Inspector を起動（ユーザー操作）
        await page.pause()

        # 終了後の状態を保存（従来どおり）
        final_png = os.path.join(base_dir, "final.png")
        final_html = os.path.join(base_dir, "final.html")

        try:
            await page.screenshot(path=final_png)
        except Exception:
            pass

        try:
            content = await page.content()
            with open(final_html, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception:
            pass

        logger.log(
            {
                "type": "final",
                "url": page.url,
                "html": final_html,
                "png": final_png,
                "snapshots_dir": snapshots_dir,
                "flow": flow_path,
            }
        )

        await browser.close()
        logger.close()
        print(f"--- CAPTURED: {final_html}, {final_png}, {flow_path}, {snapshots_dir}/ ---")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
"""

    temp_script = f"temp_inspector_{os.getpid()}.py"
    with open(temp_script, "w", encoding="utf-8") as f:
        f.write(logic_code)

    try:
        argv = [sys.executable, temp_script, json.dumps(payload, ensure_ascii=False)]
        result = subprocess.run(argv, capture_output=True, text=True)
        if result.returncode != 0:
            return "[playwright_inspector error] 子プロセスが失敗しました:\n" + (
                result.stderr or ""
            )

        return (
            f"キャプチャ完了: {prefix}.html, {prefix}.png, {prefix}.flow.jsonl, {prefix}_snapshots/ を作成しました。\n"
            + (result.stdout or "")
        )
    except Exception as e:
        return f"[playwright_inspector error] {type(e).__name__}: {e}"
    finally:
        try:
            if os.path.exists(temp_script):
                os.remove(temp_script)
        except Exception:
            pass


def run_tool(args: Dict[str, Any]) -> str:
    """LLMからの呼び出しエントリポイント"""
    url = args.get("url", "about:blank")
    prefix = args.get("prefix", "debug_capture")
    return run_playwright_inspector(url, prefix)


if __name__ == "__main__":
    print(run_playwright_inspector())
