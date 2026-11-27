from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("one\r\ntwo\r\nthree", "one\ntwo\nthree"),
        ("one\rtwo\rthree", "one\ntwo\nthree"),
        ("one\n\ntwo", "one\n\ntwo"),
    ],
)
def test_multiline_editor_normalizes_carriage_returns(
    value: str, expected: str
) -> None:
    from uagent.cli_impl.input_ui import _normalize_multiline_text

    assert _normalize_multiline_text(value) == expected


def test_multiline_editor_frames_text_area_with_horizontal_rules(monkeypatch) -> None:
    import prompt_toolkit

    from uagent.cli_impl import input_ui

    captured = {}

    class FakeApplication:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run(self):
            return "accepted"

    monkeypatch.setattr(prompt_toolkit, "Application", FakeApplication)
    monkeypatch.setattr(input_ui, "_create_prompt_output", lambda: None)

    assert input_ui._multiline_editor("draft") == "accepted"

    children = captured["layout"].container.children
    assert children[0].char == "─"
    assert children[2].char == "─"


def test_multiline_editor_copies_selection_and_pastes_from_right_click(
    monkeypatch,
) -> None:
    from types import SimpleNamespace

    import prompt_toolkit
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.clipboard import InMemoryClipboard
    from prompt_toolkit.keys import Keys
    from prompt_toolkit.mouse_events import MouseButton, MouseEventType
    from prompt_toolkit.selection import SelectionType

    from uagent.cli_impl import console_view, input_ui

    buffer = Buffer()
    buffer.text = "copy me"
    buffer.cursor_position = 0
    buffer.start_selection(SelectionType.CHARACTERS)
    buffer.cursor_position = 4
    clipboard = InMemoryClipboard()
    paste_values = iter(("right\r\npaste", " from ctrl-v"))
    applications = []

    class FakeApplication:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.current_buffer = buffer
            self.clipboard = kwargs["clipboard"]
            self.run_error = None
            applications.append(self)

        def exit(self, result=None):
            self.result = result

        def run(self):
            try:

                def fire(key):
                    binding = next(
                        binding
                        for binding in self.kwargs["key_bindings"].bindings
                        if binding.keys == (key,)
                    )
                    binding.handler(SimpleNamespace(app=self))

                fire(Keys.ControlC)
                assert self.clipboard.get_data().text == "copy"

                textarea = self.kwargs["layout"].container.children[1]
                textarea.content.mouse_handler(
                    SimpleNamespace(
                        button=MouseButton.RIGHT,
                        event_type=MouseEventType.MOUSE_UP,
                    )
                )
                assert buffer.text == "right\npaste me"

                fire(Keys.ControlV)
                assert buffer.text == "right\npaste from ctrl-v me"
            except Exception as exc:
                self.run_error = exc
            return "accepted"

    monkeypatch.setattr(prompt_toolkit, "Application", FakeApplication)
    monkeypatch.setattr(console_view, "_make_clipboard", lambda: clipboard)
    monkeypatch.setattr(
        console_view, "_read_system_clipboard", lambda: next(paste_values)
    )
    monkeypatch.setattr(input_ui, "_create_prompt_output", lambda: None)

    assert input_ui._multiline_editor("draft") == "accepted"
    assert applications[0].run_error is None
