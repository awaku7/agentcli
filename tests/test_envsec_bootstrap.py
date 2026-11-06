from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from uagent import _envsec_bootstrap as bootstrap
from uagent import _pip_auto


def _missing(name: str) -> ModuleNotFoundError:
    exc = ModuleNotFoundError(f"No module named '{name}'")
    exc.name = name
    return exc


def test_available_envsec_never_runs_pip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        bootstrap.importlib, "import_module", lambda name: SimpleNamespace()
    )

    def unexpected(*args, **kwargs):
        pytest.fail("pip must not run when uag_envsec is importable")

    monkeypatch.setattr(bootstrap.subprocess, "run", unexpected)
    bootstrap.ensure_envsec_available()


def test_missing_envsec_is_reinstalled_once(monkeypatch: pytest.MonkeyPatch) -> None:
    imports: list[str] = []
    calls: list[tuple[list[str], dict]] = []

    def importing(name: str):
        imports.append(name)
        if len(imports) == 1:
            raise _missing("uag_envsec")
        return SimpleNamespace()

    def running(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(bootstrap.importlib, "import_module", importing)
    monkeypatch.setattr(_pip_auto, "_may_install", lambda name: name == "uag-envsec")
    monkeypatch.setattr(bootstrap.subprocess, "run", running)

    bootstrap.ensure_envsec_available()

    assert imports == ["uag_envsec", "uag_envsec"]
    assert len(calls) == 1
    assert calls[0][0] == [
        bootstrap.sys.executable,
        "-m",
        "pip",
        "install",
        "--force-reinstall",
        "--no-deps",
        "uag-envsec>=0.1.1",
    ]
    assert calls[0][1]["check"] is True


def test_policy_off_does_not_install(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(name):
        raise _missing("uag_envsec")

    monkeypatch.setattr(bootstrap.importlib, "import_module", missing)
    monkeypatch.setattr(_pip_auto, "_may_install", lambda name: False)

    def unexpected(*args, **kwargs):
        pytest.fail("pip must not run when auto-install is disabled")

    monkeypatch.setattr(bootstrap.subprocess, "run", unexpected)
    with pytest.raises(ModuleNotFoundError, match="--force-reinstall"):
        bootstrap.ensure_envsec_available()


def test_transitive_missing_module_is_not_repaired(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(name):
        raise _missing("cryptography")

    monkeypatch.setattr(bootstrap.importlib, "import_module", missing)
    with pytest.raises(ModuleNotFoundError) as error:
        bootstrap.ensure_envsec_available()
    assert error.value.name == "cryptography"


def test_failed_repair_includes_manual_command(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(name):
        raise _missing("uag_envsec")

    def failing(command, **kwargs):
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(bootstrap.importlib, "import_module", missing)
    monkeypatch.setattr(_pip_auto, "_may_install", lambda name: True)
    monkeypatch.setattr(bootstrap.subprocess, "run", failing)
    with pytest.raises(ModuleNotFoundError, match="--force-reinstall"):
        bootstrap.ensure_envsec_available()


def test_missing_after_reinstall_includes_manual_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(name):
        raise _missing("uag_envsec")

    monkeypatch.setattr(bootstrap.importlib, "import_module", missing)
    monkeypatch.setattr(_pip_auto, "_may_install", lambda name: True)
    monkeypatch.setattr(
        bootstrap.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0),
    )
    with pytest.raises(ModuleNotFoundError, match="still missing after repair"):
        bootstrap.ensure_envsec_available()
