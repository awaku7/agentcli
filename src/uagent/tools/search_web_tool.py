"""DuckDuckGo HTML interface wrapper for simple web search."""

from __future__ import annotations

import json
from ..env_utils import env_get
import random
import time
import traceback
from typing import Any, Optional
from urllib.parse import parse_qs, unquote, urlparse

import requests

from .i18n_helper import make_tool_translator
from .context import get_callbacks

_ = make_tool_translator(__file__)


def _emit_debug(message: str) -> None:
    cb = get_callbacks().debug
    if cb is not None:
        try:
            cb(message)
        except Exception:
            pass


def _emit_error(message: str) -> None:
    cb = get_callbacks().error
    if cb is not None:
        try:
            cb(message)
        except Exception:
            pass


def _emit_exception(message: str) -> None:
    cb = get_callbacks().exception
    if cb is not None:
        try:
            cb(message)
        except Exception:
            pass


# ------------------------------
# Configuration
# ------------------------------

DEFAULT_ENDPOINT = "https://html.duckduckgo.com/html/"
DEFAULT_TIMEOUT_SEC = 15
DEFAULT_MAX_RESULTS = 5
DEFAULT_RETRIES = 0
DEFAULT_PROXIES: Optional[dict[str, str]] = None


def _ssl_verify_setting() -> bool:
    v = env_get("DDG_SSL_VERIFY", "").strip().lower()
    if v in ("0", "false", "no", "off"):
        return False
    return True


def _default_headers() -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
    }


# ------------------------------
# Helpers
# ------------------------------


def _sleep_backoff(attempt: int) -> None:
    base = 0.8 * (2**attempt)
    jitter = random.uniform(0.0, 0.6)
    time.sleep(base + jitter)


def _extract_real_url(href: str) -> str:
    if not href:
        return href

    try:
        u = urlparse(href)
        qs = parse_qs(u.query)

        if "uddg" in qs and qs["uddg"]:
            return unquote(qs["uddg"][0])

        return href
    except Exception:
        return href


def _parse_results(html: str, max_results: int) -> list[dict[str, str]]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, str]] = []

    for card in soup.select("div.result"):
        a = card.select_one("a.result__a")
        if not a:
            continue

        title = a.get_text(strip=True) or ""
        href_any = a.get("href", "")
        href = "" if href_any is None else str(href_any)
        href = _extract_real_url(href)

        snip = ""
        snip_tag = card.select_one(".result__snippet")
        if snip_tag:
            snip = snip_tag.get_text(strip=True) or ""

        results.append({"title": title, "href": href, "text": snip})
        if len(results) >= max_results:
            break

    return results


# ------------------------------
# Core search
# ------------------------------


def _duckduckgo_search(
    query: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    endpoint: str = DEFAULT_ENDPOINT,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    retries: int = DEFAULT_RETRIES,
    proxies: Optional[dict[str, str]] = DEFAULT_PROXIES,
) -> list[dict[str, str]]:
    """Perform a DuckDuckGo search query."""

    _emit_debug(f"Performing DuckDuckGo search: {query}")

    params = {"q": query}
    headers = _default_headers()
    verify = _ssl_verify_setting()

    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            resp = requests.get(
                endpoint,
                params=params,
                headers=headers,
                timeout=timeout_sec,
                verify=verify,
                proxies=proxies,
                allow_redirects=True,
            )

            resp.raise_for_status()
            results = _parse_results(resp.text, max_results)

            if results:
                _emit_debug(f"Found {len(results)} results")
                return results

            _emit_debug(f"Parsed 0 results (attempt {attempt + 1}/{retries + 1}).")
            if attempt < retries:
                _sleep_backoff(attempt)
                continue
            return results

        except requests.RequestException as exc:
            last_exc = exc
            _emit_debug(
                f"DDG request failed (attempt {attempt + 1}/{retries + 1}): {exc}"
            )
            if attempt < retries:
                _sleep_backoff(attempt)
                continue
            break

    raise RuntimeError(
        _(
            "error.duckduckgo_failed_after_retries",
            default="DuckDuckGo request failed after retries: {error}",
        ).format(error=last_exc)
    )


def search_web(
    query: str, max_results: int = DEFAULT_MAX_RESULTS
) -> list[dict[str, str]]:
    return _duckduckgo_search(query=query, max_results=max_results)


# --- Tool registration ---

BUSY_LABEL = True
STATUS_LABEL = "tool:search_web"

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "external",
    "function": {
        "name": "search_web",
        "description": _(
            "tool.description",
            default="Search the web via DuckDuckGo HTML interface. Returns title/link/snippet.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "web search",
                "duckduckgo",
                "search internet",
                "ウェブ検索",
                "buscar en la web",
                "recherche web",
                "웹 검색",
                "поиск в вебе",
            ],
        ),
        "x_search_terms_en": [
            "web search",
            "duckduckgo",
            "search internet",
            "ウェブ検索",
            "buscar en la web",
            "recherche web",
            "웹 검색",
            "поиск в вебе",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": _(
                        "param.query.description",
                        default="Search query.",
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": _(
                        "param.limit.description",
                        default="Maximum number of results to return (default: 5).",
                    ),
                },
            },
            "required": ["query"],
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    try:
        if not isinstance(args, dict):
            return json.dumps(
                {"error": _("error.args_must_be_dict", default="args must be a dict")},
                ensure_ascii=False,
            )

        q = args.get("query") or args.get("q")
        if not q:
            return json.dumps(
                {
                    "error": _(
                        "error.missing_query_parameter",
                        default="missing 'query' parameter",
                    )
                },
                ensure_ascii=False,
            )

        n_raw = args.get("limit", args.get("n", DEFAULT_MAX_RESULTS))
        n: int
        if isinstance(n_raw, int):
            n = n_raw
        elif isinstance(n_raw, str):
            try:
                n = int(n_raw)
            except Exception:
                n = DEFAULT_MAX_RESULTS
        else:
            n = DEFAULT_MAX_RESULTS

        q_str = str(q)
        results = search_web(q_str, n)
        return json.dumps(
            {
                "query": q_str,
                "limit": n,
                "result_count": len(results),
                "results": results,
            },
            ensure_ascii=False,
        )

    except Exception as e:
        _emit_exception(
            _("error.run_tool_error", default="run_tool error: {error}").format(
                error=""
            )
            + "\n"
            + traceback.format_exc().rstrip()
        )
        return json.dumps(
            {
                "error": _(
                    "error.run_tool_error", default="run_tool error: {error}"
                ).format(error=str(e))
            },
            ensure_ascii=False,
        )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="DuckDuckGo web search wrapper")
    parser.add_argument("query", help="Search query string")
    parser.add_argument(
        "-n",
        "--number",
        type=int,
        default=DEFAULT_MAX_RESULTS,
        help="Max results (default: 5)",
    )
    args = parser.parse_args()

    try:
        results = search_web(args.query, args.number)
        print(json.dumps(results, ensure_ascii=False, indent=2))
    except RuntimeError as e:
        _emit_error(f"Search failed: {e}")
        raise RuntimeError(f"Search failed: {e}") from e


if __name__ == "__main__":
    if not _ssl_verify_setting():
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
