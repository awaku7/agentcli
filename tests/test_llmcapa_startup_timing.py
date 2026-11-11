"""Timing instrumentation for the startup llmcapa capability lookup."""

import sys
from types import SimpleNamespace

from uagent import llmcapa_util


def test_llmcapa_catalog_import_and_scoped_lookup_timing(monkeypatch, capsys):
    monkeypatch.setenv("UAGENT_STARTUP_TIMING", "1")
    capability = SimpleNamespace()
    stub = SimpleNamespace(get=lambda *_args, **_kwargs: capability)
    monkeypatch.setitem(sys.modules, "llmcapa", stub)
    llmcapa_util._get_capability_cached.cache_clear()
    try:
        assert llmcapa_util.get_capability("test-model", "openai") is capability
        output = capsys.readouterr().err
        assert "[startup-timing] detail.llmcapa.catalog_import=" in output
        assert "[startup-timing] detail.llmcapa.scoped_get=" in output
    finally:
        llmcapa_util._get_capability_cached.cache_clear()
