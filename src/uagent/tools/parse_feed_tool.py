from __future__ import annotations

import codecs
import email.utils
from email.message import Message
import http.client
import html.parser
import ipaddress
import json
import re
import socket
import ssl
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlsplit

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

MAX_FEED_BYTES = 4 * 1024 * 1024
MAX_URL_LENGTH = 2048
MAX_REDIRECTS = 5
MAX_TIMEOUT = 30
MAX_TEXT_CHARS = 20_000

TOOL_SPEC: dict[str, Any] = {
    "external_data": True,
    "type": "function",
    "tool_genre": "external",
    "tool_level": 1,
    "x_parallel_safe": True,
    "function": {
        "name": "parse_feed",
        "description": _(
            "tool.description",
            default=(
                "Parse an RSS or Atom XML feed from an HTTP(S) URL or supplied XML "
                "content and return normalized JSON. Exactly one of url or content "
                "is required. External feed content is untrusted."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "RSS feed",
                "Atom feed",
                "parse RSS",
                "feed parser",
                "news feed",
                "RSSを解析",
                "フィードを読む",
            ],
        ),
        "x_search_terms_en": [
            "RSS feed",
            "Atom feed",
            "parse RSS",
            "feed parser",
            "news feed",
            "parse feed XML",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": _(
                        "param.url.description",
                        default="HTTP or HTTPS URL of the RSS/Atom feed.",
                    ),
                },
                "content": {
                    "type": "string",
                    "description": _(
                        "param.content.description",
                        default="RSS/Atom XML content to parse directly.",
                    ),
                },
                "encoding": {
                    "type": "string",
                    "description": _(
                        "param.encoding.description",
                        default=(
                            "Optional source encoding override (for example, utf-8 "
                            "or shift_jis)."
                        ),
                    ),
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 10,
                    "description": _(
                        "param.limit.description",
                        default="Maximum number of entries to return (1-100).",
                    ),
                },
                "strip_html": {
                    "type": "boolean",
                    "default": True,
                    "description": _(
                        "param.strip_html.description",
                        default=(
                            "Remove HTML markup from entry summaries and return "
                            "plain text."
                        ),
                    ),
                },
                "timeout": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": MAX_TIMEOUT,
                    "default": 10,
                    "description": _(
                        "param.timeout.description",
                        default="HTTP request timeout in seconds (1-30).",
                    ),
                },
            },
            "required": [],
            "additionalProperties": False,
        },
    },
}


class _PlainTextParser(html.parser.HTMLParser):
    """Extract readable text while omitting markup, comments, scripts and styles."""

    _BLOCK_TAGS = frozenset(
        {
            "address",
            "article",
            "blockquote",
            "br",
            "div",
            "dl",
            "fieldset",
            "figcaption",
            "figure",
            "footer",
            "form",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "header",
            "hr",
            "li",
            "main",
            "nav",
            "ol",
            "p",
            "pre",
            "section",
            "table",
            "td",
            "th",
            "tr",
            "ul",
        }
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style"}:
            self._skip_depth += 1
        elif not self._skip_depth and tag.lower() in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1
        elif not self._skip_depth and lowered in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)


