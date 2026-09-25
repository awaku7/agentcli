from __future__ import annotations

import sys
import types

import pytest


@pytest.mark.parametrize(
    ("flag", "expected"),
    [("--otel", True), ("--no-otel", False)],
)
def test_a2a_main_accepts_explicit_otel_argv(
    monkeypatch: pytest.MonkeyPatch, flag: str, expected: bool
) -> None:
    import uagent
    from uagent.a2a import server
    from uagent.runtime.observability.settings import (
        _reset_observability_settings_for_tests,
        get_observability_settings,
        refresh_observability_settings,
    )

    class _Stdout:
        def reconfigure(self, **_kwargs) -> None:
            return None

    _reset_observability_settings_for_tests()
    monkeypatch.delenv("UAGENT_OTEL_ENABLED", raising=False)
    monkeypatch.setattr(sys, "stdout", _Stdout())

    monkeypatch.setattr(
        server,
        "reload_dotenv_custom",
        lambda: refresh_observability_settings(environ={}),
    )
    monkeypatch.setattr(
        server,
        "validate_or_exit_startup_env",
        lambda *, context: None,
    )

    fake_cli_startup = types.ModuleType("uagent.cli_startup")
    fake_cli_startup._apply_startup_tool_genre_mask = lambda _mask: None
    monkeypatch.setitem(sys.modules, "uagent.cli_startup", fake_cli_startup)

    fake_tools = types.ModuleType("uagent.tools")
    fake_tools.configure_default_confirmation = lambda: None
    monkeypatch.setitem(sys.modules, "uagent.tools", fake_tools)

    fake_core = types.SimpleNamespace(tools_enabled=True)
    monkeypatch.setattr(uagent, "core", fake_core, raising=False)

    app = object()
    monkeypatch.setattr(server, "build_app", lambda *, recover_tasks: app)
    uvicorn_calls: list[tuple[object, str, int, bool]] = []
    monkeypatch.setattr(
        server.uvicorn,
        "run",
        lambda value, *, host, port, reload: uvicorn_calls.append(
            (value, host, port, reload)
        ),
    )

    server.main([flag, "--host", "127.0.0.1", "--port", "9876"])

    settings = get_observability_settings()
    assert settings.enabled is expected
    assert settings.enabled_source == "explicit"
    assert uvicorn_calls == [(app, "127.0.0.1", 9876, False)]
