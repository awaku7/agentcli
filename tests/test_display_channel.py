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
    core = _fake_core(print_stream_delta_locked=deltas.append)
    dc.render_notice(
        core,
        dc.Notice(text="peer message", source="bitchat", wait_for_stream=True),
    )
    assert deltas == ["peer message\n"]


def test_render_notice_after_stream_lock_order_and_atomicity(monkeypatch):
    # Regression (Codex P1 + P2 on PR #481): the insertion must stay
    # atomic under print_lock, but the spinner must be stopped BEFORE
    # that lock is taken, and the writes under it must use the
    # non-spinner-stopping locked writer.  Calling print_stream_delta
    # (which stops the spinner) under print_lock deadlocks against a
    # concurrent spinner.stop(); dropping the lock entirely lets a
    # foreground delta land between the line close and the notice.
    from uagent.runtime import spinner

    lock = threading.Lock()
    events: list = []
    monkeypatch.setattr(spinner, "stop_quietly", lambda: events.append("stop_spinner"))

    def fake_locked_write(text: str) -> None:
        acquired = lock.acquire(blocking=False)
        events.append(("locked_write", text, not acquired))
        if acquired:
            lock.release()

    def fake_plain_delta(text: str) -> None:
        events.append(("plain_delta", text))

    core = _fake_core(
        print_lock=lock,
        print_stream_delta_locked=fake_locked_write,
        print_stream_delta=fake_plain_delta,
        _prompt_line_open=True,
    )
    dc.render_notice(
        core,
        dc.Notice(text="peer message", source="bitchat", wait_for_stream=True),
    )
    assert events[0] == "stop_spinner"
    writes = [event for event in events if isinstance(event, tuple)]
    assert writes
    assert all(event[0] == "locked_write" for event in writes)
    assert all(event[2] for event in writes)  # print_lock held throughout


def _patch_spinner(monkeypatch, *, running: bool) -> list[str]:
    from uagent.runtime import spinner

    calls: list[str] = []
    monkeypatch.setattr(spinner, "is_running", lambda: running)
    monkeypatch.setattr(spinner, "stop_quietly", lambda: calls.append("stop"))
    monkeypatch.setattr(spinner, "start", lambda: calls.append("start"))
    return calls


def test_render_notice_after_stream_restores_busy_spinner(monkeypatch):
    calls = _patch_spinner(monkeypatch, running=True)
    deltas: list[str] = []
    core = _fake_core(
        print_stream_delta_locked=deltas.append,
        status_busy=True,
    )
    dc.render_notice(
        core,
        dc.Notice(text="relay notice", source="nostr", wait_for_stream=True),
    )
    assert deltas == ["relay notice\n"]
    assert calls == ["stop", "start"]


def test_render_notice_after_stream_keeps_spinner_off_when_idle(monkeypatch):
    calls = _patch_spinner(monkeypatch, running=True)
    core = _fake_core(
        print_stream_delta_locked=lambda _text: None,
        status_busy=False,
    )
    dc.render_notice(
        core,
        dc.Notice(text="relay notice", source="nostr", wait_for_stream=True),
    )
    assert calls == ["stop"]


def test_render_notice_after_stream_does_not_resume_during_stream(monkeypatch):
    monkeypatch.setattr(dc, "STREAM_GRACE_SEC", 0.05)
    calls = _patch_spinner(monkeypatch, running=True)
    core = _fake_core(
        print_stream_delta_locked=lambda _text: None,
        status_busy=True,
        _stream_line_open=True,
    )
    dc.render_notice(
        core,
        dc.Notice(text="peer message", source="bitchat", wait_for_stream=True),
    )
    assert calls == ["stop"]


def test_render_notice_after_stream_closes_open_lines():
    deltas: list[str] = []
    core = _fake_core(
        print_stream_delta_locked=deltas.append,
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
