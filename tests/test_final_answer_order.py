"""Final-answer emit: relayed reasoning must render before the answer."""

from __future__ import annotations

import time

from uagent import core
from uagent.llm_flow_helpers import _emit_final_answer_if_any
from uagent.runtime import display_channel as dc
from uagent.util_mode import get_display_reasoning, set_display_reasoning


def test_relayed_reasoning_renders_before_the_final_answer(monkeypatch, capsys):
    # Regression (PR #482 Codex P2): with the stream relay bound, the
    # reasoning render only queues a delta while print(assistant_text)
    # writes immediately, so the answer could appear before the
    # reasoning block.  Slowing the pump's render makes the race
    # deterministic: without the drain in the emit path, the answer
    # always wins.
    real_render = dc._render_stream_event

    def _slow_render(core_obj, channel, event):
        time.sleep(0.3)
        return real_render(core_obj, channel, event)

    monkeypatch.setattr(dc, "_render_stream_event", _slow_render)
    channel = dc.default_channel()
    dc.ensure_pump()
    channel.wait_for_stream_drain(timeout=5.0)

    was_enabled = get_display_reasoning()
    set_display_reasoning(True)
    try:
        with dc.bind_stream_relay(channel):
            _emit_final_answer_if_any(
                assistant_text="FINAL ANSWER",
                reasoning_content="THINKING",
                use_responses_api=False,
                stream_responses=False,
                append_result_to_outfile_fn=lambda text: None,
                try_open_images_from_text_fn=lambda text: None,
                core=core,
                provider="LLM",
            )
    finally:
        set_display_reasoning(was_enabled)
    channel.wait_for_stream_drain(timeout=5.0)

    out = capsys.readouterr().out
    assert "THINKING" in out
    assert "FINAL ANSWER" in out
    assert out.index("THINKING") < out.index("FINAL ANSWER")
