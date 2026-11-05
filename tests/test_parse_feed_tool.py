from __future__ import annotations

import json

import pytest

from uagent.tools import parse_feed_tool

RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>ニュース &amp; 更新</title>
    <link>https://example.test/</link>
    <description><![CDATA[<p>フィードの説明</p>]]></description>
    <language>ja-JP</language>
    <item>
      <guid>https://example.test/item/1</guid>
      <title>記事 &#x3042;</title>
      <link>https://example.test/item/1</link>
      <pubDate>Tue, 03 Jun 2003 09:39:21 GMT</pubDate>
      <description><![CDATA[<p>本文 <b>強調</b> &amp; 続き</p><script>ignore me</script>]]></description>
      <category>ニュース</category>
      <category>日本</category>
    </item>
    <item><guid>item-2</guid><title>二番目</title></item>
  </channel>
</rss>"""


ATOM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="en-US">
  <title>Example Atom</title>
  <link rel="self" href="https://example.test/feed" />
  <link rel="alternate" href="https://example.test/" />
  <updated>2026-11-03T20:30:00+09:00</updated>
  <entry xml:lang="ja-JP">
    <id>tag:example.test,2026:item-1</id>
    <title>記事</title>
    <updated>2026-11-03T20:15:00+09:00</updated>
    <content type="html">&lt;p&gt;Atom &lt;em&gt;content&lt;/em&gt;&lt;/p&gt;</content>
    <author><name>著者</name></author>
    <category term="国際" />
  </entry>
</feed>"""


def _run(args: dict) -> dict:
    return json.loads(parse_feed_tool.run_tool(args))


def test_parse_rss20_normalizes_fields_and_strips_html():
    result = _run({"content": RSS_XML})

    assert result["ok"] is True
    assert result["feed_type"] == "rss2.0"
    assert result["title"] == "ニュース & 更新"
    assert result["description"] == "フィードの説明"
    assert result["language"] == "ja-jp"
    assert result["total_items"] == 2
    item = result["items"][0]
    assert item["id"] == "https://example.test/item/1"
    assert item["title"] == "記事 あ"
    assert item["published_at"] == "2003-06-03T09:39:21+00:00"
    assert item["summary"] == "本文 強調 & 続き"
    assert item["categories"] == ["ニュース", "日本"]
    assert "ignore me" not in item["summary"]


def test_parse_atom_preserves_offset_and_entry_language_and_link():
    result = _run({"content": ATOM_XML})

    assert result["ok"] is True
    assert result["feed_type"] == "atom"
    assert result["language"] == "en-us"
    assert result["link"] == "https://example.test/"
    assert result["updated_at"] == "2026-11-03T20:30:00+09:00"
    item = result["items"][0]
    assert item["language"] == "ja-jp"
    assert item["published_at"] == "2026-11-03T20:15:00+09:00"
    assert item["updated_at"] == "2026-11-03T20:15:00+09:00"
    assert item["summary"] == "Atom content"
    assert item["author"] == "著者"
    assert item["categories"] == ["国際"]


@pytest.mark.parametrize("version", ["0.91", "0.92", "0.93", "0.94"])
def test_parse_rss09x_versions(version):
    xml = f"""<?xml version="1.0"?>
    <rss version="{version}"><channel>
      <title>RSS {version}</title><link>https://example.test/</link>
      <description>Legacy RSS</description>
      <item><title>Item {version}</title><link>https://example.test/item</link></item>
    </channel></rss>"""
    result = _run({"content": xml})

    assert result["ok"] is True, result
    assert result["feed_type"] == "rss0.9"
    assert result["title"] == f"RSS {version}"
    assert result["items"][0]["title"] == f"Item {version}"


def test_parse_rss090_rdf():
    xml = """<?xml version="1.0"?>
    <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
      xmlns="http://my.netscape.com/rdf/simple/0.9/">
      <channel rdf:about="https://example.test/feed">
        <title>RSS 0.90</title><link>https://example.test/</link>
        <description>Legacy RDF feed</description>
      </channel>
      <item rdf:about="https://example.test/item">
        <title>RDF item</title><link>https://example.test/item</link>
        <description>RDF summary</description>
      </item>
    </rdf:RDF>"""
    result = _run({"content": xml})

    assert result["ok"] is True, result
    assert result["feed_type"] == "rss0.9"
    assert result["title"] == "RSS 0.90"
    assert result["items"][0]["title"] == "RDF item"


