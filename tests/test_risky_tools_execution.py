from __future__ import annotations

import json
import os

import pytest

from uagent.tools.cmd_exec_json_tool import run_tool as cmd_exec_json
from uagent.tools.cmd_exec_tool import run_tool as cmd_exec
from uagent.tools.fetch_url_tool import run_tool as fetch_url
from uagent.tools.get_geoip_tool import run_tool as get_geoip
from uagent.tools.git_ops_tool import run_tool as git_ops
from uagent.tools.pwsh_exec_tool import run_tool as pwsh_exec
from uagent.tools.search_web_tool import run_tool as search_web


def test_cmd_exec_smoke_prints_ok() -> None:
    # Keep commands harmless.
    out = cmd_exec({"command": "echo ok"})
    assert isinstance(out, str)
    assert "ok" in out.lower()


def test_cmd_exec_json_smoke() -> None:
    out = cmd_exec_json({"command": "echo ok", "cwd": None})
    obj = json.loads(out)
    assert isinstance(obj, dict)
    assert obj.get("returncode") == 0


@pytest.mark.skipif(os.name != "nt", reason="PowerShell tool is Windows-only")
def test_pwsh_exec_smoke() -> None:
    out = pwsh_exec({"command": "Write-Output ok", "shell": "pwsh"})
    assert isinstance(out, str)
    assert "ok" in out.lower()


def test_git_ops_status_is_safe() -> None:
    # Read-only-ish commands only.
    out = git_ops({"command": "status", "args": [], "allow_danger": False})
    assert isinstance(out, str)
    assert out


def test_fetch_url_example_com_is_robust() -> None:
    """Network/SSL can be environment-dependent.

    - If ok==True, assert response includes 'example'
    - If ok==False, just assert it returned an error string.
    """

    out = fetch_url({"url": "https://example.com"})
    assert isinstance(out, str) and out

    obj = json.loads(out)
    assert isinstance(obj, dict)

    if obj.get("ok") is True:
        text = str(obj.get("text") or "")
        assert "example" in text.lower()
    else:
        err = str(obj.get("error") or "")
        assert err


def test_search_web_smoke() -> None:
    out = search_web({"query": "example.com", "max_results": 3, "q": "", "n": 0})
    payload = json.loads(out)
    assert isinstance(payload, dict)
    results = payload.get("results")
    assert isinstance(results, list)
    assert results, "expected at least 1 result"


def test_get_geoip_smoke() -> None:
    out = get_geoip({"format": "json"})
    obj = json.loads(out)
    assert isinstance(obj, dict)
    # country/region/city may vary; just ensure some keys exist
    assert obj, "expected non-empty geoip result"
