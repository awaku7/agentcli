# tools/fetch_url_tool.py
from __future__ import annotations

import json
import sys
from typing import Any, Dict
from urllib.request import Request, urlopen

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "fetch_url",
        "description": _(
            "tool.description",
            default=(
                "Access the specified URL via HTTP GET and return the beginning of the response as text. Useful for fetching and inspecting HTML or JSON."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default="This tool performs the operation described by the tool name 'fetch_url'.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": _(
                        "param.url.description",
                        default="URL to access (http:// or https://).",
                    ),
                }
            },
            "required": ["url"],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    url = str(args.get("url", "") or "")
    if not url:
        raise ValueError("url is required")

    print("[url] " + url, file=sys.stderr)

    req = Request(url, headers={"User-Agent": "curl/7.79.1"})

    def do_request(unverified: bool = False):
        # Keep it minimal; caller environment is responsible for SSL config.
        return urlopen(req)

    try:
        with do_request() as resp:
            content = resp.read(4000)
        try:
            text = content.decode("utf-8")
        except Exception:
            text = content.decode("latin-1", errors="replace")
        return text
    except Exception as e:
        return json.dumps(
            {
                "ok": False,
                "error": str(e),
            },
            ensure_ascii=False,
        )
