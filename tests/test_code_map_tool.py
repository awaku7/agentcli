from __future__ import annotations

import json
from pathlib import Path

from uagent.tools.code_map_tool import _tree_to_mermaid, run_tool


def _json_result(raw: str) -> dict:
    return json.loads(raw)


def test_python_relative_imports_and_source_lines(repo_tmp_path: Path) -> None:
    project = repo_tmp_path / "project"
    (project / "pkg" / "sub").mkdir(parents=True)
    (project / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (project / "pkg" / "sub" / "__init__.py").write_text("", encoding="utf-8")
    (project / "pkg" / "a.py").write_text("from . import b\n", encoding="utf-8")
    (project / "pkg" / "b.py").write_text("def target():\n    pass\n", encoding="utf-8")
    (project / "pkg" / "sub" / "c.py").write_text(
        "from .. import b\n", encoding="utf-8"
    )

    result = _json_result(
        run_tool(
            {
                "path": str(project),
                "format": "json",
                "include_relations": True,
            }
        )
    )

    relations = result["relations"]
    a_path = str((project / "pkg" / "a.py").resolve())
    c_path = str((project / "pkg" / "sub" / "c.py").resolve())
    b_path = str((project / "pkg" / "b.py").resolve())
    assert {r["source"] for r in relations if r["target"] == b_path} == {
        a_path,
        c_path,
    }
    assert all(r["source_line"] == 1 for r in relations)


def test_python_src_layout_absolute_import(repo_tmp_path: Path) -> None:
    project = repo_tmp_path / "project"
    package = project / "src" / "pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "a.py").write_text("import pkg.b\n", encoding="utf-8")
    (package / "b.py").write_text("VALUE = 1\n", encoding="utf-8")

    result = _json_result(
        run_tool({"path": str(project), "format": "json", "include_relations": True})
    )

    assert any(
        relation["target"] == str((package / "b.py").resolve())
        for relation in result["relations"]
    )


def test_project_only_does_not_fallback_to_full_scan(repo_tmp_path: Path) -> None:
    project = repo_tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        "[project]\nname='demo'\n", encoding="utf-8"
    )
    (project / "src.py").write_text("def source():\n    pass\n", encoding="utf-8")
    (project / "unrelated.py").write_text(
        "def unrelated():\n    pass\n", encoding="utf-8"
    )

    result = _json_result(
        run_tool({"path": str(project), "format": "json", "project_only": True})
    )

    assert result["files"] == []
    assert result["total_files"] == 0


def test_mixed_project_types_are_combined(repo_tmp_path: Path) -> None:
    project = repo_tmp_path / "project"
    (project / "py").mkdir(parents=True)
    (project / "js" / "src").mkdir(parents=True)
    (project / "py" / "pyproject.toml").write_text(
        "[project]\nname='demo'\n", encoding="utf-8"
    )
    (project / "py" / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    (project / "js" / "package.json").write_text("{}\n", encoding="utf-8")
    (project / "js" / "src" / "module.js").write_text(
        "const value = 1;\n", encoding="utf-8"
    )

    result = _json_result(
        run_tool({"path": str(project), "format": "json", "project_only": True})
    )
    paths = {entry["relative_path"].replace("\\", "/") for entry in result["files"]}
    assert "py/module.py" in paths
    assert "js/src/module.js" in paths


def test_go_module_relation_and_line_number(repo_tmp_path: Path) -> None:
    project = repo_tmp_path / "project"
    (project / "cmd").mkdir(parents=True)
    (project / "lib").mkdir()
    (project / "go.mod").write_text("module example.com/demo\n", encoding="utf-8")
    (project / "cmd" / "main.go").write_text(
        'package main\n\nimport "example.com/demo/lib"\n', encoding="utf-8"
    )
    (project / "lib" / "lib.go").write_text("package lib\n", encoding="utf-8")

    result = _json_result(
        run_tool({"path": str(project), "format": "json", "include_relations": True})
    )
    assert result["relations"] == [
        {
            "type": "import",
            "source": str((project / "cmd" / "main.go").resolve()),
            "target": str((project / "lib" / "lib.go").resolve()),
            "source_line": 3,
            "module": "example.com/demo/lib",
        }
    ]


def test_output_files_do_not_overwrite(repo_tmp_path: Path) -> None:
    project = repo_tmp_path / "project"
    output = repo_tmp_path / "output"
    project.mkdir()
    (project / "main.py").write_text("def main():\n    pass\n", encoding="utf-8")

    first = _json_result(
        run_tool({"path": str(project), "format": "json", "output_dir": str(output)})
    )
    second = _json_result(
        run_tool({"path": str(project), "format": "json", "output_dir": str(output)})
    )
    first_path = Path(first["saved_files"][0])
    second_path = Path(second["saved_files"][0])
    assert first_path != second_path
    assert first_path.read_text(encoding="utf-8")
    assert second_path.read_text(encoding="utf-8")


def test_mermaid_special_characters_are_escaped() -> None:
    mermaid = _tree_to_mermaid(
        [
            {
                "name": 'a"b|c&d<e>f',
                "type": "file",
                "path": "ignored",
            }
        ]
    )
    assert mermaid.startswith("graph TD")
    assert "&quot;" in mermaid
    assert "&#124;" in mermaid
    assert "&amp;" in mermaid
    assert "&lt;" in mermaid
    assert "&gt;" in mermaid


def test_invalid_input_and_ontology_default_relations(repo_tmp_path: Path) -> None:
    project = repo_tmp_path / "project"
    project.mkdir()
    (project / "a.py").write_text("import b\n", encoding="utf-8")
    (project / "b.py").write_text("VALUE = 1\n", encoding="utf-8")

    invalid = _json_result(run_tool({"path": str(project), "depth": -1}))
    assert invalid == {"ok": False, "error": "depth must be >= 0"}

    ontology = _json_result(run_tool({"path": str(project), "format": "ontology"}))
    assert any(node.get("@type") == "uag:ImportRelation" for node in ontology["@graph"])


def test_empty_and_missing_directories(repo_tmp_path: Path) -> None:
    empty = repo_tmp_path / "empty"
    empty.mkdir()
    result = _json_result(run_tool({"path": str(empty), "format": "json"}))
    assert result["ok"] is True
    assert result["total_files"] == 0

    missing = _json_result(
        run_tool({"path": str(repo_tmp_path / "missing"), "format": "json"})
    )
    assert missing["ok"] is False



def test_vba_and_lotusscript_support(repo_tmp_path: Path) -> None:
    project = repo_tmp_path / "legacy"
    project.mkdir()
    (project / "main.bas").write_text(
        'Attribute VB_Name = "Main"\nPublic Sub RunReport()\nEnd Sub\n',
        encoding="utf-8",
    )
    (project / "agent.lss").write_text(
        'Use "helper"\nFunction BuildAgent()\nEnd Function\n',
        encoding="utf-8",
    )
    (project / "helper.lss").write_text(
        'Function Helper()\nEnd Function\n', encoding="utf-8"
    )

    result = _json_result(
        run_tool({"path": str(project), "format": "json", "include_relations": True})
    )
    languages = {entry["relative_path"]: entry["language"] for entry in result["files"]}
    assert languages["main.bas"] == "VBA"
    assert languages["agent.lss"] == "LotusScript"
    assert any(
        symbol["name"] == "RunReport"
        for entry in result["files"]
        for symbol in entry.get("symbols", [])
    )
    assert any(
        relation["target"] == str((project / "helper.lss").resolve())
        for relation in result["relations"]
    )


# Keep the test module free of generated code-map artifacts.
