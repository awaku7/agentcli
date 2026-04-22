from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from uagent.tools.replace_in_file_tool import run_tool as replace_in_file


def _load(out: str) -> dict:
    obj = json.loads(out)
    assert isinstance(obj, dict)
    assert obj.get("ok") is True, obj
    return obj


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["LF", "CRLF"])
def test_replace_in_file_literal_cross_newline_tokens(
    newline: str, repo_tmp_path: Path
) -> None:
    """Regardless of file newline convention, \n token should match/replace."""

    suffix = "crlf" if newline == "\r\n" else "lf"
    p = repo_tmp_path / f"literal_{suffix}.txt"
    _write_bytes(p, f"aaa{newline}bbb{newline}ccc{newline}".encode("utf-8"))

    out_preview = replace_in_file(
        {
            "path": str(p),
            "mode": "literal",
            "pattern": "aaa\\nbbb",
            "replacement": "AAA\\nBBB",
            "preview": True,
        }
    )
    objp = _load(out_preview)
    assert objp["match_count"] == 1
    assert objp["preview"] is True
    assert json.loads(out_preview)["ok"] is True

    out_apply = replace_in_file(
        {
            "path": str(p),
            "mode": "literal",
            "pattern": "aaa\\nbbb",
            "replacement": "AAA\\nBBB",
            "preview": False,
            "confirm_over": 999,
        }
    )
    obja = _load(out_apply)
    assert obja["written"] is True
    assert "backup" in obja

    b = _read_bytes(p)
    assert (b"\r\n" in b) if newline == "\r\n" else (b"\r\n" not in b)
    assert b"AAA" in b and b"BBB" in b


@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["LF", "CRLF"])
def test_replace_in_file_regex_cross_newline_tokens(
    newline: str, repo_tmp_path: Path
) -> None:
    """Regex pattern containing \n token should match across line boundaries."""

    suffix = "crlf" if newline == "\r\n" else "lf"
    p = repo_tmp_path / f"regex_{suffix}.txt"
    _write_bytes(p, f"hello{newline}world{newline}".encode("utf-8"))

    out_preview = replace_in_file(
        {
            "path": str(p),
            "mode": "regex",
            "pattern": "hello\\nworld",
            "replacement": "HELLO\\nWORLD",
            "preview": True,
        }
    )
    objp = _load(out_preview)
    assert objp["match_count"] == 1

    out_apply = replace_in_file(
        {
            "path": str(p),
            "mode": "regex",
            "pattern": "hello\\nworld",
            "replacement": "HELLO\\nWORLD",
            "preview": False,
            "confirm_over": 999,
        }
    )
    _load(out_apply)

    b = _read_bytes(p)
    assert (b"\r\n" in b) if newline == "\r\n" else (b"\r\n" not in b)
    assert b"HELLO" in b and b"WORLD" in b


@pytest.mark.parametrize(
    "expand_newline_tokens", [True, False], ids=["expand", "no_expand"]
)
def test_replace_in_file_expand_newline_tokens_flag(
    expand_newline_tokens: bool, repo_tmp_path: Path
) -> None:
    p = repo_tmp_path / "expand_newline_tokens.txt"
    p.write_text("a\nline\nb\n", encoding="utf-8", newline="\n")

    out_preview = replace_in_file(
        {
            "path": str(p),
            "mode": "literal",
            "pattern": "a\\nline",
            "replacement": "A\\nLINE",
            "preview": True,
            "expand_newline_tokens": expand_newline_tokens,
        }
    )
    objp = _load(out_preview)

    if expand_newline_tokens:
        assert objp["match_count"] == 1
    else:
        assert objp["match_count"] == 0


@pytest.mark.parametrize("mode", ["literal", "regex"], ids=["literal", "regex"])
def test_replace_in_file_preview_does_not_write(mode: str, repo_tmp_path: Path) -> None:
    p = repo_tmp_path / f"preview_no_write_{mode}.txt"
    p.write_text("abc\n", encoding="utf-8", newline="\n")
    before = _read_bytes(p)

    out_preview = replace_in_file(
        {
            "path": str(p),
            "mode": mode,
            "pattern": "abc",
            "replacement": "ABC",
            "preview": True,
        }
    )
    objp = _load(out_preview)
    assert objp["preview"] is True

    after = _read_bytes(p)
    assert after == before


@pytest.mark.parametrize(
    "pattern,replacement,expected_count",
    [(r"name=(.+)", r"NAME=\\1", 2), (r"^name=(.+)$", r"NAME=\\1", 0)],
    ids=["no_anchors", "anchors_no_multiline"],
)
def test_replace_in_file_regex_anchor_behavior(
    pattern: str, replacement: str, expected_count: int, repo_tmp_path: Path
) -> None:
    p = repo_tmp_path / "anchor_behavior.txt"
    p.write_text("name=alice\nname=bob\n", encoding="utf-8", newline="\n")

    out = replace_in_file(
        {
            "path": str(p),
            "mode": "regex",
            "pattern": pattern,
            "replacement": replacement,
            "preview": True,
        }
    )
    obj = _load(out)
    assert obj["match_count"] == expected_count


