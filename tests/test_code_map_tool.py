from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from uagent.tools.code_map_tool import _tree_to_mermaid, run_tool


def _json_result(raw: str, *, load_saved: bool = True) -> dict:
    result = json.loads(raw)
    if load_saved and result.get("saved_files"):
        return json.loads(Path(result["saved_files"][0]).read_text(encoding="utf-8"))
    return result


def test_code_map_reports_progress_through_shared_status_callback(
    monkeypatch, tmp_path: Path
) -> None:
    import uagent.tools.context as tool_context
    import uagent.tools.code_map_impl.runner as code_map_runner

    class FakeClock:
        now = 0.0

        def monotonic(self) -> float:
            self.now += 0.5
            return self.now

    monkeypatch.setattr(
        code_map_runner, "time", SimpleNamespace(monotonic=FakeClock().monotonic)
    )
    statuses: list[tuple[bool, str]] = []
    monkeypatch.setattr(
        tool_context,
        "get_callbacks",
        lambda: SimpleNamespace(
            set_status=lambda busy, label: statuses.append((busy, label))
        ),
    )
    project = tmp_path / "project"
    project.mkdir()
    for index in range(25):
        (project / f"module_{index}.py").write_text(
            f"def function_{index}():\n    return {index}\n", encoding="utf-8"
        )

    run_tool(
        {
            "path": str(project),
            "format": "json",
            "include_relations": False,
            "output_dir": str(tmp_path / "output"),
        }
    )

    labels = [label for busy, label in statuses if busy]
    assert labels[0] == "tool:code_map:Discovering project files"
    assert "tool:code_map:Collecting source files" in labels
    symbol_updates = [label for label in labels if "Extracting symbols" in label]
    assert symbol_updates
    assert any("25/25 (100%)" in label for label in symbol_updates)
    assert len(symbol_updates) == 13
    assert labels[-1] == "tool:code_map:Saving output"


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


def test_vcxproj_project_only_collects_native_sources_and_references(
    repo_tmp_path: Path,
) -> None:
    project = repo_tmp_path / "native"
    (project / "src").mkdir(parents=True)
    (project / "include").mkdir()
    (project / "src" / "main.cpp").write_text(
        '#include "../include/main.h"\nint main() { return 0; }\n', encoding="utf-8"
    )
    (project / "include" / "main.h").write_text("int main();\n", encoding="utf-8")
    (project / "unrelated.cs").write_text("class Unrelated {}\n", encoding="utf-8")
    (project / "Native.vcxproj").write_text(
        '<Project DefaultTargets="Build" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">\n'
        "  <ItemGroup>\n"
        '    <ClCompile Include="src\\main.cpp" />\n'
        '    <ClInclude Include="include\\main.h" />\n'
        "  </ItemGroup>\n"
        "  <PropertyGroup><PlatformToolset>v143</PlatformToolset></PropertyGroup>\n"
        "</Project>\n",
        encoding="utf-8",
    )

    result = _json_result(
        run_tool({"path": str(project), "format": "json", "project_only": True})
    )
    paths = {entry["relative_path"].replace("\\", "/") for entry in result["files"]}
    assert result["project"]["type"] == "visual-cpp"
    assert any(
        Path(value).name == "Native.vcxproj" for value in result["project"]["files"]
    )
    assert {"src/main.cpp", "include/main.h"}.issubset(paths)
    assert "unrelated.cs" not in paths


