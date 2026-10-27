from __future__ import annotations

from uagent import reasoning_display


def test_show_reasoning_strips_terminal_controls(monkeypatch) -> None:
    monkeypatch.setattr(reasoning_display, "get_display_reasoning", lambda: True)
    output: list[str] = []

    reasoning_display.show_reasoning(
        "thinking\x1b[31m red\x1b[0m\nnext\tline\x9b32m",
        print_fn=output.append,
    )

    assert output == ["thinking red\nnext\tline"]
    assert "\x1b" not in output[0]
    assert "\x9b" not in output[0]


def test_show_reasoning_strips_osc_terminal_controls(monkeypatch) -> None:
    monkeypatch.setattr(reasoning_display, "get_display_reasoning", lambda: True)
    output: list[str] = []

    reasoning_display.show_reasoning(
        "before\x1b]0;malicious title\x07after",
        print_fn=output.append,
    )

    assert output == ["beforeafter"]


def test_show_reasoning_uses_gray_and_resets_terminal_color(monkeypatch) -> None:
    monkeypatch.setattr(reasoning_display, "get_display_reasoning", lambda: True)
    monkeypatch.setattr(
        reasoning_display, "_reasoning_ansi_enabled", lambda core=None: True
    )
    output: list[str] = []

    class Core:
        @staticmethod
        def print_reasoning_delta(text: str) -> None:
            output.append(text)

    reasoning_display.show_reasoning(
        "thinking\x1b[31m in gray\x1b[0m",
        provider="openai",
        is_first=True,
        core=Core(),
    )

    assert output == ["[Openai Reasoning] \x1b[90mthinking in gray\x1b[0m"]


def test_reasoning_ansi_respects_no_color(monkeypatch) -> None:
    monkeypatch.setenv("NO_COLOR", "")

    assert reasoning_display._reasoning_ansi_enabled() is False
