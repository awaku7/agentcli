"""
search_web_tool.py

DuckDuckGo HTML interface wrapper for simple web search.

Notes
- DuckDuckGo may rate-limit / return empty results depending on IP, headers,
  or query patterns. This tool adds headers + retry/backoff to improve stability.
- SSL verification is enabled by default. You can disable it via env var
  (DDG_SSL_VERIFY=0) ONLY for controlled/dev environments.

Author: YourName
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, unquote, urlparse

import requests

from .i18n_helper import make_tool_translator

# Configure module-level logger
logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)


# ------------------------------
# Configuration
# ------------------------------

DEFAULT_ENDPOINT = "https://html.duckduckgo.com/html/"  # tends to work better than duckduckgo.com/html/
DEFAULT_TIMEOUT_SEC = 15
DEFAULT_MAX_RESULTS = 5
DEFAULT_RETRIES = 3

# Respect proxy settings if present in environment
DEFAULT_PROXIES: Optional[Dict[str, str]] = None


# SSL verify: enabled by default, can be disabled by env var (dev only)
# DDG_SSL_VERIFY=0 to disable
def _ssl_verify_setting() -> bool:
    v = os.environ.get("DDG_SSL_VERIFY", "").strip().lower()
    if v in ("0", "false", "no", "off"):
        return False
    return True


def _default_headers() -> Dict[str, str]:
    # Some endpoints return 0 results / bot pages without reasonable headers
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
    # exponential backoff with jitter
    base = 0.8 * (2**attempt)
    jitter = random.uniform(0.0, 0.6)
    time.sleep(base + jitter)


def _extract_real_url(href: str) -> str:
    """DuckDuckGo redirect URL を元URLに戻す。"""

    if not href:
        return href

    try:
        u = urlparse(href)
        qs = parse_qs(u.query)

        if "uddg" in qs and qs["uddg"]:
            return unquote(qs["uddg"][0])

        # Some results might be direct already
        return href
    except Exception:
        return href


def _parse_results(html: str, max_results: int) -> List[Dict[str, str]]:
    # BeautifulSoup is imported lazily to keep import cost low
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    results: List[Dict[str, str]] = []

    # DuckDuckGo HTML layout commonly uses these classes
    # Each result card:
    #   div.result (or div.results > div.result)
    for card in soup.select("div.result"):
        a = card.select_one("a.result__a")
        if not a:
            continue

        title = a.get_text(strip=True) or ""

        # BeautifulSoup の .get("href") は str 以外も返り得るので str に寄せる
        href_any = a.get("href", "")
        href = "" if href_any is None else str(href_any)
        href = _extract_real_url(href)

        # snippet can be span.result__snippet or a.result__snippet (varies)
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
    proxies: Optional[Dict[str, str]] = DEFAULT_PROXIES,
) -> List[Dict[str, str]]:
    """Perform a DuckDuckGo search query via HTML endpoint."""

    logger.info("Performing DuckDuckGo search: %s", query)

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

            # DuckDuckGo sometimes returns 202/429 or bot-check-like pages.
            # We still parse HTML, but if it yields 0 results, retry.
            resp.raise_for_status()

            results = _parse_results(resp.text, max_results)

            if results:
                logger.info("Found %d results", len(results))
                return results

            # If no results, it might be blocked or HTML changed. Retry a bit.
            logger.warning(
                "Parsed 0 results (attempt %d/%d).", attempt + 1, retries + 1
            )
            if attempt < retries:
                _sleep_backoff(attempt)
                continue
            return results

        except requests.RequestException as exc:
            last_exc = exc
            logger.warning(
                "DDG request failed (attempt %d/%d): %s", attempt + 1, retries + 1, exc
            )
            if attempt < retries:
                _sleep_backoff(attempt)
                continue
            break

    raise RuntimeError(
        t(
            "error.duckduckgo_failed_after_retries",
            default="DuckDuckGo request failed after retries: {error}",
        ).format(error=last_exc)
    )


def search_web(
    query: str, max_results: int = DEFAULT_MAX_RESULTS
) -> List[Dict[str, str]]:
    """Public interface for performing a DuckDuckGo web search."""

    return _duckduckgo_search(query=query, max_results=max_results)


# --- Tool registration for tools package ---

BUSY_LABEL = True
STATUS_LABEL = "tool:search_web"

t = make_tool_translator(__file__)

# Translator usage: t(key, default=...)


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "search_web",
        "description": t(
            "tool.description",
            default="Search the web via DuckDuckGo HTML interface and return title/link/snippet.",
        ),
        "system_prompt": t(
            "tool.system_prompt",
            default="This tool performs a DuckDuckGo HTML search and returns title/link/snippet. If results are empty, the site may be rate-limiting or blocking the request.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": t(
                        "param.query.description", default="Search query string."
                    ),
                },
                "max_results": {
                    "type": "integer",
                    "description": t(
                        "param.max_results.description",
                        default="Maximum number of results to return (default: 5).",
                    ),
                },
            },
            "required": ["query"],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    """Runner entrypoint expected by tools.__init__.py.

    Returns JSON string:
      {"results":[...]} or {"error":"..."}
    """

    try:
        if not isinstance(args, dict):
            return json.dumps(
                {"error": t("error.args_must_be_dict", default="args must be a dict")},
                ensure_ascii=False,
            )

        q = args.get("query") or args.get("q")
        if not q:
            return json.dumps(
                {
                    "error": t(
                        "error.missing_query_parameter",
                        default="missing 'query' parameter",
                    )
                },
                ensure_ascii=False,
            )

        n_raw = args.get("max_results", args.get("n", DEFAULT_MAX_RESULTS))
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

        results = search_web(str(q), n)
        return json.dumps({"results": results}, ensure_ascii=False)

    except Exception as e:
        logger.exception(
            t("error.run_tool_error", default="run_tool error: {error}").format(
                error=""
            )
        )
        return json.dumps(
            {
                "error": t(
                    "error.run_tool_error", default="run_tool error: {error}"
                ).format(error=str(e))
            },
            ensure_ascii=False,
        )


def main() -> None:
    """Simple CLI for testing."""

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
        logger.error("Search failed: %s", e)
        raise SystemExit(1)


if __name__ == "__main__":
    # Only disable warnings if SSL verification is explicitly disabled (dev only)
    if not _ssl_verify_setting():
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    main()