@pytest.mark.skipif(os.name != "nt", reason="CP932 is Windows-oriented")
def test_replace_in_file_cp932_roundtrip(repo_tmp_path: Path) -> None:
    """CP932 read/write should preserve non-ASCII (Japanese) text."""

    p = repo_tmp_path / "cp932.txt"
    original = "日本語テスト\n次の行\n"
    _write_bytes(p, original.encode("cp932"))

    out = replace_in_file(
        {
            "path": str(p),
            "mode": "literal",
            "pattern": "テスト",
            "replacement": "置換",
            "encoding": "cp932",
            "preview": False,
            "confirm_over": 999,
        }
    )
    obj = _load(out)
    assert obj.get("encoding") in {"cp932", "utf-8"}

    b = _read_bytes(p)
    text = b.decode("cp932")
    assert "日本語" in text
    assert "置換" in text


def test_replace_in_file_utf8_bom_is_not_crashing(repo_tmp_path: Path) -> None:
    """If a UTF-8 BOM file is edited, tool should not crash."""

    p = repo_tmp_path / "utf8_bom.txt"
    _write_bytes(p, b"\xef\xbb\xbf" + b"abc\n")

    out = replace_in_file(
        {
            "path": str(p),
            "mode": "literal",
            "pattern": "abc",
            "replacement": "ABC",
            "preview": False,
            "confirm_over": 999,
        }
    )
    _load(out)

    b = _read_bytes(p)
    assert b.startswith(b"\xef\xbb\xbf")
    assert b"ABC" in b


def test_replace_in_file_regex_groups(repo_tmp_path: Path) -> None:
    p = repo_tmp_path / "groups.txt"
    p.write_text("name=alice\nname=bob\n", encoding="utf-8", newline="\n")

    out = replace_in_file(
        {
            "path": str(p),
            "mode": "regex",
            "pattern": r"name=(.+)",
            "replacement": r"NAME=\1",
            "preview": False,
            "confirm_over": 999,
        }
    )
    obj = _load(out)
    assert obj["match_count"] == 2

    txt = p.read_text(encoding="utf-8")
    assert "NAME=alice" in txt
    assert "NAME=bob" in txt


def test_replace_in_file_trailing_newline_preserved(repo_tmp_path: Path) -> None:
    """No extra newline should be introduced/removed by replacement."""

    p1 = repo_tmp_path / "no_trailing_newline.txt"
    p1.write_text("abc", encoding="utf-8", newline="\n")

    _load(
        replace_in_file(
            {
                "path": str(p1),
                "mode": "literal",
                "pattern": "a",
                "replacement": "A",
                "preview": False,
                "confirm_over": 999,
            }
        )
    )
    assert _read_bytes(p1).endswith(b"c")

    p2 = repo_tmp_path / "with_trailing_newline.txt"
    p2.write_text("abc\n", encoding="utf-8", newline="\n")

    _load(
        replace_in_file(
            {
                "path": str(p2),
                "mode": "literal",
                "pattern": "a",
                "replacement": "A",
                "preview": False,
                "confirm_over": 999,
            }
        )
    )
    assert _read_bytes(p2).endswith(b"\n")


def test_replace_in_file_binary_like_content_is_handled(repo_tmp_path: Path) -> None:
    """Binary-ish bytes with NUL should not crash."""

    p = repo_tmp_path / "binary_like.bin"
    _write_bytes(p, b"abc\x00def\n")

    out = replace_in_file(
        {
            "path": str(p),
            "mode": "literal",
            "pattern": "abc",
            "replacement": "ABC",
            "preview": False,
            "confirm_over": 999,
        }
    )
    obj = _load(out)
    assert obj.get("changed") in {True, False}


def test_replace_in_file_occurrence_only_replaces_nth_literal(
    repo_tmp_path: Path,
) -> None:
    p = repo_tmp_path / "occurrence_literal.txt"
    p.write_text("aa bb aa bb aa bb\n", encoding="utf-8", newline="\n")

    out = replace_in_file(
        {
            "path": str(p),
            "mode": "literal",
            "pattern": "aa",
            "replacement": "XX",
            "occurrence": 2,
            "preview": False,
            "confirm_over": 999,
        }
    )
    obj = _load(out)
    assert obj["occurrence"] == 2
    assert obj["match_count"] == 3
    assert obj["replaced_count"] == 1
    assert p.read_text(encoding="utf-8") == "aa bb XX bb aa bb\n"


def test_replace_in_file_occurrence_only_replaces_nth_regex(
    repo_tmp_path: Path,
) -> None:
    p = repo_tmp_path / "occurrence_regex.txt"
    p.write_text("name=alice\nname=bob\nname=carol\n", encoding="utf-8", newline="\n")

    out = replace_in_file(
        {
            "path": str(p),
            "mode": "regex",
            "pattern": r"name=(.+)",
            "replacement": r"NAME=\1",
            "occurrence": 2,
            "preview": False,
            "confirm_over": 999,
        }
    )
    obj = _load(out)
    assert obj["occurrence"] == 2
    assert obj["match_count"] == 3
    assert obj["replaced_count"] == 1
    txt = p.read_text(encoding="utf-8")
    assert txt.count("NAME=") == 1
    assert "NAME=bob" in txt


def test_replace_in_file_return_hashes(repo_tmp_path: Path) -> None:
    p = repo_tmp_path / "hashes.txt"
    p.write_text("abc\n", encoding="utf-8", newline="\n")
    before = hashlib.sha256(p.read_bytes()).hexdigest()

    out = replace_in_file(
        {
            "path": str(p),
            "mode": "literal",
            "pattern": "abc",
            "replacement": "ABC",
            "preview": False,
            "confirm_over": 999,
            "return_hashes": True,
        }
    )
    obj = _load(out)
    assert obj["sha256_before"] == before
    assert obj["sha256_after"] == hashlib.sha256(p.read_bytes()).hexdigest()
    assert obj["sha256_before"] != obj["sha256_after"]
