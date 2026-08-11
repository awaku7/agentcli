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


def test_replace_in_file_replace_po_entry_match_hits_are_capped(
    repo_tmp_path: Path,
) -> None:
    p = repo_tmp_path / "many.po"
    entries = [
        'msgid ""\n',
        'msgstr ""\n',
        "\n",
    ]
    entries.extend(f'msgid "target"\nmsgstr "value{i}"\n\n' for i in range(101))
    p.write_text("".join(entries), encoding="utf-8", newline="\n")

    out = replace_in_file(
        {
            "path": str(p),
            "action": "replace_po_entry",
            "po_msgid": "target",
            "replacement": "replaced",
            "preview": True,
        }
    )
    obj = _load(out)
    assert obj["diagnostics"]["po_msgid_match_count"] == 101
    assert obj["diagnostics"]["po_msgid_replaced_count"] == 101
    assert len(obj["match_hits"]) == 100


def test_replace_all_in_files_excludes_binary_and_globs(repo_tmp_path: Path) -> None:
    included = repo_tmp_path / "included.txt"
    excluded = repo_tmp_path / "excluded.pyc"
    binary = repo_tmp_path / "binary.bin"
    nested = repo_tmp_path / "nested"
    nested.mkdir()
    nested_file = nested / "nested.txt"

    included.write_text("needle\n", encoding="utf-8")
    excluded.write_bytes(b"needle\x00\n")
    binary.write_bytes(b"needle\x00binary\n")
    nested_file.write_text("needle\n", encoding="utf-8")

    out = replace_in_file(
        {
            "path": str(repo_tmp_path),
            "action": "replace_all_in_files",
            "mode": "literal",
            "pattern": "needle",
            "replacement": "changed",
            "preview": False,
            "confirm_over": 999,
            "glob": "*",
            "recur": True,
        }
    )
    obj = _load(out)
    assert obj["written_files"] == 2
    assert included.read_text(encoding="utf-8") == "changed\n"
    assert nested_file.read_text(encoding="utf-8") == "changed\n"
    assert excluded.read_bytes() == b"needle\x00\n"
    assert binary.read_bytes() == b"needle\x00binary\n"


def test_replace_all_in_files_honors_custom_exclude_glob(repo_tmp_path: Path) -> None:
    keep = repo_tmp_path / "keep.txt"
    skip = repo_tmp_path / "skip.txt"
    keep.write_text("needle\n", encoding="utf-8")
    skip.write_text("needle\n", encoding="utf-8")

    out = replace_in_file(
        {
            "path": str(repo_tmp_path),
            "action": "replace_all_in_files",
            "pattern": "needle",
            "replacement": "changed",
            "preview": False,
            "confirm_over": 999,
            "exclude_globs": ["skip.txt"],
        }
    )
    _load(out)
    assert keep.read_text(encoding="utf-8") == "changed\n"
    assert skip.read_text(encoding="utf-8") == "needle\n"


def test_insert_before_respects_confirm_over(repo_tmp_path: Path) -> None:
    p = repo_tmp_path / "insert_many.txt"
    p.write_text("needle\nneedle\n", encoding="utf-8")

    obj = _load(
        replace_in_file(
            {
                "path": str(p),
                "action": "insert_before",
                "anchor_before": "needle",
                "replacement": "header\n",
                "preview": False,
                "confirm_over": 1,
            }
        )
    )
    assert obj["blocked"] is True
    assert obj["match_count"] == 2
    assert p.read_text(encoding="utf-8") == "needle\nneedle\n"


def test_replace_all_in_files_uses_aggregate_confirm_over(
    repo_tmp_path: Path,
) -> None:
    first = repo_tmp_path / "first.txt"
    second = repo_tmp_path / "second.txt"
    first.write_text("needle\n", encoding="utf-8")
    second.write_text("needle\n", encoding="utf-8")

    obj = _load(
        replace_in_file(
            {
                "path": str(repo_tmp_path),
                "action": "replace_all_in_files",
                "pattern": "needle",
                "replacement": "changed",
                "preview": False,
                "confirm_over": 1,
                "glob": "*.txt",
            }
        )
    )
    assert obj["blocked"] is True
    assert obj["match_count"] == 2
    assert first.read_text(encoding="utf-8") == "needle\n"
    assert second.read_text(encoding="utf-8") == "needle\n"
