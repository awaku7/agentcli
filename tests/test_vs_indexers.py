from __future__ import annotations

from pathlib import Path

from uagent.tools.msbuild2idx_tool import run_tool as run_msbuild
from uagent.tools.sln2idx_tool import run_tool as run_sln


def _write(name: str, content: str) -> Path:
    path = Path("tests") / name
    path.write_text(content, encoding="utf-8")
    return path


def test_msbuild_index_and_section() -> None:
    path = _write(
        "._vs_App.csproj",
        '<Project Sdk="Microsoft.NET.Sdk">\n'
        "  <PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup>\n"
        '  <ItemGroup><ProjectReference Include="../Core/Core.csproj" /></ItemGroup>\n'
        "</Project>\n",
    )
    try:
        index = run_msbuild({"path": str(path), "mode": "index"})
        assert "SDK: Microsoft.NET.Sdk" in index
        assert "PropertyGroup" in index
        section = run_msbuild({"path": str(path), "mode": "section", "section": 2})
        assert "ProjectReference" in section
    finally:
        path.unlink(missing_ok=True)


def test_sln_index_and_section() -> None:
    path = _write(
        "._vs_App.sln",
        "Microsoft Visual Studio Solution File, Format Version 12.00\n"
        'Project("{TYPE}") = "App", "App\\App.csproj", "{APP}"\n'
        "EndProject\n",
    )
    try:
        index = run_sln({"path": str(path), "mode": "index"})
        assert "Projects" in index
        section = run_sln({"path": str(path), "mode": "section", "section": 1})
        assert "App" in section
    finally:
        path.unlink(missing_ok=True)


def test_slnx_index() -> None:
    path = _write(
        "._vs_App.slnx",
        '<Solution><Project Path="App/App.csproj" Name="App" /></Solution>',
    )
    try:
        result = run_sln({"path": str(path), "mode": "section", "section": 1})
        assert "App/App.csproj" in result
    finally:
        path.unlink(missing_ok=True)


def test_indexers_reject_unsafe_xml() -> None:
    path = _write(
        "._vs_bad.csproj",
        "<!DOCTYPE Project [<!ENTITY x SYSTEM 'file:///secret'>]><Project />",
    )
    try:
        result = run_msbuild({"path": str(path), "mode": "index"})
        assert "DTD" in result
    finally:
        path.unlink(missing_ok=True)
