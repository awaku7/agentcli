from __future__ import annotations

from uagent.runtime import reasoning_renderer


class _Core:
    def print_stream_delta(self, text: str) -> None:
        self.last = text


def test_reasoning_renderer_delegates_to_host_display(monkeypatch) -> None:
    calls = []

    def fake_show_reasoning(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr("uagent.reasoning_display.show_reasoning", fake_show_reasoning)
    core = _Core()

    reasoning_renderer.render_tool_call_reasoning(
        "internal reasoning", provider="Deepseek", core=core
    )

    assert calls == [
        (
            ("internal reasoning",),
            {
                "provider": "Deepseek",
                "is_first": True,
                "print_fn": core.print_stream_delta,
                "core": core,
            },
        )
    ]


__all__ = []
