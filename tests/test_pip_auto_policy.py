from __future__ import annotations

from uagent import _pip_auto


def test_off_never_runs_pip(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_AUTO_INSTALL", "off")
    called = []
    monkeypatch.setattr(_pip_auto.subprocess, "run", lambda *a, **k: called.append(a))

    assert not _pip_auto.auto_install("fastapi", "missing_module")
    assert called == []


def test_unknown_packages_are_not_installed(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_AUTO_INSTALL", "allow")
    called = []
    monkeypatch.setattr(_pip_auto.subprocess, "run", lambda *a, **k: called.append(a))

    assert not _pip_auto.auto_install("untrusted-package", "missing_module")
    assert called == []


def test_case_insensitive_package_allowed(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_AUTO_INSTALL", "allow")
    called = []
    monkeypatch.setattr(_pip_auto.subprocess, "run", lambda *a, **k: called.append(a))

    assert not _pip_auto.auto_install(
        "winrt-Windows.Devices.Geolocation", "missing_module"
    )
    assert len(called) == 1


def test_confirm_install_asks_via_human_ask_when_view_active(monkeypatch) -> None:
    # Regression (PR #483 Codex P2): with UAGENT_AUTO_INSTALL=prompt
    # and the console view owning the terminal, _confirm_install's
    # direct input() raced the view's stdin reading.  While a view
    # is active the confirmation goes through human_ask.
    import json

    from uagent.runtime import display_channel as dc

    tty = type(
        "TTY",
        (),
        {
            "isatty": lambda self: True,
            "write": lambda self, _s: 0,
            "flush": lambda self: None,
        },
    )()
    monkeypatch.setattr(_pip_auto.sys, "stdin", tty)
    monkeypatch.setattr(_pip_auto.sys, "stderr", tty)
    monkeypatch.setattr(dc, "_active_console_view", lambda: object())
    monkeypatch.setattr(
        "builtins.input",
        lambda prompt: (_ for _ in ()).throw(AssertionError("direct read")),
    )

    monkeypatch.setattr(
        "uagent.tools.run_tool",
        lambda name, args: json.dumps({"user_reply": "y"}),
    )
    assert _pip_auto._confirm_install("markitdown") is True

    monkeypatch.setattr(
        "uagent.tools.run_tool",
        lambda name, args: json.dumps({"user_reply": "n"}),
    )
    assert _pip_auto._confirm_install("markitdown") is False


def test_confirm_install_reads_directly_without_a_view(monkeypatch) -> None:
    from uagent.runtime import display_channel as dc

    tty = type(
        "TTY",
        (),
        {
            "isatty": lambda self: True,
            "write": lambda self, _s: 0,
            "flush": lambda self: None,
        },
    )()
    monkeypatch.setattr(_pip_auto.sys, "stdin", tty)
    monkeypatch.setattr(_pip_auto.sys, "stderr", tty)
    monkeypatch.setattr(dc, "_active_console_view", lambda: None)
    monkeypatch.setattr("builtins.input", lambda prompt: "y")

    assert _pip_auto._confirm_install("markitdown") is True
