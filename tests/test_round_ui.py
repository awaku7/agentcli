from __future__ import annotations

from uagent.runtime import round_ui


def test_round_ui_delegates_spinner_stop(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        "uagent.runtime.spinner.stop_quietly", lambda: calls.append(True)
    )

    round_ui.stop_round_spinner()

    assert calls == [True]


__all__ = []
