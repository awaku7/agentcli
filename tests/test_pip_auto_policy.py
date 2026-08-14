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
