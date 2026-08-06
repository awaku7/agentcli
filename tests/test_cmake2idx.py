from __future__ import annotations

from pathlib import Path

from uagent.tools.cmake2idx_tool import run_tool


def test_cmake_index_and_section() -> None:
    path = Path("tests/._cmake_CMakeLists.txt")
    path.write_text(
        "cmake_minimum_required(VERSION 3.24)\n"
        "project(MyApp)\n"
        "find_package(Threads REQUIRED)\n"
        "add_executable(app main.cpp)\n"
        "target_link_libraries(app PRIVATE Threads::Threads)\n",
        encoding="utf-8",
    )
    try:
        index = run_tool({"path": str(path), "mode": "index"})
        assert "Project metadata" in index
        section = run_tool({"path": str(path), "mode": "section", "section": 2})
        assert "add_executable" in section
    finally:
        path.unlink(missing_ok=True)


def test_cmake_preset_index() -> None:
    path = Path("tests/CMakePresets.json")
    path.write_text(
        '{"version": 6, "configurePresets": [{"name": "debug", "generator": "Ninja"}]}',
        encoding="utf-8",
    )
    try:
        section = run_tool({"path": str(path), "mode": "section", "section": 1})
        assert "debug" in section
    finally:
        path.unlink(missing_ok=True)
