import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import openpyxl
from uagent.tools.excel2idx_tool import run_tool


@pytest.fixture
def sample_excel():
    tmp_dir = Path("tmp_test_dir")
    tmp_dir.mkdir(exist_ok=True)

    wb = openpyxl.Workbook()
    # Sheet 1
    ws1 = wb.active
    ws1.title = "Summary"
    ws1.append(["ID", "Name", "Score"])
    ws1.append([1, "Alice", 90])
    ws1.append([2, "Bob", 85])

    # Sheet 2
    ws2 = wb.create_sheet(title="Details")
    ws2.append(["Date", "Event", "Status"])
    ws2.append(["2026-01-01", "Launch", "Done"])

    path = tmp_dir / "test.xlsx"
    wb.save(str(path))
    yield str(path)

    if path.exists():
        path.unlink()
    if tmp_dir.exists():
        try:
            tmp_dir.rmdir()
        except Exception:
            pass


def test_excel2idx_index(sample_excel):
    res = run_tool({"path": sample_excel, "mode": "index"})
    assert ("Index for:" in res) or ("インデックス:" in res)
    assert "Sheet  1: 'Summary'" in res
    assert "Sheet  2: 'Details'" in res


def test_excel2idx_section(sample_excel):
    res1 = run_tool({"path": sample_excel, "mode": "section", "section": 1})
    assert "=== Sheet 1: 'Summary'" in res1
    assert "Alice" in res1

    res2 = run_tool({"path": sample_excel, "mode": "section", "section": 2})
    assert "=== Sheet 2: 'Details'" in res2
    assert "Launch" in res2


def test_excel2idx_errors():
    res_err_path = run_tool({"mode": "index"})
    assert ("Error: 'path' is required" in res_err_path) or (
        "エラー: 'path' は必須です。" in res_err_path
    )

    res_err_file = run_tool({"path": "non_existent.xlsx", "mode": "index"})
    assert ("Error: File not found" in res_err_file) or (
        "エラー: ファイルが見つかりません" in res_err_file
    )
