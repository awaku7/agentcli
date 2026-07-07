"""DuckDuckGo / Brave Search HTML interface wrapper for simple web search."""

from __future__ import annotations

import json
from ..env_utils import env_get
import random
import time
import traceback
from typing import Any, Optional
from urllib.parse import parse_qs, unquote, urlparse

import requests

import os
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

DG_ENDPOINT = "https://html.duckduckgo.com/html/"
BRAVE_ENDPOINT = "https://search.brave.com/search"
BRAVE_API_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
YAHOO_ENDPOINT = "https://search.yahoo.co.jp/search"
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


# ------------------------------
# DuckDuckGo parser
# ------------------------------


def _parse_ddg_results(html: str, max_results: int) -> list[dict[str, str]]:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        from .._pip_auto import install_with_status as _install_bs4
        _install_bs4("beautifulsoup4", "bs4")
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
# Brave Search parser
# ------------------------------


def _parse_brave_results(html: str, max_results: int) -> list[dict[str, str]]:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        from .._pip_auto import install_with_status as _install_bs4
        _install_bs4("beautifulsoup4", "bs4")
        from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, str]] = []

    for wrapper in soup.select(".result-wrapper"):
        a = wrapper.select_one(".title a")
        if not a:
            a = wrapper.select_one("a")
        if not a:
            continue
        title = a.get_text(strip=True) or ""
        href = a.get("href", "")
        if not href or href.startswith("/") or href.startswith("#"):
            continue
        desc_el = wrapper.select_one(".snippet")
        desc = desc_el.get_text(strip=True) if desc_el else ""
        results.append({"title": title, "href": str(href), "text": desc})
        if len(results) >= max_results:
            break

    return results


# ------------------------------
# DuckDuckGo search
# ------------------------------



