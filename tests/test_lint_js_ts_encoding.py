from __future__ import annotations

from types import SimpleNamespace

from uagent.tools import lint_js_ts_tool


def test_windows_npx_runner_keeps_output_as_bytes(monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return SimpleNamespace(
            returncode=1,
            stdout=b'{"summary":{"errors":1,"warnings":0},"message":"\xe2\x80\x94"}',
            stderr=b"\x97",
        )

    monkeypatch.setattr(lint_js_ts_tool.subprocess, "run", fake_run)
    result = lint_js_ts_tool._run_npx(
        ["--yes", "@biomejs/biome", "check"],
        timeout=60,
        filepath="frontend/src/App.svelte",
        is_windows=True,
    )

    assert captured["command"] == (
        "npx.cmd --yes @biomejs/biome check frontend/src/App.svelte"
    )
    assert captured["shell"] is True
    assert captured["capture_output"] is True
    assert "text" not in captured
    assert "encoding" not in captured
    assert lint_js_ts_tool._decode_npx_output(result.stdout).startswith('{"summary"')
    assert lint_js_ts_tool._decode_npx_output(result.stderr) == "�"


def test_biome_output_utf8_is_decoded_before_json_parsing():
    output = '{"summary":{"errors":2,"warnings":1},"message":"lint — issue"}'

    assert (
        lint_js_ts_tool._parse_biome_output(
            lint_js_ts_tool._decode_npx_output(output.encode("utf-8"))
        )
        == 3
    )
