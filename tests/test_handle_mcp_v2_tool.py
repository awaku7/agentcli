from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest


def test_handle_mcp_v2_requires_tool_name() -> None:
    from uagent.tools.handle_mcp_v2_tool import run_tool

    out = run_tool({})
    assert isinstance(out, str)
    assert (
        "tool_name" in out.lower()
        or "required" in out.lower()
        or "error" in out.lower()
    )


def test_handle_mcp_v2_unconfigured_returns_message() -> None:
    from uagent.tools.handle_mcp_v2_tool import run_tool

    out = run_tool({"tool_name": "x"})
    assert "not configured" in out.lower() or "no operation" in out.lower()


def test_handle_mcp_v2_server_name_not_found(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.tools.handle_mcp_v2_tool import run_tool

    cfg = repo_tmp_path / "mcp_servers.json"
    cfg.write_text(
        json.dumps(
            {"mcp_servers": [{"name": "other", "url": "http://example.com/mcp"}]}
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("UAGENT_MCP_CONFIG", str(cfg))

    out = run_tool({"server_name": "missing", "tool_name": "x"})
    assert "not found" in out.lower() or "error" in out.lower()


def test_handle_mcp_v2_uses_http_and_truncates(monkeypatch: pytest.MonkeyPatch) -> None:
    import uagent.tools.handle_mcp_v2_tool as m
    from uagent.tools.context import ToolCallbacks

    def fake_asyncio_run(coro):
        try:
            name = getattr(coro, "cr_code", None).co_name  # type: ignore[union-attr]
        except Exception:
            name = ""
        try:
            coro.close()
        except Exception:
            pass
        assert name == "_call_mcp_http"
        return "HTTP_RESULT"

    monkeypatch.setattr(m.asyncio, "run", fake_asyncio_run)

    cb = ToolCallbacks(
        truncate_output=lambda tool, text, limit: f"TRUNC({tool})[{text}]"
    )
    monkeypatch.setattr(m, "get_callbacks", lambda: cb)

    out = m.run_tool(
        {
            "url": "http://example.com",
            "tool_name": "some_tool",
            "tool_arguments": {"a": 1},
        }
    )
    assert out == "TRUNC(handle_mcp_v2)[HTTP_RESULT]"


def test_handle_mcp_v2_stdio_url_uses_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    import uagent.tools.handle_mcp_v2_tool as m
    from uagent.tools.context import ToolCallbacks

    def fake_asyncio_run(coro):
        try:
            name = getattr(coro, "cr_code", None).co_name  # type: ignore[union-attr]
        except Exception:
            name = ""
        try:
            coro.close()
        except Exception:
            pass
        assert name == "_call_mcp_stdio"
        return "STDIO_RESULT"

    monkeypatch.setattr(m.asyncio, "run", fake_asyncio_run)

    cb = ToolCallbacks(
        truncate_output=lambda tool, text, limit: f"TRUNC({tool})[{text}]"
    )
    monkeypatch.setattr(m, "get_callbacks", lambda: cb)

    out = m.run_tool({"url": "stdio://mycmd --flag", "tool_name": "some_tool"})
    assert out == "TRUNC(handle_mcp_v2)[STDIO_RESULT]"


def test_format_result_saves_returned_file_payload(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import uagent.tools.handle_mcp_v2_tool as m

    monkeypatch.setenv("UAGENT_DOWNLOAD_DIR", str(repo_tmp_path))

    payload = {
        "filename": "hello.txt",
        "mime": "text/plain",
        "data_base64": base64.b64encode(b"hello").decode("ascii"),
    }

    out = m._format_result(payload)
    assert out.startswith("[Saved] ")
    saved_path = out[len("[Saved] ") :].strip()
    p = Path(saved_path)
    assert p.exists()
    assert p.read_bytes() == b"hello"


def test_format_result_returns_server_side_saved_path() -> None:
    import uagent.tools.handle_mcp_v2_tool as m

    out = m._format_result({"saved_path": "/tmp/already_saved.bin"})
    assert out == "[Saved] /tmp/already_saved.bin"