def _parse_yahoo_results(html: str, max_results: int) -> list[dict[str, str]]:
    """Parse Yahoo Japan search results."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        from .._pip_auto import install_with_status as _install_bs4
        _install_bs4("beautifulsoup4", "bs4")
        from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, str]] = []
    for algo in soup.select(".Algo"):
        a = algo.select_one("a[href^=\"http\"]")
        if not a:
            continue
        href = str(a.get("href", ""))
        title_el = algo.select_one(".sw-Card__titleMain")
        title = title_el.get_text(strip=True) if title_el else ""
        desc_el = algo.select_one(".sw-Card__summary")
        desc = desc_el.get_text(strip=True) if desc_el else ""
        if title and href:
            results.append({"title": title, "href": href, "text": desc})
            if len(results) >= max_results:
                break
    return results


def _duckduckgo_search(
    query: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    retries: int = DEFAULT_RETRIES,
    proxies: Optional[dict[str, str]] = DEFAULT_PROXIES,
) -> list[dict[str, str]]:
    _emit_debug(f"Performing DuckDuckGo search: {query}")
    params = {"q": query}
    headers = _default_headers()
    verify = _ssl_verify_setting()

    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            resp = requests.get(
                DG_ENDPOINT,
                params=params,
                headers=headers,
                timeout=timeout_sec,
                verify=verify,
                proxies=proxies,
                allow_redirects=True,
            )
            resp.raise_for_status()
            results = _parse_ddg_results(resp.text, max_results)
            if results:
                _emit_debug(f"Found {len(results)} DDG results")
                return results
            _emit_debug(f"Parsed 0 DDG results (attempt {attempt + 1}/{retries + 1}).")
            if attempt < retries:
                _sleep_backoff(attempt)
                continue
            return results
        except requests.RequestException as exc:
            last_exc = exc
            _emit_debug(f"DDG request failed (attempt {attempt + 1}/{retries + 1}): {exc}")
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


# ------------------------------
# Brave Search
# ------------------------------


def _brave_api_search(
    query: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    api_key: str = "",
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    proxies: Optional[dict[str, str]] = DEFAULT_PROXIES,
) -> list[dict[str, str]]:
    """Brave Search API 経由で検索（UAGENT_BRAVE_API_KEY が必要）"""
    _emit_debug(f"Performing Brave API Search: {query}")
    params = {"q": query, "count": min(max_results, 20)}
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": api_key,
    }
    verify = _ssl_verify_setting()

    try:
        resp = requests.get(
            BRAVE_API_ENDPOINT,
            params=params,
            headers=headers,
            timeout=timeout_sec,
            verify=verify,
            proxies=proxies,
        )
        resp.raise_for_status()
        data = resp.json()
        web_results = data.get("web", {}).get("results", [])
        results = []
        for r in web_results[:max_results]:
            results.append({
                "title": r.get("title", ""),
                "href": r.get("url", ""),
                "text": r.get("description", ""),
            })
        _emit_debug(f"Found {len(results)} Brave API results")
        return results
    except Exception as exc:
        _emit_debug(f"Brave API request failed: {exc}")
        raise


def _brave_search(
    query: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    retries: int = DEFAULT_RETRIES,
    proxies: Optional[dict[str, str]] = DEFAULT_PROXIES,
) -> list[dict[str, str]]:
    """Brave Search: 環境変数 UAGENT_BRAVE_API_KEY があればAPI経由、なければHTMLスクレイピング"""
    api_key = os.environ.get("UAGENT_BRAVE_API_KEY", "").strip()
    if api_key:
        _emit_debug(f"Brave API key found, using API")
        try:
            return _brave_api_search(query, max_results, api_key, timeout_sec, proxies)
        except Exception as e:
            _emit_debug(f"Brave API failed ({e}), falling back to HTML scraping")

    _emit_debug(f"Performing Brave HTML search: {query}")
    params = {"q": query, "source": "web"}
    headers = _default_headers()
    verify = _ssl_verify_setting()

    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            resp = requests.get(
                BRAVE_ENDPOINT,
                params=params,
                headers=headers,
                timeout=timeout_sec,
                verify=verify,
                proxies=proxies,
                allow_redirects=True,
            )
            resp.raise_for_status()
            results = _parse_brave_results(resp.text, max_results)
            if results:
                _emit_debug(f"Found {len(results)} Brave HTML results")
                return results
            _emit_debug(f"Parsed 0 Brave HTML results (attempt {attempt + 1}/{retries + 1}).")
            if attempt < retries:
                _sleep_backoff(attempt)
                continue
            return results
        except requests.RequestException as exc:
            last_exc = exc
            _emit_debug(f"Brave HTML request failed (attempt {attempt + 1}/{retries + 1}): {exc}")
            if attempt < retries:
                _sleep_backoff(attempt)
                continue
            break

    # 429の場合はAPIキー設定を促す
    if last_exc and "429" in str(last_exc):
        raise RuntimeError(
            _(
                "error.brave_429_with_api_hint",
                default="Brave Search rate limited (429). Set environment variable UAGENT_BRAVE_API_KEY with a Brave Search API key (free tier available at https://brave.com/search/api/) to use the API instead of HTML scraping.",
            )
        )
    raise RuntimeError(
        _(
            "error.brave_failed_after_retries",
            default="Brave Search request failed after retries: {error}",
        ).format(error=last_exc)
    )



# ------------------------------
# Yahoo Japan Search
# ------------------------------


def _yahoo_search(
    query: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    retries: int = DEFAULT_RETRIES,
    proxies: Optional[dict[str, str]] = DEFAULT_PROXIES,
) -> list[dict[str, str]]:
    _emit_debug(f"Performing Yahoo Japan search: {query}")
    params = {"p": query, "ei": "UTF-8"}
    headers = _default_headers()
    verify = _ssl_verify_setting()

    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            resp = requests.get(
                YAHOO_ENDPOINT,
                params=params,
                headers=headers,
                timeout=timeout_sec,
                verify=verify,
                proxies=proxies,
                allow_redirects=True,
            )
            resp.raise_for_status()
            results = _parse_yahoo_results(resp.text, max_results)
            if results:
                _emit_debug(f"Found {len(results)} Yahoo results")
                return results
        except requests.RequestException as exc:
            last_exc = exc
            _emit_debug(f"Yahoo request failed: {exc}")
            if attempt < retries:
                _sleep_backoff(attempt)
                continue
            break

    raise RuntimeError(
        _("error.yahoo_failed", default="Yahoo Japan search request failed: {error}").format(error=last_exc)
    )


# ------------------------------
# Public API
# ------------------------------


def search_web(
    query: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    engine: str = "duckduckgo",
) -> list[dict[str, str]]:
    """Search the web using specified engine (duckduckgo, brave, or yahoo)."""
    if engine == "brave":
        return _brave_search(query=query, max_results=max_results)
    if engine == "yahoo":
        return _yahoo_search(query=query, max_results=max_results)
    return _duckduckgo_search(query=query, max_results=max_results)


# --- Tool registration ---

BUSY_LABEL = True
STATUS_LABEL = "tool:search_web"

TOOL_SPEC: dict[str, Any] = {
    "external_data": True,
    "type": "function",
    "x_parallel_safe": True,
    "tool_genre": "external",
    "function": {
        "name": "search_web",
        "description": _(
            "tool.description",
            default="Search the web via DuckDuckGo (default) or Brave Search HTML interface. Returns title/link/snippet. Brave Search is better for Japanese/local queries.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "web search",
                "duckduckgo",
                "brave search",
                "search internet",
                "ウェブ検索",
                "ネット検索",
            ],
        ),
        "x_search_terms_en": [
            "web search",
            "duckduckgo",
            "brave search",
            "search internet",
            "google",
            "browse",
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
                "engine": {
                    "type": "string",
                    "description": _(
                        "param.engine.description",
                        default="Search engine: 'duckduckgo' (default), 'brave', or 'yahoo'.",
                    ),
                    "enum": ["duckduckgo", "brave", "yahoo"],
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
                {"error": _("error.missing_query_parameter", default="missing 'query' parameter")},
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

        engine = args.get("engine", "duckduckgo")
        if engine not in ("duckduckgo", "brave", "yahoo"):
            engine = "duckduckgo"

        q_str = str(q)
        results = search_web(q_str, n, engine)
        return json.dumps(
            {
                "query": q_str,
                "engine": engine,
                "limit": n,
                "result_count": len(results),
                "results": results,
            },
            ensure_ascii=False,
        )

    except Exception as e:
        _emit_exception(
            _("error.run_tool_error", default="run_tool error: {error}").format(error="")
            + "\n"
            + traceback.format_exc().rstrip()
        )
        return json.dumps(
            {"error": _("error.run_tool_error", default="run_tool error: {error}").format(error=str(e))},
            ensure_ascii=False,
        )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Web search wrapper (DuckDuckGo / Brave)")
    parser.add_argument("query", help="Search query string")
    parser.add_argument("-n", "--number", type=int, default=DEFAULT_MAX_RESULTS, help="Max results (default: 5)")
    parser.add_argument("--engine", choices=["duckduckgo", "brave", "yahoo"], default="duckduckgo", help="Search engine (default: duckduckgo)")
    args = parser.parse_args()

    try:
        results = search_web(args.query, args.number, args.engine)
        print(json.dumps(results, ensure_ascii=False, indent=2))
    except RuntimeError as e:
        _emit_error(f"Search failed: {e}")
        raise RuntimeError(f"Search failed: {e}") from e


if __name__ == "__main__":
    if not _ssl_verify_setting():
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
