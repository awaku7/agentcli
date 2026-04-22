from __future__ import annotations

import json
from pathlib import Path

import pytest

from uagent.tools.replace_in_file_tool import run_tool as replace_in_file


def _load(out: str) -> dict:
    obj = json.loads(out)
    assert isinstance(obj, dict)
    assert obj.get("ok") is True, obj
    return obj


@pytest.mark.parametrize(
    "msgstr_text, expected_msgid, expected_kind, expected_line_count, expected_is_empty",
    [
        ("hello", "single", "singleline", 1, False),
        ("", "empty", "empty", 1, True),
        ("line1\nline2\n", "multi", "multiline", 3, False),
    ],
    ids=["singleline", "empty", "multiline"],
)
def test_replace_in_file_replace_po_entry_diagnostics(
    msgstr_text: str,
    expected_msgid: str,
    expected_kind: str,
    expected_line_count: int,
    expected_is_empty: bool,
    repo_tmp_path: Path,
) -> None:
    p = repo_tmp_path / "sample.po"
    p.write_text(
        'msgid ""\n'
        'msgstr ""\n'
        "\n"
        'msgid "single"\n'
        'msgstr "hello"\n'
        "\n"
        'msgid "empty"\n'
        'msgstr ""\n'
        "\n"
        'msgid "multi"\n'
        'msgstr ""\n'
        '"line1\\n"\n'
        '"line2\\n"\n',
        encoding="utf-8",
        newline="\n",
    )

    out = replace_in_file(
        {
            "path": str(p),
            "action": "replace_po_entry",
            "po_msgid": expected_msgid,
            "replacement": msgstr_text,
            "preview": True,
        }
    )
    obj = _load(out)
    diag = obj["diagnostics"]
    assert diag["po_msgid"] == expected_msgid
    assert diag["po_msgid_found"] is True
    assert diag["po_msgid_match_count"] == 1
    assert diag["po_msgid_replaced_count"] == 1
    assert diag["msgstr_kind"] == expected_kind
    assert diag["msgstr_line_count"] == expected_line_count
    assert diag["msgstr_is_empty"] is expected_is_empty
    assert obj["match_hits"][0]["msgstr_kind"] == expected_kind
    assert obj["match_hits"][0]["msgstr_line_count"] == expected_line_count
    assert obj["match_hits"][0]["msgstr_is_empty"] is expected_is_empty