def test_solution_discovers_vcxproj_and_slnx_projects(repo_tmp_path: Path) -> None:
    project = repo_tmp_path / "solution"
    (project / "cpp").mkdir(parents=True)
    (project / "cpp" / "app.cpp").write_text(
        "int app() { return 0; }\n", encoding="utf-8"
    )
    (project / "cpp" / "app.vcxproj").write_text(
        '<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003">'
        '<ItemGroup><ClCompile Include="app.cpp" /></ItemGroup></Project>',
        encoding="utf-8",
    )
    (project / "app.sln").write_text(
        "Microsoft Visual Studio Solution File, Format Version 12.00\n"
        'Project("{TYPE}") = "App", "cpp\\app.vcxproj", "{APP}"\n'
        "EndProject\n",
        encoding="utf-8",
    )
    result = _json_result(
        run_tool({"path": str(project), "format": "json", "project_only": True})
    )
    assert any(value.endswith("app.vcxproj") for value in result["project"]["files"])
    assert any(
        entry["relative_path"].replace("\\", "/") == "cpp/app.cpp"
        for entry in result["files"]
    )

    (project / "app.sln").unlink()
    (project / "app.slnx").write_text(
        '<Solution><Project Path="cpp\\app.vcxproj" Name="App" /></Solution>',
        encoding="utf-8",
    )
    result = _json_result(
        run_tool({"path": str(project), "format": "json", "project_only": True})
    )
    assert any(value.endswith("app.slnx") for value in result["project"]["files"])
    assert any(
        entry["relative_path"].replace("\\", "/") == "cpp/app.cpp"
        for entry in result["files"]
    )


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

    first = json.loads(
        run_tool({"path": str(project), "format": "json", "output_dir": str(output)})
    )
    second = json.loads(
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
        "Function Helper()\nEnd Function\n", encoding="utf-8"
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


def test_manifest_discovery_skips_hidden_and_generated_trees(
    repo_tmp_path: Path,
) -> None:
    project = repo_tmp_path / "project"
    (project / ".git").mkdir(parents=True)
    (project / ".hidden").mkdir()
    (project / "node_modules" / "somepkg").mkdir(parents=True)
    (project / "build").mkdir()
    (project / "package.json").write_text(
        '{"dependencies": {"real-dep": "1.0.0"}}\n', encoding="utf-8"
    )
    # Git metadata whose name collides with the R manifest on
    # case-insensitive filesystems.
    (project / ".git" / "description").write_text(
        "Package: decoy\nImports: decoylib\n", encoding="utf-8"
    )
    (project / ".hidden" / "package.json").write_text(
        '{"dependencies": {"hidden-dep": "1.0.0"}}\n', encoding="utf-8"
    )
    (project / "node_modules" / "somepkg" / "package.json").write_text(
        '{"dependencies": {"nm-dep": "1.0.0"}}\n', encoding="utf-8"
    )
    (project / "build" / "package.json").write_text(
        '{"dependencies": {"build-dep": "1.0.0"}}\n', encoding="utf-8"
    )

    result = _json_result(
        run_tool({"path": str(project), "format": "json", "include_relations": True})
    )
    project_files = result["project"]["files"]
    assert any(
        path.endswith("package.json") and ".git" not in path for path in project_files
    )
    assert not any(".git" in path for path in project_files)
    assert not any(".hidden" in path for path in project_files)
    assert not any("node_modules" in path for path in project_files)
    assert not any(
        f"{Path('build')}" in path.split("/")[-2:-1] for path in project_files
    )
    dep_names = {dep["name"] for dep in result["project"]["dependencies"]}
    assert "real-dep" in dep_names
    assert "hidden-dep" not in dep_names
    assert "nm-dep" not in dep_names
    assert "build-dep" not in dep_names
    assert "decoylib" not in dep_names


def test_description_manifest_requires_exact_case(repo_tmp_path: Path) -> None:
    project = repo_tmp_path / "project"
    (project / "docs").mkdir(parents=True)
    (project / "rpkg").mkdir()
    (project / "package.json").write_text("{}\n", encoding="utf-8")
    # A lowercase "description" file is not an R package manifest, even
    # though the dependency extractor keys on the lowercased name.
    (project / "docs" / "description").write_text(
        "Imports: notanrpackage\n", encoding="utf-8"
    )
    (project / "rpkg" / "DESCRIPTION").write_text(
        "Package: realr\nImports: realdep\n", encoding="utf-8"
    )

    result = _json_result(
        run_tool({"path": str(project), "format": "json", "include_relations": True})
    )
    project_files = result["project"]["files"]
    assert any(path.endswith("DESCRIPTION") for path in project_files)
    assert not any(path.endswith("description") for path in project_files)
    dep_names = {dep["name"] for dep in result["project"]["dependencies"]}
    assert "realdep" in dep_names
    assert "notanrpackage" not in dep_names


def test_lockfile_discovery_skips_generated_trees_but_keeps_obj_assets(
    repo_tmp_path: Path,
) -> None:
    project = repo_tmp_path / "project"
    (project / "node_modules").mkdir(parents=True)
    (project / "obj").mkdir()
    (project / "package.json").write_text("{}\n", encoding="utf-8")
    (project / "composer.lock").write_text(
        '{"packages": [{"name": "real/pkg", "version": "1.0.0"}]}',
        encoding="utf-8",
    )
    (project / "node_modules" / "composer.lock").write_text(
        '{"packages": [{"name": "decoy/pkg", "version": "9.9.9"}]}',
        encoding="utf-8",
    )
    # NuGet assets live under obj/ by design and must still be read.
    (project / "obj" / "project.assets.json").write_text(
        '{"libraries": {"Newtonsoft.Json/13.0.0": {}}, "targets": {}}',
        encoding="utf-8",
    )

    result = _json_result(
        run_tool({"path": str(project), "format": "json", "include_relations": True})
    )
    transitive = result["project"]["transitive_dependencies"]
    names = {(dep["manager"], dep["name"]) for dep in transitive}
    assert ("Composer", "real/pkg") in names
    assert ("Composer", "decoy/pkg") not in names
    assert ("NuGet", "Newtonsoft.Json") in names


def test_project_source_collection_skips_venv(repo_tmp_path: Path) -> None:
    project = repo_tmp_path / "project"
    package = project / "pkg"
    (package / ".venv" / "lib").mkdir(parents=True)
    (package / "pyproject.toml").write_text(
        "[project]\nname='demo'\n", encoding="utf-8"
    )
    (package / "mod.py").write_text("VALUE = 1\n", encoding="utf-8")
    (package / ".venv" / "lib" / "decoy.py").write_text("VALUE = 2\n", encoding="utf-8")

    result = _json_result(
        run_tool({"path": str(project), "format": "json", "project_only": True})
    )
    paths = {entry["relative_path"].replace("\\", "/") for entry in result["files"]}
    assert "pkg/mod.py" in paths
    assert not any("decoy.py" in path for path in paths)


# Keep the test module free of generated code-map artifacts.


def test_swift_package_resolved_under_swiftpm_is_found(repo_tmp_path: Path) -> None:
    project = repo_tmp_path / "project"
    workspace = (
        project
        / ".swiftpm"
        / "xcode"
        / "package.xcworkspace"
        / "xcshareddata"
        / "swiftpm"
    )
    workspace.mkdir(parents=True)
    (project / "Package.swift").write_text(
        "// swift-tools-version:5.9\nimport PackageDescription\n", encoding="utf-8"
    )
    (workspace / "Package.resolved").write_text(
        json.dumps(
            {
                "pins": [
                    {
                        "identity": "alamofire",
                        "kind": "remoteSourceControl",
                        "location": "https://github.com/Alamofire/Alamofire.git",
                        "state": {"version": "5.9.1"},
                    }
                ],
                "version": 2,
            }
        ),
        encoding="utf-8",
    )
    # Other hidden trees stay pruned even for Package.resolved.
    (project / ".hidden").mkdir()
    (project / ".hidden" / "Package.resolved").write_text(
        json.dumps(
            {
                "pins": [
                    {
                        "identity": "decoy",
                        "kind": "remoteSourceControl",
                        "location": "https://example.com/decoy.git",
                        "state": {"version": "0.0.1"},
                    }
                ],
                "version": 2,
            }
        ),
        encoding="utf-8",
    )

    from uagent.tools.code_map_impl.lockfiles import extract_lock_dependencies

    dep_names = {dep["name"] for dep in extract_lock_dependencies(project)}
    assert "alamofire" in dep_names
    assert "decoy" not in dep_names
