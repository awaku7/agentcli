from __future__ import annotations

from types import SimpleNamespace

import pytest


class _TTYStream:
    def isatty(self) -> bool:
        return True


class _NonTTYStream:
    def isatty(self) -> bool:
        return False


def test_startup_tool_genre_prompt_uses_prompt_toolkit_when_tty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent import cli_startup

    captured: dict[str, object] = {}

    class _Dialog:
        def run(self):
            captured["run"] = True
            return ["comm", "devel"]

    monkeypatch.setattr(cli_startup.sys, "stdin", _TTYStream())
    monkeypatch.setattr(cli_startup.sys, "stdout", _TTYStream())
    monkeypatch.setattr(cli_startup.sys, "__stdout__", _TTYStream(), raising=False)
    monkeypatch.setattr(
        "prompt_toolkit.shortcuts.checkboxlist_dialog",
        lambda **kwargs: _Dialog(),
    )

    assert cli_startup._prompt_startup_tool_genre_mask() == 5
    assert captured["run"] is True


def test_startup_tool_genre_prompt_falls_back_without_tty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent import cli_startup

    monkeypatch.setattr(cli_startup.sys, "stdin", _NonTTYStream())
    monkeypatch.setattr(cli_startup.sys, "stdout", _NonTTYStream())
    monkeypatch.setattr(cli_startup.sys, "__stdout__", _NonTTYStream(), raising=False)
    monkeypatch.setattr("builtins.input", lambda: "3")

    def fail_import(*args, **kwargs):
        raise AssertionError("prompt_toolkit should not be imported for non-TTY input")

    monkeypatch.setattr(cli_startup, "checkboxlist_dialog", None, raising=False)
    monkeypatch.setattr("prompt_toolkit.shortcuts.checkboxlist_dialog", fail_import)

    assert cli_startup._prompt_startup_tool_genre_mask() == 3
