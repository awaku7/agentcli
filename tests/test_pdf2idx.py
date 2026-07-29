import os
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pdfplumber
from uagent.tools.pdf2idx_tool import run_tool

def test_pdf2idx_errors():
    res_err_path = run_tool({"mode": "index"})
    assert ("Error: 'path' is required" in res_err_path) or ("エラー: 'path' は必須です。" in res_err_path)

    res_err_file = run_tool({"path": "non_existent.pdf", "mode": "index"})
    assert ("Error: File not found" in res_err_file) or ("エラー: ファイルが見つかりません" in res_err_file)
