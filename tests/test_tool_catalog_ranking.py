from __future__ import annotations

from uagent import tools


def test_broad_file_search_prefers_filename_search() -> None:
    names = [
        row["name"]
        for row in tools.get_tool_catalog(query="search files", max_results=6)
    ]

    assert names[0] == "search_files"
    assert "file_grep" not in names


def test_explicit_grep_intent_keeps_file_grep_available() -> None:
    names = [
        row["name"]
        for row in tools.get_tool_catalog(
            query="grep regex pattern in files", max_results=6
        )
    ]

    assert names[0] == "file_grep"
