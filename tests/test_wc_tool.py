from __future__ import annotations

import json
from pathlib import Path

from uagent.tools.wc_tool import run_tool


def test_wc_counts_utf8_and_chunk_boundaries(repo_tmp_path: Path) -> None:
    path = repo_tmp_path / "sample.txt"
    content = "alpha βeta\n最後の単語"
    path.write_text(content, encoding="utf-8")

    result = json.loads(
        run_tool({"paths": [str(path)], "chunk_size": 4096, "return": "json"})
    )
    counts = result["files"][0]
    encoded = path.read_bytes()
    assert counts["lines"] == encoded.count(b"\n")
    assert counts["words"] == len(encoded.split())
    assert counts["bytes"] == len(encoded)
    assert counts["chars"] == len(encoded.decode("utf-8"))


def test_wc_rejects_invalid_chunk_size(repo_tmp_path: Path) -> None:
    path = repo_tmp_path / "sample.txt"
    path.write_text("text", encoding="utf-8")
    result = json.loads(run_tool({"paths": [str(path)], "chunk_size": "bad"}))
    assert result == {"ok": False, "error": "chunk_size must be an integer"}


def test_wc_text_output_includes_all_counts(repo_tmp_path: Path) -> None:
    path = repo_tmp_path / "sample.txt"
    path.write_text("a b\n", encoding="utf-8")
    output = run_tool({"paths": [str(path)], "return": "text"})
    fields = output.split()
    assert fields[:4] == ["1", "2", "5", "5"]
    assert fields[4].endswith("sample.txt")