def test_parse_rss10_and_unzoned_dates():
    xml = """<?xml version="1.0"?>
    <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
      xmlns="http://purl.org/rss/1.0/">
      <channel rdf:about="https://example.test/feed">
        <title>RDF feed</title><link>https://example.test/</link>
        <description>RSS 1.0 test</description>
      </channel>
      <item rdf:about="https://example.test/rdf-item">
        <title>RDF item</title><link>https://example.test/rdf-item</link>
        <description>RDF summary</description>
      </item>
    </rdf:RDF>"""
    result = _run({"content": xml})

    assert result["ok"] is True
    assert result["feed_type"] == "rss1.0"
    assert result["items"][0]["id"] == "https://example.test/rdf-item"
    assert (
        parse_feed_tool._parse_datetime("2026-11-03T20:30:00")
        == "2026-11-03T20:30:00+00:00"
    )


def test_limit_and_keep_html_option():
    result = _run({"content": RSS_XML, "limit": 1, "strip_html": False})

    assert result["total_items"] == 2
    assert len(result["items"]) == 1
    assert "<b>強調</b>" in result["items"][0]["summary"]


def test_explicit_shift_jis_encoding_is_supported():
    xml = """<?xml version="1.0"?><rss version="2.0"><channel>
    <title>日本語のフィード</title></channel></rss>"""
    result = _run({"content": xml, "encoding": "shift_jis"})

    assert result["ok"] is True
    assert result["title"] == "日本語のフィード"
    assert result["encoding"] in {"shift-jis", "shift_jis"}


def test_untagged_non_utf8_bytes_use_charset_detection():
    xml = "<rss version='2.0'><channel><title>日本語フィード</title></channel></rss>"
    decoded, _source_encoding = parse_feed_tool._decode_source_payload(
        xml.encode("shift_jis"), {}, None
    )
    assert "日本語フィード" in decoded


def test_direct_content_uses_or_overrides_xml_encoding_declaration():
    xml_declared = """<?xml version="1.0" encoding="shift_jis"?>
    <rss version="2.0"><channel><title>日本語フィード</title></channel></rss>"""
    result = _run({"content": xml_declared})
    assert result["ok"] is True, result
    assert result["title"] == "日本語フィード"
    assert result["encoding"] in {"shift-jis", "shift_jis"}

    conflicting_declaration = xml_declared.replace("shift_jis", "utf-8")
    result = _run({"content": conflicting_declaration, "encoding": "shift_jis"})
    assert result["ok"] is True
    assert result["title"] == "日本語フィード"


def test_source_bytes_are_decoded_then_normalized_to_utf8():
    xml = "<rss version='2.0'><channel><title>日本語</title></channel></rss>"
    raw = xml.encode("shift_jis")
    decoded, source_encoding = parse_feed_tool._decode_source_payload(
        raw, {"content-type": "application/rss+xml; charset=shift_jis"}, None
    )

    assert "日本語" in decoded
    assert source_encoding == "shift_jis"
    assert "日本語" in parse_feed_tool._utf8_xml_payload(decoded).decode("utf-8")


def test_url_fetch_passes_response_headers_and_normalizes(monkeypatch):
    captured = {}

    def fake_fetch(url: str, timeout: int):
        captured["url"] = url
        captured["timeout"] = timeout
        return RSS_XML.encode("utf-8"), {
            "content-type": "application/rss+xml; charset=utf-8"
        }

    monkeypatch.setattr(parse_feed_tool, "_fetch_url", fake_fetch)
    result = _run({"url": "https://feeds.example.test/rss", "timeout": 7})

    assert captured == {"url": "https://feeds.example.test/rss", "timeout": 7}
    assert result["feed_type"] == "rss2.0"


