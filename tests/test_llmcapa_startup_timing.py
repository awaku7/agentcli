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


def test_capability_miss_during_catalog_load_is_not_cached(monkeypatch):
    """A lookup that misses while the catalog loads must be retried later.

    llmcapa raises ModelNotFoundError for existing models while its first
    load runs in another thread. If that miss were cached, the model would
    stay "unknown" for the whole process (e.g. native tool_search would
    never engage for gpt-6-luna on the Responses route).
    """
    capability = SimpleNamespace()
    state = {"loading": True}
    calls = {"n": 0}

    def flaky_get(*_args, **_kwargs):
        calls["n"] += 1
        if state["loading"]:
            raise RuntimeError("catalog still loading")
        return capability

    stub = SimpleNamespace(get=flaky_get)
    monkeypatch.setitem(sys.modules, "llmcapa", stub)
    llmcapa_util._get_capability_cached.cache_clear()
    try:
        assert llmcapa_util.get_capability("test-model", "openai") is None
        state["loading"] = False
        assert llmcapa_util.get_capability("test-model", "openai") is capability
        calls_after_hit = calls["n"]
        # A successful result is cached: no further llmcapa calls.
        assert llmcapa_util.get_capability("test-model", "openai") is capability
        assert calls["n"] == calls_after_hit
    finally:
        llmcapa_util._get_capability_cached.cache_clear()
