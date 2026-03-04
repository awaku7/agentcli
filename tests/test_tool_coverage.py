from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest


def _iter_tool_module_paths() -> list[Path]:
    repo_root = Path(__file__).resolve().parents[1]
    tools_dir = repo_root / "src" / "uagent" / "tools"
    out: list[Path] = []
    for p in sorted(tools_dir.glob("*.py")):
        if p.name == "__init__.py":
            continue
        out.append(p)
    return out


def _module_name_from_path(p: Path) -> str:
    return f"uagent.tools.{p.stem}"


def _tool_name_from_spec(spec: dict[str, Any]) -> str:
    fn = spec.get("function") or {}
    return str(fn.get("name") or "")


def _safe_or_skip_reason(tool_name: str) -> str | None:
    """Return skip reason if tool should not be executed under policy A."""

    # Destructive file ops
    if tool_name in {"delete_file", "binary_edit"}:
        return "Destructive file operation"

    # External commands / process execution
    if tool_name in {
        "cmd_exec",
        "cmd_exec_json",
        "pwsh_exec",
        "spawn_process",
        "git_ops",
        "run_tests",
        "lint_format",
        "libcst_transform",
        "system_reload",
        "change_workdir",
    }:
        return "External process / repo-modifying operation"

    # Network / external services
    if tool_name in {
        "fetch_url",
        "search_web",
        "get_geoip",
        "handle_mcp_v2",
        "mcp_tools_list",
        "graph_rag_search",
        "index_files",
        "semantic_search_files",
    }:
        return "Network/service dependent"

    # GUI dependent
    if tool_name in {"screenshot", "playwright_inspector", "list_windows_titles"}:
        return "GUI/desktop dependent"

    # Requires user interaction
    if tool_name in {"human_ask"}:
        return "Interactive tool"

    # External providers
    if tool_name in {"generate_image", "analyze_image"}:
        return "Provider/API dependent"

    # Memory tools depend on env configuration (may write files). Keep as skip.
    if tool_name in {"add_long_memory", "get_long_memory", "add_shared_memory", "get_shared_memory"}:
        return "Environment-dependent persistence"

    # Heavy/format-dependent tools: treat as skip for now.
    if tool_name in {"read_pptx_pdf", "excel_ops", "exstruct"}:
        return "Requires binary fixtures / office formats"

    # Skills tools are safe-ish but depend on skills dir content; skip by default.
    if tool_name in {"skills_list", "skills_load", "skills_read_file", "skills_validate"}:
        return "Depends on skills directory content"

    # rename_path can be safe but still modifies filesystem; skip under conservative policy.
    if tool_name in {"rename_path"}:
        return "Filesystem-modifying operation"

    # set_timer: would delay the test suite.
    if tool_name in {"set_timer"}:
        return "Time-dependent (would sleep)"

    return None


@pytest.mark.parametrize("modname", [_module_name_from_path(p) for p in _iter_tool_module_paths()])
def test_all_tool_specs_are_covered_by_exec_or_explicit_skip(modname: str) -> None:
    mod = importlib.import_module(modname)
    spec = getattr(mod, "TOOL_SPEC", None)
    if not isinstance(spec, dict):
        pytest.skip("No TOOL_SPEC")

    tool_name = _tool_name_from_spec(spec)
    if not tool_name:
        pytest.fail(f"{modname}: TOOL_SPEC missing function.name")

    reason = _safe_or_skip_reason(tool_name)
    if reason:
        pytest.skip(reason)

    # If it's not explicitly skipped, require that the module provides run_tool.
    runner = getattr(mod, "run_tool", None)
    assert callable(runner), f"{modname}: expected callable run_tool()"

    # We intentionally do not auto-execute arbitrary tools here.
    # Execution coverage lives in dedicated smoke tests.
    # This test enforces that any tool we don't skip is at least runnable.
