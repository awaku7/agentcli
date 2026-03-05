from __future__ import annotations

from pathlib import Path

import pytest

from uagent.tools.read_pptx_pdf_tool import run_tool as read_pptx_pdf


@pytest.mark.parametrize("kind", ["pdf", "pptx"])
def test_read_pptx_pdf_reads_fixture(repo_tmp_path: Path, kind: str) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fixture = repo_root / "tests" / "fixtures" / f"sample.{kind}"
    assert fixture.exists(), f"missing fixture: {fixture}"

    out = read_pptx_pdf(
        {
            "path": str(fixture),
            "page_index": 1,
            "max_chars": 2000,
        }
    )
    assert isinstance(out, str)
    assert out.strip(), "expected non-empty extracted text"
