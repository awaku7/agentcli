from __future__ import annotations

from types import SimpleNamespace

from uagent.providers.responses_common import (
    parse_responses_response,
    parse_responses_stream,
)


def test_parse_responses_response_emits_compaction_notice() -> None:
    notices: list[str] = []
    core = SimpleNamespace(print_stream_delta=notices.append)
    response = SimpleNamespace(
        id="resp_compact_1",
        output=[SimpleNamespace(type="compaction", id="cmp_1")],
        usage=None,
    )

    text, reasoning, tools, response_id, items = parse_responses_response(
        response, core=core
    )

    assert (text, reasoning, tools, response_id) == ("", "", [], "resp_compact_1")
    assert items and items[0]["type"] == "compaction"
    assert len(notices) == 1
    assert "compressed" in notices[0] or "圧縮" in notices[0]


def test_parse_responses_stream_emits_compaction_done_notice() -> None:
    notices: list[str] = []
    core = SimpleNamespace(_is_web=False, print_stream_delta=notices.append)
    stream = [
        SimpleNamespace(
            type="response.compaction.done",
            response=SimpleNamespace(id="resp_compact_2"),
        )
    ]

    text, reasoning, tools, response_id, items = parse_responses_stream(
        stream, print_delta_fn=lambda _text: None, core=core
    )

    assert (text, reasoning, tools, response_id, items) == ("", "", [], None, [])
    assert len(notices) == 1
    assert "compressed" in notices[0] or "圧縮" in notices[0]


def test_parse_responses_stream_emits_compaction_output_item_notice() -> None:
    notices: list[str] = []
    core = SimpleNamespace(_is_web=False, print_stream_delta=notices.append)
    stream = [
        SimpleNamespace(
            type="response.output_item.done",
            item=SimpleNamespace(type="compaction", id="cmp_2"),
        )
    ]

    parse_responses_stream(stream, print_delta_fn=lambda _text: None, core=core)

    assert len(notices) == 1
    assert "compressed" in notices[0] or "圧縮" in notices[0]


__all__ = []