def _plain_text(value: str) -> str:
    parser = _PlainTextParser()
    try:
        parser.feed(value)
        parser.close()
        text = "".join(parser.parts)
    except Exception:
        # Malformed HTML should not prevent an otherwise useful feed parse.
        text = re.sub(r"<[^>]*>", " ", value)
    text = re.sub(r"[\t\r\f\v ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()[:MAX_TEXT_CHARS]


def _text(
    value: Any, *, strip_html: bool = False, max_chars: int = MAX_TEXT_CHARS
) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        value = value.get("value") or value.get("name") or value.get("term")
    if isinstance(value, (list, tuple)):
        value = ", ".join(str(item) for item in value if item is not None)
    result = str(value).strip()
    if not result:
        return None
    if strip_html:
        result = _plain_text(result)
    return result[:max_chars] or None


def _normalize_language(value: Any) -> str | None:
    raw = _text(value, max_chars=128)
    if raw is None:
        return None
    tag = raw.replace("_", "-").strip()
    if not re.fullmatch(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*", tag):
        return None
    return tag.lower()


def _parse_datetime(value: Any, parsed_value: Any = None) -> str | None:
    raw = _text(value, max_chars=256)
    parsed: datetime | None = None
    if raw:
        candidate = raw.strip()
        if candidate.endswith(("Z", "z")):
            candidate = candidate[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            try:
                parsed = email.utils.parsedate_to_datetime(raw)
            except (TypeError, ValueError, OverflowError):
                parsed = None
        if parsed is None:
            japanese = re.fullmatch(
                r"\s*(\d{4})年(\d{1,2})月(\d{1,2})日"
                r"(?:\s*(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?\s*",
                raw,
            )
            if japanese:
                groups = [
                    int(part) if part is not None else 0 for part in japanese.groups()
                ]
                try:
                    parsed = datetime(
                        groups[0], groups[1], groups[2], groups[3], groups[4], groups[5]
                    )
                except ValueError:
                    parsed = None

    if parsed is None and parsed_value is not None:
        try:
            parts = tuple(parsed_value)
            parsed = datetime(*parts[:6], tzinfo=timezone.utc)
        except (TypeError, ValueError, OverflowError):
            parsed = None
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat()


def _validate_public_url(url: str) -> tuple[str, int, list[str]]:
    if not isinstance(url, str) or not url or len(url) > MAX_URL_LENGTH:
        raise ValueError(
            f"url must be a non-empty string no longer than {MAX_URL_LENGTH} characters"
        )
    if any(ord(char) < 0x20 or char.isspace() for char in url):
        raise ValueError("url must not contain whitespace or control characters")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise ValueError(f"invalid URL: {exc}") from exc
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ValueError("url must be an absolute HTTP or HTTPS URL")
    if parts.username is not None or parts.password is not None:
        raise ValueError("URL credentials are not allowed")
    host = parts.hostname.rstrip(".")
    if not host or "%" in host:
        raise ValueError("invalid URL hostname")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        try:
            host = host.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise ValueError("invalid internationalized URL hostname") from exc
    if port == 0:
        raise ValueError("URL port must be between 1 and 65535")
    port = port or (443 if parts.scheme.lower() == "https" else 80)

    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            records = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise ValueError(f"could not resolve feed host: {exc}") from exc
        addresses = []
        for record in records:
            address_text = str(record[4][0]).split("%", 1)[0]
            try:
                addresses.append(ipaddress.ip_address(address_text))
            except ValueError as exc:
                raise ValueError("feed host resolved to an invalid IP address") from exc
    if not addresses:
        raise ValueError("feed host did not resolve to an IP address")
    if any(not address.is_global for address in addresses):
        raise ValueError("feed URL must resolve only to public IP addresses")
    pinned_addresses = list(dict.fromkeys(str(address) for address in addresses))
    return host, port, pinned_addresses


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, port: int, address: str, timeout: int) -> None:
        super().__init__(host, port, timeout=timeout)
        self._pinned_address = address

    def connect(self) -> None:
        self.sock = socket.create_connection(
            (self._pinned_address, self.port), self.timeout
        )


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, port: int, address: str, timeout: int) -> None:
        super().__init__(
            host, port, timeout=timeout, context=ssl.create_default_context()
        )
        self._pinned_address = address

    def connect(self) -> None:
        raw_socket = socket.create_connection(
            (self._pinned_address, self.port), self.timeout
        )
        try:
            self.sock = self._context.wrap_socket(
                raw_socket, server_hostname=self.host.strip("[]")
            )
        except Exception:
            raw_socket.close()
            raise


def _fetch_url(url: str, timeout: int) -> tuple[bytes, dict[str, str]]:
    current_url = url
    redirect_codes = {301, 302, 303, 307, 308}
    request_headers = {
        "User-Agent": "uag-parse-feed/1.0",
        "Accept": "application/atom+xml, application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.1",
        "Accept-Encoding": "identity",
    }

    for redirect_count in range(MAX_REDIRECTS + 1):
        host, port, addresses = _validate_public_url(current_url)
        parts = urlsplit(current_url)
        request_target = parts.path or "/"
        if parts.query:
            request_target += "?" + parts.query
        connection_type = (
            _PinnedHTTPSConnection
            if parts.scheme.lower() == "https"
            else _PinnedHTTPConnection
        )
        connection_host = f"[{host}]" if ":" in host else host
        connection: http.client.HTTPConnection | None = None
        last_error: OSError | None = None
        response: http.client.HTTPResponse | None = None
        for address in addresses:
            connection = connection_type(connection_host, port, address, timeout)
            try:
                connection.request("GET", request_target, headers=request_headers)
                response = connection.getresponse()
                break
            except OSError as exc:
                last_error = exc
                connection.close()
                connection = None
        if response is None or connection is None:
            raise ValueError(
                f"feed request failed: {last_error or 'connection failed'}"
            )

        try:
            if response.status in redirect_codes:
                location = response.getheader("Location")
                if not location:
                    raise ValueError(
                        f"feed server returned HTTP status {response.status} without a Location header"
                    )
                if redirect_count >= MAX_REDIRECTS:
                    raise ValueError(f"too many redirects (maximum {MAX_REDIRECTS})")
                target_url = urljoin(current_url, location)
                if (
                    parts.scheme.lower() == "https"
                    and urlsplit(target_url).scheme.lower() != "https"
                ):
                    raise ValueError("HTTPS feed redirects may not downgrade to HTTP")
                _validate_public_url(target_url)
                current_url = target_url
                continue
            if response.status < 200 or response.status >= 300:
                raise ValueError(f"feed server returned HTTP status {response.status}")
            length = response.getheader("Content-Length")
            if length:
                try:
                    declared_length = int(length)
                except ValueError:
                    declared_length = 0
                if declared_length > MAX_FEED_BYTES:
                    raise ValueError(
                        f"feed response exceeds {MAX_FEED_BYTES} byte limit"
                    )
            payload = response.read(MAX_FEED_BYTES + 1)
            if len(payload) > MAX_FEED_BYTES:
                raise ValueError(f"feed response exceeds {MAX_FEED_BYTES} byte limit")
            response_headers = {
                key.lower(): value for key, value in response.getheaders()
            }
            return payload, response_headers
        finally:
            connection.close()
    raise ValueError(f"too many redirects (maximum {MAX_REDIRECTS})")


def _load_feedparser() -> Any:
    try:
        import feedparser

        return feedparser
    except ImportError:
        from .._pip_auto import install_with_status

        if not install_with_status("feedparser", "feedparser", version_spec=">=6.0.11"):
            raise ModuleNotFoundError("feedparser is required to parse RSS/Atom feeds")
        import importlib

        return importlib.import_module("feedparser")


def _feed_type(version: Any) -> str:
    value = str(version or "").lower().replace(" ", "")
    if value.startswith("atom"):
        return "atom"
    if value.startswith("rss10") or value.startswith("rss1"):
        return "rss1.0"
    if value.startswith(("rss090", "rss091", "rss092", "rss093", "rss094", "rss09")):
        return "rss0.9"
    if value.startswith("rss"):
        return "rss2.0"
    return "unknown"


def _first(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _link(value: Any, link_detail: Any = None) -> str | None:
    if isinstance(link_detail, list):
        for item in link_detail:
            if isinstance(item, dict) and item.get("rel", "alternate") == "alternate":
                candidate = _text(item.get("href"), max_chars=4096)
                if candidate:
                    return candidate
        for item in link_detail:
            if isinstance(item, dict):
                candidate = _text(item.get("href"), max_chars=4096)
                if candidate:
                    return candidate
    return _text(value, max_chars=4096)


def _entry_content(entry: Any, strip_html: bool) -> str | None:
    if not isinstance(entry, dict):
        return None
    content = entry.get("content")
    if isinstance(content, list):
        for item in content:
            value = item.get("value") if isinstance(item, dict) else item
            result = _text(value, strip_html=strip_html)
            if result:
                return result
    value = _first(entry.get("summary"), entry.get("description"))
    return _text(value, strip_html=strip_html)


def _normalize_entry(
    entry: Any, *, strip_html: bool, xml_language: str | None = None
) -> dict[str, Any]:
    if not isinstance(entry, dict):
        entry = {}
    author_detail = entry.get("author_detail")
    author = None
    if isinstance(author_detail, dict):
        author = _first(author_detail.get("name"), author_detail.get("email"))
    author = _text(_first(author, entry.get("author")), max_chars=2000)
    tags = entry.get("tags")
    categories: list[str] = []
    if isinstance(tags, list):
        for tag in tags:
            term = _text(
                tag.get("term") or tag.get("label") if isinstance(tag, dict) else tag,
                max_chars=500,
            )
            if term and term not in categories:
                categories.append(term)
            if len(categories) >= 100:
                break

    published = _first(entry.get("published"), entry.get("pubdate"), entry.get("date"))
    updated = entry.get("updated")
    if published is None and updated is not None:
        published = updated
    return {
        "id": _text(
            _first(entry.get("id"), entry.get("guid"), entry.get("link")),
            max_chars=4096,
        ),
        "title": _text(entry.get("title"), strip_html=strip_html, max_chars=4000),
        "link": _link(entry.get("link"), entry.get("links")),
        "language": _normalize_language(
            _first(entry.get("language"), entry.get("xml:lang"), xml_language)
        ),
        "published_at": _parse_datetime(
            published, entry.get("published_parsed") or entry.get("updated_parsed")
        ),
        "updated_at": _parse_datetime(updated, entry.get("updated_parsed")),
        "summary": _entry_content(entry, strip_html),
        "author": author,
        "categories": categories,
    }


def _has_doctype(payload: bytes) -> bool:
    """Detect DTD declarations in common XML byte encodings before parsing."""
    declaration = re.compile(r"<!\s*DOCTYPE\b", flags=re.IGNORECASE)
    for encoding in ("utf-8", "utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be"):
        text = payload.decode(encoding, errors="ignore")
        if declaration.search(text):
            return True
    return False


def _xml_encoding_info(content: str) -> tuple[str, int, int] | None:
    """Read the encoding name and value span from a short XML declaration."""
    start = 1 if content.startswith("\ufeff<?xml") else 0
    if not content.startswith("<?xml", start):
        return None
    declaration_end = content.find("?>", start, min(len(content), 512))
    if declaration_end < 0:
        return None
    lower = content.lower()
    position = lower.find("encoding", start, declaration_end)
    if position < 0 or (position > start and not content[position - 1].isspace()):
        return None
    position += len("encoding")
    while position < declaration_end and content[position].isspace():
        position += 1
    if position >= declaration_end or content[position] != "=":
        return None
    position += 1
    while position < declaration_end and content[position].isspace():
        position += 1
    if position >= declaration_end or content[position] not in {"'", '"'}:
        return None
    quote = content[position]
    value_start = position + 1
    value_end = content.find(quote, value_start, declaration_end)
    if value_end < 0:
        return None
    return content[value_start:value_end], value_start, value_end


def _error(message: str) -> str:
    return json.dumps({"ok": False, "error": message}, ensure_ascii=False)


def run_tool(args: dict[str, Any]) -> str:
    """Fetch or parse one RSS/Atom feed and return its normalized representation."""
    if not isinstance(args, dict):
        return _error("arguments must be an object")

    url = args.get("url")
    content = args.get("content")
    has_url = isinstance(url, str) and bool(url.strip())
    has_content = isinstance(content, str)
    if has_url == has_content:
        return _error("provide exactly one of url or content")
    if url is not None and not has_url:
        return _error("url must be a non-empty string")
    if content is not None and not has_content:
        return _error("content must be a string")

    limit = args.get("limit", 10)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        return _error("limit must be an integer between 1 and 100")
    timeout = args.get("timeout", 10)
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, int)
        or not 1 <= timeout <= MAX_TIMEOUT
    ):
        return _error(f"timeout must be an integer between 1 and {MAX_TIMEOUT}")
    strip_html = args.get("strip_html", True)
    if not isinstance(strip_html, bool):
        return _error("strip_html must be a boolean")

    encoding = args.get("encoding")
    if encoding is not None:
        if not isinstance(encoding, str) or not encoding.strip():
            return _error("encoding must be a non-empty string when supplied")
        encoding = encoding.strip()
        try:
            codecs.lookup(encoding)
        except LookupError:
            return _error(f"unknown encoding: {encoding}")

    try:
        if has_url:
            source_payload, response_headers = _fetch_url(url.strip(), timeout)
            if len(source_payload) > MAX_FEED_BYTES:
                return _error(f"feed response exceeds {MAX_FEED_BYTES} byte limit")
            if _has_doctype(source_payload):
                return _error("DOCTYPE declarations are not allowed in feed content")
            source_text, source_encoding = _decode_source_payload(
                source_payload, response_headers, encoding
            )
        else:
            if len(content) > MAX_FEED_BYTES:
                return _error(f"feed content exceeds {MAX_FEED_BYTES} byte limit")
            declaration = _xml_encoding_info(content)
            source_encoding = encoding or (declaration[0] if declaration else "utf-8")
            try:
                source_encoding = codecs.lookup(source_encoding).name
            except LookupError:
                source_encoding = "utf-8"
            source_text = content

        payload = _utf8_xml_payload(source_text)
        if len(payload) > MAX_FEED_BYTES:
            return _error(f"feed content exceeds {MAX_FEED_BYTES} byte limit")
        if _has_doctype(payload):
            return _error("DOCTYPE declarations are not allowed in feed content")
        parser_headers = {"content-type": "application/xml; charset=utf-8"}
        parsed = _load_feedparser().parse(payload, response_headers=parser_headers)
        xml_language, xml_entry_languages = _xml_language_metadata(payload)
        normalized = _normalize_feed(
            parsed,
            limit=limit,
            strip_html=strip_html,
            encoding=source_encoding,
            xml_language=xml_language,
            xml_entry_languages=xml_entry_languages,
        )
        return json.dumps(normalized, ensure_ascii=False)
    except Exception as exc:
        return _error(f"{type(exc).__name__}: {exc}")


