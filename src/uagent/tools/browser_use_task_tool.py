# tools/browser_use_task_tool.py
from __future__ import annotations

import asyncio
import concurrent.futures
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from .context import get_callbacks
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:browser_use_task"

_DANGEROUS_KEYWORDS = [
    "buy",
    "purchase",
    "order",
    "submit",
    "send",
    "delete",
    "remove",
    "upload",
    "download",
    "login",
    "log in",
    "sign in",
    "password",
    "payment",
    "checkout",
    "post",
    "publish",
    "share",
    "comment",
    "like",
    "follow",
    "subscribe",
    "unsubscribe",
    "購入",
    "注文",
    "送信",
    "削除",
    "除去",
    "アップロード",
    "ダウンロード",
    "ログイン",
    "サインイン",
    "パスワード",
    "決済",
    "支払い",
    "投稿",
    "公開",
    "共有",
    "コメント",
    "フォロー",
    "登録",
    "解除",
]


LOAD_DISABLED_REASON = ""


TOOL_SPEC: Dict[str, Any] = {
    "tool_level": -1,
    "type": "function",
    "function": {
        "name": "browser_use_task",
        "description": _(
            "tool.description",
            default=(
                "Run an autonomous browser task using the browser-use Python library. "
                "Use this when a site must be operated interactively, not merely fetched. "
                "Dangerous actions require explicit user confirmation via confirmed=true."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "This tool launches browser-use to operate a browser for a natural-language task. "
                "Do not use it for purchases, submissions, deletions, uploads, downloads, logins, "
                "posts, or other state-changing actions unless the user has explicitly approved "
                "the exact action and confirmed=true is supplied."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": _(
                        "param.task.description",
                        default="Natural-language browser task to perform.",
                    ),
                },
                "start_url": {
                    "type": "string",
                    "description": _(
                        "param.start_url.description",
                        default="Optional initial URL to open before executing the task.",
                    ),
                },
                "headless": {
                    "type": "boolean",
                    "default": True,
                    "description": _(
                        "param.headless.description",
                        default="Run the browser without a visible window (default: true).",
                    ),
                },
                "max_steps": {
                    "type": "integer",
                    "default": 20,
                    "description": _(
                        "param.max_steps.description",
                        default="Maximum number of browser-use agent steps (default: 20).",
                    ),
                },
                "timeout_s": {
                    "type": "integer",
                    "default": 180,
                    "description": _(
                        "param.timeout_s.description",
                        default="Overall timeout in seconds (default: 180).",
                    ),
                },
                "model": {
                    "type": "string",
                    "description": _(
                        "param.model.description",
                        default="Optional Browser Use model name for ChatBrowserUse, for example 'bu-latest'.",
                    ),
                },
                "use_cloud": {
                    "type": "boolean",
                    "default": False,
                    "description": _(
                        "param.use_cloud.description",
                        default="Use Browser Use Cloud browser infrastructure (default: false).",
                    ),
                },
                "allowed_domains": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _(
                        "param.allowed_domains.description",
                        default="Optional list of allowed domains for browser navigation.",
                    ),
                },
                "deny_downloads": {
                    "type": "boolean",
                    "default": True,
                    "description": _(
                        "param.deny_downloads.description",
                        default="Disable browser downloads where supported (default: true).",
                    ),
                },
                "use_vision": {
                    "type": "boolean",
                    "default": True,
                    "description": _(
                        "param.use_vision.description",
                        default="Allow browser-use to use screenshots/vision if supported (default: true).",
                    ),
                },
                "output_dir": {
                    "type": "string",
                    "default": "outputs/browser_use",
                    "description": _(
                        "param.output_dir.description",
                        default="Directory where run history JSON is saved.",
                    ),
                },
                "confirmed": {
                    "type": "boolean",
                    "default": False,
                    "description": _(
                        "param.confirmed.description",
                        default="Set true only after explicit user approval for dangerous/state-changing tasks.",
                    ),
                },
            },
            "required": ["task"],
        },
    },
}


def _emit_debug(message: str) -> None:
    cb = get_callbacks().debug
    if cb is not None:
        try:
            cb(message)
        except Exception:
            pass


def _looks_dangerous(task: str) -> bool:
    text = (task or "").lower()
    return any(keyword.lower() in text for keyword in _DANGEROUS_KEYWORDS)


def _normalize_domains(value: Any) -> Optional[List[str]]:
    if value in (None, ""):
        return None
    if isinstance(value, str):
        raw_items = [item.strip() for item in value.split(",")]
    elif isinstance(value, list):
        raw_items = [str(item).strip() for item in value]
    else:
        raise ValueError(
            "allowed_domains must be a list of strings or comma-separated string"
        )

    domains: List[str] = []
    for item in raw_items:
        if not item:
            continue
        parsed = urlparse(item if "://" in item else "https://" + item)
        host = (parsed.hostname or item).strip().lower().rstrip(".")
        if not host:
            continue
        domains.append(host)

    return domains or None


def _host_matches_allowed(host: str, allowed_domains: List[str]) -> bool:
    host = host.lower().rstrip(".")
    for domain in allowed_domains:
        domain = domain.lower().rstrip(".")
        if host == domain or host.endswith("." + domain):
            return True
    return False


