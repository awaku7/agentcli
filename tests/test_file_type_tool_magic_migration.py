from __future__ import annotations

import io
import sys
from types import SimpleNamespace
from unittest.mock import Mock

from uagent.tools import file_type_tool


def test_windows_generic_magic_is_replaced_with_bin(monkeypatch):
    monkeypatch.setattr(file_type_tool, "_os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(
        file_type_tool,
        "_distribution_is_installed",
        lambda name: name == "python-magic",
    )

    module_cache = {"magic": object(), "magic.loader": object(), "unrelated": object()}
    invalidate_caches = Mock()
    monkeypatch.setattr(
        file_type_tool,
        "_sys",
        SimpleNamespace(
            executable=sys.executable,
            stderr=io.StringIO(),
            modules=module_cache,
        ),
    )
    monkeypatch.setattr(
        file_type_tool,
        "_importlib",
        SimpleNamespace(invalidate_caches=invalidate_caches),
    )

    run = Mock(
        side_effect=[SimpleNamespace(returncode=0), SimpleNamespace(returncode=0)]
    )
    monkeypatch.setattr(file_type_tool, "_subprocess", SimpleNamespace(run=run))
    monkeypatch.setattr("uagent._pip_auto._may_install", lambda *a, **kw: True)

    assert file_type_tool._remove_windows_python_magic_conflict() is True
    commands = [call.args[0] for call in run.call_args_list]
    assert commands[0][3:] == ["uninstall", "-y", "python-magic"]
    assert commands[1][3:7] == [
        "install",
        "--force-reinstall",
        "--no-deps",
        "python-magic-bin",
    ]
    assert "magic" not in module_cache
    assert "magic.loader" not in module_cache
    assert "unrelated" in module_cache
    invalidate_caches.assert_called_once_with()


def test_windows_generic_magic_is_not_removed_when_install_is_disallowed(monkeypatch):
    monkeypatch.setattr(file_type_tool, "_os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(
        file_type_tool,
        "_distribution_is_installed",
        lambda name: name == "python-magic",
    )
    run = Mock()
    monkeypatch.setattr(file_type_tool, "_subprocess", SimpleNamespace(run=run))
    monkeypatch.setattr("uagent._pip_auto._may_install", lambda *a, **kw: False)

    assert file_type_tool._remove_windows_python_magic_conflict() is False
    run.assert_not_called()


def test_non_windows_does_not_remove_python_magic(monkeypatch):
    monkeypatch.setattr(file_type_tool, "_os", SimpleNamespace(name="posix"))
    run = Mock()
    monkeypatch.setattr(file_type_tool, "_subprocess", SimpleNamespace(run=run))

    assert file_type_tool._remove_windows_python_magic_conflict() is True
    run.assert_not_called()
