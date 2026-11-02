"""The retained source launcher dispatches to the independently installed host."""

from pathlib import Path
import runpy
import sys
from types import SimpleNamespace

import pytest


def _launcher(monkeypatch):
    from uagent import checks

    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(checks, "check_git_installation", lambda: None)
    return runpy.run_path(str(Path(__file__).parents[1] / "scheck.py"))["main"]


@pytest.mark.parametrize(
    ("mode", "module"),
    [
        ("web", "uag_web.server"),
        ("cli", "uagent.cli"),
        ("gui", "uagent.gui"),
        ("a2a", "uagent.a2a.server"),
    ],
)
def test_source_launcher_dispatches_entry_points(monkeypatch, mode, module):
    launcher = _launcher(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["scheck.py", mode])
    monkeypatch.setenv("UAGENT_GUI_MODE", "0")
    calls = []

    def load(name, **kwargs):
        assert name == module
        return SimpleNamespace(main=lambda *args: calls.append(args))

    monkeypatch.setitem(launcher.__globals__, "__import__", load)
    launcher()
    expected = [([],)] if mode == "a2a" else [()]
    assert calls == expected


def test_source_launcher_explains_missing_web_install(monkeypatch, capsys):
    launcher = _launcher(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["scheck.py", "web"])

    def missing(name, **kwargs):
        raise ModuleNotFoundError("No module named 'uag_web'", name="uag_web")

    monkeypatch.setitem(launcher.__globals__, "__import__", missing)
    with pytest.raises(SystemExit) as exited:
        launcher()
    assert exited.value.code == 1
    assert "python -m pip install uag-web" in capsys.readouterr().out
