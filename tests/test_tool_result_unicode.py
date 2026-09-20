from uagent.llm_flow_helpers import _normalize_tool_result_json


def test_tool_result_json_unicode_unescape_is_opt_in(monkeypatch):
    encoded = '{"message":"\\u65e5\\u672c\\u8a9e"}'

    monkeypatch.delenv("UAGENT_TOOL_RESULT_JSON_UNESCAPE", raising=False)
    assert "\\u65e5" in _normalize_tool_result_json(encoded)

    monkeypatch.setenv("UAGENT_TOOL_RESULT_JSON_UNESCAPE", "1")
    normalized = _normalize_tool_result_json(encoded)
    assert "日本語" in normalized
    assert "\\u65e5" not in normalized


def test_tool_result_json_unicode_unescape_leaves_plain_text(monkeypatch):
    monkeypatch.setenv("UAGENT_TOOL_RESULT_JSON_UNESCAPE", "1")
    assert _normalize_tool_result_json("plain text") == "plain text"