def _xml_declared_encoding(payload: bytes) -> str | None:
    prefix_encoding = _bom_encoding(payload) or "ascii"
    prefix = payload[:512].decode(prefix_encoding, errors="ignore")
    declaration = _xml_encoding_info(prefix)
    return declaration[0] if declaration else None


def _content_type_charset(headers: dict[str, str]) -> str | None:
    message = Message()
    message["content-type"] = headers.get("content-type", "")
    return message.get_content_charset()


def _detect_source_encoding(payload: bytes) -> str:
    try:
        from charset_normalizer import from_bytes
    except ImportError:
        from .._pip_auto import install_with_status

        if not install_with_status(
            "charset-normalizer", "charset_normalizer", version_spec=">=3.0.0"
        ):
            return "latin-1"
        from charset_normalizer import from_bytes

    match = from_bytes(payload).best()
    return match.encoding if match is not None and match.encoding else "latin-1"


def _decode_source_payload(
    payload: bytes, headers: dict[str, str], override: str | None
) -> tuple[str, str]:
    candidates = (
        [override, _content_type_charset(headers)]
        if override
        else [_content_type_charset(headers)]
    )
    candidates.extend((_bom_encoding(payload), _xml_declared_encoding(payload)))
    selected = None
    for candidate in candidates:
        if not candidate:
            continue
        try:
            selected = codecs.lookup(candidate).name
            break
        except LookupError:
            continue
    if selected is None:
        try:
            payload.decode("utf-8")
            selected = "utf-8"
        except UnicodeDecodeError:
            selected = _detect_source_encoding(payload)
            try:
                selected = codecs.lookup(selected).name
            except LookupError:
                selected = "latin-1"
    return payload.decode(selected, errors="replace"), selected


