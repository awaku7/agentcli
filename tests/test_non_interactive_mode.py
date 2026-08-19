from __future__ import annotations

import json
from pathlib import Path


def test_non_interactive_mode_skips_project_instructions(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "AGENTS.md").write_text("do not load me", encoding="utf-8")
    monkeypatch.setenv("UAGENT_NON_INTERACTIVE", "1")

    from uagent.runtime.runtime_instructions import load_project_instruction_files

    assert load_project_instruction_files(workdir=str(tmp_path)) == []


def test_non_interactive_mode_human_ask_does_not_wait(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_NON_INTERACTIVE", "1")

    from uagent.tools.human_ask_tool import run_tool

    result = json.loads(run_tool({"message": "continue?"}))
    assert result["non_interactive_skipped"] is True
    assert result["cancelled"] is False
    assert result["user_reply"] == ""
