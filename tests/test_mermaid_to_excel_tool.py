from __future__ import annotations

import json
import zipfile

from uagent.tools.mermaid_to_excel_tool import run_tool


def test_mermaid_to_excel_generates_connected_labeled_flowchart(tmp_path):
    output = tmp_path / "flow.xlsx"
    result = run_tool(
        {
            "mermaid": (
                "flowchart TD\n"
                "    A[開始] --> B{入力確認}\n"
                "    B -->|Yes| C[処理を実行]\n"
                "    B -->|No| D[エラー表示]\n"
                "    C --> E[終了]\n"
                "    D --> E\n"
            ),
            "output_path": str(output),
        }
    )

    result = json.loads(result)
    assert result["nodes"] == 5
    assert result["edges"] == 5
    with zipfile.ZipFile(output) as archive:
        drawing = archive.read("xl/drawings/drawing1.xml").decode("utf-8")
    assert drawing.count("<xdr:cxnSp>") == 5
    assert "Yes" in drawing
    assert "No" in drawing
