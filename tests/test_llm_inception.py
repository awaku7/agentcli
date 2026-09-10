from __future__ import annotations

import types

from uagent.providers.llm_inception import parse_inception_stream


class _Chunk:
    def __init__(self, content: str) -> None:
        self.choices = [
            types.SimpleNamespace(
                delta=types.SimpleNamespace(content=content, tool_calls=[])
            )
        ]


def test_diffusing_stream_replaces_snapshots() -> None:
    output: list[str] = []
    result = parse_inception_stream(
        [_Chunk("H"), _Chunk("He"), _Chunk("Hello")],
        diffusing=True,
        print_delta_fn=output.append,
        core=types.SimpleNamespace(_is_web=False),
    )

    assert result[0] == "Hello"
    assert any("Hello" in item for item in output)


def test_normal_stream_concatenates_deltas() -> None:
    result = parse_inception_stream(
        [_Chunk("Hel"), _Chunk("lo")],
        diffusing=False,
        print_delta_fn=lambda _: None,
        core=types.SimpleNamespace(_is_web=False),
    )

    assert result[0] == "Hello"
