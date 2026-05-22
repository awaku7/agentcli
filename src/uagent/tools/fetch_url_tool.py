# tools/fetch_url_tool.py
from __future__ import annotations

import json
import sys
import warnings
from typing import Any, Optional
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

BUSY_LABEL = True

TOOL_SPEC: dict[str, Any] = {
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
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "fetch url",
                "http get",
                "download page",
                "URL取得",
                "obtener url",
                "récupérer url",
                "URL 가져오기",
                "получить url",
            ],
        ),
        "x_search_terms_en": [
            "fetch url",
            "http get",
            "download page",
            "URL取得",
            "obtener url",
            "récupérer url",
            "URL 가져오기",
            "получить url",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": _(
                        "param.url.description",
                        default="URL to access (http:// or https://).",
                    ),
                },
                "extract": {
                    "type": "string",
                    "enum": ["head", "text", "html", "json"],
                    "default": "head",
                    "description": _(
                        "param.extract.description",
                        default=(
                            "Extraction mode. head=return the beginning of the response; text=extract text from HTML; html=extract HTML fragment; json=parse JSON (optionally apply json_pointer)."
                        ),
                    ),
                },
                "selector": {
                    "type": "string",
                    "description": _(
                        "param.selector.description",
                        default=(
                            "Optional CSS selector. If provided, the first matched element is extracted for extract=text/html."
                        ),
                    ),
                },
                "json_pointer": {
                    "type": "string",
                    "description": _(
                        "param.json_pointer.description",
                        default=(
                            "Optional RFC 6901 JSON Pointer (e.g., /items/0/title) used when extract=json."
                        ),
                    ),
                },
                "max_bytes": {
                    "type": "integer",
                    "default": 4000,
                    "description": _(
                        "param.max_bytes.description",
                        default="Maximum bytes to read from the response.",
                    ),
                },
                "max_chars": {
                    "type": "integer",
                    "default": 8000,
                    "description": _(
                        "param.max_chars.description",
                        default="Maximum characters to return (applied after decoding/extraction).",
                    ),
                },
                "user_agent": {
                    "type": "string",
                    "description": _(
                        "param.user_agent.description",
                        default="Optional User-Agent header value.",
                    ),
                },
            },
            "required": ["url"],
        },
    },
}


def _json_pointer_get(doc: Any, pointer: str) -> Any:
    if pointer in ("", None):
        return doc
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("json_pointer must start with '/'")

    cur: Any = doc
    for token in pointer.split("/")[1:]:
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, list):
            try:
                idx = int(token)
            except Exception as e:  # pragma: no cover
                raise ValueError(f"invalid list index: {token}") from e
            cur = cur[idx]
        elif isinstance(cur, dict):
            cur = cur[token]
        else:
            raise KeyError(token)
    return cur


def _decode_bytes(content: bytes, declared_charset: Optional[str]) -> str:
    if declared_charset:
        try:
            return content.decode(declared_charset, errors="replace")
        except Exception:
            pass

    try:
        return content.decode("utf-8")
    except Exception:
        return content.decode("latin-1", errors="replace")


def _truncate_chars(s: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(s) <= max_chars:
        return s
    return s[:max_chars]


def _pick_html_element(soup: BeautifulSoup, selector: str | None):
    if selector:
        el = soup.select_one(selector)
        if el is not None:
            return el

    for sel in ("main", "article", "[role=main]", "body"):
        el = soup.select_one(sel)
        if el is not None:
            return el

    return soup


def run_tool(args: dict[str, Any]) -> str:
    url = str(args.get("url", "") or "")
    if not url:
        raise ValueError("url is required")

    extract = str(args.get("extract") or "head")
    selector = str(args.get("selector") or "") or None
    json_pointer = str(args.get("json_pointer") or "") or None

    max_bytes = int(args.get("max_bytes") or 4000)
    max_chars = int(args.get("max_chars") or 8000)

    if max_bytes <= 0:
        max_bytes = 0
    max_bytes = min(max_bytes, 2_000_000)

    if max_chars <= 0:
        max_chars = 0
    max_chars = min(max_chars, 200_000)

    ua = str(args.get("user_agent") or "") or "curl/7.79.1"

    print("[url] " + url, file=sys.stderr)

    req = Request(url, headers={"User-Agent": ua})

    def do_request(unverified: bool = False):
        # Keep it minimal; caller environment is responsible for SSL config.
        return urlopen(req)

    def _is_ssl_error(exc: Exception) -> bool:
        s = f"{type(exc).__name__}: {exc}".lower()
        return (
            "ssl" in s
            or "certificate verify failed" in s
            or "certificate" in s
            or "tls" in s
        )

    try:
        with do_request() as resp:
            declared = None
            try:
                declared = resp.headers.get_content_charset()  # type: ignore[attr-defined]
            except Exception:
                declared = None
            content = resp.read(max_bytes)

        text = _decode_bytes(content, declared_charset=declared)

        if extract == "head":
            return _truncate_chars(text, max_chars)

        if extract in ("text", "html"):
            soup = BeautifulSoup(text, "html.parser")
            el = _pick_html_element(soup, selector=selector)
            if extract == "text":
                extracted = el.get_text("\n", strip=True)
                return _truncate_chars(extracted, max_chars)
            extracted = str(el)
            return _truncate_chars(extracted, max_chars)

        if extract == "json":
            try:
                doc = json.loads(text)
            except Exception as e:
                return json.dumps(
                    {
                        "ok": False,
                        "error": f"json parse failed: {type(e).__name__}: {e}",
                    },
                    ensure_ascii=False,
                )

            if json_pointer:
                try:
                    doc = _json_pointer_get(doc, json_pointer)
                except Exception as e:
                    return json.dumps(
                        {
                            "ok": False,
                            "error": f"json_pointer failed: {type(e).__name__}: {e}",
                        },
                        ensure_ascii=False,
                    )

            return _truncate_chars(json.dumps(doc, ensure_ascii=False), max_chars)

        return json.dumps(
            {
                "ok": False,
                "error": f"invalid extract: {extract}",
            },
            ensure_ascii=False,
        )

    except Exception as e:
        msg = str(e)
        if _is_ssl_error(e):
            msg = "SSL error: " + msg
        return json.dumps(
            {
                "ok": False,
                "error": msg,
            },
            ensure_ascii=False,
        )
