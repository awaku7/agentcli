from __future__ import annotations

import builtins
import threading
from types import ModuleType, SimpleNamespace

from uagent import cli_startup
from uagent.providers import util_providers


def test_provider_sdk_module_mapping(monkeypatch):
    assert util_providers.provider_sdk_module("openai") == "openai"
    assert util_providers.provider_sdk_module("claude") == "anthropic"
    assert util_providers.provider_sdk_module("gemini") == "google.genai"
    assert util_providers.provider_sdk_module("grok") is None

    monkeypatch.setenv("UAGENT_LMSTUDIO_TRANSPORT", "sdk")
    assert util_providers.provider_sdk_module("lmstudio") == "lmstudio"
    monkeypatch.setenv("UAGENT_LMSTUDIO_TRANSPORT", "http")
    assert util_providers.provider_sdk_module("lmstudio") == "openai"


def test_openai_sdk_preload_also_imports_httpx(monkeypatch):
    imports: list[str] = []
    real_import = builtins.__import__

    def import_sdk(name, globals=None, locals=None, fromlist=(), level=0):
        if name in {"openai", "httpx"}:
            imports.append(name)
            return ModuleType(name)
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", import_sdk)
    assert cli_startup._preload_provider_sdk("openai") is True
    assert imports == ["openai", "httpx"]


def test_provider_sdk_import_overlaps_but_client_stays_on_cli_thread(monkeypatch):
    result = ("openai", object(), "test-model")
    import_threads: list[str] = []
    client_threads: list[str] = []
    providers = SimpleNamespace(
        detect_provider=lambda: "openai",
        provider_sdk_module=lambda provider: "test_preload_sdk",
        make_client=lambda _core: (
            client_threads.append(threading.current_thread().name),
            result,
        )[1],
    )
    real_import = builtins.__import__

    def import_sdk(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "test_preload_sdk":
            import_threads.append(threading.current_thread().name)
            return ModuleType(name)
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", import_sdk)
    executor, future = cli_startup._start_provider_client_preload(providers)
    assert executor is not None
    try:
        assert (
            cli_startup._resolve_provider_client_preload(object(), providers, future)
            == result
        )
        assert import_threads and import_threads[0].startswith("uag-provider")
        assert client_threads == [threading.current_thread().name]
    finally:
        executor.shutdown(wait=True, cancel_futures=True)


def test_missing_sdk_falls_back_to_foreground_client_path(monkeypatch):
    result = ("openai", object(), "test-model")
    client_threads: list[str] = []
    providers = SimpleNamespace(
        detect_provider=lambda: "openai",
        provider_sdk_module=lambda provider: "missing_preload_sdk",
        make_client=lambda _core: (
            client_threads.append(threading.current_thread().name),
            result,
        )[1],
    )
    real_import = builtins.__import__

    def import_sdk(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "missing_preload_sdk":
            raise ModuleNotFoundError(name)
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", import_sdk)
    executor, future = cli_startup._start_provider_client_preload(providers)
    assert executor is not None
    try:
        assert (
            cli_startup._resolve_provider_client_preload(object(), providers, future)
            == result
        )
        assert client_threads == [threading.current_thread().name]
    finally:
        executor.shutdown(wait=True, cancel_futures=True)


def test_provider_with_custom_dependency_handling_is_not_preloaded():
    providers = SimpleNamespace(detect_provider=lambda: "grok")
    assert cli_startup._start_provider_client_preload(providers) == (None, None)
