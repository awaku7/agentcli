from __future__ import annotations

import uagent.core as core
from uagent.core_impl import console
from uagent import reasoning_display
from uagent.cli_impl import prompt_session


def test_windows_vt_mode_can_be_disabled(monkeypatch):
    monkeypatch.setattr(console.os, "name", "nt")
    monkeypatch.setattr(
        console,
        "env_get",
        lambda name, default=None: "0" if name == "UAGENT_WINDOWS_VT_MODE" else default,
    )
    assert console._enable_windows_vt_mode() is False


def test_reasoning_does_not_enable_windows_vt_when_disabled(monkeypatch):
    monkeypatch.setattr(reasoning_display.sys, "platform", "win32")
    monkeypatch.setattr(
        reasoning_display,
        "env_get",
        lambda name, default=None: "0" if name == "UAGENT_WINDOWS_VT_MODE" else default,
    )
    assert reasoning_display._enable_vt_if_windows() is False


def test_prompt_output_uses_legacy_backend_when_vt_is_disabled(monkeypatch):
    monkeypatch.setattr(prompt_session.sys, "platform", "win32")
    monkeypatch.setattr(core, "_enable_windows_vt_mode", lambda: False)
    assert prompt_session._create_prompt_output() is None