def _bom_encoding(payload: bytes) -> str | None:
    if payload.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
        return "utf-32"
    if payload.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return "utf-16"
    if payload.startswith(codecs.BOM_UTF8):
        return "utf-8-sig"
    if payload.startswith(bytes((0, 0, 0, 60))):
        return "utf-32-be"
    if payload.startswith(bytes((60, 0, 0, 0))):
        return "utf-32-le"
    if payload.startswith(bytes((0, 60, 0, 63))):
        return "utf-16-be"
    if payload.startswith(bytes((60, 0, 63, 0))):
        return "utf-16-le"
    return None


def _utf8_xml_payload(text: str) -> bytes:
    declaration = _xml_encoding_info(text)
    if declaration:
        text = text[: declaration[1]] + "utf-8" + text[declaration[2] :]
    return text.encode("utf-8")


def _xml_language_metadata(payload: bytes) -> tuple[str | None, list[str | None]]:
    """Extract inherited xml:lang values which feedparser does not expose."""
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return None, []

    xml_lang = "{http://www.w3.org/XML/1998/namespace}lang"

    def local_name(element: ET.Element) -> str:
        return element.tag.rsplit("}", 1)[-1].split(":")[-1].lower()

    root_language = root.attrib.get(xml_lang)
    if local_name(root) in {"rss", "rdf"}:
        for element in root.iter():
            if local_name(element) == "channel" and element.attrib.get(xml_lang):
                root_language = element.attrib[xml_lang]
                break

    entry_languages: list[str | None] = []

    def visit(element: ET.Element, inherited_language: str | None) -> None:
        language = element.attrib.get(xml_lang) or inherited_language
        if local_name(element) in {"item", "entry"}:
            entry_languages.append(language)
        for child in element:
            visit(child, language)

    visit(root, None)
    return root_language, entry_languages


