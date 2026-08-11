from __future__ import annotations

from pathlib import Path

import pytest

from uagent.tools.code_map_impl.symbols import extract_symbols
from uagent.tools.code_map_impl.tree_sitter_symbols import (
    extract_tree_sitter_symbols,
)


@pytest.mark.parametrize(
    ("filename", "language", "source", "expected"),
    [
        (
            "sample.py",
            "Python",
            "class Demo:\n    def greet(self):\n        return 1\n",
            {"Demo": (1, "class"), "greet": (2, "function")},
        ),
        (
            "sample.js",
            "JavaScript",
            "class Demo {}\nfunction greet() {}\nconst value = 1;\n",
            {
                "Demo": (1, "class"),
                "greet": (2, "function"),
                "value": (3, "symbol"),
            },
        ),
    ],
)
def test_tree_sitter_extracts_symbols(
    tmp_path: Path,
    filename: str,
    language: str,
    source: str,
    expected: dict[str, tuple[int, str]],
) -> None:
    pytest.importorskip("tree_sitter_language_pack")
    path = tmp_path / filename
    path.write_text(source, encoding="utf-8")

    symbols = extract_tree_sitter_symbols(str(path), language)
    actual = {item["name"]: (item["line"], item["type"]) for item in symbols}
    assert actual == expected


def test_vba_and_lotusscript_keep_regex_support(tmp_path: Path) -> None:
    vba = tmp_path / "module.bas"
    lotus = tmp_path / "agent.lss"
    vba.write_text("Public Sub RunReport()\nEnd Sub\n", encoding="utf-8")
    lotus.write_text("Function BuildAgent()\nEnd Function\n", encoding="utf-8")

    assert extract_symbols(str(vba)) == [
        {"name": "RunReport", "line": 1, "type": "function"}
    ]
    assert extract_symbols(str(lotus)) == [
        {"name": "BuildAgent", "line": 1, "type": "function"}
    ]
