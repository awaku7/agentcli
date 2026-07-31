import sys
import json
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from uagent.tools.json2idx_tool import run_tool as run_json
from uagent.tools.csv2idx_tool import run_tool as run_csv
from uagent.tools.docx2idx_tool import run_tool as run_docx
from uagent.tools.html2idx_tool import run_tool as run_html
from uagent.tools.sql2idx_tool import run_tool as run_sql
from uagent.tools.log2idx_tool import run_tool as run_log


@pytest.fixture
def sample_dir():
    tmp_dir = Path("tmp_test_dir_new2idx")
    tmp_dir.mkdir(exist_ok=True)
    yield tmp_dir
    # Cleanup
    for f in tmp_dir.glob("*"):
        f.unlink()
    try:
        tmp_dir.rmdir()
    except Exception:
        pass


def test_json2idx(sample_dir):
    p = sample_dir / "test.json"
    p.write_text(json.dumps({"a": 1, "b": [1, 2, 3]}), encoding="utf-8")
    res1 = run_json({"path": str(p), "mode": "index"})
    assert ("Index for:" in res1) or ("インデックス:" in res1)
    res2 = run_json({"path": str(p), "mode": "section", "section": 1})
    assert "Node:" in res2


def test_csv2idx(sample_dir):
    p = sample_dir / "test.csv"
    p.write_text("h1,h2\n1,2\n3,4", encoding="utf-8")
    res1 = run_csv({"path": str(p), "mode": "index"})
    assert ("Index for:" in res1) or ("インデックス:" in res1)
    res2 = run_csv({"path": str(p), "mode": "section", "section": 1})
    assert "Block 1" in res2


def test_docx2idx_error(sample_dir):
    res = run_docx({"mode": "index"})
    assert ("Error: 'path' is required" in res) or (
        "エラー: 'path' は必須です。" in res
    )


def test_html2idx(sample_dir):
    p = sample_dir / "test.html"
    p.write_text(
        "<html><body><h1>Title</h1><p>Body</p></body></html>", encoding="utf-8"
    )
    res1 = run_html({"path": str(p), "mode": "index"})
    assert ("Index for:" in res1) or ("インデックス:" in res1)
    res2 = run_html({"path": str(p), "mode": "section", "section": 1})
    assert "Section 1" in res2


def test_sql2idx(sample_dir):
    p = sample_dir / "test.sql"
    p.write_text(
        "CREATE TABLE users (id INT);\nINSERT INTO users VALUES (1);", encoding="utf-8"
    )
    res1 = run_sql({"path": str(p), "mode": "index"})
    assert ("Index for:" in res1) or ("インデックス:" in res1)
    res2 = run_sql({"path": str(p), "mode": "section", "section": 1})
    assert "Section 1" in res2


def test_log2idx(sample_dir):
    p = sample_dir / "test.log"
    p.write_text(
        "2026-07-29 INFO start\n2026-07-29 ERROR db connection failed", encoding="utf-8"
    )
    res1 = run_log({"path": str(p), "mode": "index"})
    assert ("Index for:" in res1) or ("インデックス:" in res1)
    res2 = run_log({"path": str(p), "mode": "section", "section": 1})
    assert "Block 1" in res2
