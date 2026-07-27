"""pybitchat_send_tool の TDD テスト."""

from __future__ import annotations

from typing import Any


def test_tool_spec_structure() -> None:
    """pybitchat_send_tool が正しい TOOL_SPEC をエクスポートする."""
    from uagent.tools import pybitchat_send_tool as mod

    spec: dict[str, Any] = mod.TOOL_SPEC
    assert isinstance(spec, dict)
    assert spec.get("type") == "function"
    fn = spec.get("function", {})
    assert fn.get("name") == "pybitchat_send"
    params = fn.get("parameters", {})
    assert params.get("type") == "object"
    props = params.get("properties", {})
    assert "type" in props
    assert "payload" in props


def test_tool_has_run_tool() -> None:
    """pybitchat_send_tool が run_tool() 関数を持つ."""
    from uagent.tools import pybitchat_send_tool as mod

    assert hasattr(mod, "run_tool")
    assert callable(mod.run_tool)


class TestRunToolSend:
    """run_tool の send 動作."""

    def test_send_text_message(self) -> None:
        """テキストメッセージ送信が JSON 結果を返す."""
        from uagent.tools import pybitchat_send_tool as mod

        result = mod.run_tool({
            "type": "text",
            "payload": "Hello from pybitchat",
            "recipient": None,
        })
        import json

        data = json.loads(result) if isinstance(result, str) else result
        assert data.get("ok") is True
        assert "message_id" in data

    def test_send_with_recipient(self) -> None:
        """受信者指定メッセージ."""
        from uagent.tools import pybitchat_send_tool as mod

        result = mod.run_tool({
            "type": "text",
            "payload": "Direct message",
            "recipient": "0123456789abcdef",
        })
        import json

        data = json.loads(result) if isinstance(result, str) else result
        assert data.get("ok") is True
        assert data.get("recipient") == "0123456789abcdef"

    def test_send_announce(self) -> None:
        """Announce 送信."""
        from uagent.tools import pybitchat_send_tool as mod

        result = mod.run_tool({
            "type": "announce",
            "payload": "testnode",
            "recipient": None,
        })
        import json

        data = json.loads(result) if isinstance(result, str) else result
        assert data.get("ok") is True

    def test_send_no_payload(self) -> None:
        """ペイロードなしはエラー."""
        from uagent.tools import pybitchat_send_tool as mod

        result = mod.run_tool({
            "type": "text",
            "payload": "",
            "recipient": None,
        })
        import json

        data = json.loads(result) if isinstance(result, str) else result
        assert data.get("ok") is False
