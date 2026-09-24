"""Regression tests for mdformat tool diagnostics."""

import json
from subprocess import CompletedProcess

from uagent.tools import mdformat_tool


def test_format_failure_keeps_multiline_mdformat_diagnostic(tmp_path, monkeypatch):
    markdown = tmp_path / "example.md"
    markdown.write_text("# Example\n", encoding="utf-8")

    monkeypatch.setattr(mdformat_tool, "_ensure_mdformat", lambda: True)
    monkeypatch.setattr(
        mdformat_tool.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(
            args=args[0],
            returncode=1,
            stdout="",
            stderr=f'Error: File "{markdown}" is not\nformatted.\n',
        ),
    )

    result = json.loads(mdformat_tool.run_tool({"path": str(markdown)}))

    assert result["data"]["format_ok"] is False
    assert result["data"]["failed"] == 1
    assert f'Error: File "{markdown}" is not\nformatted.' in result["data"]["detail"]
