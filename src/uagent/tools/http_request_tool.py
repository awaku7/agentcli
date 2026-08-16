from __future__ import annotations

import base64
import json
import ssl
from http.client import HTTPMessage
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

TOOL_SPEC: dict[str, Any] = {
    "computer_use_conflict": True,
    "external_data": True,
    "type": "function",
    "tool_genre": "external",
    "tool_level": 1,
    "x_parallel_safe": False,
    "function": {
        "name": "http_request",
        "description": _(
            "tool.description",
            default=(
                "Send an HTTP request to a REST or HTTP API and return the status, headers, "
                "and response body. Supports JSON, form, and text request bodies. "
                "GET/HEAD/OPTIONS requests are read-only; write methods remain serial by default."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "HTTPリクエスト",
                "REST API",
                "APIリクエスト",
                "POST API",
                "PUT API",
                "PATCH API",
                "DELETE API",
                "HTTPクライアント",
                "Postman",
            ],
        ),
        "x_search_terms_en": [
            "http request",
            "REST API",
            "API request",
            "POST API",
            "PUT API",
            "PATCH API",
            "DELETE API",
            "HTTP client",
            "Postman",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "enum": [
                        "GET",
                        "POST",
                        "PUT",
                        "PATCH",
                        "DELETE",
                        "HEAD",
                        "OPTIONS",
                    ],
                    "default": "GET",
                    "description": _(
                        "param.method.description", default="HTTP method."
                    ),
                },
                "url": {
                    "type": "string",
                    "description": _(
                        "param.url.description", default="HTTP or HTTPS URL."
                    ),
                },
                "query": {
                    "type": "object",
                    "description": _(
                        "param.query.description", default="Query-string parameters."
                    ),
                },
                "headers": {
                    "type": "object",
                    "description": _(
                        "param.headers.description", default="Additional HTTP headers."
                    ),
                },
                "body": {
                    "description": _(
                        "param.body.description",
                        default="Request body. Objects and arrays are JSON-encoded; strings are sent as text.",
                    ),
                },
                "body_text": {
                    "type": "string",
                    "description": _(
                        "param.body_text.description",
                        default="Raw request body. Takes precedence over body.",
                    ),
                },
                "content_type": {
                    "type": "string",
                    "default": "application/json",
                    "description": _(
                        "param.content_type.description",
                        default="Content-Type for a supplied body.",
                    ),
                },
                "bearer_token": {
                    "type": "string",
                    "description": _(
                        "param.bearer_token.description",
                        default="Optional Bearer token.",
                    ),
                },
                "username": {
                    "type": "string",
                    "description": _(
                        "param.username.description",
                        default="Optional HTTP Basic-auth username.",
                    ),
                },
                "password": {
                    "type": "string",
                    "description": _(
                        "param.password.description",
                        default="Optional HTTP Basic-auth password.",
                    ),
                },
                "timeout": {
                    "type": "integer",
                    "default": 30,
                    "minimum": 1,
                    "maximum": 300,
                    "description": _(
                        "param.timeout.description",
                        default="Request timeout in seconds.",
                    ),
                },
                "max_bytes": {
                    "type": "integer",
                    "default": 2000000,
                    "minimum": 1,
                    "maximum": 10000000,
                    "description": _(
                        "param.max_bytes.description",
                        default="Maximum response size in bytes.",
                    ),
                },
                "ssl": {
                    "type": "boolean",
                    "default": True,
                    "description": _(
                        "param.ssl.description", default="Verify TLS certificates."
                    ),
                },
                "parse_json": {
                    "type": "boolean",
                    "default": False,
                    "description": _(
                        "param.parse_json.description",
                        default="Parse a JSON response into response_json when possible.",
                    ),
                },
            },
            "required": ["url"],
        },
    },
}


class _RedirectHandler(HTTPRedirectHandler):
    max_redirections = 5


def _query_url(url: str, query: Any) -> str:
    if not query:
        return url
    if not isinstance(query, dict):
        raise ValueError("query must be an object")
    parts = urlsplit(url)
    existing = parts.query
    extra: list[tuple[str, str]] = []
    for key, value in query.items():
        if isinstance(value, (list, tuple)):
            extra.extend((str(key), str(item)) for item in value)
        else:
            extra.append((str(key), str(value)))
    combined = "&".join(item for item in (existing, urlencode(extra)) if item)
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, combined, parts.fragment)
    )


