from __future__ import annotations

import builtins
import importlib

from uagent import _pip_auto
from uagent.tools.mcp import client as mcp_client


def test_importing_mcp_client_does_not_install_optional_sdk(monkeypatch) -> None:
    real_import = builtins.__import__
    install_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def import_without_mcp(name: str, *args: object, **kwargs: object):
        if name == "mcp" or name.startswith("mcp."):
            raise ImportError("MCP SDK intentionally unavailable in this test")
        return real_import(name, *args, **kwargs)

    def record_install(*args: object, **kwargs: object) -> bool:
        install_calls.append((args, kwargs))
        return False

    monkeypatch.setattr(builtins, "__import__", import_without_mcp)
    monkeypatch.setattr(_pip_auto, "install_with_status", record_install)

    importlib.reload(mcp_client)

    assert install_calls == []
