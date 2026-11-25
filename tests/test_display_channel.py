"""Display channel policies and producer routing (single-writer stage 1)."""

from __future__ import annotations

import threading
import types

from uagent.runtime import display_channel as dc


def test_notice_bound_drops_oldest_and_counts():
    channel = dc.DisplayChannel(notice_limit=3)
    for i in range(5):
        channel.post_notice(dc.Notice(text=f"n{i}", source="test"))
    assert channel.dropped_notices == 2
    got = [channel.take(timeout=0.1) for _ in range(3)]
    assert [event.text for event in got] == ["n2", "n3", "n4"]
    assert channel.take(timeout=0.05) is None


def test_status_redraw_is_latest_only():
    channel = dc.DisplayChannel()
    channel.post_status(dc.StatusRedraw(reason="first"))
    channel.post_status(dc.StatusRedraw(reason="second"))
    event = channel.take(timeout=0.1)
    assert isinstance(event, dc.StatusRedraw)
    assert event.reason == "second"
    assert channel.take(timeout=0.05) is None


def test_stream_deltas_are_fifo_and_unbounded():
    channel = dc.DisplayChannel(notice_limit=1)
    for i in range(50):
        channel.post_stream(dc.StreamDelta(text=f"s{i}"))
    got = [channel.take(timeout=0.1) for _ in range(50)]
    assert [event.text for event in got] == [f"s{i}" for i in range(50)]


def test_take_priority_stream_then_notice_then_status():
    channel = dc.DisplayChannel()
    channel.post_status(dc.StatusRedraw(reason="status"))
    channel.post_notice(dc.Notice(text="notice", source="test"))
    channel.post_stream(dc.StreamDelta(text="stream"))
    assert isinstance(channel.take(timeout=0.1), dc.StreamDelta)
    assert isinstance(channel.take(timeout=0.1), dc.Notice)
    assert isinstance(channel.take(timeout=0.1), dc.StatusRedraw)


def _fake_core(**overrides):
    core = types.SimpleNamespace(
        print_lock=threading.RLock(),
        _stream_line_open=False,
        _reasoning_stream_open=False,
        _prompt_line_open=False,
        _cli_prompt_toolkit_active=False,
        _cli_prompt_app=None,
        prompt_needs_redraw=False,
        status_busy=False,
    )
    for name, value in overrides.items():
        setattr(core, name, value)
    return core


def test_render_notice_now_prints_and_requests_redraw(capsys):
    core = _fake_core(_prompt_line_open=True)
    dc.render_notice(core, dc.Notice(text="hello notice", source="nostr"))
    assert "hello notice" in capsys.readouterr().out
    assert core._prompt_line_open is False
    assert core.prompt_needs_redraw is True


def test_render_notice_after_stream_uses_stream_delta():
    deltas: list[str] = []
    core = _fake_core(print_stream_delta=deltas.append)
    dc.render_notice(
        core,
        dc.Notice(text="peer message", source="bitchat", wait_for_stream=True),
    )
    assert deltas == ["peer message\n"]


def test_render_notice_after_stream_never_holds_print_lock_for_delta_calls():
    # Regression: print_stream_delta stops the spinner (spinner lifecycle
    # lock) before taking print_lock itself.  If the renderer held
    # print_lock while calling it, a concurrent spinner.stop() (holding
    # the lifecycle lock while waiting for print_lock) would deadlock.
    lock = threading.Lock()
    held_when_called: list[bool] = []

    def fake_delta(_text: str) -> None:
        acquired = lock.acquire(blocking=False)
        held_when_called.append(not acquired)
        if acquired:
            lock.release()

    core = _fake_core(
        print_lock=lock,
        print_stream_delta=fake_delta,
        _prompt_line_open=True,
    )
    dc.render_notice(
        core,
        dc.Notice(text="peer message", source="bitchat", wait_for_stream=True),
    )
    assert held_when_called
    assert not any(held_when_called)


def test_render_notice_after_stream_closes_open_lines():
    deltas: list[str] = []
    core = _fake_core(
        print_stream_delta=deltas.append,
        _stream_line_open=True,
        _prompt_line_open=True,
    )
    dc.render_notice(
        core,
        dc.Notice(text="peer message", source="bitchat", wait_for_stream=True),
    )
    assert deltas == ["\n", "\n", "peer message\n"]
    assert core._prompt_line_open is False
    assert core.prompt_needs_redraw is True


def test_bitchat_notify_posts_to_channel(monkeypatch):
    from uagent.tools import pybitchat_shared as shared

    posted: list[tuple[str, dict]] = []
    monkeypatch.setattr(dc, "post_notice", lambda text, **kw: posted.append((text, kw)))
    shared._notify_display("[bitchat] hello")
    assert posted == [
        ("[bitchat] hello", {"source": "bitchat", "wait_for_stream": True})
    ]

    posted.clear()
    shared._notify_display("[bitchat] [debug] noise")
    assert posted == []


def test_nostr_tool_notify_posts_to_channel(monkeypatch):
    from uagent.tools import nostr_transport

    posted: list[tuple[str, dict]] = []
    monkeypatch.setattr(dc, "post_notice", lambda text, **kw: posted.append((text, kw)))
    nostr_transport._notify_display("[nostr] relay up")
    assert posted == [
        ("[nostr] relay up", {"source": "nostr", "wait_for_stream": True})
    ]


def test_nostr_remote_incoming_renders_formatted_preview(monkeypatch):
    from uagent import nostr_remote_runtime

    rendered: list[dc.Notice] = []
    monkeypatch.setattr(
        dc, "render_notice", lambda core, notice: rendered.append(notice)
    )
    nostr_remote_runtime._display_nostr_incoming(
        object(), {"pubkey": "a" * 64, "content": "hello\n world"}
    )
    assert rendered == [
        dc.Notice(
            text="[NOSTR] Received from aaaaaaaaaaaa: hello world", source="nostr"
        )
    ]

    rendered.clear()
    nostr_remote_runtime._display_nostr_incoming(object(), {"pubkey": 1})
    assert rendered == []