def _normalize_feed(
    parsed: Any,
    *,
    limit: int,
    strip_html: bool,
    encoding: str | None,
    xml_language: str | None = None,
    xml_entry_languages: list[str | None] | None = None,
) -> dict[str, Any]:
    if not isinstance(parsed, dict):
        return {"ok": False, "error": "feed parser returned an invalid result"}
    feed = parsed.get("feed")
    if not isinstance(feed, dict):
        feed = {}
    entries = parsed.get("entries")
    if not isinstance(entries, list):
        entries = []

    title = _text(feed.get("title"), max_chars=4000)
    description = _text(
        _first(feed.get("subtitle"), feed.get("description")),
        strip_html=strip_html,
        max_chars=MAX_TEXT_CHARS,
    )
    feed_lang = _normalize_language(
        _first(
            feed.get("language"),
            feed.get("xml:lang"),
            feed.get("dc_language"),
            xml_language,
        )
    )
    feed_updated = _first(feed.get("updated"), feed.get("published"))
    detected_encoding = _text(_first(encoding, parsed.get("encoding")), max_chars=100)
    if detected_encoding:
        try:
            detected_encoding = (
                codecs.lookup(detected_encoding).name.replace("_", "-").lower()
            )
        except LookupError:
            detected_encoding = detected_encoding.lower()

    normalized_entries = [
        _normalize_entry(
            entry,
            strip_html=strip_html,
            xml_language=(
                xml_entry_languages[index]
                if xml_entry_languages is not None and index < len(xml_entry_languages)
                else None
            ),
        )
        for index, entry in enumerate(entries[:limit])
    ]
    bozo = bool(parsed.get("bozo", False))
    exception = parsed.get("bozo_exception")
    result: dict[str, Any] = {
        "ok": bool(feed or entries) or not bozo,
        "feed_type": _feed_type(parsed.get("version")),
        "title": title,
        "link": _link(feed.get("link"), feed.get("links")),
        "description": description,
        "language": feed_lang,
        "encoding": detected_encoding,
        "updated_at": _parse_datetime(
            feed_updated, feed.get("updated_parsed") or feed.get("published_parsed")
        ),
        "total_items": len(entries),
        "items": normalized_entries,
        "bozo": bozo,
    }
    if exception is not None:
        result["bozo_exception"] = f"{type(exception).__name__}: {exception}"[:500]
    if not result["ok"]:
        result["error"] = "The response could not be parsed as a feed."
    return result


__all__ = ["TOOL_SPEC", "run_tool"]