def _validate_start_url(start_url: str, allowed_domains: Optional[List[str]]) -> None:
    if not start_url:
        return
    parsed = urlparse(start_url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("start_url must use http or https")
    if not parsed.hostname:
        raise ValueError("start_url must include a host")
    if allowed_domains and not _host_matches_allowed(parsed.hostname, allowed_domains):
        raise ValueError("start_url host is not included in allowed_domains")


def _history_summary(history: Any) -> Dict[str, Any]:
    def call(name: str, default: Any = None, *args: Any) -> Any:
        attr = getattr(history, name, None)
        if not callable(attr):
            return default
        try:
            return attr(*args)
        except Exception:
            return default

    return {
        "result": call("final_result"),
        "is_done": call("is_done"),
        "is_successful": call("is_successful"),
        "steps": call("number_of_steps"),
        "duration_s": call("total_duration_seconds"),
        "urls": call("urls", []),
        "errors": [e for e in (call("errors", []) or []) if e],
        "extracted_content": call("extracted_content", []),
        "screenshots": call("screenshots", [], 5),
    }


async def _run_browser_use_async(
    *,
    task: str,
    start_url: str,
    headless: bool,
    max_steps: int,
    timeout_s: int,
    model: str,
    use_cloud: bool,
    allowed_domains: Optional[List[str]],
    deny_downloads: bool,
    use_vision: bool,
    output_dir: str,
) -> Dict[str, Any]:
    try:
        from browser_use import Agent, Browser, ChatBrowserUse
    except Exception as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "browser-use is not installed in this Python environment. "
            "Install it with: python -m pip install browser-use"
        ) from exc

    full_task = task.strip()
    if start_url:
        full_task = f"Start at {start_url}. {full_task}"

    run_id = time.strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", full_task[:60]).strip("._-") or "run"
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    history_path = out_dir / f"browser_use_{run_id}_{safe_name}.json"

    browser = Browser(
        headless=headless,
        use_cloud=use_cloud,
        allowed_domains=allowed_domains,
        accept_downloads=not deny_downloads,
        auto_download_pdfs=not deny_downloads,
    )
    llm = ChatBrowserUse(model=model or "bu-latest")

    agent = Agent(
        task=full_task,
        llm=llm,
        browser=browser,
        use_vision=use_vision,
        save_conversation_path=str(history_path),
    )

    history = await asyncio.wait_for(agent.run(max_steps=max_steps), timeout=timeout_s)
    summary = _history_summary(history)

    try:
        if hasattr(history, "save_to_file"):
            history.save_to_file(str(history_path))
    except Exception:
        pass

    return {**summary, "history_path": str(history_path)}


def _run_in_thread(**kwargs: Any) -> Dict[str, Any]:
    def worker() -> Dict[str, Any]:
        return asyncio.run(_run_browser_use_async(**kwargs))

    # Run in a dedicated thread so this tool also works if the host already owns
    # an asyncio event loop.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(worker)
        return future.result(timeout=int(kwargs["timeout_s"]) + 10)


def run_tool(args: Dict[str, Any]) -> str:
    task = str(args.get("task") or "").strip()
    if not task:
        raise ValueError("task is required")

    start_url = str(args.get("start_url") or "").strip()
    headless = bool(args.get("headless", True))
    max_steps = int(args.get("max_steps") or 20)
    timeout_s = int(args.get("timeout_s") or 180)
    model = str(args.get("model") or "").strip()
    use_cloud = bool(args.get("use_cloud", False))
    allowed_domains = _normalize_domains(args.get("allowed_domains"))
    deny_downloads = bool(args.get("deny_downloads", True))
    use_vision = bool(args.get("use_vision", True))
    output_dir = str(args.get("output_dir") or "outputs/browser_use")
    confirmed = bool(args.get("confirmed", False))

    max_steps = max(1, min(max_steps, 200))
    timeout_s = max(10, min(timeout_s, 3600))

    _validate_start_url(start_url, allowed_domains)

    dangerous = _looks_dangerous(task)
    if dangerous and not confirmed:
        return json.dumps(
            {
                "ok": False,
                "requires_confirmation": True,
                "error": "Task appears to include dangerous or state-changing browser actions. Ask the user for explicit approval, then retry with confirmed=true.",
                "matched_policy": "dangerous_browser_action",
            },
            ensure_ascii=False,
        )

    started = time.time()
    _emit_debug(f"Running browser-use task: {task!r}")

    try:
        result = _run_in_thread(
            task=task,
            start_url=start_url,
            headless=headless,
            max_steps=max_steps,
            timeout_s=timeout_s,
            model=model,
            use_cloud=use_cloud,
            allowed_domains=allowed_domains,
            deny_downloads=deny_downloads,
            use_vision=use_vision,
            output_dir=output_dir,
        )
        return json.dumps(
            {
                "ok": True,
                "elapsed_s": round(time.time() - started, 3),
                "dangerous": dangerous,
                **result,
            },
            ensure_ascii=False,
            default=str,
        )
    except Exception as exc:
        return json.dumps(
            {
                "ok": False,
                "elapsed_s": round(time.time() - started, 3),
                "error": f"{type(exc).__name__}: {exc}",
            },
            ensure_ascii=False,
        )