def test_rejects_missing_or_ambiguous_input_and_invalid_options():
    assert _run({})["ok"] is False
    assert _run({"url": "https://example.test", "content": "<rss/>"})["ok"] is False
    assert _run({"content": RSS_XML, "limit": 0})["ok"] is False
    assert _run({"content": RSS_XML, "timeout": True})["ok"] is False
    assert _run({"content": RSS_XML, "encoding": "not-a-real-codec"})["ok"] is False


def test_http_fetch_pins_the_validated_public_address(monkeypatch):
    connections = []

    class Response:
        status = 200

        def getheader(self, name):
            return (
                str(len(RSS_XML.encode("utf-8"))) if name == "Content-Length" else None
            )

        def read(self, limit):
            assert limit == parse_feed_tool.MAX_FEED_BYTES + 1
            return RSS_XML.encode("utf-8")

        def getheaders(self):
            return [("Content-Type", "application/rss+xml; charset=utf-8")]

    class FakeConnection:
        def __init__(self, host, port, address, timeout):
            connections.append((host, port, address, timeout))

        def request(self, method, target, headers):
            assert method == "GET"
            assert target == "/feed?x=1"
            assert headers["Accept-Encoding"] == "identity"

        def getresponse(self):
            return Response()

        def close(self):
            pass

    monkeypatch.setattr(
        parse_feed_tool.socket,
        "getaddrinfo",
        lambda host, port, **kwargs: [(2, 1, 6, "", ("93.184.216.34", port))],
    )
    monkeypatch.setattr(parse_feed_tool, "_PinnedHTTPConnection", FakeConnection)

    payload, headers = parse_feed_tool._fetch_url(
        "http://feeds.example.test/feed?x=1", timeout=4
    )

    assert payload == RSS_XML.encode("utf-8")
    assert headers["content-type"] == "application/rss+xml; charset=utf-8"
    assert connections == [("feeds.example.test", 80, "93.184.216.34", 4)]


def test_http_fetch_rejects_private_redirect_before_connecting(monkeypatch):
    connections = []

    class RedirectResponse:
        status = 302

        def getheader(self, name):
            return "http://127.0.0.1/internal" if name == "Location" else None

    class FakeConnection:
        def __init__(self, host, port, address, timeout):
            connections.append((host, port, address, timeout))

        def request(self, method, target, headers):
            pass

        def getresponse(self):
            return RedirectResponse()

        def close(self):
            pass

    monkeypatch.setattr(
        parse_feed_tool.socket,
        "getaddrinfo",
        lambda host, port, **kwargs: [(2, 1, 6, "", ("93.184.216.34", port))],
    )
    monkeypatch.setattr(parse_feed_tool, "_PinnedHTTPConnection", FakeConnection)

    with pytest.raises(ValueError, match="public IP"):
        parse_feed_tool._fetch_url("http://feeds.example.test/feed", timeout=4)
    assert len(connections) == 1


def test_rejects_non_public_and_credentialed_feed_urls(monkeypatch):
    with pytest.raises(ValueError, match="public IP"):
        parse_feed_tool._validate_public_url("http://127.0.0.1/feed")
    with pytest.raises(ValueError, match="credentials"):
        parse_feed_tool._validate_public_url("https://user:pass@example.test/feed")

    monkeypatch.setattr(
        parse_feed_tool.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("10.0.0.2", 0))],
    )
    with pytest.raises(ValueError, match="public IP"):
        parse_feed_tool._validate_public_url("https://internal.example/feed")


def test_rejects_doctype_and_oversized_direct_content():
    doctype = '<!DOCTYPE rss [<!ENTITY x "unsafe">]><rss version="2.0" />'
    assert "DOCTYPE" in _run({"content": doctype})["error"]
    assert "DOCTYPE" in _run({"content": doctype, "encoding": "utf-16"})["error"]
    assert parse_feed_tool._has_doctype(doctype.encode("utf-16")) is True
    assert (
        "byte limit"
        in _run({"content": "x" * (parse_feed_tool.MAX_FEED_BYTES + 1)})["error"]
    )


def test_bad_xml_returns_structured_parse_result():
    result = _run({"content": "<not-xml"})

    assert "ok" in result
    assert "feed_type" in result
    if not result["ok"]:
        assert result["error"]
