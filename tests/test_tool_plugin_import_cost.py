"""Loading the tool plugins must not pay for libraries a tool only needs at run time."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SRC_DIR = Path(__file__).resolve().parents[1] / "src"

# Imported lazily by the tools that need them (P0-1 of the speed-first split).
_DEFERRED_MODULES = (
    "bs4",  # fetch_url
    "docx",  # document_extract
    "odf",  # document_extract
    "striprtf",  # document_extract
    "holidays",  # date_calc
    "pyautogui",  # screenshot
    "pygetwindow",  # screenshot
    "tkinter",  # qr_reader_ui (standalone script, not a plugin)
    "uagent.a2a.client",  # a2a_send / a2a_poll
    "uagent.tools.qr_reader_ui",
)


def test_loading_plugins_does_not_import_deferred_libraries() -> None:
    code = (
        "import json, sys\n"
        f"sys.path.insert(0, {str(SRC_DIR)!r})\n"
        "import uagent.tools as tools\n"
        "tools._ensure_loaded()\n"
        f"print(json.dumps([m for m in {_DEFERRED_MODULES!r} if m in sys.modules]))\n"
    )
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["UAGENT_AUTO_INSTALL"] = "off"
    env["UAGENT_TOOLS_WARMUP"] = "0"
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    loaded = json.loads(proc.stdout.strip().splitlines()[-1])
    assert loaded == []


def test_pwsh_description_does_not_launch_powershell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib
    import shutil
    import subprocess as subprocess_mod

    from uagent.tools import pwsh_exec_tool

    def _fail_run(*_args, **_kwargs):
        raise AssertionError("pwsh_exec_tool must not spawn a process at import")

    monkeypatch.setattr(subprocess_mod, "run", _fail_run)
    monkeypatch.setattr(shutil, "which", lambda name: f"C:\\fake\\{name}.exe")
    try:
        mod = importlib.reload(pwsh_exec_tool)
        description = mod.TOOL_SPEC["function"]["description"]
        assert description.endswith(
            " (detected: pwsh / powershell)" if os.name == "nt" else " (detected: pwsh)"
        )
    finally:
        monkeypatch.undo()
        importlib.reload(pwsh_exec_tool)


def test_screenshot_loads_dependencies_once_on_first_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent.tools import screenshot_tool

    imported: list[str] = []
    fakes = {
        "pyautogui": SimpleNamespace(screenshot=lambda *_a, **_k: None),
        "pygetwindow": SimpleNamespace(getWindowsWithTitle=lambda _t: []),
    }

    def _fake_import(name: str):
        imported.append(name)
        return fakes[name]

    monkeypatch.setattr(screenshot_tool, "pyautogui", screenshot_tool._NOT_LOADED)
    monkeypatch.setattr(screenshot_tool, "pygetwindow", screenshot_tool._NOT_LOADED)
    monkeypatch.setattr(screenshot_tool, "_import_or_install", _fake_import)

    screenshot_tool._ensure_screenshot_dependencies()
    screenshot_tool._ensure_screenshot_dependencies()

    assert imported == ["pyautogui", "pygetwindow"]
    assert screenshot_tool.pyautogui is fakes["pyautogui"]
    assert screenshot_tool.pygetwindow is fakes["pygetwindow"]


def test_screenshot_does_not_reinstall_a_package_that_fails_to_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib
    import importlib.util

    from uagent.tools import screenshot_tool

    installs: list[str] = []

    def _broken_import(_name: str):
        raise OSError("no display")

    monkeypatch.setattr(importlib, "import_module", _broken_import)
    monkeypatch.setattr(importlib.util, "find_spec", lambda _name: object())
    monkeypatch.setattr(
        screenshot_tool, "install_with_status", lambda name: installs.append(name)
    )

    assert screenshot_tool._import_or_install("pyautogui") is None
    assert installs == []


def test_document_extract_reports_missing_library_without_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent.tools import document_extract_tool as mod

    monkeypatch.setattr(mod, "rtf_to_text", mod._NOT_LOADED)
    monkeypatch.setattr(mod, "_import_optional", lambda *_args: None)

    with pytest.raises(RuntimeError, match="striprtf is not available"):
        mod._rtf_extract(Path("unused.rtf"))
    assert mod.rtf_to_text is None
