from __future__ import annotations

import json
from pathlib import Path

from uagent.tools.replace_in_file_tool import run_tool as replace_in_file


def _load(out: str) -> dict:
    obj = json.loads(out)
    assert isinstance(obj, dict)
    assert obj.get("ok") is True, obj
    return obj


def _apply_and_read_bytes(p: Path, initial_text: str) -> bytes:
    p.write_text(initial_text, encoding="utf-8", newline="")
    out = replace_in_file(
        {
            "path": str(p),
            "mode": "literal",
            "pattern": "alpha",
            "replacement": "A\r\nB",
            "preview": False,
            "confirm_over": 999,
        }
    )
    obj = _load(out)
    assert obj["written"] is True
    assert obj["replaced_count"] == 1
    return p.read_bytes()


def test_replace_in_file_crlf_replacement_roundtrip(repo_tmp_path: Path) -> None:
    """Replacement strings containing CRLF should survive preview/apply paths."""

    p = repo_tmp_path / "crlf_roundtrip.txt"
    p.write_text("alpha\nbeta\n", encoding="utf-8", newline="\n")

    out_preview = replace_in_file(
        {
            "path": str(p),
            "mode": "literal",
            "pattern": "alpha",
            "replacement": "A\r\nB",
            "preview": True,
        }
    )
    obj_preview = _load(out_preview)
    assert obj_preview["preview"] is True
    assert obj_preview["match_count"] == 1
    assert json.loads(out_preview)["ok"] is True

    out_apply = replace_in_file(
        {
            "path": str(p),
            "mode": "literal",
            "pattern": "alpha",
            "replacement": "A\r\nB",
            "preview": False,
            "confirm_over": 999,
        }
    )
    obj_apply = _load(out_apply)
    assert obj_apply["written"] is True
    assert obj_apply["replaced_count"] == 1

    data = p.read_bytes()
    assert b"A\nB" in data
    assert data.endswith(b"beta\n")


def test_replace_in_file_preserves_lf_as_lf(repo_tmp_path: Path) -> None:
    data = _apply_and_read_bytes(repo_tmp_path / "lf.txt", "alpha\nbeta\n")
    assert data == b"A\nB\nbeta\n"


def test_replace_in_file_preserves_cr_as_cr(repo_tmp_path: Path) -> None:
    data = _apply_and_read_bytes(repo_tmp_path / "cr.txt", "alpha\rbeta\r")
    assert data == b"A\rB\rbeta\r"


def test_replace_in_file_mixed_uses_first_newline_kind(repo_tmp_path: Path) -> None:
    data = _apply_and_read_bytes(repo_tmp_path / "mixed.txt", "alpha\r\nbeta\n")
    assert data == b"A\r\nB\r\nbeta\r\n"


def test_replace_in_file_triple_quoted_mixed_pattern_and_replacement(
    repo_tmp_path: Path,
) -> None:
    p = repo_tmp_path / "triple_mixed.txt"
    p.write_text(
        """before
alpha
line1\\nline2
beta
after
""",
        encoding="utf-8",
        newline="\n",
    )

    out = replace_in_file(
        {
            "path": str(p),
            "mode": "literal",
            "pattern": """alpha
line1\\nline2""",
            "replacement": """A
mid\\npart
B""",
            "preview": False,
            "confirm_over": 999,
            "expand_newline_tokens": False,
        }
    )
    obj = _load(out)
    assert obj["written"] is True
    assert obj["replaced_count"] == 1

    data = p.read_bytes()
    assert data == b"before\nA\nmid\\npart\nB\nbeta\nafter\n"
