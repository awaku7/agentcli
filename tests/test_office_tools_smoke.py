from __future__ import annotations

import json
from pathlib import Path

import pytest

from uagent.tools.excel_ops_tool import run_tool as excel_ops


@pytest.mark.parametrize("sheet_name", ["Sheet1", "Data"])
def test_excel_ops_write_then_read(repo_tmp_path: Path, sheet_name: str) -> None:
    xlsx = repo_tmp_path / "sample.xlsx"

    # Write a tiny table
    payload = {
        "action": "write",
        "file_path": str(xlsx),
        "sheet_name": sheet_name,
        "data": json.dumps(
            [
                {"col1": "a", "col2": 1},
                {"col1": "b", "col2": 2},
            ]
        ),
    }
    out_w = excel_ops(payload)
    assert isinstance(out_w, str) and out_w
    assert xlsx.exists()

    # Read back
    out_r = excel_ops(
        {
            "action": "read",
            "file_path": str(xlsx),
            "sheet_name": sheet_name,
            "data": "[]",
        }
    )

    # read returns JSON string (list of rows = list[list[Any]])
    rows = json.loads(out_r)
    assert isinstance(rows, list)
    assert rows, "expected at least one row"

    header = rows[0]
    assert isinstance(header, list)
    assert "col1" in header

    col1_idx = header.index("col1")
    assert rows[1][col1_idx] == "a"


def test_excel_ops_get_sheet_names(repo_tmp_path: Path) -> None:
    xlsx = repo_tmp_path / "sheets.xlsx"

    # Ensure file exists with at least one sheet
    excel_ops(
        {
            "action": "write",
            "file_path": str(xlsx),
            "sheet_name": "Sheet1",
            "data": json.dumps([{"x": 1}]),
        }
    )

    out = excel_ops(
        {
            "action": "get_sheet_names",
            "file_path": str(xlsx),
            "sheet_name": "Sheet1",
            "data": "[]",
        }
    )
    names = json.loads(out)
    assert isinstance(names, list)
    assert "Sheet1" in names


@pytest.mark.skip(
    reason=(
        "exstruct python package API in current environment does not match uagent.tools.exstruct_tool "
        "(missing include_shapes / export_file). Keep schema coverage only under policy A."
    )
)
def test_exstruct_skipped_documentation_only() -> None:
    # Intentionally skipped; see reason above.
    assert True
