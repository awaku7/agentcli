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
    monkeypatch.setattr(
        _pip_auto, "_may_install", lambda name, **kwargs: name == "uag-envsec"
    )
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
    monkeypatch.setattr(_pip_auto, "_may_install", lambda name, **kwargs: False)

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
    monkeypatch.setattr(_pip_auto, "_may_install", lambda name, **kwargs: True)
    monkeypatch.setattr(bootstrap.subprocess, "run", failing)
    with pytest.raises(ModuleNotFoundError, match="--force-reinstall"):
        bootstrap.ensure_envsec_available()


def test_missing_after_reinstall_includes_manual_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(name):
        raise _missing("uag_envsec")

    monkeypatch.setattr(bootstrap.importlib, "import_module", missing)
    monkeypatch.setattr(_pip_auto, "_may_install", lambda name, **kwargs: True)
    monkeypatch.setattr(
        bootstrap.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0),
    )
    with pytest.raises(ModuleNotFoundError, match="still missing after repair"):
        bootstrap.ensure_envsec_available()


def _always_missing_envsec(name: str) -> None:
    raise _missing("uag_envsec")


def test_project_dotenv_off_prevents_install(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    (tmp_path / ".env").write_text("UAGENT_AUTO_INSTALL=off\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(bootstrap.sys, "argv", ["uag"])
    monkeypatch.delenv("UAGENT_AUTO_INSTALL", raising=False)
    monkeypatch.delenv("UAGENT_WORKDIR", raising=False)
    monkeypatch.setattr(bootstrap.importlib, "import_module", _always_missing_envsec)

    def unexpected(*args, **kwargs):
        pytest.fail("pip ran despite the project's off policy")

    monkeypatch.setattr(bootstrap.subprocess, "run", unexpected)
    with pytest.raises(ModuleNotFoundError, match="--force-reinstall"):
        bootstrap.ensure_envsec_available()


def test_project_dotenv_prompt_respected(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    (tmp_path / ".env").write_text(
        'export UAGENT_AUTO_INSTALL="prompt"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(bootstrap.sys, "argv", ["uag"])
    monkeypatch.delenv("UAGENT_AUTO_INSTALL", raising=False)
    monkeypatch.delenv("UAGENT_WORKDIR", raising=False)
    monkeypatch.setattr(bootstrap.importlib, "import_module", _always_missing_envsec)
    prompted = []

    def confirm(label):
        prompted.append(label)
        return False

    monkeypatch.setattr(_pip_auto, "_confirm_install", confirm)
    monkeypatch.setattr(
        bootstrap.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("pip ran without consent"),
    )
    with pytest.raises(ModuleNotFoundError):
        bootstrap.ensure_envsec_available()
    assert prompted == ["uag-envsec"]


def test_cli_workdir_policy_is_used(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".env").write_text("UAGENT_AUTO_INSTALL=off\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(bootstrap.sys, "argv", ["uag", "-C", str(project)])
    monkeypatch.delenv("UAGENT_AUTO_INSTALL", raising=False)
    monkeypatch.delenv("UAGENT_WORKDIR", raising=False)
    assert bootstrap._project_auto_install_policy() == "off"


def test_process_policy_overrides_dotenv(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    (tmp_path / ".env").write_text("UAGENT_AUTO_INSTALL=off\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("UAGENT_AUTO_INSTALL", "allow")
    monkeypatch.setattr(bootstrap.sys, "argv", ["uag"])
    assert bootstrap._project_auto_install_policy() is None
    assert _pip_auto._may_install("uag-envsec")
