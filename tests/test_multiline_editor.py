from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("one\r\ntwo\r\nthree", "one\ntwo\nthree"),
        ("one\rtwo\rthree", "one\ntwo\nthree"),
        ("one\n\ntwo", "one\n\ntwo"),
    ],
)
def test_multiline_editor_normalizes_carriage_returns(
    value: str, expected: str
) -> None:
    from uagent.cli_impl.input_ui import _normalize_multiline_text

    assert _normalize_multiline_text(value) == expected