def _header_dict(headers: HTTPMessage | None) -> dict[str, str]:
    if headers is None:
        return {}
    return {str(k): str(v) for k, v in headers.items()}


def run_tool(args: dict[str, Any]) -> str:
    method = str(args.get("method") or "GET").upper()
    allowed = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
    if method not in allowed:
        raise ValueError(f"unsupported HTTP method: {method}")

    url = _query_url(str(args.get("url") or ""), args.get("query"))
    if not url.startswith(("http://", "https://")):
        raise ValueError("url must start with http:// or https://")

    headers_arg = args.get("headers") or {}
    if not isinstance(headers_arg, dict):
        raise ValueError("headers must be an object")
    headers = {str(k): str(v) for k, v in headers_arg.items()}
    headers.setdefault("User-Agent", "uagent-http-request/1.0")

    bearer = str(args.get("bearer_token") or "")
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"

    username = args.get("username")
    password = args.get("password")
    if username is not None or password is not None:
        raw = f"{username or ''}:{password or ''}".encode("utf-8")
        headers["Authorization"] = "Basic " + base64.b64encode(raw).decode("ascii")

    body_value = args.get("body")
    body_text = args.get("body_text")
    data: bytes | None = None
    if body_text is not None:
        data = str(body_text).encode("utf-8")
    elif body_value is not None:
        if isinstance(body_value, (dict, list)):
            data = json.dumps(body_value, ensure_ascii=False).encode("utf-8")
        elif isinstance(body_value, bool):
            data = ("true" if body_value else "false").encode("utf-8")
        else:
            data = str(body_value).encode("utf-8")

    if data is not None:
        headers.setdefault(
            "Content-Type", str(args.get("content_type") or "application/json")
        )

    request = Request(url, data=data, headers=headers, method=method)
    verify_ssl = args.get("ssl", True)
    if not isinstance(verify_ssl, bool):
        verify_ssl = str(verify_ssl).lower() in {"1", "true", "yes", "on"}
    context = None
    if url.startswith("https://") and not verify_ssl:
        context = ssl._create_unverified_context()

    timeout = max(1, min(int(args.get("timeout") or 30), 300))
    max_bytes = max(1, min(int(args.get("max_bytes") or 2_000_000), 10_000_000))
    handlers: list[Any] = [_RedirectHandler]
    if context is not None:
        handlers.append(HTTPSHandler(context=context))
    opener = build_opener(*handlers)

    try:
        response = opener.open(request, timeout=timeout)
        with response:
            raw = response.read(max_bytes + 1)
            truncated = len(raw) > max_bytes
            raw = raw[:max_bytes]
            response_headers = _header_dict(getattr(response, "headers", None))
            charset = getattr(
                getattr(response, "headers", None), "get_content_charset", lambda: None
            )()
            try:
                text = raw.decode(charset or "utf-8", errors="replace")
            except Exception:
                text = raw.decode("latin-1", errors="replace")
            result: dict[str, Any] = {
                "ok": True,
                "status_code": int(getattr(response, "status", 200)),
                "url": str(getattr(response, "url", url)),
                "headers": response_headers,
                "body": text,
                "truncated": truncated,
            }
            if args.get("parse_json"):
                try:
                    result["response_json"] = json.loads(text)
                except Exception as exc:
                    result["json_error"] = f"{type(exc).__name__}: {exc}"
            return json.dumps(result, ensure_ascii=False)
    except HTTPError as exc:
        raw = exc.read(max_bytes)
        text = raw.decode("utf-8", errors="replace")
        return json.dumps(
            {
                "ok": False,
                "status_code": exc.code,
                "url": url,
                "headers": _header_dict(exc.headers),
                "body": text,
                "error": str(exc.reason),
            },
            ensure_ascii=False,
        )
    except (URLError, TimeoutError, ValueError) as exc:
        return json.dumps(
            {"ok": False, "url": url, "error": f"{type(exc).__name__}: {exc}"},
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps(
            {"ok": False, "url": url, "error": f"{type(exc).__name__}: {exc}"},
            ensure_ascii=False,
        )
